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
from sqlmodel import Session, select

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
    """Связать книгу с авторами из её строки. Идемпотентно: повторный вызов
    не создаёт ни вторых авторов, ни вторых связей."""
    authors = []
    for position, name in enumerate(split_authors(raw_author)):
        author = get_or_create(session, name)
        exists = session.exec(
            select(BookAuthor).where(
                BookAuthor.book_id == book_id,
                BookAuthor.author_id == author.id,
            )
        ).first()
        if exists is None:
            session.add(
                BookAuthor(book_id=book_id, author_id=author.id, position=position)
            )
        authors.append(author)
    return authors


def display_name(author: Author) -> str:
    """Как показывать автора: по-русски, а если русского нет — как записано."""
    return author.name_ru or author.name_original or ""
