import csv
import io
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from sqlmodel import Session, select, or_, col
import database
from models import Book, AISelection, Catalog, ALLOWED_STATUSES
from schemas import BookCreate, BookUpdate
from i18n import ALLOWED_LANGS, msg
from google_books import fetch_book_info, search_books
from atmosphere import generate_music, generate_design
from events import log_event

router = APIRouter()

CATALOG_TTL_DAYS = 30   # сколько дней запись каталога считается свежей


def _norm_isbn(value):
    """ISBN без дефисов и пробелов — для сравнения/дедупликации."""
    return value.replace("-", "").replace(" ", "") if value else None


def _enrich_in_background(book_id: int, lang: str) -> None:
    """Фоновая задача: сходить в Google Books и дозаполнить книгу.
    Ошибка не роняет ничего — просто ставим статус failed."""
    try:
        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            if book is None:               # книгу успели удалить
                return
            title, author = book.title, book.author

        info = fetch_book_info(title, author, lang)   # медленный внешний вызов — вне сессии

        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            if book is None:
                return
            book.cover_url = info["cover_url"]
            book.description = info["description"]
            book.page_count = info["page_count"]
            book.categories = info["categories"]
            book.published_year = info["published_year"]
            book.language = info["language"]
            book.external_rating = info["external_rating"]
            book.raw_metadata = info["raw_metadata"]
            book.enrich_status = "ready"
            session.add(book)
            session.commit()
        log_event("enriched", book_id, detail="ok" if info["raw_metadata"] else "miss")
    except Exception as e:
        print("Фоновое обогащение не удалось:", e)
        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            if book is not None:
                book.enrich_status = "failed"
                session.add(book)
                session.commit()
        log_event("enriched", book_id, detail="failed")


@router.post("/books")
def add_book(data: BookCreate, background_tasks: BackgroundTasks, lang: str = "ru"):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))
    # книга сохраняется сразу, без похода в Google Books — ответ мгновенный
    book = Book(title=data.title, author=data.author, enrich_status="pending")
    with Session(database.engine) as session:
        session.add(book)
        session.commit()
        session.refresh(book)
    log_event("book_added", book.id, detail="source=manual")
    background_tasks.add_task(_enrich_in_background, book.id, lang)  # запустится после ответа
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

    if data.status is not None:
        log_event("status_changed", book_id, detail=book.status)
    if data.rating is not None and book.rating is not None:
        log_event("rated", book_id, detail=str(book.rating))
    return book


@router.get("/books")
def list_books():
    with Session(database.engine) as session:
        books = session.exec(select(Book)).all()
    return books

@router.get("/books/{book_id}")
def get_book(book_id: int, lang: str = "ru"):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail=msg("book_not_found", lang))
    return book

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
        session.flush()   # применяем DELETE до вставки новых строк

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

    log_event("ai_music_generated", book_id)
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
        session.flush() 
        session.add(AISelection(
            book_id=book_id,
            category="design",
            source="Claude",
            payload=result.model_dump_json(),   # весь паспорт как JSON-строка
            explanation=result.statement,
        ))
        session.commit()

    log_event("ai_design_generated", book_id)
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

    cutoff = datetime.now() - timedelta(days=CATALOG_TTL_DAYS)
    with Session(database.engine) as session:
        pattern = f"%{q}%"
        # берём только свежие записи каталога (TTL) — протухшие игнорируем
        local = session.exec(
            select(Catalog).where(
                Catalog.created_at >= cutoff,
                or_(col(Catalog.title).ilike(pattern), col(Catalog.author).ilike(pattern)),
            ).limit(10)
        ).all()

        results = [
            {"title": c.title, "author": c.author, "cover_url": c.cover_url}
            for c in local
        ]

        # мало нашли в своём каталоге — идём во внешний источник и кэшируем/обновляем
        if len(results) < 5:
            external = search_books(q)
            seen = {(r["title"].lower(), r["author"].lower()) for r in results}
            for item in external:
                if item["external_id"]:
                    existing = session.exec(
                        select(Catalog).where(Catalog.external_id == item["external_id"])
                    ).first()
                    if existing:
                        existing.created_at = datetime.now()      # обновляем TTL
                        existing.cover_url = item["cover_url"] or existing.cover_url
                        session.add(existing)
                    else:
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

    log_event("search", detail=f"q={q}; found={len(results)}")
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
    duplicates = 0
    with Session(database.engine) as session:
        # ключи уже существующих книг — чтобы не задваивать при повторном импорте
        existing = session.exec(select(Book)).all()
        seen_isbn = {_norm_isbn(b.isbn) for b in existing if b.isbn}
        seen_key = {(b.title.strip().lower(), b.author.strip().lower()) for b in existing}

        for row in reader:
            title = (row.get("Название") or "").strip()
            author = (row.get("Автор") or "").strip()
            if not title or not author:       # нет названия/автора — пропускаем строку
                skipped += 1
                continue

            isbn = (row.get("ISBN") or "").strip() or None
            clean_isbn = _norm_isbn(isbn)
            key = (title.lower(), author.lower())
            if (clean_isbn and clean_isbn in seen_isbn) or key in seen_key:
                duplicates += 1               # такая книга уже есть — пропускаем
                continue

            rating = None
            raw = (row.get("Моя оценка") or "").strip()
            if raw.isdigit() and 1 <= int(raw) <= 10:
                rating = int(raw)

            read_date = (row.get("Дата прочтения") or "").strip()
            status = "read" if (rating is not None or read_date) else "want"

            session.add(Book(title=title, author=author, rating=rating, status=status, isbn=isbn))
            imported += 1
            if clean_isbn:
                seen_isbn.add(clean_isbn)
            seen_key.add(key)
        session.commit()

    log_event("import", detail=f"imported={imported}; duplicates={duplicates}; skipped={skipped}")
    return {"imported": imported, "duplicates": duplicates, "skipped": skipped}

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
        found = bool(info["raw_metadata"])
        if found:                             # нашли подходящую книгу — обновляем
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
    log_event("enriched", book_id, detail="ok" if found else "miss")
    return book

@router.delete("/books/{book_id}")
def delete_book(book_id: int, lang: str = "ru"):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail=msg("book_not_found", lang))
        title = book.title
        session.delete(book)
        session.commit()
    log_event("book_deleted", book_id, detail=title)
    return {"deleted": book_id}