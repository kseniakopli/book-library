"""Диагностика поиска треков в Spotify (инцидент 20.07: половина плейлиста
уходила в «не найдено»).

Показывает по каждому треку: что вернул Spotify, какой кандидат прошёл проверку
`_matches` и почему остальные отклонены. Токены AI не тратит — только Spotify.

Запуск из папки backend/:
    python scripts/check_track_search.py "Ólafur Arnalds" "Familiar Ground"
    python scripts/check_track_search.py --book 42     # все треки книги
"""

import sys

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import services.spotify as sp


def check(artist: str, title: str) -> None:
    headers = {"Authorization": f"Bearer {sp._access_token()}"}
    print(f"\n=== {artist} — {title}")
    for query in (f"track:{title} artist:{artist}", f"{artist} {title}"):
        items = sp._search_request(headers, query)
        print(f"  запрос {query!r} → кандидатов: {len(items)}")
        for item in items:
            performers = ", ".join(a["name"] for a in item.get("artists", []))
            verdict = "✓ ПОДХОДИТ" if sp._matches(item, title, artist) else "✗ отклонён"
            t_ratio = sp._similar(item.get("name", ""), title)
            a_ratio = max(
                (sp._similar(a.get("name", ""), artist) for a in item.get("artists", [])),
                default=0,
            )
            print(
                f"    {verdict}: «{item.get('name')}» — {performers} "
                f"(название {t_ratio:.2f}, исполнитель {a_ratio:.2f})"
            )
        if any(sp._matches(i, title, artist) for i in items):
            return
    print("  → трек не найден ни одним запросом")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    if args[0] == "--book":
        import json

        from sqlmodel import Session, select

        import database
        from models import AISelection

        with Session(database.engine) as session:
            rows = session.exec(
                select(AISelection).where(
                    AISelection.book_id == int(args[1]),
                    AISelection.category == "music",
                )
            ).all()
        songs = []
        for row in rows:
            songs.extend(json.loads(row.payload))
        songs = sp.dedupe_songs(songs)
        print(f"Треков в атмосфере книги: {len(songs)}")
        for song in songs:
            check(song["artist"], song["title"])
        return

    check(args[0], args[1])


if __name__ == "__main__":
    main()
