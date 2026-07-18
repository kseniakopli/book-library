# Сервис обогащения книги данными Google Books (рефакторинг R1).
# Фоновая версия — для добавления книги (BackgroundTasks);
# применение результата вынесено отдельно, его же использует ручной enrich.
from sqlmodel import Session

import database
from constants import ENRICH_FAILED, ENRICH_READY, EVENT_ENRICHED
from events import log_event
from google_books import fetch_book_info, fetch_volume_by_id
from models import Book


def apply_enrichment(book: Book, info: dict) -> None:
    """Переносит словарь fetch_* в поля книги (без commit).
    Обложку и описание не затираем пустыми значениями."""
    book.cover_url = info["cover_url"] or book.cover_url
    book.description = info["description"] or book.description
    book.page_count = info["page_count"]
    book.categories = info["categories"]
    book.published_year = info["published_year"]
    book.language = info["language"]
    book.external_rating = info["external_rating"]
    book.raw_metadata = info["raw_metadata"]
    # updated_at (когда книгу трогали) переехал в userbook — это личное поле;
    # обогащение меняет общие данные книги и полку пользователя не двигает


def backfill_in_background(book_ids: list[int], lang: str) -> None:
    """Задача 12: фоновый дозаполнитель партии книг. Каждая книга проходит
    обычный путь enrich_in_background — сбой одной не мешает остальным."""
    for book_id in book_ids:
        enrich_in_background(book_id, lang)


def enrich_in_background(book_id: int, lang: str, external_id: str = None) -> None:
    """Фоновая задача: дозаполнить книгу. Ошибка ничего не роняет — статус failed.
    external_id (том Google Books, выбранный пользователем) даёт точное
    обогащение без повторного поиска."""
    try:
        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            if book is None:               # книгу успели удалить
                return
            title, author = book.title, book.author

        # медленный внешний вызов — сознательно вне сессии БД
        if external_id:
            info = fetch_volume_by_id(external_id)
        else:
            info = fetch_book_info(title, author, lang)

        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            if book is None:
                return
            apply_enrichment(book, info)
            book.enrich_status = ENRICH_READY
            session.add(book)
            session.commit()
        log_event(EVENT_ENRICHED, book_id, detail="ok" if info["raw_metadata"] else "miss")
    except Exception as e:
        print("Фоновое обогащение не удалось:", e)
        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            if book is not None:
                book.enrich_status = ENRICH_FAILED
                session.add(book)
                session.commit()
        log_event(EVENT_ENRICHED, book_id, detail="failed")
