import os
import requests
from dotenv import load_dotenv
import json
import time
import random


load_dotenv()
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")

# --- Обогащение: тянем обложку и описание из Google Books ---
def _books_request(query: str, max_results: int = 10, attempts: int = 3) -> list:
    """Запрос к Google Books с повтором при временных сбоях.
    Повторяем при тайм-ауте, 5xx и 429 (лимит частоты); при окончательной
    неудаче — пустой список. Пауза: Retry-After (если пришёл) или
    экспоненциальный backoff с джиттером."""
    for attempt in range(attempts):
        try:
            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={"q": query, "maxResults": max_results, "key": GOOGLE_BOOKS_API_KEY},
                timeout=5,
            )
            response.raise_for_status()
            return response.json().get("items", [])
        except requests.RequestException as e:
            status = getattr(e.response, "status_code", None)
            # временные сбои: нет ответа (тайм-аут), 5xx или 429; 4xx не повторяем
            retriable = status is None or status == 429 or status >= 500
            if not retriable or attempt == attempts - 1:
                return []
            # уважаем Retry-After при 429, иначе backoff 1с, 2с… + случайный джиттер
            retry_after = None
            if e.response is not None:
                header = e.response.headers.get("Retry-After", "")
                if header.isdigit():
                    retry_after = int(header)
            delay = retry_after if retry_after is not None else (2 ** attempt) + random.random()
            time.sleep(delay)
    return []


def _author_matches(author: str, candidate: dict) -> bool:
    """Хотя бы одно слово (длиннее 2 букв) из искомого автора есть в авторах кандидата."""
    tokens = [t for t in author.strip().lower().split() if len(t) > 2]
    found = " ".join(candidate.get("authors", [])).lower()
    return any(tok in found for tok in tokens)

def _parse_volume_info(info: dict) -> dict:
    """volumeInfo Google Books → наш плоский словарь с метаданными."""
    result = {
        "cover_url": None, "description": None, "page_count": None,
        "categories": None, "published_year": None, "language": None,
        "external_rating": None, "raw_metadata": None,
    }
    result["description"] = info.get("description")
    image_links = info.get("imageLinks", {})
    cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
    if cover:
        result["cover_url"] = cover.replace("http://", "https://")
    result["page_count"] = info.get("pageCount")
    categories = info.get("categories")
    result["categories"] = json.dumps(categories, ensure_ascii=False) if categories else None
    published = info.get("publishedDate", "")
    result["published_year"] = int(published[:4]) if published[:4].isdigit() else None
    result["language"] = info.get("language")
    result["external_rating"] = info.get("averageRating")
    result["raw_metadata"] = json.dumps(info, ensure_ascii=False)
    return result


def fetch_book_info(title: str, author: str, lang: str = "ru", isbn: str = None) -> dict:
    """Данные из Google Books. Сначала по ISBN, если не нашли — по названию+автору.
    Всегда проверяем и название, и автора, чтобы не подставить чужую книгу."""
    result = {
        "cover_url": None,
        "description": None,
        "page_count": None,
        "categories": None,
        "published_year": None,
        "language": None,
        "external_rating": None,
        "raw_metadata": None,
    }
    try:
        info = None

        # 1) по ISBN — точное издание; берём, только если есть данные И совпадает автор
        clean_isbn = isbn.replace("-", "").replace(" ", "") if isbn else None
        if clean_isbn:
            items = _books_request(f"isbn:{clean_isbn}")
            if items:
                candidate = items[0].get("volumeInfo", {})
                has_data = candidate.get("imageLinks") or candidate.get("description")
                if has_data and _author_matches(author, candidate):
                    info = candidate

        # 2) не нашли по ISBN — по названию+автору
        if info is None:
            items = _books_request(f"{title} {author}")
            wanted_title = title.strip().lower()
            for item in items:
                candidate = item.get("volumeInfo", {})
                found_title = (candidate.get("title") or "").strip().lower()
                title_ok = found_title == wanted_title or wanted_title in found_title
                if title_ok and _author_matches(author, candidate):
                    info = candidate
                    break

            if info is not None:
                result = _parse_volume_info(info)
    except requests.RequestException:
        pass
    return result


def search_books(query: str, max_results: int = 8) -> list[dict]:
    """Свободный поиск в Google Books — список кандидатов
    [{title, author, cover_url, external_id}]. Идёт через устойчивый
    _books_request (повторы при сбоях), при неудаче — пустой список."""
    results = []
    for item in _books_request(query, max_results=max_results):
        info = item.get("volumeInfo", {})
        title = info.get("title")
        if not title:
            continue
        authors = info.get("authors", [])
        author = ", ".join(authors) if authors else "—"
        image_links = info.get("imageLinks", {})
        cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if cover:
            cover = cover.replace("http://", "https://")
        results.append({
            "title": title,
            "author": author,
            "cover_url": cover,
            "external_id": item.get("id"),
        })
    return results

def fetch_volume_by_id(volume_id: str, attempts: int = 3) -> dict:
    """Обогащение без поиска: том Google Books точно по его id.
    Никакого сопоставления названий — пользователь уже выбрал книгу сам."""
    empty = {
        "cover_url": None, "description": None, "page_count": None,
        "categories": None, "published_year": None, "language": None,
        "external_rating": None, "raw_metadata": None,
    }
    for attempt in range(attempts):
        try:
            response = requests.get(
                f"https://www.googleapis.com/books/v1/volumes/{volume_id}",
                params={"key": GOOGLE_BOOKS_API_KEY},
                timeout=5,
            )
            response.raise_for_status()
            return _parse_volume_info(response.json().get("volumeInfo", {}))
        except requests.RequestException as e:
            status = getattr(e.response, "status_code", None)
            retriable = status is None or status == 429 or status >= 500
            if not retriable or attempt == attempts - 1:
                return empty
            time.sleep((2 ** attempt) + random.random())
    return empty