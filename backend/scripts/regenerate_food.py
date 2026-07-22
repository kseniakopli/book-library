"""Перегенерация угощений для книг, у которых еда уже есть (22.07).

Зачем: промпт еды и модель Claude сменились (Haiku + температура + новый
промпт) — старые подборки хочется обновить массово, не открывая каждую книгу.

В отличие от `backfill_atmosphere.py` (генерит НЕДОСТАЮЩЕЕ), этот скрипт
ЗАМЕНЯЕТ уже существующую еду. Защита з.74 сохраняется: если генерация вернула
пустое (AI не ответил), старая подборка не затирается.

Тратит токены: на каждую книгу — 2 запроса (Claude Haiku + OpenAI). Haiku
дешёвый, но книг может быть много — есть `--limit` и `--dry-run`.

⚠ Перед прогоном: python scripts/backup_db.py

Запуск из папки backend/:
    python scripts/regenerate_food.py --dry-run      # сколько книг, без вызовов AI
    python scripts/regenerate_food.py --limit 10     # первые 10 (проба)
    python scripts/regenerate_food.py                # все, у кого еда есть
    python scripts/regenerate_food.py --book 200     # одна книга
    python scripts/regenerate_food.py --category aroma  # то же для ароматов
"""

import asyncio
import sys

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
from sqlmodel import Session, select

import database
from events import log_event
from models import AISelection, Book
from services.atmosphere import CATEGORIES, replace_selections


async def main() -> None:
    args = sys.argv[1:]
    dry = "--dry-run" in args
    category = args[args.index("--category") + 1] if "--category" in args else "food"
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    book_id = int(args[args.index("--book") + 1]) if "--book" in args else None

    if category not in CATEGORIES:
        print(f"Неизвестная категория: {category}. Есть: {', '.join(CATEGORIES)}")
        return

    with Session(database.engine) as session:
        # книги, у которых для этой категории УЖЕ есть подборка
        query = select(AISelection.book_id).where(AISelection.category == category)
        if book_id is not None:
            query = query.where(AISelection.book_id == book_id)
        book_ids = sorted(set(session.exec(query).all()))
        if limit is not None:
            book_ids = book_ids[:limit]

        titles = {
            b.id: (b.title, b.author)
            for b in session.exec(select(Book).where(Book.id.in_(book_ids))).all()
        }

    print(f"Категория: {category} | книг к перегенерации: {len(book_ids)}"
          + (" (пробный прогон)" if dry else ""))
    for bid in book_ids:
        title, _ = titles.get(bid, ("(нет книги)", ""))
        print(f"  book {bid}: {title}")
    if dry:
        print("\n--dry-run: AI не вызывался, база не менялась.")
        return
    if not book_ids:
        return

    cfg = CATEGORIES[category]
    print("\nГенерирую…")
    ok = failed = 0
    for bid in book_ids:
        title, author = titles.get(bid, (None, None))
        if not title:
            continue
        try:
            results = await cfg["generate"](title, author, "ru")
            replace_selections(bid, category, cfg, results)  # пустое не затирает
            log_event(cfg["event"], bid, detail={"trigger": "regenerate"})
            print(f"  ✓ book {bid} · {title}")
            ok += 1
        except Exception as e:
            print(f"  ✗ book {bid} · {title}: {e}")
            failed += 1
    print(f"\nГотово. Обновлено: {ok}, ошибок: {failed}.")


if __name__ == "__main__":
    asyncio.run(main())
