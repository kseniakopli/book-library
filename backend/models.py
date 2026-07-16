from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, UniqueConstraint


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
    # --- поля под статистику (из Google Books) ---
    page_count: Optional[int] = None
    categories: Optional[str] = None         # JSON-строка со списком жанров
    published_year: Optional[int] = None
    language: Optional[str] = None
    external_rating: Optional[float] = None   # средний рейтинг Google
    raw_metadata: Optional[str] = None        # полный volumeInfo как JSON (страховка)
    isbn: Optional[str] = None
    enrich_status: str = "ready"                 # pending / ready / failed
    spotify_playlist_url: Optional[str] = None   # постоянная ссылка на плейлист (этап 10.2)

# --- AI-подборка «Атмосфера»: одна строка = один вариант (источник) для книги ---
class AISelection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "book_id", "category", "source",
            name="uq_aiselection_book_category_source",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", index=True, ondelete="CASCADE")  # к какой книге
    category: str                     # music / food / aroma
    source: str                       # Claude / ChatGPT
    payload: str                      # JSON-строка со списком (например, песен)
    explanation: str = ""             # пояснение от AI
    created_at: datetime = Field(default_factory=datetime.now)

# --- Каталог для поиска: наполняется из внешних источников, кэш для автоподсказки ---
class Catalog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)          # ищем по вхождению — индекс ускоряет
    author: str = Field(index=True)
    cover_url: Optional[str] = None
    source: str = "google"                  # откуда (google / openlibrary)
    external_id: Optional[str] = None       # id записи во внешнем источнике
    created_at: datetime = Field(default_factory=datetime.now)


# ALLOWED_STATUSES и прочие константы переехали в constants.py (рефакторинг R3)