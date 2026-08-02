"""Точечный перенос подборок AI между базами: музыка, паспорта оформления (02.08).

⚠ Имя файла историческое — скрипт начинался с музыки. Категория задаётся
флагом `--category=`; для паспортов это `design`.

ПРОБЛЕМА, ради которой написан. Прод и дев ходят в ОДИН сервисный аккаунт
Spotify (`nctrnlib`), а плейлисты пересобираются по месту —
`replace_playlist_items` меняет содержимое, ссылка остаётся прежней. Значит
любая локальная перегенерация музыки молча переписывает плейлисты, на которые
ссылается ПРОД: на странице книги там остаётся старый список треков, а в
встроенном плеере уже новый. Расхождение видно только глазами.

Почему не подмена базы целиком (как 28.07): на проде живут 3 пользователя,
5 инвайтов и 1210 событий витрины (з.96) — подмена стёрла бы их. Плюс
`layout-audit.mjs` проставляет `featured` в локальной базе, и состав витрины
уехал бы на прод сам собой, а витрина связана с печатным тиражом.

Для ПАСПОРТОВ (`--category=design`) причина другая, но следствие то же:
пересборка идёт локально (`backfill_passports.py`), а прод остаётся со старым
оформлением. Общего внешнего ресурса тут нет, поэтому «молча» ничего
не ломается — просто дев и прод показывают разные книги.

Переносятся ТОЛЬКО строки AISelection выбранной категории (и ссылка
на плейлист книги — для музыки). Пользователи, события, инвайты, витрина
и прочие категории не трогаются.

--- Как пользоваться ---

Локально (выгрузка изменённого):
    python scripts/sync_music_to_prod.py --export --since=2026-08-02
    python scripts/sync_music_to_prod.py --export --since=2026-08-02 --category=design
    → music_sync.json / design_sync.json

Залить файл на прод (из КОРНЯ репозитория):
    fly ssh sftp shell
    put backend/design_sync.json /data/design_sync.json

На проде:
    fly ssh console
    cd /app/backend
    python scripts/sync_music_to_prod.py --import=/data/design_sync.json --dry-run
    python scripts/sync_music_to_prod.py --import=/data/design_sync.json

⚠ Сопоставление идёт по book_id. Базы разошлись по идентификаторам —
перенос делать нельзя; скрипт сверяет ещё и название книги и ругается
на несовпадения, не применяя их.

⚠ Витринные книги в выгрузку не попадут сами собой: их паспорта не
пересобирались (исключены в `backfill_passports.py`), значит и `created_at`
у них старый, а фильтр `--since` их отсечёт. Проверить это глазами
в списке выгрузки — их палитры ушли в печатный тираж.
"""

import json
import sys
from datetime import datetime

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from models import AISelection, Book
from sqlmodel import Session, select

EXPORT = "--export" in sys.argv
IMPORT_PATH = next(
    (a.split("=", 1)[1] for a in sys.argv if a.startswith("--import=")), None
)
SINCE = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--since=")), None)
DRY = "--dry-run" in sys.argv
CATEGORY = next(
    (a.split("=", 1)[1] for a in sys.argv if a.startswith("--category=")), "music"
)
OUT = f"{CATEGORY}_sync.json"


def do_export() -> None:
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection).where(AISelection.category == CATEGORY)
        ).all()
        if SINCE:
            rows = [
                r for r in rows
                if r.created_at and r.created_at.date().isoformat() >= SINCE
            ]
        books = {b.id: b for b in session.exec(select(Book)).all()}

        payload = []
        for row in rows:
            book = books.get(row.book_id)
            if book is None:
                continue
            payload.append({
                "book_id": row.book_id,
                "book_title": book.title,          # страховка от расхождения id
                "category": CATEGORY,
                "source": row.source,
                "payload": row.payload,
                "explanation": row.explanation,
                "analysis": row.analysis,
                "verified": row.verified,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                # Ссылка на плейлист — только для музыки: у паспортов её нет,
                # и перезаписывать её пустым значением на проде нельзя.
                "spotify_playlist_url": (
                    book.spotify_playlist_url if CATEGORY == "music" else None
                ),
            })

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    books_touched = {p["book_id"] for p in payload}
    print(f"Выгружено строк: {len(payload)} по {len(books_touched)} книгам → {OUT}")
    if SINCE:
        print(f"Фильтр: created_at >= {SINCE}")
    for book_id in sorted(books_touched):
        title = next(p["book_title"] for p in payload if p["book_id"] == book_id)
        print(f"  {book_id}: {title}")


def do_import(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        items = json.load(f)

    applied = skipped = mismatched = 0
    with Session(database.engine) as session:
        for item in items:
            book = session.get(Book, item["book_id"])
            if book is None:
                print(f"  ПРОПУСК: книги {item['book_id']} здесь нет")
                skipped += 1
                continue
            # Названия должны совпасть — иначе базы разъехались по id и перенос
            # положил бы чужую музыку в чужую книгу.
            if book.title.strip() != item["book_title"].strip():
                print(
                    f"  НЕСОВПАДЕНИЕ id {item['book_id']}: "
                    f"здесь «{book.title}», в файле «{item['book_title']}»"
                )
                mismatched += 1
                continue

            # Категорию берём ИЗ ФАЙЛА, а не из флага командной строки:
            # иначе файл паспортов, импортированный без `--category=design`,
            # молча лёг бы в музыку.
            category = item.get("category", "music")

            existing = session.exec(
                select(AISelection).where(
                    AISelection.book_id == item["book_id"],
                    AISelection.category == category,
                    AISelection.source == item["source"],
                )
            ).first()

            print(f"  {item['book_id']} / {item['source']}: «{book.title}»")
            if DRY:
                applied += 1
                continue

            if existing is not None:
                session.delete(existing)
                session.flush()   # DELETE до INSERT — уникальный индекс
            session.add(AISelection(
                book_id=item["book_id"],
                category=category,
                source=item["source"],
                payload=item["payload"],
                explanation=item["explanation"],
                analysis=item.get("analysis", ""),
                verified=item.get("verified", True),
                created_at=(
                    datetime.fromisoformat(item["created_at"])
                    if item.get("created_at") else datetime.now()
                ),
            ))
            # Ссылка на плейлист: у книги её могло не быть вовсе (плейлист
            # создался при локальной генерации). Существующую НЕ перетираем
            # пустым значением.
            if item.get("spotify_playlist_url"):
                book.spotify_playlist_url = item["spotify_playlist_url"]
                session.add(book)
            applied += 1

        if not DRY:
            session.commit()

    print(
        f"\n{'[dry-run] ' if DRY else ''}Применено: {applied}, "
        f"пропущено: {skipped}, несовпадений: {mismatched}."
    )
    if mismatched:
        print("⚠ Несовпадения НЕ применялись — сверь базы по id, прежде чем повторять.")


def main() -> None:
    if EXPORT:
        do_export()
    elif IMPORT_PATH:
        do_import(IMPORT_PATH)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
