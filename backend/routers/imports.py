# Массовые операции: импорт CSV и дозаполнение старых книг (backfill).
import csv
import io

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import defer
from sqlmodel import Session, col, func, select

import database
from constants import ENRICH_PENDING, EVENT_BACKFILL, EVENT_IMPORT, STATUS_READ, STATUS_WANT
from dates import parse_read_date
from deps import CURRENT_USER_ID, get_lang, require_admin
from events import log_event
from google_books import search_books
from i18n import msg
from models import Book, UserBook
from services.ai import map_csv_columns, start_ai_metrics, take_ai_metrics
from services.enrichment import backfill_in_background

router = APIRouter(tags=["import"])

MAX_IMPORT_BYTES = 2 * 1024 * 1024   # лимит CSV-файла: 2 МБ (задача 38)
MAX_IMPORT_ROWS = 2000               # лимит строк за один импорт

# Стандартные заголовки (LiveLib и наш экспорт) — распознаются без AI
STANDARD_COLUMNS = {
    "title": "Название",
    "author": "Автор",
    "rating": "Моя оценка",
    "read_date": "Дата прочтения",
    "isbn": "ISBN",
}
SAMPLE_ROWS = 3          # столько строк-примеров показываем модели
SAMPLE_CELL_CHARS = 80   # длинные ячейки обрезаем — модели хватит начала


def _norm_isbn(value):
    """ISBN без дефисов и пробелов — для сравнения/дедупликации."""
    return value.replace("-", "").replace(" ", "") if value else None


async def _resolve_columns(fieldnames: list[str], rows: list[dict], lang: str) -> tuple[dict, bool]:
    """Роль → имя колонки. Стандартные заголовки — эвристикой; незнакомые —
    моделью (задача 28, structured output). Возвращает (маппинг, использован_ли_AI).
    Имена от модели проверяем по реальным заголовкам: выдуманную колонку
    молча превращать в пустые значения нельзя."""
    if STANDARD_COLUMNS["title"] in fieldnames and STANDARD_COLUMNS["author"] in fieldnames:
        return STANDARD_COLUMNS, False

    sample = [
        {k: (v or "")[:SAMPLE_CELL_CHARS] for k, v in row.items() if k}
        for row in rows[:SAMPLE_ROWS]
    ]
    try:
        mapping = await map_csv_columns(fieldnames, sample, lang)
    except Exception as e:
        print("AI-маппинг колонок не удался:", e)
        raise HTTPException(status_code=400, detail=msg("import_unknown_columns", lang))

    if mapping.title_column not in fieldnames or mapping.author_column not in fieldnames:
        raise HTTPException(status_code=400, detail=msg("import_unknown_columns", lang))
    optional = {
        role: name
        for role, name in {
            "rating": mapping.rating_column,
            "read_date": mapping.read_date_column,
            "isbn": mapping.isbn_column,
        }.items()
        if name in fieldnames   # None и выдуманные имена отбрасываем
    }
    return {"title": mapping.title_column, "author": mapping.author_column, **optional}, True


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
    # Разделитель: LiveLib отдаёт CSV с ';', обычные выгрузки — с ','. Определяем
    # по заголовку — какого символа больше, тот и разделитель.
    header = text.splitlines()[0] if text else ""
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)

    # Задача 28: роли колонок. LiveLib-заголовки — без AI; незнакомые — моделью.
    start_ai_metrics()
    cols, ai_mapped = await _resolve_columns(reader.fieldnames or [], rows, lang)

    def cell(row: dict, role: str) -> str:
        name = cols.get(role)
        return (row.get(name) or "").strip() if name else ""

    imported = 0
    skipped = 0
    duplicates = 0
    with Session(database.engine) as session:
        # каталог книг: (нормализованный ключ) → book_id, чтобы переиспользовать книгу
        # (и её атмосферу), а не заводить дубль. Задача 52: без raw_metadata.
        existing = session.exec(select(Book.id, Book.title, Book.author, Book.isbn)).all()
        book_by_isbn = {_norm_isbn(isbn): bid for bid, _, _, isbn in existing if isbn}
        book_by_key = {(t.strip().lower(), a.strip().lower()): bid for bid, t, a, _ in existing}
        # книги, уже лежащие на полке пользователя — их пропускаем как дубли
        shelf_ids = set(session.exec(
            select(UserBook.book_id).where(UserBook.user_id == CURRENT_USER_ID)
        ).all())

        for row in rows:
            title = cell(row, "title")
            author = cell(row, "author")
            if not title or not author:       # нет названия/автора — пропускаем строку
                skipped += 1
                continue

            isbn = cell(row, "isbn") or None
            clean_isbn = _norm_isbn(isbn)
            key = (title.lower(), author.lower())

            # книга уже известна системе?
            book_id = (clean_isbn and book_by_isbn.get(clean_isbn)) or book_by_key.get(key)
            if book_id and book_id in shelf_ids:
                duplicates += 1               # уже на полке пользователя — пропускаем
                continue

            rating = None
            raw = cell(row, "rating")
            if raw.isdigit() and 1 <= int(raw) <= 10:
                rating = int(raw)

            read_date = cell(row, "read_date")
            status = STATUS_READ if (rating is not None or read_date) else STATUS_WANT
            # задача 1: гибкий разбор даты («Июль 2026 г.», ISO, дд.мм.гггг);
            # не разобрали — книга прочитана, но без даты
            read_at = parse_read_date(read_date) if status == STATUS_READ else None

            if not book_id:                   # новой книги ещё нет — заводим в каталоге
                book = Book(title=title, author=author, isbn=isbn)
                session.add(book)
                session.flush()               # нужен book.id до создания UserBook
                book_id = book.id
                book_by_key[key] = book_id
                if clean_isbn:
                    book_by_isbn[clean_isbn] = book_id

            # кладём на полку пользователя с личными полями из CSV
            session.add(UserBook(
                user_id=CURRENT_USER_ID, book_id=book_id,
                status=status, rating=rating, read_at=read_at,
            ))
            imported += 1
            shelf_ids.add(book_id)
        session.commit()

    detail = {"imported": imported, "duplicates": duplicates, "skipped": skipped}
    if ai_mapped:   # задача 28: чем распознали колонки + цена вызова (з.80)
        detail["ai_mapping"] = {role: name for role, name in cols.items()}
        detail["ai_calls"] = take_ai_metrics()
    log_event(EVENT_IMPORT, detail=detail)
    return {"imported": imported, "duplicates": duplicates, "skipped": skipped}


