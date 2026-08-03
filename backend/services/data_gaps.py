"""Что в каталоге не заполнено (задача 113).

⚠ Порядок работ в задаче был задан явно: **сначала замер, потом списки**.
От долей зависит, ручная это работа или нужен ещё один источник данных:
двадцать книг без описания заполняются за вечер, сто восемьдесят — нет.
Поэтому сводка (`summary`) отвечает на вопрос «сколько», а списки (`items`)
показывают конкретные объекты уже после того, как решение принято.

Считается по ОБЩЕМУ каталогу, как справочники авторов и жанров: незаполненное
поле — свойство книги, а не чьей-то полки.
"""

from sqlmodel import Session, col, func, select

from models import AISelection, Author, Book, BookGenre

# Сколько объектов отдаём в списке. Заполняют руками и по одному, так что
# видеть все 189 сразу незачем — это только утомляет и грузит страницу.
PAGE_SIZE = 50

# Виды неполноты. Ключ уезжает в адрес (`/admin/data-gaps/{kind}`), поэтому
# менять их нельзя без правки фронта.
BOOK_GAPS = ("no_description", "no_cover", "no_genres", "no_design")
AUTHOR_GAPS = ("no_bio",)
ALL_GAPS = BOOK_GAPS + AUTHOR_GAPS


def _books_with_genres():
    """Подзапрос: id книг, у которых есть хотя бы один жанр."""
    return select(BookGenre.book_id).distinct()


def _books_with_design():
    """Подзапрос: id книг с готовым паспортом оформления.

    ⚠ Именно `AISelection` категории `design`, а не «есть хоть какая-то
    атмосфера»: серый фон карточки на витрине (з.94) даёт отсутствие
    палитры, то есть паспорта.
    """
    return select(AISelection.book_id).where(AISelection.category == "design").distinct()


def _book_gap_query(kind: str):
    """Запрос книг с указанным пробелом. Одно место для условий — иначе
    сводка и список разъедутся, и цифра перестанет отвечать за содержимое."""
    query = select(Book)
    if kind == "no_description":
        # пустая строка бывает у книг, где Google вернул описание из пробелов
        return query.where(
            col(Book.description).is_(None) | (func.trim(Book.description) == "")
        )
    if kind == "no_cover":
        return query.where(col(Book.cover_url).is_(None))
    if kind == "no_genres":
        return query.where(col(Book.id).not_in(_books_with_genres()))
    if kind == "no_design":
        return query.where(col(Book.id).not_in(_books_with_design()))
    raise ValueError(f"Неизвестный вид пробела: {kind}")


def summary(session: Session) -> dict:
    """Сводка: сколько всего и сколько с пробелами.

    Доли считает фронт — здесь только факты, иначе процент в интерфейсе
    и процент в отчёте разъедутся при первой же правке округления.
    """
    total_books = session.exec(select(func.count()).select_from(Book)).one()
    total_authors = session.exec(select(func.count()).select_from(Author)).one()

    books = {}
    for kind in BOOK_GAPS:
        query = _book_gap_query(kind).with_only_columns(func.count())
        books[kind] = session.exec(query).one()

    authors_without_bio = session.exec(
        select(func.count())
        .select_from(Author)
        .where(col(Author.bio).is_(None) | (func.trim(Author.bio) == ""))
    ).one()

    return {
        "books_total": total_books,
        "authors_total": total_authors,
        "books": books,
        "authors": {"no_bio": authors_without_bio},
    }


def items(session: Session, kind: str, limit: int = PAGE_SIZE) -> list[dict]:
    """Конкретные объекты с пробелом — со ссылками, чтобы сразу пойти править."""
    if kind == "no_bio":
        rows = session.exec(
            select(Author)
            .where(col(Author.bio).is_(None) | (func.trim(Author.bio) == ""))
            .order_by(Author.sort_key)
            .limit(limit)
        ).all()
        # локальный импорт: services.authors не нужен модулю целиком,
        # а на уровне файла дал бы лишнюю связь между сервисами
        from services.authors import display_name

        return [
            {"id": author.id, "name": display_name(author), "kind": "author"}
            for author in rows
        ]

    rows = session.exec(
        _book_gap_query(kind).order_by(Book.title).limit(limit)
    ).all()
    return [
        {"id": book.id, "name": book.title, "author": book.author, "kind": "book"}
        for book in rows
    ]
