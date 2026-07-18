# Разовое восстановление атмосферы (инцидент 18.07): ранние прогоны миграции
# 0005 каскадом снесли music/food/aroma у части книг (design сам восстановился
# при открытии, остальное — нет). Скрипт находит книги, где категория когда-то
# генерировалась (по событийному логу), но строк сейчас нет, и генерирует заново.
#
# Запуск из backend/ (нужны .env с AI-ключами и prompt_config.py):
#   python backfill_atmosphere.py            # восстановить всё недостающее
#   python backfill_atmosphere.py --dry-run  # только показать список, без вызовов AI
#
# Тратит токены: ~ (число книг × 3 категории × 2 AI). Идёт по одной книге.
import asyncio
import sys

from sqlmodel import Session, select

import database
from events import Event
from models import AISelection, Book
from routers.atmosphere import CATEGORIES, _replace_selections

CATS = ["music", "food", "aroma"]


def _targets(session) -> dict[int, set[str]]:
    """{book_id: {категории, которые генерировались ранее, но сейчас пусты}}."""
    result: dict[int, set[str]] = {}
    for cat in CATS:
        # выбор одной колонки в SQLModel даёт скаляры (id), а не кортежи
        ever = set(session.exec(
            select(Event.book_id).where(
                Event.type == f"ai_{cat}_generated", Event.book_id.is_not(None)
            )
        ).all())
        now = set(session.exec(
            select(AISelection.book_id).where(AISelection.category == cat)
        ).all())
        for bid in ever - now:
            result.setdefault(bid, set()).add(cat)
    return result


async def main():
    dry = "--dry-run" in sys.argv
    with Session(database.engine) as session:
        targets = _targets(session)
        titles = {
            b.id: (b.title, b.author)
            for b in session.exec(select(Book).where(Book.id.in_(targets))).all()
        }

    print(f"Книг к восстановлению: {len(targets)}")
    for bid, cats in sorted(targets.items()):
        title, author = titles.get(bid, ("(нет книги)", ""))
        print(f"  book {bid}: {title} — категории: {', '.join(sorted(cats))}")
    if dry:
        print("\n--dry-run: AI не вызывался, база не менялась.")
        return
    if not targets:
        return

    print("\nГенерирую…")
    for bid, cats in sorted(targets.items()):
        title, author = titles.get(bid, (None, None))
        if not title:
            continue
        for cat in sorted(cats):
            cfg = CATEGORIES[cat]
            results = await cfg["generate"](title, author, "ru")
            _replace_selections(bid, cat, cfg, results)   # с защитой: пустое не пишет
            print(f"  ✓ book {bid} · {cat}")
    print("Готово.")


if __name__ == "__main__":
    asyncio.run(main())
