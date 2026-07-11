import json

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

import database
from models import Book, AISelection, ALLOWED_STATUSES
from schemas import BookCreate, BookUpdate
from i18n import ALLOWED_LANGS, msg
from google_books import fetch_book_info
from atmosphere import generate_music, generate_design

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

@router.post("/books/{book_id}/music")
async def generate_book_music(book_id: int, lang: str = "ru"):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))

    # 1) берём книгу (короткая сессия, сразу закрываем — не держим её во время запроса к AI)
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail=msg("book_not_found", lang))
        title, author = book.title, book.author

    # 2) спрашиваем оба AI (здесь идут реальные вызовы и тратятся токены)
    results = await generate_music(title, author, lang)

    # 3) сохраняем: удаляем прежние музыкальные подборки книги и кладём свежие
    with Session(database.engine) as session:
        old = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == "music",
            )
        ).all()
        for row in old:
            session.delete(row)

        for source, result in results.items():
            songs = [song.model_dump() for song in result.songs]
            session.add(AISelection(
                book_id=book_id,
                category="music",
                source=source,
                payload=json.dumps(songs, ensure_ascii=False),
                explanation=result.explanation,
            ))
        session.commit()

    # 4) отдаём результат
    return {
        "book_id": book_id,
        "category": "music",
        "selections": [
            {
                "source": source,
                "songs": [s.model_dump() for s in result.songs],
                "explanation": result.explanation,
            }
            for source, result in results.items()
        ],
    }


@router.get("/books/{book_id}/music")
def get_book_music(book_id: int):
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == "music",
            )
        ).all()
    return {
        "book_id": book_id,
        "category": "music",
        "selections": [
            {
                "source": row.source,
                "songs": json.loads(row.payload),
                "explanation": row.explanation,
            }
            for row in rows
        ],
    }

@router.post("/books/{book_id}/design")
async def generate_book_design(book_id: int, lang: str = "ru"):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))

    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail=msg("book_not_found", lang))
        title, author = book.title, book.author

    result = await generate_design(title, author, lang)   # реальный AI-вызов (Claude)

    with Session(database.engine) as session:
        old = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == "design",
            )
        ).all()
        for row in old:
            session.delete(row)
        session.add(AISelection(
            book_id=book_id,
            category="design",
            source="Claude",
            payload=result.model_dump_json(),   # весь паспорт как JSON-строка
            explanation=result.statement,
        ))
        session.commit()

    return result


@router.get("/books/{book_id}/design")
def get_book_design(book_id: int):
    with Session(database.engine) as session:
        row = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == "design",
            )
        ).first()
    if row is None:
        return {"design": None}
    return {"design": json.loads(row.payload)}