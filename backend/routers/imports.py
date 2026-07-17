# Массовые операции: импорт CSV и дозаполнение старых книг (backfill).
import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, col, select

import database
from constants import EVENT_IMPORT, STATUS_READ, STATUS_WANT
from dates import parse_read_date
from deps import get_lang
from events import log_event
from google_books import fetch_book_info, search_books
from i18n import msg
from models import Book
from services.enrichment import apply_enrichment

router = APIRouter(tags=["import"])

MAX_IMPORT_BYTES = 2 * 1024 * 1024   # лимит CSV-файла: 2 МБ (задача 38)
MAX_IMPORT_ROWS = 2000               # лимит строк за один импорт


def _norm_isbn(value):
    """ISBN без дефисов и пробелов — для сравнения/дедупликации."""
    return value.replace("-", "").replace(" ", "") if value else None


@router.post("/import")
async def import_csv(file: UploadFile = File(...), lang: str = Depends(get_lang)):
    content = await file.read(MAX_IMPORT_BYTES + 1)   # читаем на байт больше лимита
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=400, detail=msg("import_too_large", lang))
    try:
        text = content.decode("utf-8-sig")    # utf-8-sig убирает BOM, если он есть
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail=msg("import_bad_encoding", lang))
    if text.count("\n") > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=400, detail=msg("import_too_many_rows", lang))
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
            status = STATUS_READ if (rating is not None or read_date) else STATUS_WANT
            # задача 1: гибкий разбор даты («Июль 2026 г.», ISO, дд.мм.гггг);
            # не разобрали — книга прочитана, но без даты
            read_at = parse_read_date(read_date) if status == STATUS_READ else None

            session.add(Book(
                title=title, author=author, rating=rating,
                status=status, isbn=isbn, read_at=read_at,
            ))
            imported += 1
            if clean_isbn:
                seen_isbn.add(clean_isbn)
            seen_key.add(key)
        session.commit()

    log_event(EVENT_IMPORT, detail=f"imported={imported}; duplicates={duplicates}; skipped={skipped}")
    return {"imported": imported, "duplicates": duplicates, "skipped": skipped}


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


@router.post("/books/backfill-metadata")
def backfill_metadata(limit: int = 40, lang: str = Depends(get_lang)):
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
            apply_enrichment(book, info)
            session.add(book)
            updated += 1
        session.commit()
        remaining = len(session.exec(
            select(Book).where(col(Book.raw_metadata).is_(None))
        ).all())
    return {"updated": updated, "remaining": remaining}
