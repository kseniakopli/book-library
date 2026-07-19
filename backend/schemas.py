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
    read_at: Optional[datetime] = None   # задача 1: явная дата прочтения (ISO)
    # Задача 3 (ручная правка): промахи обогащения исправляются руками.
    # None означает «не менять»; пустая строка в isbn/cover_url/description —
    # «очистить поле» (в title/author пустота запрещена — см. роутер).
    title: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    cover_url: Optional[str] = None
    description: Optional[str] = None

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


class BookRead(BaseModel):
    """Ответ API (R4/задача 34): всё, что знает Book, КРОМЕ raw_metadata —
    полный JSON Google Books наружу не отдаём (и он тяжёлый, и он внутренний).

    После разделения таблиц ответ склеивается из двух источников: общие поля
    книги (Book) + личные поля полки (UserBook). Сборка — в `from_pair`,
    рядом с самим контрактом (ревью 19.07: раньше жила в роутере)."""
    id: int
    user_id: int
    title: str
    author: str
    cover_url: Optional[str] = None
    description: Optional[str] = None
    status: str
    rating: Optional[int] = None
    created_at: datetime
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

    @classmethod
    def from_pair(cls, book, user_book) -> "BookRead":
        """Склейка ответа: общие поля книги + личные поля полки.
        Контракт остаётся плоским — фронт читает как до разделения таблиц."""
        return cls(
            id=book.id,
            user_id=user_book.user_id,
            title=book.title,
            author=book.author,
            cover_url=book.cover_url,
            description=book.description,
            status=user_book.status,
            rating=user_book.rating,
            created_at=user_book.created_at,      # когда книга легла на полку
            page_count=book.page_count,
            categories=book.categories,
            published_year=book.published_year,
            language=book.language,
            external_rating=book.external_rating,
            isbn=book.isbn,
            enrich_status=book.enrich_status,
            spotify_playlist_url=book.spotify_playlist_url,
            updated_at=user_book.updated_at,
            read_at=user_book.read_at,
        )