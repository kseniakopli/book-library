from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class BookCreate(BaseModel):
    title: str
    author: str
    cover_url: Optional[str] = None      # обложка выбранного кандидата из поиска
    external_id: Optional[str] = None    # id тома Google Books — для точного обогащения

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


class BookRead(BaseModel):
    """Ответ API (R4/задача 34): всё, что знает Book, КРОМЕ raw_metadata —
    полный JSON Google Books наружу не отдаём (и он тяжёлый, и он внутренний)."""
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