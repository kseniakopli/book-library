from datetime import datetime
from typing import Optional

from fastapi import FastAPI
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


# --- Что присылают при добавлении книги ---
class BookCreate(BaseModel):
    title: str
    author: str


@app.post("/books")
def add_book(data: BookCreate):
    book = Book(title=data.title, author=data.author)
    with Session(engine) as session:       # session — «сеанс общения» с БД
        session.add(book)                  # готовим к сохранению
        session.commit()                   # сохраняем
        session.refresh(book)              # подтягиваем присвоенный id
    return book


@app.get("/books")
def list_books():
    with Session(engine) as session:
        books = session.exec(select(Book)).all()   # select(Book) = «выбрать все книги»
    return books