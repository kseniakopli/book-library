from typing import Optional

from pydantic import BaseModel


class BookCreate(BaseModel):
    title: str
    author: str


class BookUpdate(BaseModel):
    status: Optional[str] = None
    rating: Optional[int] = None