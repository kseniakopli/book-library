from typing import Optional

from pydantic import BaseModel


class BookCreate(BaseModel):
    title: str
    author: str
    cover_url: Optional[str] = None      # обложка выбранного кандидата из поиска
    external_id: Optional[str] = None    # id тома Google Books — для точного обогащения


class BookUpdate(BaseModel):
    status: Optional[str] = None
    rating: Optional[int] = None