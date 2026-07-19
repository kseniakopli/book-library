# CRUD книг: добавление на полку, чтение, изменение статуса/оценки, правка, удаление, enrich.
# После рефакторинга User/Book/UserBook: Book — общий каталог, UserBook — личная полка.
import json
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
from deps import (
    CURRENT_USER_ID,
    get_book_or_404,
    get_lang,
    get_userbook_or_404,
    require_admin,
)
from events import log_event
from google_books import fetch_book_info
from i18n import msg
from models import AISelection, Book, UserBook
from schemas import BookCreate, BookRead, BookUpdate
from services.enrichment import apply_enrichment, enrich_in_background

router = APIRouter(tags=["books"])


def _to_book_read(book: Book, ub: UserBook) -> dict:
    """Склейка ответа API: общие поля книги + личные поля полки.
    Контракт BookRead сохранён плоским — фронт читает как раньше."""
    return {
        "id": book.id,
        "user_id": ub.user_id,
        "title": book.title,
        "author": book.author,
        "cover_url": book.cover_url,
        "description": book.description,
        "status": ub.status,
        "rating": ub.rating,
        "created_at": ub.created_at,          # когда книга добавлена на полку
        "page_count": book.page_count,
        "categories": book.categories,
        "published_year": book.published_year,
        "language": book.language,
        "external_rating": book.external_rating,
        "isbn": book.isbn,
        "enrich_status": book.enrich_status,
        "spotify_playlist_url": book.spotify_playlist_url,
        "updated_at": ub.updated_at,
        "read_at": ub.read_at,
    }


def _norm_isbn(value: str | None) -> str | None:
    """Первый ISBN из списка, без дефисов и пробелов (как в импорте CSV)."""
    if not value:
        return None
    return value.split(",")[0].replace("-", "").replace(" ", "").strip() or None


def _find_existing_book(session: Session, data: BookCreate) -> Book | None:
    """Ищем книгу в общем каталоге, чтобы переиспользовать её (вместе с готовой
    атмосферой и плейлистом). Приоритет: явный book_id (выбор из локального
    поиска) → ISBN, если он передан → нормализованная пара «название+автор».

    Сравнение по-питоновски: SQLite lower() не понижает кириллицу.
    Выбираем ТОЛЬКО ключевые колонки — иначе на каждое добавление поднимался бы
    весь каталог вместе с raw_metadata (5–30 КБ на книгу)."""
    if data.book_id is not None:
        return session.get(Book, data.book_id)

    key_title = data.title.strip().lower()
    key_author = data.author.strip().lower()
    key_isbn = _norm_isbn(data.isbn)

    rows = session.exec(select(Book.id, Book.title, Book.author, Book.isbn)).all()
    for book_id, title, author, isbn in rows:
        if key_isbn and _norm_isbn(isbn) == key_isbn:
            return session.get(Book, book_id)
        if (
            title.strip().lower() == key_title
            and author.strip().lower() == key_author
        ):
            return session.get(Book, book_id)
    return None


@router.get("/books", response_model=list[BookRead])
def list_books(
    status: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """Полка текущего пользователя: JOIN userbook → book.
    Задача 70: фильтр по статусу + limit/offset — под пополковую (ленивую)
    загрузку на фронте. Задача 52: raw_metadata (тяжёлый JSON) в список не грузим."""
    with Session(database.engine) as session:
        query = (
            select(Book, UserBook)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(UserBook.user_id == CURRENT_USER_ID)
        )
        if status is not None:
            query = query.where(UserBook.status == status)
        query = (
            query.options(defer(Book.raw_metadata)).order_by(Book.id).offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)
        return [_to_book_read(book, ub) for book, ub in session.exec(query).all()]


@router.get("/books/design-summary")
def design_summary():
    """Символьный режим полки (задача 66): для книг пользователя — экслибрис и
    палитры из паспорта оформления, чтобы полка рисовала символы, не догружая
    паспорт по каждой книге отдельно. Маршрут ВЫШЕ /books/{book_id}, иначе
    'design-summary' поймается как book_id."""
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection)
            .join(UserBook, UserBook.book_id == AISelection.book_id)
            .where(
                UserBook.user_id == CURRENT_USER_ID,
                AISelection.category == "design",
            )
        ).all()
    designs = []
    for row in rows:
        payload = json.loads(row.payload)
        designs.append({
            "book_id": row.book_id,
            "symbol_svg": payload.get("symbol_svg"),
            # старый формат паспорта — одно поле palette (тёмное)
            "palette_dark": payload.get("palette_dark") or payload.get("palette"),
            "palette_light": payload.get("palette_light"),
        })
    return {"designs": designs}


