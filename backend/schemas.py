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