# HTTP-слой для книг: разобрать запрос → вызвать сервис → вернуть схему.
# Доменная логика полки — в services/shelf.py, атмосферы — в services/atmosphere.py,
# склейка ответа — BookRead.from_pair (ревью 19.07).
# Сессия приходит зависимостью get_session (задача 77).
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func
from sqlalchemy.orm import defer
from sqlmodel import Session, select

from constants import (
    ENRICH_PENDING,
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
    get_session,
    get_userbook_or_404,
    require_admin,
)
from events import log_event
from google_books import fetch_book_info
from models import Book, UserBook
from schemas import BookCreate, BookRead, BookUpdate
from services.atmosphere import generate_design_in_background, read_design_summary
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
    session: Session = Depends(get_session),
):
    """Полка текущего пользователя: JOIN userbook → book.
    Задача 70: фильтр по статусу + limit/offset (под ленивую загрузку полок).
    Задача 52: raw_metadata (тяжёлый JSON) в список не грузим."""
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
def design_summary(session: Session = Depends(get_session)):
    """Символьный режим полки (задача 66). Маршрут объявлен ВЫШЕ /books/{book_id},
    иначе 'design-summary' поймается как book_id."""
    return {"designs": read_design_summary(session, CURRENT_USER_ID)}


@router.get("/books/pending-count")
def pending_count(session: Session = Depends(get_session)):
    """Задача 56б: лёгкий счётчик недообогащённых книг. Пока идёт фоновое
    обогащение, фронт поллит ЭТОТ эндпоинт (одно число), а не весь список книг.
    Маршрут тоже выше /books/{book_id}."""
    count = session.exec(
        select(func.count())
        .select_from(Book)
        .join(UserBook, UserBook.book_id == Book.id)
        .where(
            UserBook.user_id == CURRENT_USER_ID,
            Book.enrich_status == ENRICH_PENDING,
        )
    ).one()
    return {"pending": count}


@router.get("/books/{book_id}", response_model=BookRead)
def get_book(
    book_id: int,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    book = get_book_or_404(session, book_id, lang)
    user_book = get_userbook_or_404(session, book_id, lang)
    return BookRead.from_pair(book, user_book)


@router.post("/books", response_model=BookRead)
def add_book(
    data: BookCreate,
    background_tasks: BackgroundTasks,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    book, user_book, is_new = add_to_shelf(session, data, CURRENT_USER_ID, lang)
    result = BookRead.from_pair(book, user_book)
    book_id = book.id

    log_event(
        EVENT_BOOK_ADDED, book_id, detail={"source": "new" if is_new else "catalog"}
    )
    # обогащение и оформление — только для НОВОЙ книги; у существующей всё есть.
    # Фоновые задачи открывают свои сессии, эта к тому моменту уже закрыта.
    if is_new:
        background_tasks.add_task(enrich_in_background, book_id, lang, data.external_id)
        background_tasks.add_task(generate_design_in_background, book_id, lang)
    return result


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(
    book_id: int,
    data: BookUpdate,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    book = get_book_or_404(session, book_id, lang)
    user_book = get_userbook_or_404(session, book_id, lang)

    edited = apply_book_fields(session, book, data, lang)   # общие поля — admin
    apply_shelf_fields(user_book, data, lang)               # личные поля полки

    session.add(user_book)
    session.commit()
    session.refresh(user_book)
    session.refresh(book)
    result = BookRead.from_pair(book, user_book)

    if data.status is not None:
        log_event(EVENT_STATUS_CHANGED, book_id, detail={"status": user_book.status})
    if data.rating is not None and user_book.rating is not None:
        log_event(EVENT_RATED, book_id, detail={"rating": user_book.rating})
    if edited:
        log_event(EVENT_BOOK_EDITED, book_id, detail={"fields": edited})
    return result


@router.delete("/books/{book_id}")
def delete_book(
    book_id: int,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    user_book = get_userbook_or_404(session, book_id, lang)
    book = get_book_or_404(session, book_id, lang)
    title = book.title
    remove_from_shelf(session, book, user_book)
    log_event(EVENT_BOOK_DELETED, book_id, detail={"title": title})
    return {"deleted": book_id}


@router.post("/books/{book_id}/enrich", response_model=BookRead)
def enrich_book(
    book_id: int,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    """Ручное обогащение (кнопка «Обновить информацию») — синхронное.
    Меняет общие данные книги, поэтому только admin."""
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

    log_event(EVENT_ENRICHED, book_id, detail={"result": "ok" if found else "miss"})
    return BookRead.from_pair(book, user_book)
