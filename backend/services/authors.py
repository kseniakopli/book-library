"""Авторы как сущность (задача 97): тождество имени и разбор строк книги.

Почему домен здесь, а не в скрипте заполнения: этими же правилами будут
пользоваться добавление книги и импорт CSV — иначе таблица через месяц зарастёт
дублями одного человека.

Разведка 28.07 (`scripts/explore_authors.py`) по 150 уникальным строкам:
склеены всего три, случаев «фамилия, имя» нет вовсе, латиницей записаны двое.
Поэтому здесь НЕТ парсера с эвристиками — исключения перечислены явно. Писать
разбор по правилам ради трёх строк значило бы завести источник тихих ошибок:
«Аркадий и Борис Стругацкие» ломает любое разбиение по разделителю, потому что
фамилия стоит один раз и во множественном числе.
"""

import unicodedata

from models import Author, BookAuthor
from services.catalog import books_split, entity_directory
from sqlmodel import Session, col, select

# Строка ровно как в базе → авторы по порядку обложки.
EXCEPTIONS: dict[str, list[str]] = {
    "Екатерина Казакова, Алена Харитонова": [
        "Екатерина Казакова",
        "Алёна Харитонова",
    ],
    "Аркадий и Борис Стругацкие": [
        "Аркадий Стругацкий",
        "Борис Стругацкий",
    ],
}

# Авторы, записанные латиницей: оригинал → имя по-русски.
# Без этого двое выглядят инородно среди 148 кириллических имён.
ORIGINAL_NAMES: dict[str, str] = {
    "Ann Patchett": "Энн Пэтчетт",
    "Joan Didion": "Джоан Дидион",
}


def norm_key(name: str) -> str:
    """Ключ тождества автора.

    Регистр, лишние пробелы, точки в инициалах и ё/е — шум, а не различие:
    «А.С. Пушкин», «А. С. Пушкин» и «а.с. пушкин» — один человек.
    Ключ намеренно грубый и работает только внутри одного алфавита: «Ann
    Patchett» и «Энн Пэтчетт» так не связать, для этого есть ORIGINAL_NAMES.
    """
    text = unicodedata.normalize("NFKC", name).lower().replace("ё", "е")
    text = text.replace(".", " ")
    return " ".join(text.split())


def split_authors(raw: str | None) -> list[str]:
    """Строка книги → список авторов.

    Разбираются ТОЛЬКО известные исключения; всё остальное — один человек.
    Это сознательный выбор в пользу предсказуемости: лучше не разделить редкую
    новую пару соавторов (и заметить это глазами), чем разрезать пополам
    настоящее имя.
    """
    raw = (raw or "").strip()
    if raw in EXCEPTIONS:
        return list(EXCEPTIONS[raw])
    return [raw] if raw else []


def get_or_create(session: Session, name: str) -> Author:
    """Автор по имени: находит существующего по ключу или заводит нового.

    Ключ уникален в схеме, поэтому дубль нельзя создать даже гонкой — база
    не даст. Латинское имя раскладывается на два поля.
    """
    key = norm_key(name)
    found = session.exec(select(Author).where(Author.sort_key == key)).first()
    if found is not None:
        return found

    russian = ORIGINAL_NAMES.get(name)
    author = Author(
        name_ru=russian or (None if name in ORIGINAL_NAMES else name),
        name_original=name if name in ORIGINAL_NAMES else None,
        sort_key=key,
    )
    session.add(author)
    session.flush()          # нужен id для связи
    return author


def link_book(session: Session, book_id: int, raw_author: str | None) -> list[Author]:
    """Связать книгу с авторами из её строки — ПОЛНОСТЬЮ, а не «добавить».

    После вызова связей ровно столько, сколько имён в строке: лишние снимаются.
    Идемпотентно — повторный вызов ничего не дублирует.

    ⚠ Почему не «только добавлять» (баг 28.07): строка автора у книги меняется —
    руками в правке или когда Google возвращает имя на другом языке. У «Года
    магического мышления» так вышло два автора сразу: старая связь на «Джоан
    Дидион» и новая на «Joan Didion», и на странице книги имя показывалось
    дважды. Строка книги — источник истины, связи обязаны ей соответствовать.
    """
    names = split_authors(raw_author)
    authors = [get_or_create(session, name) for name in names]
    wanted = {author.id: position for position, author in enumerate(authors)}

    existing = session.exec(
        select(BookAuthor).where(BookAuthor.book_id == book_id)
    ).all()

    orphan_candidates = []
    for link in existing:
        if link.author_id in wanted:
            link.position = wanted.pop(link.author_id)   # порядок мог измениться
            session.add(link)
        else:
            orphan_candidates.append(link.author_id)
            session.delete(link)

    for author_id, position in wanted.items():
        session.add(BookAuthor(book_id=book_id, author_id=author_id, position=position))

    session.flush()
    _drop_orphans(session, orphan_candidates)
    return authors


def _drop_orphans(session: Session, author_ids: list[int]) -> None:
    """Автор, у которого не осталось ни одной книги, удаляется.

    Тот же принцип, что у книги-сироты при снятии с полки (`services/shelf.py`):
    сущность существует ради связей, без них это мусор в базе и пустая
    страница по прямой ссылке."""
    for author_id in author_ids:
        still_used = session.exec(
            select(BookAuthor).where(BookAuthor.author_id == author_id)
        ).first()
        if still_used is None:
            author = session.get(Author, author_id)
            if author is not None:
                session.delete(author)
    session.flush()


def display_name(author: Author) -> str:
    """Как показывать автора: по-русски, а если русского нет — как записано."""
    return author.name_ru or author.name_original or ""


def authors_of(session: Session, book_ids: list[int]) -> dict[int, list[Author]]:
    """Авторы для списка книг ОДНИМ запросом: полка на 200 книг иначе дала бы
    двести обращений к базе. Порядок соавторов сохраняется (`position`)."""
    if not book_ids:
        return {}
    rows = session.exec(
        select(BookAuthor, Author)
        .join(Author, Author.id == BookAuthor.author_id)
        .where(col(BookAuthor.book_id).in_(book_ids))
        .order_by(BookAuthor.book_id, BookAuthor.position)
    ).all()
    result: dict[int, list[Author]] = {}
    for link, author in rows:
        result.setdefault(link.book_id, []).append(author)
    return result


def catalog_authors(session: Session) -> list[dict]:
    """Все авторы КАТАЛОГА с числом книг (задача 111).

    ⚠ Считаем по общей базе, а не по полке спрашивающего (решение Ксении
    03.08). `/authors` — справочный раздел сервиса, а не срез личной полки:
    он отвечает на вопрос «что вообще есть в библиотеке», и у Донато Карризи
    здесь честные семь книг, даже если читатель завёл у себя две. Что из этого
    лежит на полке лично у него, показывает страница автора — там книги
    разложены на две стопки.

    Следствие: список одинаков для всех пользователей, `user_id` не нужен.

    Механика — общая с жанрами (`services/catalog.py`, ревью 03.08): здесь
    остаётся только то, чем автор отличается от жанра, — имя собирается
    из двух полей.
    """
    return entity_directory(
        session,
        Author,
        BookAuthor,
        BookAuthor.author_id,
        Author.sort_key,      # сортируем по ключу тождества, а не по показу
        display_name,
    )


def books_of(session: Session, author_id: int, user_id: int) -> dict:
    """Книги автора: `shelf` — с полки читателя, `catalog` — остальные из базы.

    Разложение общее с жанрами (`services/catalog.books_split`).
    """
    return books_split(session, BookAuthor, BookAuthor.author_id, author_id, user_id)
