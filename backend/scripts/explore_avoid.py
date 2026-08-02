"""Почему молчит механизм `avoid` (з.99, разбор 02.08).

Вопрос: `_overused_items` в `services/prompt_context.py` должен класть в промпт
самое затасканное по библиотеке, но «Dead Can Dance — The Host of Seraphim»
всё равно в каждом втором плейлисте. Механизм ЕСТЬ — значит вопрос не «сделать
защиту», а «почему существующая не срабатывает».

Скрипт не догадывается, а показывает три вещи по каждой категории:
  1. что реально лежит в payload (форма данных: список? словарь? какие ключи);
  2. сколько книг у самых частых пунктов — БЕЗ порога AVOID_MIN_BOOKS,
     чтобы увидеть, ловит ли счётчик повторы вообще;
  3. что в итоге возвращает сам `_overused_items` — то есть что уедет в промпт.

Если 2 показывает повторы, а 3 пустой — виноват порог или ключ.
Если 2 тоже пустой — счётчик не видит данные, дело в разборе payload.
Если 3 непустой — механизм работает, и искать надо в другом месте:
в том, доезжает ли контекст до вызова модели.

Ничего не меняет. Запуск из backend/:
    python scripts/explore_avoid.py
    python scripts/explore_avoid.py --category=music --top=30
"""

import json
import sys
from collections import Counter

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from models import AISelection
from services.prompt_context import (
    AVOID_ARTIST_LIMIT,
    AVOID_ARTIST_MIN_BOOKS,
    AVOID_LIMIT,
    AVOID_MIN_BOOKS,
    _item_key,
    _overused_artists,
    _overused_items,
    artist_key,
    track_key,
)
from sqlmodel import Session, select

CATEGORIES = ["music", "food", "aroma"]
ONE = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--category=")), None)
TOP = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--top=")), 15))


