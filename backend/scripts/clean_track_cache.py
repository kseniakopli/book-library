"""Чистка кэша резолва треков (задача 82 / инцидент 22.07).

Во время бана Spotify и шквала 429 существующие треки могли закэшироваться как
«не найдено» (`found=False`) — потому что Spotify не отвечал, а не потому что
трека нет. Такой ложный негатив держится вечно и выбрасывает реальные треки
(например, Woodkid — Run Boy Run).

По умолчанию удаляет ТОЛЬКО отрицательные записи (`found=False`) — положительные
(канонические названия+uri) верны, их сохраняем. После чистки ложные негативы
перерезолвятся при следующей генерации (уже с новой логикой: сбой Spotify
не кэшируется).

Запуск из папки backend/:
    python scripts/clean_track_cache.py --dry-run   # сколько записей
    python scripts/clean_track_cache.py             # удалить негатив
    python scripts/clean_track_cache.py --all       # весь кэш (и положительный)
"""

import sys

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
from sqlmodel import Session, select

import database
from models import TrackCache


def main() -> None:
    args = sys.argv[1:]
    dry = "--dry-run" in args
    wipe_all = "--all" in args

    with Session(database.engine) as session:
        query = select(TrackCache)
        if not wipe_all:
            query = query.where(TrackCache.found == False)  # noqa: E712
        rows = session.exec(query).all()

        kind = "всех записей" if wipe_all else "отрицательных записей (found=False)"
        print(f"Кэш треков: {kind} к удалению — {len(rows)}"
              + (" (пробный прогон)" if dry else ""))
        if dry or not rows:
            return

        for row in rows:
            session.delete(row)
        session.commit()
        print(f"Удалено: {len(rows)}. Треки перерезолвятся при генерации музыки.")


if __name__ == "__main__":
    main()
