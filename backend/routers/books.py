# CRUD книг: добавление, чтение, изменение статуса/оценки, удаление, ручной enrich.
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import defer
from sqlmodel import Session, select

import database
from constants import (
    ALLOWED_STATUSES,
    ENRICH_PENDING,
    ENRICH_READY,
    EVENT_BOOK_ADDED,
    EVENT_BOOK_DELETED,
    EVENT_BOOK_EDITED,
    EVENT_ENRICHED,
    EVENT_RATED,
    EVENT_STATUS_CHANGED,
    STATUS_READ,
)
from deps import get_book_or_404, get_lang
from events import log_event
from google_books import fetch_book_info
from i18n import msg
from models import Book
from schemas import BookCreate, BookRead, BookUpdate
from services.enrichment import apply_enrichment, enrich_in_background

router = APIRouter(tags=["books"])


@router.get("/books", response_model=list[BookRead])
def list_books(limit: int | None = None, offset: int = 0):
    """Задача 34: пагинация поддерживается (limit/offset); без параметров —
    вся библиотека (текущий фронт так и ходит, включим при росте данных).
    Задача 52: raw_metadata (5–30 КБ JSON на книгу) в список не грузим —
    defer() исключает колонку из SELECT, наружу её всё равно не отдаём."""
    with Session(database.engine) as session:
        query = select(Book).options(defer(Book.raw_metadata)).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return session.exec(query).all()


@router.get("/books/{book_id}", response_model=BookRead)
def get_book(book_id: int, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        return get_book_or_404(session, book_id, lang)


@router.post("/books", response_model=BookRead)
def add_book(
    data: BookCreate,
    background_tasks: BackgroundTasks,
    lang: str = Depends(get_lang),
):
    # задача 18: статус задаётся при добавлении
    if data.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=msg("bad_status", lang))

    # книга сохраняется сразу, без похода в Google Books — ответ мгновенный;
    # метаданные доедут фоном (services/enrichment.py)
    book = Book(
        title=data.title,
        author=data.author,
        cover_url=data.cover_url,          # обложка кандидата из поиска видна сразу
        status=data.status,
        # дата прочтения: явная, иначе «сейчас» для прочитанной (как в PATCH)
        read_at=(data.read_at or datetime.now())
        if data.status == STATUS_READ
        else None,
        enrich_status=ENRICH_PENDING,
    )
    with Session(database.engine) as session:
        session.add(book)
        session.commit()
        session.refresh(book)
    log_event(EVENT_BOOK_ADDED, book.id, detail="source=manual")
    background_tasks.add_task(enrich_in_background, book.id, lang, data.external_id)
    # задача 57: оформление (палитры, шрифты, символ) — тоже фоном, сразу
    # при добавлении; задачи выполняются по очереди после ответа
    from routers.atmosphere import design_in_background
    background_tasks.add_task(design_in_background, book.id, lang)
    return book


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(book_id: int, data: BookUpdate, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)

        # Задача 3: ручная правка полей (промахи обогащения исправляются руками).
        # Название и автор пустыми быть не могут; isbn/cover_url/description
        # пустая строка очищает поле.
        edited = []
        if data.title is not None:
            if not data.title.strip():
                raise HTTPException(status_code=400, detail=msg("empty_title_author", lang))
            book.title = data.title.strip()
            edited.append("title")
        if data.author is not None:
            if not data.author.strip():
                raise HTTPException(status_code=400, detail=msg("empty_title_author", lang))
            book.author = data.author.strip()
            edited.append("author")
        if data.isbn is not None:
            book.isbn = data.isbn.strip() or None
            edited.append("isbn")
        if data.cover_url is not None:
            book.cover_url = data.cover_url or None   # "" из валидатора → очистка
            edited.append("cover_url")
        if data.description is not None:
            book.description = data.description.strip() or None
            edited.append("description")

        if data.status is not None:
            if data.status not in ALLOWED_STATUSES:
                raise HTTPException(status_code=400, detail=msg("bad_status", lang))
            book.status = data.status

        if data.rating is not None:
            if not (1 <= data.rating <= 10):
                raise HTTPException(status_code=400, detail=msg("bad_rating", lang))
            if book.status != STATUS_READ:
                raise HTTPException(
                    status_code=400, detail=msg("rating_needs_read", lang)
                )
            book.rating = data.rating

        # задача 1: явная дата прочтения (ISO из запроса)
        if data.read_at is not None:
            book.read_at = data.read_at
        # книга стала прочитанной, дата не указана — ставим «сейчас»
        if book.status == STATUS_READ and book.read_at is None:
            book.read_at = datetime.now()

        # инварианты: оценка и дата прочтения живут только у read
        if book.status != STATUS_READ:
            book.rating = None
            book.read_at = None

        book.updated_at = datetime.now()
        session.add(book)
        session.commit()
        session.refresh(book)

    if data.status is not None:
        log_event(EVENT_STATUS_CHANGED, book_id, detail=book.status)
    if data.rating is not None and book.rating is not None:
        log_event(EVENT_RATED, book_id, detail=str(book.rating))
    if edited:
        log_event(EVENT_BOOK_EDITED, book_id, detail=",".join(edited))
    return book


@router.delete("/books/{book_id}")
def delete_book(book_id: int, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        title = book.title
        session.delete(book)      # AISelection уйдут каскадом (FK ON DELETE CASCADE)
        session.commit()
    log_event(EVENT_BOOK_DELETED, book_id, detail=title)
    return {"deleted": book_id}


@router.post("/books/{book_id}/enrich", response_model=BookRead)
def enrich_book(book_id: int, lang: str = Depends(get_lang)):
    """Ручное обогащение (кнопка «Обновить информацию») — синхронное."""
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)

        info = fetch_book_info(book.title, book.author, lang, isbn=book.isbn)
        found = bool(info["raw_metadata"])
        if found:
            apply_enrichment(book, info)
        book.enrich_status = ENRICH_READY   # ручной повтор снимает статус failed
        session.add(book)
        session.commit()
        session.refresh(book)
    log_event(EVENT_ENRICHED, book_id, detail="ok" if found else "miss")
    return book
