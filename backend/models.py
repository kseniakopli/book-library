from datetime import datetime
from typing import Optional
from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel, UniqueConstraint

from constants import SOURCE_CLAUDE


# --- Пользователь. Пока один (id=1, admin); задел под авторизацию (этап 9) ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    display_name: str = "Ксения"
    is_admin: bool = False          # перегенерация атмосферы и правка книги — только admin
    created_at: datetime = Field(default_factory=datetime.now)


# --- Книга (общий каталог). Одна строка = одна реальная книга, общая для всех,
# кто добавил её на полку. Только книго-внутренние поля; личное — в UserBook ---
class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    author: str
    cover_url: Optional[str] = None        # обложка (из Google Books)
    description: Optional[str] = None       # описание (из Google Books)
    created_at: datetime = Field(default_factory=datetime.now)
    # --- метаданные (из Google Books) ---
    page_count: Optional[int] = None
    categories: Optional[str] = None         # JSON-строка со списком жанров
    published_year: Optional[int] = None
    language: Optional[str] = None
    external_rating: Optional[float] = None   # средний рейтинг Google
    raw_metadata: Optional[str] = None        # полный volumeInfo как JSON (страховка)
    isbn: Optional[str] = None
    enrich_status: str = "ready"                 # pending / ready / failed
    # Атмосфера/оформление (AISelection) и плейлист генерируются один раз на книгу
    # и переиспользуются всеми, кто её добавил (решение 18.07)
    spotify_playlist_url: Optional[str] = None   # постоянная ссылка на плейлист (этап 10.2)
    # Задача 89: принадлежность циклу — свойство самой книги (объективное),
    # поэтому здесь, а не в UserBook. Заполняется вручную со страницы цикла.
    series_id: Optional[int] = Field(
        default=None, foreign_key="series.id", index=True, ondelete="SET NULL"
    )
    series_index: Optional[int] = None            # номер книги в цикле (1, 2, 3…)


# --- Полка пользователя: одна строка = одна книга у одного пользователя.
# Личные данные (статус, оценка, дата прочтения) живут здесь, не в Book ---
class UserBook(SQLModel, table=True):
    __table_args__ = (
        # одна книга на полке пользователя один раз (заодно дедуп добавления)
        UniqueConstraint("user_id", "book_id", name="uq_userbook_user_book"),
        # Задача 7: инвариант «оценка только у прочитанной» переехал сюда вместе
        # со статусом и оценкой
        CheckConstraint(
            "rating IS NULL OR status = 'read'",
            name="ck_userbook_rating_only_read",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    book_id: int = Field(foreign_key="book.id", index=True, ondelete="CASCADE")
    status: str = "want"                   # want / reading / read
    rating: Optional[int] = None           # 1..10, только для прочитанных
    read_at: Optional[datetime] = None     # дата прочтения (фундамент статистики)
    created_at: datetime = Field(default_factory=datetime.now)  # когда добавлена на полку
    updated_at: datetime = Field(default_factory=datetime.now)  # задача 1


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
    # Задача 85: для music — прошла ли подборка резолв в Spotify. False = сохранена
    # при бане Spotify (треки не проверены, плейлиста нет); скрипт reverify_music
    # перепроверит, когда Spotify отпустит. Для остальных категорий всегда True.
    verified: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

# --- Рекомендации (этап 8): книги, которых у пользователя ещё НЕТ.
# Генерируются по кнопке (LLM по высоко оценённым книгам) и хранятся до
# следующей генерации — набор целиком заменяется. Ссылки на book.id нет:
# рекомендованной книги в каталоге может не быть вовсе ---
class Recommendation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str
    author: str
    reason: str                            # почему именно эта книга
    # Кто посоветовал: Claude / ChatGPT (20.07 — советы от обоих, как в атмосфере)
    source: str = Field(default=SOURCE_CLAUDE)
    cover_url: Optional[str] = None        # подтягиваем из Google Books
    external_id: Optional[str] = None      # том Google Books — точное добавление
    created_at: datetime = Field(default_factory=datetime.now)


# --- Обратная связь по AI-подборкам (задача 26): 👍/👎 на атмосферу и советы.
# Копится у нас (не отправляется провайдерам — API моделей без памяти) для двух
# целей: (1) acceptance rate Claude vs ChatGPT; (2) «профиль вкуса» в промпт
# будущих генераций. `ref` — стабильный ключ цели оценки:
#   атмосфера   → "atmosphere:{book_id}:{category}:{source}"
#   рекомендация→ "recommendation:{norm_title}|{norm_author}"
# `source` дублируем отдельным полем — для сводки по провайдерам без разбора ref.
# UNIQUE(user_id, ref): у пользователя одна оценка на цель (меняется/снимается) ---
class Feedback(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "ref", name="uq_feedback_user_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    ref: str = Field(index=True)
    source: Optional[str] = None            # Claude / ChatGPT (для сводки)
    verdict: str                            # "up" / "down"
    created_at: datetime = Field(default_factory=datetime.now)


# --- Циклы книг (задача 89). Разделение как у книг: `Series` — общий каталог
# (цикл существует объективно, независимо от читателя), `UserSeries` — личный
# статус. Книги цикла, которых нет на полке, — это обычные записи `Book` без
# `UserBook`: они находятся поиском и показывают «что читать дальше».
# Разведка 22.07: ни Google Books, ни OpenLibrary серий не отдают — заполняется
# вручную (`scripts/explore_series.py`, подробности в задаче 89) ---
class Series(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)               # «Неаполитанский квартет»
    author: Optional[str] = None                # автор цикла (для карточки)
    description: Optional[str] = None
    # Паспорт оформления цикла (экслибрис + палитры), JSON как у книги
    design: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class UserSeries(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "series_id", name="uq_userseries_user_series"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    series_id: int = Field(foreign_key="series.id", index=True, ondelete="CASCADE")
    status: str = Field(default="reading")      # reading / read / dropped
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


# --- Кэш резолва треков в Spotify (задача 82, часть 1). Каждый трек резолвится
# ОДИН раз на всю систему: атмосферные подборки сильно пересекаются, а квота
# Spotify — на приложение (инцидент 21.07 — бан). Кэшируем и «не найдено»
# (found=False): выдуманные моделью треки иначе долбили бы Spotify каждый раз.
# query_key — нормализованный «артист|название» из запроса модели (не канон);
# при found=True title/artist/uri — канонические из Spotify ---
class TrackCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    query_key: str = Field(index=True, unique=True)
    found: bool = False
    title: Optional[str] = None       # канонические (если found)
    artist: Optional[str] = None
    uri: Optional[str] = None
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