@router.get("/books/{book_id}", response_model=BookRead)
def get_book(book_id: int, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        ub = get_userbook_or_404(session, book_id, lang)
        return _to_book_read(book, ub)


@router.post("/books", response_model=BookRead)
def add_book(
    data: BookCreate,
    background_tasks: BackgroundTasks,
    lang: str = Depends(get_lang),
):
    # задача 18: статус задаётся при добавлении
    if data.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=msg("bad_status", lang))

    with Session(database.engine) as session:
        # 1) книга уже в общем каталоге? — переиспользуем (готовая атмосфера/плейлист)
        book = _find_existing_book(session, data)
        is_new = book is None
        if is_new:
            book = Book(
                title=data.title,
                author=data.author,
                cover_url=data.cover_url,   # обложка кандидата из поиска видна сразу
                isbn=data.isbn,             # если передан — сохраняем, дедуп по нему
                enrich_status=ENRICH_PENDING,
            )
            session.add(book)
            session.commit()
            session.refresh(book)

        # 2) уже на полке у пользователя? — дубль (UNIQUE user+book это и гарантирует)
        already = session.exec(
            select(UserBook).where(
                UserBook.user_id == CURRENT_USER_ID, UserBook.book_id == book.id
            )
        ).first()
        if already:
            raise HTTPException(status_code=409, detail=msg("already_on_shelf", lang))

        # 3) кладём книгу на полку пользователя
        ub = UserBook(
            user_id=CURRENT_USER_ID,
            book_id=book.id,
            status=data.status,
            read_at=(data.read_at or datetime.now())
            if data.status == STATUS_READ
            else None,
        )
        session.add(ub)
        session.commit()
        session.refresh(ub)
        session.refresh(book)
        result = _to_book_read(book, ub)
        book_id = book.id

    log_event(EVENT_BOOK_ADDED, book_id, detail="source=new" if is_new else "source=catalog")
    # обогащение и оформление — только для НОВОЙ книги; у существующей всё уже есть
    if is_new:
        background_tasks.add_task(enrich_in_background, book_id, lang, data.external_id)
        from routers.atmosphere import design_in_background
        background_tasks.add_task(design_in_background, book_id, lang)
    return result


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(book_id: int, data: BookUpdate, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        ub = get_userbook_or_404(session, book_id, lang)

        # --- Общие поля книги (задача 3): правит только admin, меняет книгу у всех ---
        book_fields = (data.title, data.author, data.isbn, data.cover_url, data.description)
        if any(f is not None for f in book_fields):
            require_admin(session, lang)
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
            session.add(book)
        else:
            edited = []

        # --- Личные поля полки (статус, оценка, дата прочтения) ---
        if data.status is not None:
            if data.status not in ALLOWED_STATUSES:
                raise HTTPException(status_code=400, detail=msg("bad_status", lang))
            ub.status = data.status

        if data.rating is not None:
            if not (1 <= data.rating <= 10):
                raise HTTPException(status_code=400, detail=msg("bad_rating", lang))
            if ub.status != STATUS_READ:
                raise HTTPException(status_code=400, detail=msg("rating_needs_read", lang))
            ub.rating = data.rating

        # задача 1: явная дата прочтения (ISO из запроса)
        if data.read_at is not None:
            ub.read_at = data.read_at
        # стала прочитанной, дата не указана — «сейчас»
        if ub.status == STATUS_READ and ub.read_at is None:
            ub.read_at = datetime.now()
        # инварианты: оценка и дата прочтения живут только у read
        if ub.status != STATUS_READ:
            ub.rating = None
            ub.read_at = None

        ub.updated_at = datetime.now()
        session.add(ub)
        session.commit()
        session.refresh(ub)
        session.refresh(book)
        result = _to_book_read(book, ub)

    if data.status is not None:
        log_event(EVENT_STATUS_CHANGED, book_id, detail=ub.status)
    if data.rating is not None and ub.rating is not None:
        log_event(EVENT_RATED, book_id, detail=str(ub.rating))
    if edited:
        log_event(EVENT_BOOK_EDITED, book_id, detail=",".join(edited))
    return result


@router.delete("/books/{book_id}")
def delete_book(book_id: int, lang: str = Depends(get_lang)):
    with Session(database.engine) as session:
        ub = get_userbook_or_404(session, book_id, lang)
        book = get_book_or_404(session, book_id, lang)
        title = book.title
        session.delete(ub)                       # снимаем книгу с полки пользователя
        session.commit()

        # книга-сирота (никто больше не держит её на полке) — удаляем из каталога,
        # атмосфера уходит каскадом (FK ON DELETE CASCADE, включён в приложении)
        others = session.exec(
            select(UserBook).where(UserBook.book_id == book_id)
        ).first()
        if others is None:
            session.delete(book)
            session.commit()
    log_event(EVENT_BOOK_DELETED, book_id, detail=title)
    return {"deleted": book_id}


@router.post("/books/{book_id}/enrich", response_model=BookRead)
def enrich_book(book_id: int, lang: str = Depends(get_lang)):
    """Ручное обогащение (кнопка «Обновить информацию») — синхронное.
    Меняет общие данные книги, поэтому только admin."""
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        ub = get_userbook_or_404(session, book_id, lang)
        require_admin(session, lang)

        info = fetch_book_info(book.title, book.author, lang, isbn=book.isbn)
        found = bool(info["raw_metadata"])
        if found:
            apply_enrichment(book, info)
        book.enrich_status = ENRICH_READY   # ручной повтор снимает статус failed
        session.add(book)
        session.commit()
        session.refresh(book)
        session.refresh(ub)
        result = _to_book_read(book, ub)
    log_event(EVENT_ENRICHED, book_id, detail="ok" if found else "miss")
    return result
