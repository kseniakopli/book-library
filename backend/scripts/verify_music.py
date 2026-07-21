"""Чистка уже сохранённых музыкальных подборок от несуществующих треков.

С 20.07 музыка проверяется в Spotify при генерации, но подборки, созданные
раньше, могут содержать выдуманные моделью названия («Familiar Ground»
у Ólafur Arnalds). Скрипт проверяет их и переписывает: несуществующее
убирает, у остального ставит канонические названия из Spotify.

Токены AI не тратит — только поиск в Spotify (client credentials).

Запуск из папки backend/:
    python scripts/verify_music.py --dry-run    # только показать, что уберётся
    python scripts/verify_music.py              # применить
    python scripts/verify_music.py --book 42    # одна книга
"""

import json
import sys

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
from sqlmodel import Session, select

import database
from models import AISelection, Book
from services.spotify import verify_songs


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    book_id = None
    if "--book" in args:
        book_id = int(args[args.index("--book") + 1])

    with Session(database.engine) as session:
        query = select(AISelection).where(AISelection.category == "music")
        if book_id is not None:
            query = query.where(AISelection.book_id == book_id)
        rows = session.exec(query).all()

        print(f"Подборок к проверке: {len(rows)}"
              + (" (пробный прогон)" if dry_run else ""))
        total_dropped = 0
        for row in rows:
            try:
                songs = json.loads(row.payload)
            except (TypeError, ValueError):
                continue
            if not songs:
                continue

            verified, dropped = verify_songs(songs)
            if not dropped:
                continue

            book = session.get(Book, row.book_id)
            title = book.title if book else f"книга {row.book_id}"
            print(f"\n{title} ({row.source}): убрано {len(dropped)} из {len(songs)}")
            for item in dropped:
                print(f"    − {item}")
            total_dropped += len(dropped)

            # Защита из з.74: пустым результатом сохранённое не затираем
            if not dry_run and verified:
                row.payload = json.dumps(verified, ensure_ascii=False)
                session.add(row)

        if not dry_run:
            session.commit()
        print(f"\nИтого убрано треков: {total_dropped}"
              + (" (изменения НЕ сохранены)" if dry_run else ""))


if __name__ == "__main__":
    main()
