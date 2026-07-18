# Разовый скрипт: ищет обложки для книг из docs/covers_missing.json
# (Google Books + OpenLibrary) и пишет результат в docs/covers_found.json.
# Запуск из backend/:  python find_covers.py
# БД не трогает — заливка отдельным скриптом apply_covers.py после просмотра JSON.
import json
import time
from pathlib import Path

import requests

from google_books import _author_matches, _books_request

DOCS = Path(__file__).resolve().parent.parent / "docs"


def clean_isbn(isbn: str | None) -> str | None:
    """Первый ISBN из списка, без дефисов и пробелов."""
    if not isbn:
        return None
    return isbn.split(",")[0].replace("-", "").replace(" ", "").strip() or None


def from_google_books(book: dict) -> str | None:
    """Обложка из Google Books: сначала точно по ISBN, потом по названию+автору.
    Та же логика сверки, что в enrichment, — чтобы не подтянуть чужую книгу."""
    isbn = clean_isbn(book.get("isbn"))
    candidates = []
    if isbn:
        candidates += _books_request(f"isbn:{isbn}", max_results=3)
    candidates += _books_request(f"{book['title']} {book['author']}")

    wanted_title = book["title"].strip().lower()
    for item in candidates:
        info = item.get("volumeInfo", {})
        found_title = (info.get("title") or "").strip().lower()
        title_ok = found_title == wanted_title or wanted_title in found_title
        # для выдачи по ISBN название может отличаться (другое издание) — достаточно автора
        by_isbn = candidates.index(item) < 3 and isbn
        if not (title_ok or by_isbn) or not _author_matches(book["author"], info):
            continue
        links = info.get("imageLinks", {})
        cover = links.get("thumbnail") or links.get("smallThumbnail")
        if cover:
            return cover.replace("http://", "https://")
    return None


def from_openlibrary(book: dict) -> str | None:
    """Обложка из OpenLibrary: поиск по ISBN, затем по названию+автору;
    cover_i из выдачи → прямой URL картинки."""
    isbn = clean_isbn(book.get("isbn"))
    queries = []
    if isbn:
        queries.append({"isbn": isbn})
    queries.append({"title": book["title"], "author": book["author"]})

    for params in queries:
        try:
            response = requests.get(
                "https://openlibrary.org/search.json",
                params={**params, "fields": "title,author_name,cover_i", "limit": 5},
                timeout=10,
            )
            response.raise_for_status()
            docs = response.json().get("docs", [])
        except requests.RequestException:
            continue
        for doc in docs:
            cover_i = doc.get("cover_i")
            if not cover_i:
                continue
            # по ISBN верим изданию; по тексту — сверяем автора (название
            # в OpenLibrary часто на языке оригинала)
            candidate = {"authors": doc.get("author_name", [])}
            if "isbn" in params or _author_matches(book["author"], candidate):
                return f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg"
        time.sleep(0.5)  # вежливая пауза между запросами к OpenLibrary
    return None


def main():
    books = json.loads((DOCS / "covers_missing.json").read_text(encoding="utf-8"))
    found, not_found = [], []

    for i, book in enumerate(books, 1):
        cover = from_google_books(book)
        source = "google_books"
        if not cover:
            cover = from_openlibrary(book)
            source = "openlibrary"
        if cover:
            found.append({"id": book["id"], "title": book["title"],
                          "cover_url": cover, "source": source})
        else:
            not_found.append({"id": book["id"], "title": book["title"]})
        print(f"[{i}/{len(books)}] {book['title']} — "
              f"{'✓ ' + source if cover else '✗ не нашлось'}")

    result = {"found": found, "not_found": not_found}
    out = DOCS / "covers_found.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nНайдено: {len(found)}, не найдено: {len(not_found)}. Результат: {out}")


if __name__ == "__main__":
    main()