@router.post("/books/backfill-covers")
def backfill_covers(lang: str = Depends(get_lang)):
    """Массовая операция над общим каталогом → только admin (план деплоя п.1.3):
    на проде эндпоинт не должен быть доступен любому тестеру."""
    updated = 0
    with Session(database.engine) as session:
        require_admin(session, lang)
        books = session.exec(
            # задача 52: raw_metadata здесь не нужен — не грузим
            select(Book)
            .options(defer(Book.raw_metadata))
            .where(col(Book.cover_url).is_(None))
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
def backfill_metadata(
    background_tasks: BackgroundTasks,
    limit: int = 40,
    lang: str = Depends(get_lang),
):
    """Задача 12: дозаполнение старых книг метаданными — В ФОНЕ.
    Ответ мгновенный; партия помечается pending, фронт поллит счётчик,
    и обложки/жанры «проявляются» по мере обогащения.
    Массовая операция над общим каталогом → только admin (план деплоя п.1.3)."""
    with Session(database.engine) as session:
        require_admin(session, lang)
        # порция книг без метаданных (raw_metadata пуст)
        books = session.exec(
            select(Book).where(col(Book.raw_metadata).is_(None)).limit(limit)
        ).all()
        ids = [book.id for book in books]
        for book in books:
            book.enrich_status = ENRICH_PENDING
            session.add(book)
        session.commit()

        # задача 53: SQL COUNT вместо загрузки всех строк ради числа
        total_without = session.exec(
            select(func.count())
            .select_from(Book)
            .where(col(Book.raw_metadata).is_(None))
        ).one()

    if ids:
        background_tasks.add_task(backfill_in_background, ids, lang)
        log_event(EVENT_BACKFILL, detail={"scheduled": len(ids)})
    return {"scheduled": len(ids), "remaining": total_without - len(ids)}
