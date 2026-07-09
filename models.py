from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# --- Таблица «книги». Одна такая строка = одна книга в БД ---
class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = 1                       # пока один пользователь; связь под будущий вход
    title: str
    author: str
    cover_url: Optional[str] = None        # обложка (из Google Books)
    description: Optional[str] = None       # описание (из Google Books)
    status: str = "want"                   # want / reading / read
    rating: Optional[int] = None           # 1..10, только для прочитанных
    created_at: datetime = Field(default_factory=datetime.now)


ALLOWED_STATUSES = {"want", "reading", "read"}