"""Перепроверка музыки, сохранённой при бане Spotify (задача 85).

Когда Spotify в куладауне, музыка сохраняется без резолва: треки не проверены
(могут быть выдумки), плейлиста нет, `AISelection.verified = False`. Этот скрипт
находит такие подборки и, если Spotify снова доступен, перерезолвивает их —
чистит выдумки, ставит канонические названия, собирает плейлист.

Проверить, что бан снят: python scripts/spotify_status.py

Запуск из папки backend/:
    python scripts/reverify_music.py --dry-run   # что перепроверится
    python scripts/reverify_music.py             # перепроверить всё
"""

import asyncio
import sys

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
from sqlmodel import Session, select

import database
import services.spotify as spotify_service
from models import AISelection, Book
from services.ai import MusicResult, Song
from services.atmosphere import CATEGORIES, verify_music_results, replace_selections


def _pending_book_ids(session) -> list[int]:
    rows = session.exec(
        select(AISelection.book_id).where(
            AISelection.category == "music", AISelection.verified == False  # noqa: E712
        )
    ).all()
    return sorted(set(rows))


async def main() -> None:
    dry = "--dry-run" in sys.argv

    if not spotify_service.available():
        print("Spotify недоступен (бан/нет ключей) — перепроверять нечем. "
              "Проверьте: python scripts/spotify_status.py")
        return

    with Session(database.engine) as session:
        book_ids = _pending_book_ids(session)
        titles = {
            b.id: (b.title, b.author)
            for b in session.exec(select(Book).where(Book.id.in_(book_ids))).all()
        }

    print(f"Непроверенной музыки: {len(book_ids)} книг"
          + (" (пробный прогон)" if dry else ""))
    for bid in book_ids:
        print(f"  book {bid}: {titles.get(bid, ('?',))[0]}")
    if dry or not book_ids:
        return

    cfg = CATEGORIES["music"]
    print("\nПерепроверяю…")
    for bid in book_ids:
        title, _ = titles.get(bid, (None, None))
        if not title:
            continue
        # восстанавливаем результат из сохранённого payload (без нового AI-вызова)
        with Session(database.engine) as session:
            rows = session.exec(
                select(AISelection).where(
                    AISelection.book_id == bid, AISelection.category == "music"
                )
            ).all()
            results = {
                row.source: MusicResult(
                    songs=[Song(**s) for s in _load(row.payload)],
                    explanation=row.explanation,
                )
                for row in rows
            }

        # тот же путь, что при генерации: резолв + плейлист, но без токенов AI
        results = await verify_music_results(results, bid, title)
        if spotify_service.available():
            replace_selections(bid, "music", cfg, results, verified=True)
            print(f"  ✓ book {bid} · {title}")
        else:
            print(f"  ⏸ Spotify ушёл в куладаун — останавливаюсь")
            break
    print("Готово.")


def _load(payload: str) -> list[dict]:
    import json
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return []


if __name__ == "__main__":
    asyncio.run(main())
