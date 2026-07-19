# HTTP-слой для книг: разобрать запрос → вызвать сервис → вернуть схему.
# Доменная логика полки — в services/shelf.py, склейка ответа — BookRead.from_pair
# (ревью 19.07: раньше роутер держал все три слоя сразу).
import json

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import defer
from sqlmodel import Session, select

import database
from constants import (
    ENRICH_READY,
    EVENT_BOOK_ADDED,
    EVENT_BOOK_DELETED,
    EVENT_BOOK_EDITED,
    EVENT_ENRICHED,
    EVENT_RATED,
    EVENT_STATUS_CHANGED,
)
from deps import (
    CURRENT_USER_ID,
    get_book_or_404,
    get_lang,
    get_userbook_or_404,
    require_admin,
)
from events import log_event
from google_books import fetch_book_info
from models import AISelection, Book, UserBook
from schemas import BookCreate, BookRead, BookUpdate
from services.enrichment import apply_enrichment, enrich_in_background
from services.shelf import (
    add_to_shelf,
    apply_book_fields,
    apply_shelf_fields,
    remove_from_shelf,
)

router = APIRouter(tags=["books"])


@router.get("/books", response_model=list[BookRead])
def list_books(
    status: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """Полка текущего пользователя: JOIN userbook → book.
    Задача 70: фильтр по статусу + limit/offset (под ленивую загрузку полок).
    Задача 52: raw_metadata (тяжёлый JSON) в список не грузим."""
    with Session(database.engine) as session:
        query = (
            select(Book, UserBook)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(UserBook.user_id == CURRENT_USER_ID)
        )
        if status is not None:
            query = query.where(UserBook.status == status)
        query = query.options(defer(Book.raw_metadata)).order_by(Book.id).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return [BookRead.from_pair(b, ub) for b, ub in session.exec(query).all()]


@router.get("/books/design-summary")
def design_summary():
    """Символьный режим полки (задача 66): экслибрис и палитры паспорта по книгам
    пользователя — чтобы полка не догружала паспорт по каждой книге отдельно.
    Маршрут ВЫШЕ /books/{book_id}, иначе 'design-summary' поймается как book_id."""
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection)
            .join(UserBook, UserBook.book_id == AISelection.book_id)
            .where(
                UserBook.user_id == CURRENT_USER_ID,
                AISelection.category == "design",
            )
        ).all()
        designs = [
            {
                "book_id": row.book_id,
                "symbol_svg": payload.get("symbol_svg"),
                # старый формат паспорта — одно поле palette (тёмное)
                "palette_dark": payload.get("palette_dark") or payload.get("palette"),
                "palette_light": payload.get("palette_light"),
            }
            for row, payload in ((r, json.loads(r.payload)) for r in rows)
        ]
    return {"designs": designs}


@router.get("/books/{book_id}", response_model=BookRead)
def get_book(book_id: int, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        user_book = get_userbook_or_404(session, book_id, lang)
        return BookRead.from_pair(book, user_book)


@router.post("/books", response_model=BookRead)
def add_book(
    data: BookCreate,
    background_tasks: BackgroundTasks,
    lang: str = Depends(get_lang),
):
    with Session(database.engine) as session:
        book, user_book, is_new = add_to_shelf(session, data, CURRENT_USER_ID, lang)
        result = BookRead.from_pair(book, user_book)
        book_id = book.id

    log_event(
        EVENT_BOOK_ADDED, book_id, detail="source=new" if is_new else "source=catalog"
    )
    # обогащение и оформление — только для НОВОЙ книги; у существующей всё есть
    if is_new:
        background_tasks.add_task(enrich_in_background, book_id, lang, data.external_id)
        from routers.atmosphere import design_in_background
        background_tasks.add_task(design_in_background, book_id, lang)
    return result


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(book_id: int, data: BookUpdate, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        user_book = get_userbook_or_404(session, book_id, lang)

        edited = apply_book_fields(session, book, data, lang)   # общие поля — admin
        apply_shelf_fields(user_book, data, lang)               # личные поля полки

        session.add(user_book)
        session.commit()
        session.refresh(user_book)
        session.refresh(book)
        result = BookRead.from_pair(book, user_book)
        status, rating = user_book.status, user_book.rating

    if data.status is not None:
        log_event(EVENT_STATUS_CHANGED, book_id, detail=status)
    if data.rating is not None and rating is not None:
        log_event(EVENT_RATED, book_id, detail=str(rating))
    if edited:
        log_event(EVENT_BOOK_EDITED, book_id, detail=",".join(edited))
    return result


@router.delete("/books/{book_id}")
def delete_book(book_id: int, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        user_book = get_userbook_or_404(session, book_id, lang)
        book = get_book_or_404(session, book_id, lang)
        title = book.title
        remove_from_shelf(session, book, user_book)
    log_event(EVENT_BOOK_DELETED, book_id, detail=title)
    return {"deleted": book_id}


@router.post("/books/{book_id}/enrich", response_model=BookRead)
def enrich_book(book_id: int, lang: str = Depends(get_lang)):
    """Ручное обогащение (кнопка «Обновить информацию») — синхронное.
    Меняет общие данные книги, поэтому только admin."""
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        user_book = get_userbook_or_404(session, book_id, lang)
        require_admin(session, lang)

        info = fetch_book_info(book.title, book.author, lang, isbn=book.isbn)
        found = bool(info["raw_metadata"])
        if found:
            apply_enrichment(book, info)
        book.enrich_status = ENRICH_READY   # ручной повтор снимает статус failed
        session.add(book)
        session.commit()
        session.refresh(book)
        session.refresh(user_book)
        result = BookRead.from_pair(book, user_book)
    log_event(EVENT_ENRICHED, book_id, detail="ok" if found else "miss")
    return result
