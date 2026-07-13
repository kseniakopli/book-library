import os
import requests
from dotenv import load_dotenv


load_dotenv()
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")

# --- Обогащение: тянем обложку и описание из Google Books ---
def fetch_book_info(title: str, author: str, lang: str = "ru") -> dict:
    """Спрашиваем у Google Books обложку и описание.
    Возвращаем словарь {cover_url, description}. Если что-то не нашлось
    или сервис недоступен — возвращаем None, книга всё равно сохранится."""
    result = {"cover_url": None, "description": None}
    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": f"intitle:{title}+inauthor:{author}",
                "maxResults": 1,
                "langRestrict": lang,
                "key": GOOGLE_BOOKS_API_KEY,
            },
            timeout=5,                      # не ждём ответа дольше 5 секунд
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            return result
        info = items[0].get("volumeInfo", {})
        result["description"] = info.get("description")
        image_links = info.get("imageLinks", {})
        cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if cover:
            result["cover_url"] = cover.replace("http://", "https://")
    except requests.RequestException:
        pass
    return result


def search_books(query: str, max_results: int = 8) -> list[dict]:
    """Свободный поиск в Google Books — список кандидатов
    [{title, author, cover_url, external_id}]. При ошибке сети — пустой список."""
    results = []
    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": max_results, "key": GOOGLE_BOOKS_API_KEY},
            timeout=5,
        )
        response.raise_for_status()
        for item in response.json().get("items", []):
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
    except requests.RequestException:
        pass
    return results