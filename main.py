from datetime import datetime
from typing import Optional
import requests
from fastapi import FastAPI,  HTTPException
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, create_engine, select


# --- Таблица «книги». Одна такая строка = одна книга в БД ---
class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = 1                       # пока один пользователь; связь под будущий вход
    title: str
    author: str
    cover_url: Optional[str] = None        # обложка (подтянем позже из внешнего API)
    description: Optional[str] = None      # описание (тоже позже)
    status: str = "want"                   # want / reading / read
    rating: Optional[int] = None           # 1..10, только для прочитанных
    created_at: datetime = Field(default_factory=datetime.now)


# --- Подключение к базе (файл library.db создастся сам) ---
engine = create_engine("sqlite:///library.db")
SQLModel.metadata.create_all(engine)       # создаём таблицы при запуске

app = FastAPI()


# --- Обогащение: тянем обложку и описание из Google Books ---
def fetch_book_info(title: str, author: str) -> dict:
    """Спрашиваем у Google Books обложку и описание.
    Возвращаем словарь {cover_url, description}. Если что-то не нашлось
    или сервис недоступен — возвращаем None, книга всё равно сохранится."""
    result = {"cover_url": None, "description": None}
    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": f"intitle:{title}+inauthor:{author}", "maxResults": 1},
            timeout=5,                      # не ждём ответа дольше 5 секунд
        )
        response.raise_for_status()         # ошибка сети/сервера → уходим в except
        items = response.json().get("items", [])
        if not items:                       # ничего не нашлось по запросу
            return result
        info = items[0].get("volumeInfo", {})
        result["description"] = info.get("description")
        image_links = info.get("imageLinks", {})
        # берём картинку покрупнее, если есть, иначе обычную миниатюру
        cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if cover:
            result["cover_url"] = cover.replace("http://", "https://")
    except requests.RequestException:
        pass                                # молча оставляем None — не роняем добавление
    return result


# --- Что присылают при добавлении книги ---
class BookCreate(BaseModel):
    title: str
    author: str

class BookUpdate(BaseModel):
    status: Optional[str] = None
    rating: Optional[int] = None


ALLOWED_STATUSES = {"want", "reading", "read"}


@app.post("/books")
def add_book(data: BookCreate):
    info = fetch_book_info(data.title, data.author)   # 1) спрашиваем Google Books
    book = Book(
        title=data.title,
        author=data.author,
        cover_url=info["cover_url"],                   # 2) кладём обложку
        description=info["description"],               # 3) и описание
    )
    with Session(engine) as session:       # session — «сеанс общения» с БД
        session.add(book)                  # готовим к сохранению
        session.commit()                   # сохраняем
        session.refresh(book)              # подтягиваем присвоенный id
    return book

@app.patch("/books/{book_id}")
def update_book(book_id: int, data: BookUpdate):
    with Session(engine) as session:
        book = session.get(Book, book_id)          # находим книгу по id
        if book is None:                           # такой книги нет
            raise HTTPException(status_code=404, detail="Книга не найдена")

        # 1) если прислали статус — проверяем его и применяем
        if data.status is not None:
            if data.status not in ALLOWED_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail="Статус должен быть want, reading или read",
                )
            book.status = data.status

        # 2) правило оценки: только для прочитанной книги и только 1..10
        if data.rating is not None:
            if not (1 <= data.rating <= 10):
                raise HTTPException(status_code=400, detail="Оценка должна быть от 1 до 10")
            if book.status != "read":
                raise HTTPException(
                    status_code=400,
                    detail="Оценку можно ставить только книге со статусом read",
                )
            book.rating = data.rating

        # 3) если книга не «прочитана» — оценка бессмысленна, обнуляем
        if book.status != "read":
            book.rating = None

        session.add(book)
        session.commit()
        session.refresh(book)
    return book

@app.get("/books")
def list_books():
    with Session(engine) as session:
        books = session.exec(select(Book)).all()   # select(Book) = «выбрать все книги»
    return books