# Доменные операции над полкой пользователя (ревью 19.07).
#
# Раньше это жило прямо в routers/books.py, и роутер держал сразу три слоя:
# HTTP, маппинг ответа и бизнес-логику. Здесь — только логика: поиск книги в
# каталоге, добавление на полку, применение правок, снятие с полки.
# Роутер остаётся тонким: разобрать запрос → вызвать сервис → вернуть схему.
#
# Ошибки бросаем через HTTPException: слой тонкий, а отдельная иерархия доменных
# исключений на этом размере проекта добавила бы церемоний без пользы.
from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from constants import ALLOWED_STATUSES, ENRICH_PENDING, STATUS_READ
from deps import require_admin
from i18n import msg
from models import Book, UserBook


def norm_isbn(value: str | None) -> str | None:
    """Первый ISBN из списка, без дефисов и пробелов (как в импорте CSV)."""
    if not value:
        return None
    return value.split(",")[0].replace("-", "").replace(" ", "").strip() or None


def find_existing_book(session: Session, data) -> Book | None:
    """Книга в общем каталоге, которую можно переиспользовать вместе с готовой
    атмосферой и плейлистом. Приоритет: явный book_id (выбор из локального
    поиска) → ISBN, если передан → нормализованная пара «название+автор».

    Сравнение по-питоновски: SQLite lower() не понижает кириллицу.
    Выбираем только ключевые колонки — иначе на каждое добавление поднимался бы
    весь каталог вместе с raw_metadata (5–30 КБ на книгу)."""
    if data.book_id is not None:
        return session.get(Book, data.book_id)

    key_title = data.title.strip().lower()
    key_author = data.author.strip().lower()
    key_isbn = norm_isbn(getattr(data, "isbn", None))

    for book_id, title, author, isbn in session.exec(
        select(Book.id, Book.title, Book.author, Book.isbn)
    ).all():
        if key_isbn and norm_isbn(isbn) == key_isbn:
            return session.get(Book, book_id)
        if title.strip().lower() == key_title and author.strip().lower() == key_author:
            return session.get(Book, book_id)
    return None


def add_to_shelf(session: Session, data, user_id: int, lang: str) -> tuple[Book, UserBook, bool]:
    """Положить книгу на полку. Возвращает (book, userbook, is_new_book).
    Существующая книга каталога переиспользуется — атмосферу не генерим заново."""
    if data.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=msg("bad_status", lang))

    book = find_existing_book(session, data)
    is_new = book is None
    if is_new:
        book = Book(
            title=data.title,
            author=data.author,
            cover_url=data.cover_url,   # обложка кандидата из поиска видна сразу
            isbn=getattr(data, "isbn", None),
            enrich_status=ENRICH_PENDING,
        )
        session.add(book)
        session.commit()
        session.refresh(book)

    # уже на полке? (UNIQUE user+book это и гарантирует — отвечаем понятнее)
    already = session.exec(
        select(UserBook).where(
            UserBook.user_id == user_id, UserBook.book_id == book.id
        )
    ).first()
    if already:
        raise HTTPException(status_code=409, detail=msg("already_on_shelf", lang))

    user_book = UserBook(
        user_id=user_id,
        book_id=book.id,
        status=data.status,
        read_at=(data.read_at or datetime.now())
        if data.status == STATUS_READ
        else None,
    )
    session.add(user_book)
    session.commit()
    session.refresh(user_book)
    session.refresh(book)
    return book, user_book, is_new


def apply_book_fields(session: Session, book: Book, data, lang: str) -> list[str]:
    """Правка ОБЩИХ полей книги (задача 3). Меняет книгу у всех, кто держит её
    на полке, поэтому только admin. Возвращает список изменённых полей."""
    fields = (data.title, data.author, data.isbn, data.cover_url, data.description)
    if all(f is None for f in fields):
        return []

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
    return edited


def apply_shelf_fields(user_book: UserBook, data, lang: str) -> None:
    """Правка ЛИЧНЫХ полей полки: статус, оценка, дата прочтения — и инварианты."""
    if data.status is not None:
        if data.status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail=msg("bad_status", lang))
        user_book.status = data.status

    if data.rating is not None:
        if not (1 <= data.rating <= 10):
            raise HTTPException(status_code=400, detail=msg("bad_rating", lang))
        if user_book.status != STATUS_READ:
            raise HTTPException(status_code=400, detail=msg("rating_needs_read", lang))
        user_book.rating = data.rating

    # задача 1: явная дата прочтения (ISO из запроса)
    if data.read_at is not None:
        user_book.read_at = data.read_at
    # стала прочитанной, дата не указана — «сейчас»
    if user_book.status == STATUS_READ and user_book.read_at is None:
        user_book.read_at = datetime.now()
    # инварианты: оценка и дата прочтения живут только у read
    if user_book.status != STATUS_READ:
        user_book.rating = None
        user_book.read_at = None

    user_book.updated_at = datetime.now()


def remove_from_shelf(session: Session, book: Book, user_book: UserBook) -> None:
    """Снять книгу с полки. Если книгу больше никто не держит — удаляем и её
    из каталога, атмосфера уходит каскадом (FK ON DELETE CASCADE)."""
    book_id = book.id
    session.delete(user_book)
    session.commit()

    others = session.exec(
        select(UserBook).where(UserBook.book_id == book_id)
    ).first()
    if others is None:
        session.delete(book)
        session.commit()