def main():
    cats = [ONE] if ONE else CATEGORIES

    with Session(database.engine) as session:
        for category in cats:
            rows = session.exec(
                select(AISelection).where(AISelection.category == category)
            ).all()
            print(f"\n{'=' * 60}\nКАТЕГОРИЯ: {category}  (записей: {len(rows)})")
            if not rows:
                continue

            # --- 1. Форма данных. Код ждёт список словарей с artist/title.
            shapes = Counter()
            sample = None
            for row in rows:
                try:
                    payload = json.loads(row.payload)
                except (TypeError, ValueError):
                    shapes["не парсится"] += 1
                    continue
                if isinstance(payload, list):
                    inner = type(payload[0]).__name__ if payload else "пусто"
                    shapes[f"список[{inner}]"] += 1
                    if sample is None and payload:
                        sample = payload[0]
                elif isinstance(payload, dict):
                    shapes[f"словарь(ключи: {','.join(sorted(payload)[:5])})"] += 1
                    if sample is None:
                        sample = payload
                else:
                    shapes[type(payload).__name__] += 1

            print("\n1) Форма payload:")
            for shape, n in shapes.most_common():
                print(f"   {n:5}  {shape}")
            if sample is not None:
                preview = json.dumps(sample, ensure_ascii=False)[:200]
                print(f"   пример элемента: {preview}")

            # --- 2. Счётчик БЕЗ порога: ловятся ли повторы в принципе
            books_by_item: dict[str, set] = {}
            names: dict[str, str] = {}
            broken = 0
            for row in rows:
                try:
                    items = json.loads(row.payload)
                except (TypeError, ValueError):
                    continue
                if not isinstance(items, list):
                    broken += 1
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        broken += 1
                        continue
                    if category == "music":
                        # зовём ТУ ЖЕ функцию, что и продакшен-код: своя копия
                        # правила уже один раз показала устаревшую картину
                        name, key = track_key(item.get("artist", ""), item.get("title", ""))
                    else:
                        name = (item.get("title") or "").strip()
                        key = _item_key(name)
                    if not key:
                        continue
                    books_by_item.setdefault(key, set()).add(row.book_id)
                    if key not in names or len(name) < len(names[key]):
                        names[key] = name

            if broken:
                print(f"   ⚠ элементов неожиданной формы: {broken}")

            ranked = sorted(books_by_item.items(), key=lambda kv: len(kv[1]), reverse=True)
            print(f"\n2) Самое частое БЕЗ порога (всего пунктов: {len(ranked)}):")
            for key, books in ranked[:TOP]:
                mark = "  ← прошёл бы порог" if len(books) >= AVOID_MIN_BOOKS else ""
                print(f"   {len(books):4} книг  {names[key][:60]}{mark}")

            over = [k for k, b in ranked if len(b) >= AVOID_MIN_BOOKS]
            print(f"\n   пунктов с {AVOID_MIN_BOOKS}+ книгами: {len(over)}")

            # --- 2б. Когда это сгенерировано. Механизм avoid появился 22.07:
            # если почти всё старше, он ни разу и не применялся, а повторы —
            # исторические. Тогда чинить нечего, надо просто перегенерировать.
            by_date = Counter(
                r.created_at.date().isoformat() for r in rows if r.created_at
            )
            print("\n2б) По дате генерации:")
            for day, n in sorted(by_date.items()):
                mark = "  ← до появления avoid" if day < "2026-07-22" else ""
                print(f"   {day}  {n}{mark}")

            # --- 2в. Коллапс на уровне ИСПОЛНИТЕЛЯ, а не трека
            if category == "music":
                by_artist: dict[str, set] = {}
                for row in rows:
                    try:
                        items = json.loads(row.payload)
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        artist = artist_key(item.get("artist", ""))
                        if artist:
                            by_artist.setdefault(artist.lower(), set()).add(row.book_id)
                top_artists = sorted(by_artist.items(), key=lambda kv: len(kv[1]), reverse=True)
                print(f"\n2в) Самые частые ИСПОЛНИТЕЛИ (всего: {len(top_artists)}):")
                for artist, books in top_artists[:TOP]:
                    print(f"   {len(books):4} книг  {artist}")

            # --- 3. Что вернёт сама функция — то, что уедет в промпт
            actual = _overused_items(session, category, exclude_book_id=-1)
            print(f"\n3) Возвращает _overused_items: {len(actual)} шт. (лимит {AVOID_LIMIT})")
            for name in actual[:TOP]:
                print(f"   {name[:70]}")
            if not actual:
                print("   ПУСТО — в промпт не уедет ничего.")

            if category == "music":
                artists = _overused_artists(session, exclude_book_id=-1)
                print(
                    f"\n3б) Возвращает _overused_artists: {len(artists)} шт. "
                    f"(порог {AVOID_ARTIST_MIN_BOOKS} книг, лимит {AVOID_ARTIST_LIMIT})"
                )
                print("   " + ", ".join(artists) if artists else "   ПУСТО.")

                # --- 4. Рассуждение модели (сохраняется с 02.08, миграция 0016).
                # Ради него всё и затевалось: видно, придумала ли модель свежих
                # исполнителей и взяла ли их, или заполнила поле формально.
                with_analysis = [r for r in rows if (r.analysis or "").strip()]
                print(
                    f"\n4) Записей с сохранённым analysis: {len(with_analysis)} из {len(rows)}"
                )
                if not with_analysis:
                    print("   Ни одной — перегенерируй книгу после миграции 0016.")
                for row in sorted(
                    with_analysis, key=lambda r: r.created_at or "", reverse=True
                )[:3]:
                    try:
                        data = json.loads(row.analysis)
                    except (TypeError, ValueError):
                        continue
                    print(f"\n   книга {row.book_id} / {row.source}:")
                    for key in ("tone", "dominant_factor", "era_code",
                                "replaced_artists", "fresh_artists"):
                        value = data.get(key)
                        if not value:
                            continue
                        if isinstance(value, list):
                            value = ", ".join(str(v) for v in value)
                        print(f"      {key}: {str(value)[:300]}")


if __name__ == "__main__":
    main()
