"""Диагностика: какие треки повторяются в разных книгах (20.07).

Если одна композиция всплывает в большинстве плейлистов — это почти всегда
артефакт резолва, а не вкус модели. Скрипт считает по СОХРАНЁННЫМ музыкальным
подборкам (`AISelection` category=music), в скольких книгах встречается каждый
трек, и показывает самые частые.

Токенов и сети не тратит — читает только базу.

Запуск из папки backend/:
    python scripts/track_frequency.py          # топ повторяющихся треков
    python scripts/track_frequency.py --full    # все треки с частотой > 1
"""

import json
import sys
from collections import defaultdict

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
from sqlmodel import Session, select

import database
from models import AISelection, Book


def main() -> None:
    full = "--full" in sys.argv

    # трек -> множество book_id (чтобы одна книга с двумя источниками не считалась дважды)
    books_by_track: dict[tuple[str, str], set[int]] = defaultdict(set)
    total_books = set()

    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection).where(AISelection.category == "music")
        ).all()
        for row in rows:
            total_books.add(row.book_id)
            try:
                songs = json.loads(row.payload)
            except (TypeError, ValueError):
                continue
            for song in songs:
                key = (song.get("title", "").strip(), song.get("artist", "").strip())
                books_by_track[key].add(row.book_id)

        ranked = sorted(
            books_by_track.items(), key=lambda kv: len(kv[1]), reverse=True
        )

        print(f"Книг с музыкой: {len(total_books)}")
        print("Трек — в скольких книгах:\n")
        shown = 0
        for (title, artist), book_ids in ranked:
            count = len(book_ids)
            if not full and shown >= 15:
                break
            if full and count < 2:
                break
            print(f"  {count:>3}×  {artist} — {title}")
            # для самого частого покажем, в каких книгах — вдруг видна закономерность
            if shown < 3 and count > 1:
                titles = []
                for bid in list(book_ids)[:6]:
                    book = session.get(Book, bid)
                    titles.append(book.title if book else str(bid))
                print(f"        книги: {', '.join(titles)}"
                      + (" …" if count > 6 else ""))
            shown += 1


if __name__ == "__main__":
    main()
