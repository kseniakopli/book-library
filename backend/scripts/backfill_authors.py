"""Заполнение таблицы авторов из строк `Book.author` (задача 97).

Разбор и правила тождества живут в `services/authors.py` — теми же правилами
будут пользоваться добавление книги и импорт. Здесь только проход по базе,
отчёт и запись.

Идемпотентен: авторы ищутся по нормализованному ключу, связи — по паре
(книга, автор). Повторный запуск ничего не дублирует.

Запуск из папки backend/:
    python scripts/backfill_authors.py --dry-run   # показать, что получится
    python scripts/backfill_authors.py             # записать
    python scripts/backfill_authors.py --show      # что уже в базе

⚠ Перед записью: python scripts/backup_db.py
"""

import sys
from collections import defaultdict

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from models import Author, Book, BookAuthor
from services.authors import (
    EXCEPTIONS,
    ORIGINAL_NAMES,
    display_name,
    link_book,
    norm_key,
    split_authors,
)
from sqlmodel import Session, select

DRY_RUN = "--dry-run" in sys.argv
SHOW = "--show" in sys.argv


def show() -> None:
    with Session(database.engine) as session:
        authors = session.exec(select(Author)).all()
        links = session.exec(select(BookAuthor)).all()

    print(f"Авторов: {len(authors)}   связей книга↔автор: {len(links)}")
    counts = defaultdict(int)
    for link in links:
        counts[link.author_id] += 1

    print("\n--- чаще всего на полке ---")
    for author in sorted(authors, key=lambda a: -counts[a.id])[:15]:
        original = (
            f"  ({author.name_original})"
            if author.name_original and author.name_ru
            else ""
        )
        print(f"{counts[author.id]:>3}  {display_name(author)}{original}")


def plan(books: list[Book]) -> tuple[set[str], int, list[int]]:
    """Что получится, ничего не записывая: ключи новых авторов, число связей,
    книги без автора."""
    keys: set[str] = set()
    links = 0
    skipped: list[int] = []
    for book in books:
        names = split_authors(book.author)
        if not names:
            skipped.append(book.id)
            continue
        for name in names:
            keys.add(norm_key(name))
        links += len(names)
    return keys, links, skipped


def report(books: list[Book]) -> None:
    """Проверка глазами: сработали ли ручные исключения на реальных данных.
    Если строка помечена «не встретилась» — либо её поправили в базе, либо
    в исключении опечатка."""
    print("\n--- разобранные исключения ---")
    for raw, parts in EXCEPTIONS.items():
        used = any((b.author or "").strip() == raw for b in books)
        mark = "✓" if used else "⚠ в базе не встретилась"
        print(f"{mark}  «{raw}» → {', '.join(parts)}")

    print("\n--- имена латиницей ---")
    for original, russian in ORIGINAL_NAMES.items():
        used = any(original in (b.author or "") for b in books)
        mark = "✓" if used else "⚠ в базе не встретилась"
        print(f"{mark}  {original} → {russian} ({original})")


def main() -> None:
    if SHOW:
        show()
        return

    with Session(database.engine) as session:
        books = session.exec(select(Book)).all()
        known = {a.sort_key for a in session.exec(select(Author)).all()}

        keys, links, skipped = plan(books)
        print(f"Книг просмотрено:  {len(books)}")
        print(f"Авторов всего:     {len(keys)}  (новых: {len(keys - known)})")
        print(f"Связей книга↔автор: {links}")
        if skipped:
            print(f"⚠ Без автора, пропущены: {len(skipped)} книг {skipped[:10]}")

        report(books)

        if DRY_RUN:
            print("\nСухой прогон: в базу ничего не записано.")
            return

        for book in books:
            link_book(session, book.id, book.author)
        session.commit()

    print("\nГотово. Проверить: python scripts/backfill_authors.py --show")


if __name__ == "__main__":
    main()
