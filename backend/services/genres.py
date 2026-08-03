"""Жанры как сущность (задача 112).

⚠ В отличие от авторов, здесь НЕТ разбора внешних данных. У авторов строка
`Book.author` была настоящим источником — её оставалось нормализовать.
Google Books же отдаёт «Fiction / General», «Juvenile Fiction» и подобное:
это рубрикатор магазина, а не жанр книги. Поэтому жанры заводит человек,
а `Book.categories` остаётся подсказкой админу в интерфейсе (решение Ксении
03.08) и в промпт больше не уезжает.

Устройство повторяет авторов там, где это уместно: ключ тождества `slug`,
связь многие-ко-многим, полная перепривязка вместо «добавить».
"""

import unicodedata

from sqlmodel import Session, col, select

from models import BookGenre, Genre
from services.catalog import books_split, entity_directory

MAX_NAME_CHARS = 60      # «Магический реализм» — 18; 60 хватает с запасом


def norm_slug(name: str) -> str:
    """Ключ тождества жанра.

    Регистр, лишние пробелы и ё/е — шум: «Тёмное фэнтези», «тёмное фэнтези»
    и «Темное  фэнтези» должны схлопнуться в один жанр, иначе список через
    месяц зарастёт дублями (ровно то, от чего страхует `sort_key` у автора).
    """
    text = unicodedata.normalize("NFKC", name).strip().lower().replace("ё", "е")
    return " ".join(text.split())


def get_or_create(session: Session, name: str) -> Genre:
    """Жанр по имени: находит существующий по ключу или заводит новый.

    Имя сохраняется КАК ВВЕЛИ (с заглавной, с «ё»), а ищется по ключу:
    показывать надо человеческий вариант, а сравнивать — нормализованный.
    """
    slug = norm_slug(name)
    found = session.exec(select(Genre).where(Genre.slug == slug)).first()
    if found is not None:
        return found

    genre = Genre(name=name.strip(), slug=slug)
    session.add(genre)
    session.flush()      # нужен id для связи
    return genre


def set_book_genres(session: Session, book_id: int, names: list[str]) -> list[Genre]:
    """Заменить набор жанров книги ЦЕЛИКОМ.

    Именно замена, а не добавление, — тот же урок, что с авторами (баг 28.07):
    интерфейс правки показывает полный список, значит и сохранять надо полный.
    «Только добавлять» означало бы, что снятую галочку никак не снять.

    Жанр, оставшийся без книг, удаляется: сущность живёт ради связей, пустой
    жанр — это мусор в списке и пустая страница по прямой ссылке.
    """
    wanted = {}
    for raw in names:
        clean = (raw or "").strip()[:MAX_NAME_CHARS]
        if clean:
            wanted[norm_slug(clean)] = clean

    genres = [get_or_create(session, name) for name in wanted.values()]
    keep = {genre.id for genre in genres}

    orphan_candidates = []
    for link in session.exec(
        select(BookGenre).where(BookGenre.book_id == book_id)
    ).all():
        if link.genre_id in keep:
            keep.discard(link.genre_id)      # уже связано — ничего не делаем
        else:
            orphan_candidates.append(link.genre_id)
            session.delete(link)

    for genre_id in keep:
        session.add(BookGenre(book_id=book_id, genre_id=genre_id))

    session.flush()
    _drop_orphans(session, orphan_candidates)
    return genres


def _drop_orphans(session: Session, genre_ids: list[int]) -> None:
    for genre_id in genre_ids:
        still_used = session.exec(
            select(BookGenre).where(BookGenre.genre_id == genre_id)
        ).first()
        if still_used is None:
            genre = session.get(Genre, genre_id)
            if genre is not None:
                session.delete(genre)
    session.flush()


def genres_of(session: Session, book_ids: list[int]) -> dict[int, list[Genre]]:
    """Жанры для списка книг ОДНИМ запросом (как `authors_of`): полка на 200
    книг иначе дала бы двести обращений к базе."""
    if not book_ids:
        return {}
    rows = session.exec(
        select(BookGenre, Genre)
        .join(Genre, Genre.id == BookGenre.genre_id)
        .where(col(BookGenre.book_id).in_(book_ids))
        .order_by(BookGenre.book_id, Genre.slug)
    ).all()
    result: dict[int, list[Genre]] = {}
    for link, genre in rows:
        result.setdefault(link.book_id, []).append(genre)
    return result


def catalog_genres(session: Session) -> list[dict]:
    """Справочник жанров с числом книг.

    Считается по ОБЩЕМУ каталогу, а не по полке спрашивающего — тем же
    правилом, что и авторы (решение Ксении 03.08): раздел отвечает
    на вопрос «что есть в библиотеке».

    Механика общая (`services/catalog.py`); от автора жанр отличается только
    тем, что имя у него одно и разрешать его не нужно.
    """
    return entity_directory(
        session,
        Genre,
        BookGenre,
        BookGenre.genre_id,
        Genre.slug,           # сортируем по ключу тождества, а не по показу
        lambda genre: genre.name,
    )


def books_of(session: Session, genre_id: int, user_id: int) -> dict:
    """Книги жанра: `shelf` — с полки читателя, `catalog` — остальные из базы.

    Вторая стопка здесь не бонус, а половина смысла: по ней и выбирают,
    что читать дальше. Разложение общее с авторами
    (`services/catalog.books_split`).
    """
    return books_split(session, BookGenre, BookGenre.genre_id, genre_id, user_id)
