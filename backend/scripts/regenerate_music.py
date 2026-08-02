"""Пересборка музыки пачкой книг — замер разнообразия (з.99, 02.08).

Зачем скрипт, а не кнопка: чтобы измерить эффект правок, нужна выборка
хотя бы в десяток книг, а кликать по одной долго и легко сбиться, какие
именно перегенерированы.

Повторяет ровно путь эндпоинта POST /books/{id}/atmosphere/music:
build_book_context → generate_music → verify_music_results → replace_selections.
Batch API здесь не подходит: музыка идёт через ОБА провайдера, проверяется
в Spotify и тянет за собой пересборку плейлиста — это не один вызов модели.

⚠ КНИГИ ВИТРИНЫ ИСКЛЮЧАЮТСЯ ВСЕГДА. Флага «включить» нет намеренно:
их плейлисты закодированы в QR печатного тиража 28.07, и подмена содержимого
у них — отдельное осознанное действие, а не побочный эффект замера.

⚠ Квота Spotify считается НА ПРИЛОЖЕНИЕ, и массовая пересборка 21.07 стоила
бана на 21 час. Поэтому: книги идут последовательно, между ними пауза,
и есть --limit. Кэш TrackCache общий, поэтому повторные прогоны дешевле первого.

Запуск из backend/:
    python scripts/regenerate_music.py --limit=10 --dry-run
    python scripts/regenerate_music.py --limit=10
    python scripts/regenerate_music.py --limit=10 --pause=10
"""

import asyncio
import sys

from dotenv import load_dotenv

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
import services.spotify as spotify_service
from events import log_event
from models import Book, UserBook
from services.ai import start_ai_metrics, take_ai_metrics
from services.atmosphere import CATEGORIES, replace_selections
from services.prompt_context import build_book_context
from sqlmodel import Session, select

load_dotenv()

DRY = "--dry-run" in sys.argv
LIMIT = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--limit=")), 10))
PAUSE = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--pause=")), 5))
# Владелец: генерация admin-действие, и профиль вкуса берётся по пользователю.
USER_ID = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--user=")), 1))


def _targets(session) -> list[Book]:
    featured = set(
        session.exec(select(UserBook.book_id).where(UserBook.featured.is_(True))).all()
    )
    from models import AISelection

    have_music = set(
        session.exec(
            select(AISelection.book_id).where(AISelection.category == "music")
        ).all()
    )
    books = [
        b for b in session.exec(select(Book)).all()
        if b.id in have_music and b.id not in featured
    ]
    books.sort(key=lambda b: b.id)
    return books[:LIMIT]


async def regenerate(book_id: int, title: str, author: str) -> int:
    """Одна книга. Возвращает число сохранённых треков (по всем источникам)."""
    cfg = CATEGORIES["music"]
    with Session(database.engine) as session:
        context = build_book_context(session, book_id, "music", USER_ID)

    start_ai_metrics()
    results = await cfg["generate"](title, author, "ru", context)
    results = await cfg["postprocess"](results, book_id, title)

    verified = spotify_service.available()
    replace_selections(book_id, "music", cfg, results, verified=verified)
    log_event(cfg["event"], book_id, detail={
        "trigger": "script:regenerate_music",
        "ai_calls": take_ai_metrics(),
    })
    return sum(len(r.songs) for r in results.values())


async def main():
    with Session(database.engine) as session:
        targets = [(b.id, b.title, b.author) for b in _targets(session)]

    print(f"К пересборке: {len(targets)} книг (лимит {LIMIT}), витринные исключены.")
    for book_id, title, _ in targets:
        print(f"  {book_id}: {title}")
    if DRY:
        print("\n--dry-run: ничего не генерировалось.")
        return
    if not targets:
        return

    print(f"\nПауза между книгами: {PAUSE} с. Прерывание — Ctrl+C.\n")
    done = failed = 0
    for i, (book_id, title, author) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {book_id}: {title}")
        try:
            saved = await regenerate(book_id, title, author)
            print(f"    сохранено треков: {saved}")
            done += 1
        except Exception as e:                     # noqa: BLE001 — прогон не должен падать целиком
            print(f"    ОШИБКА: {type(e).__name__}: {e}")
            failed += 1
        if i < len(targets):
            await asyncio.sleep(PAUSE)

    print(f"\nГотово. Успешно: {done}, с ошибкой: {failed}.")
    print("Замер: python scripts/explore_avoid.py --category=music")


if __name__ == "__main__":
    asyncio.run(main())
