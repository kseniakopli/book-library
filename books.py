from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

import database
from models import Book, ALLOWED_STATUSES
from schemas import BookCreate, BookUpdate
from i18n import ALLOWED_LANGS, msg
from google_books import fetch_book_info

router = APIRouter()


@router.post("/books")
def add_book(data: BookCreate, lang: str = "ru"):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))
    info = fetch_book_info(data.title, data.author, lang)
    book = Book(
        title=data.title,
        author=data.author,
        cover_url=info["cover_url"],
        description=info["description"],
    )
    with Session(database.engine) as session:
        session.add(book)
        session.commit()
        session.refresh(book)
    return book


@router.patch("/books/{book_id}")
def update_book(book_id: int, data: BookUpdate, lang: str = "ru"):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail=msg("book_not_found", lang))

        if data.status is not None:
            if data.status not in ALLOWED_STATUSES:
                raise HTTPException(status_code=400, detail=msg("bad_status", lang))
            book.status = data.status

        if data.rating is not None:
            if not (1 <= data.rating <= 10):
                raise HTTPException(status_code=400, detail=msg("bad_rating", lang))
            if book.status != "read":
                raise HTTPException(status_code=400, detail=msg("rating_needs_read", lang))
            book.rating = data.rating

        if book.status != "read":
            book.rating = None

        session.add(book)
        session.commit()
        session.refresh(book)
    return book


@router.get("/books")
def list_books():
    with Session(database.engine) as session:
        books = session.exec(select(Book)).all()
    return books