from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class BookCreate(BaseModel):
    title: str
    author: str
    cover_url: Optional[str] = None      # обложка выбранного кандидата из поиска
    external_id: Optional[str] = None    # id тома Google Books — для точного обогащения
    book_id: Optional[int] = None        # книга уже в каталоге (выбор из локального поиска) —
                                         # тогда переиспользуем её (атмосферу не генерим заново)
    isbn: Optional[str] = None           # если известен — дедуп при добавлении идёт и по нему
    status: str = "want"                 # задача 18: статус выбирается при добавлении
    read_at: Optional[datetime] = None   # задача 18: дата прочтения (для status=read)

    # Security (задача 37): cover_url рендерится в <img src> — только https
    @field_validator("cover_url")
    @classmethod
    def _https_only(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not v.startswith("https://"):
            raise ValueError("cover_url должен начинаться с https://")
        return v


class BookUpdate(BaseModel):
    status: Optional[str] = None
    rating: Optional[int] = None
    # Задача 1: явная дата прочтения (ISO).
    # ⚠ Задача 115: у этого поля `null` значит «очистить», а не «не менять» —
    # «прочитана, но не помню когда» это честное состояние (з.98), и вернуться
    # к нему надо уметь. Отличить одно от другого позволяет `model_fields_set`
    # (см. `apply_shelf_fields`), поэтому тип менять не пришлось.
    read_at: Optional[datetime] = None
    # Задача 3 (ручная правка): промахи обогащения исправляются руками.
    # None означает «не менять»; пустая строка в isbn/cover_url/description —
    # «очистить поле» (в title/author пустота запрещена — см. роутер).
    title: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    description: Optional[str] = None
    # Задача 121: год правится руками. Google Books отдаёт год ИЗДАНИЯ
    # найденного экземпляра, а не написания — у классики это расходится,
    # и поправить надо уметь.
    # ⚠ Как и у `read_at` (з.115), `null` здесь значит «очистить», а не
    # «не менять»: неверный год без права стереть его хуже пустого поля.
    # Отличает одно от другого `model_fields_set` в `apply_book_fields`.
    published_year: Optional[int] = None
    # Задача 30: показывать книгу в публичной витрине (личная отметка полки)
    featured: Optional[bool] = None

    # та же политика безопасности, что при создании: в <img src> — только https
    @field_validator("cover_url")
    @classmethod
    def _https_only(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return ""          # пустая строка = «убрать обложку» (не None: None = «не менять»)
        if not v.startswith("https://"):
            raise ValueError("cover_url должен начинаться с https://")
        return v


class AuthorBrief(BaseModel):
    """Автор в ответе книги (задача 97): ровно столько, сколько нужно ссылке.
    `name` уже разрешён — `name_ru`, а если русского нет, оригинальное написание."""
    id: int
    name: str


class GenreBrief(BaseModel):
    """Жанр в ответе книги (задача 112): столько, сколько нужно ссылке."""
    id: int
    name: str


class BookRead(BaseModel):
    """Ответ API (R4/задача 34): всё, что знает Book, КРОМЕ raw_metadata —
    полный JSON Google Books наружу не отдаём (и он тяжёлый, и он внутренний).

    После разделения таблиц ответ склеивается из двух источников: общие поля
    книги (Book) + личные поля полки (UserBook). Сборка — в `from_pair`,
    рядом с самим контрактом (ревью 19.07: раньше жила в роутере).

    ⚠ С 03.08 личные поля НЕОБЯЗАТЕЛЬНЫ. Книга — общая сущность каталога,
    и открыть её страницу можно, даже если на своей полке её нет: её завёл
    другой читатель или это том цикла, попавший в базу вместе с серией.
    Тогда `on_shelf=false`, а `status`/`rating`/`read_at` просто отсутствуют —
    подставлять «хочу прочитать» значило бы врать контрактом.
    Найдено Ксенией на проде 03.08: книга 211 отдавала 404 всем, кроме
    того, кто её добавил."""
    id: int
    # у книги вне полки нет владельца — поле остаётся ради обратной
    # совместимости контракта, но может быть пустым
    user_id: Optional[int] = None
    title: str
    author: str
    cover_url: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = None
    # created_at — это когда книга легла НА ПОЛКУ, а не когда появилась в базе
    created_at: Optional[datetime] = None
    on_shelf: bool = True
    page_count: Optional[int] = None
    categories: Optional[str] = None
    published_year: Optional[int] = None
    language: Optional[str] = None
    external_rating: Optional[float] = None
    isbn: Optional[str] = None
    enrich_status: str
    spotify_playlist_url: Optional[str] = None
    updated_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    # Задача 89/90б: принадлежность циклу — для блока на странице книги.
    # series_name подставляется в роутере (нужен JOIN на Series).
    series_id: Optional[int] = None
    series_index: Optional[int] = None
    series_name: Optional[str] = None
    featured: bool = False               # задача 30: книга в публичной витрине
    # Задача 97: авторы как сущности — чтобы имя на странице книги стало ссылкой.
    # Строка `author` остаётся: она нужна для показа и печатной карточки, а список
    # может быть пустым у книг, добавленных до появления таблицы.
    authors: list["AuthorBrief"] = []
    # Задача 112: наши жанры (заведённые вручную). `categories` рядом остаётся —
    # это рубрикатор Google Books, он показывается админу подсказкой при
    # заполнении, но жанрами не считается.
    genres: list["GenreBrief"] = []

    @classmethod
    def from_pair(
        cls,
        book,
        user_book,
        series_name: Optional[str] = None,
        authors: Optional[list] = None,
        genres: Optional[list] = None,
    ) -> "BookRead":
        """Склейка ответа: общие поля книги + личные поля полки.
        Контракт остаётся плоским — фронт читает как до разделения таблиц.

        `user_book=None` — книга есть в каталоге, но не на полке спрашивающего
        (03.08). Личные поля тогда не заполняются, `on_shelf=false`.
        """
        return cls(
            id=book.id,
            user_id=user_book.user_id if user_book else None,
            title=book.title,
            author=book.author,
            cover_url=book.cover_url,
            description=book.description,
            status=user_book.status if user_book else None,
            rating=user_book.rating if user_book else None,
            featured=user_book.featured if user_book else False,
            created_at=user_book.created_at if user_book else None,
            on_shelf=user_book is not None,
            page_count=book.page_count,
            categories=book.categories,
            published_year=book.published_year,
            language=book.language,
            external_rating=book.external_rating,
            isbn=book.isbn,
            enrich_status=book.enrich_status,
            spotify_playlist_url=book.spotify_playlist_url,
            updated_at=user_book.updated_at if user_book else None,
            read_at=user_book.read_at if user_book else None,
            series_id=book.series_id,
            series_index=book.series_index,
            series_name=series_name,
            authors=authors or [],
            genres=genres or [],
        )


def build_book_read(session, book, user_book, *, full: bool = False) -> "BookRead":
    """Собрать ответ по книге со связанными сущностями (ревью 03.08, Б2).

    До этого сборка жила в трёх местах роутера и различалась не по замыслу,
    а по истории правок: список тянул авторов, одиночная книга — авторов,
    жанры и цикл, добавление — ничего.

    `full=False` (список полки) — только авторы: без них на карточке остаётся
    строка каталога, а в ней написание как в источнике («Ann Patchett»).
    `full=True` (страница книги) — плюс жанры и имя цикла: они нужны только
    там, а в списке из 30 книг это лишние JOIN на каждую строку.

    ⚠ Пакетный вызов (список) собирает авторов ОДНИМ запросом на страницу —
    см. `list_books`. Здесь функция работает по одной книге и рассчитана
    на одиночные ответы.
    """
    # локальные импорты: schemas не должен зависеть от сервисов на уровне
    # модуля — иначе получаем круг (services → models → schemas)
    from models import Series
    from services.authors import authors_of, display_name
    from services.genres import genres_of

    authors = [
        AuthorBrief(id=a.id, name=display_name(a))
        for a in authors_of(session, [book.id]).get(book.id, [])
    ]
    if not full:
        return BookRead.from_pair(book, user_book, authors=authors)

    series_name = None
    if book.series_id is not None:
        series = session.get(Series, book.series_id)
        series_name = series.name if series else None

    genres = [
        GenreBrief(id=g.id, name=g.name)
        for g in genres_of(session, [book.id]).get(book.id, [])
    ]
    return BookRead.from_pair(book, user_book, series_name, authors, genres)