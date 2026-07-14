import csv
import io
import json
from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlmodel import Session, select, or_, col
import database
from models import Book, AISelection, Catalog, ALLOWED_STATUSES
from schemas import BookCreate, BookUpdate
from i18n import ALLOWED_LANGS, msg
from google_books import fetch_book_info, search_books
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
        page_count=info["page_count"],
        categories=info["categories"],
        published_year=info["published_year"],
        language=info["language"],
        external_rating=info["external_rating"],
        raw_metadata=info["raw_metadata"],
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

@router.get("/search")
def search(q: str):
    q = q.strip()
    if len(q) < 3:                       # от 3 символов — бережём внешний API
        return {"results": []}

    with Session(database.engine) as session:
        pattern = f"%{q}%"
        local = session.exec(
            select(Catalog).where(
                or_(col(Catalog.title).ilike(pattern), col(Catalog.author).ilike(pattern))
            ).limit(10)
        ).all()

        results = [
            {"title": c.title, "author": c.author, "cover_url": c.cover_url}
            for c in local
        ]

        # Мало нашли в своём каталоге — идём во внешний источник и кэшируем найденное
        if len(results) < 5:
            external = search_books(q)
            known_ids = {c.external_id for c in local if c.external_id}
            seen = {(r["title"].lower(), r["author"].lower()) for r in results}
            for item in external:
                if item["external_id"] and item["external_id"] not in known_ids:
                    session.add(Catalog(
                        title=item["title"],
                        author=item["author"],
                        cover_url=item["cover_url"],
                        source="google",
                        external_id=item["external_id"],
                    ))
                key = (item["title"].lower(), item["author"].lower())
                if key not in seen:
                    results.append({
                        "title": item["title"],
                        "author": item["author"],
                        "cover_url": item["cover_url"],
                    })
                    seen.add(key)
            session.commit()

    return {"results": results[:10]}

@router.post("/books/backfill-covers")
def backfill_covers():
    updated = 0
    with Session(database.engine) as session:
        books = session.exec(
            select(Book).where(col(Book.cover_url).is_(None))
        ).all()
        for book in books:
            # свободный поиск лучше находит многословные русские названия
            candidates = search_books(f"{book.title} {book.author}", max_results=5)
            cover = next((c["cover_url"] for c in candidates if c["cover_url"]), None)
            if cover:
                book.cover_url = cover
                session.add(book)
                updated += 1
        session.commit()
    return {"updated": updated}

@router.post("/import")
async def import_csv(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8-sig")        # utf-8-sig убирает BOM, если он есть
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped = 0
    with Session(database.engine) as session:
        for row in reader:
            title = (row.get("Название") or "").strip()
            author = (row.get("Автор") or "").strip()
            if not title or not author:       # нет названия/автора — пропускаем строку
                skipped += 1
                continue

            rating = None
            raw = (row.get("Моя оценка") or "").strip()
            if raw.isdigit() and 1 <= int(raw) <= 10:
                rating = int(raw)

            read_date = (row.get("Дата прочтения") or "").strip()
            status = "read" if (rating is not None or read_date) else "want"

            isbn = (row.get("ISBN") or "").strip() or None
            session.add(Book(title=title, author=author, rating=rating, status=status, isbn=isbn))
            imported += 1
        session.commit()

    return {"imported": imported, "skipped": skipped}

@router.post("/books/backfill-metadata")
def backfill_metadata(limit: int = 40, lang: str = "ru"):
    updated = 0
    with Session(database.engine) as session:
        # берём порцию книг, у которых ещё нет метаданных (raw_metadata пуст)
        books = session.exec(
            select(Book).where(col(Book.raw_metadata).is_(None)).limit(limit)
        ).all()
        for book in books:
            info = fetch_book_info(book.title, book.author, lang)
            if not info["raw_metadata"]:
                continue          # не нашли или сбой сети — попробуем в следующий заход
            book.cover_url = info["cover_url"] or book.cover_url
            book.description = info["description"] or book.description
            book.page_count = info["page_count"]
            book.categories = info["categories"]
            book.published_year = info["published_year"]
            book.language = info["language"]
            book.external_rating = info["external_rating"]
            book.raw_metadata = info["raw_metadata"]
            session.add(book)
            updated += 1
        session.commit()
        remaining = len(session.exec(
            select(Book).where(col(Book.raw_metadata).is_(None))
        ).all())
    return {"updated": updated, "remaining": remaining}

@router.post("/books/{book_id}/enrich")
def enrich_book(book_id: int, lang: str = "ru"):
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail=msg("book_not_found", lang))

        info = fetch_book_info(book.title, book.author, lang, isbn=book.isbn)
        if info["raw_metadata"]:              # нашли подходящую книгу — обновляем
            book.cover_url = info["cover_url"] or book.cover_url
            book.description = info["description"] or book.description
            book.page_count = info["page_count"]
            book.categories = info["categories"]
            book.published_year = info["published_year"]
            book.language = info["language"]
            book.external_rating = info["external_rating"]
            book.raw_metadata = info["raw_metadata"]
            session.add(book)
            session.commit()
            session.refresh(book)
    return book