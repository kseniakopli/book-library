"""Разведка данных о книжных циклах (задача 89).

Вопрос, на который отвечает скрипт: **можно ли определять серию и номер тома
автоматически** — или фича упрётся в ручной ввод.

Смотрим два источника:
  1. `Book.raw_metadata` — полный `volumeInfo` от Google Books, уже сохранённый
     у добавленных книг. Интересует `seriesInfo` (id серии + номер тома),
     а также `subtitle` и сам `title` — в русских изданиях номер часто зашит
     в название («Полари. Книга 2» / «Демон из Пустоши»).
  2. OpenLibrary — свободный второй источник, у него бывает поле `series`.

Запуск из папки backend/:
    python scripts/explore_series.py                 # только локальные данные
    python scripts/explore_series.py --openlibrary   # + запросы в OpenLibrary
    python scripts/explore_series.py --author Ферранте   # сузить выборку

⚠ Сеть нужна только для --openlibrary. Локальный режим ничего не запрашивает.
"""

import json
import re
import sys
import time

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import requests
from sqlmodel import Session, col, select

import database
from models import Book

# Циклы, которые Ксения назвала для разведки (22.07)
KNOWN_SERIES = [
    ("Ферранте", "Неаполитанский квартет"),
    ("Суржиков", "Полари"),
    ("Френч", "Дублинский отдел"),
    ("Дашкевич", "Колдун Российской империи"),
    ("Карризи", "Мила Васкес / Пьетро Джербер"),
]

# номер тома, зашитый в название: «Книга 2», «Том 3», «#1», «. 2»
NUMBER_PATTERNS = [
    re.compile(r"книга\s+(\d+)", re.I),
    re.compile(r"том\s+(\d+)", re.I),
    re.compile(r"#\s*(\d+)"),
    re.compile(r"часть\s+(\d+)", re.I),
]


def _guess_number(text: str):
    for pattern in NUMBER_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return int(match.group(1))
    return None


def _books(session, author_filter: str | None):
    query = select(Book)
    if author_filter:
        query = query.where(col(Book.author).contains(author_filter))
    return session.exec(query.order_by(Book.author, Book.title)).all()


def _inspect_local(book: Book) -> dict:
    """Что о серии знает уже сохранённый volumeInfo от Google Books."""
    info = {}
    if book.raw_metadata:
        try:
            info = json.loads(book.raw_metadata)
        except (TypeError, ValueError):
            info = {}
    series_info = info.get("seriesInfo")
    return {
        "series_info": series_info,
        "subtitle": info.get("subtitle"),
        "number_in_title": _guess_number(f"{book.title} {info.get('subtitle') or ''}"),
        "has_raw": bool(info),
    }


def _openlibrary_series(book: Book):
    """Поле `series` в OpenLibrary. Ищем по ISBN, иначе по названию+автору."""
    try:
        if book.isbn:
            clean = book.isbn.replace("-", "").replace(" ", "")
            resp = requests.get(
                f"https://openlibrary.org/isbn/{clean}.json", timeout=10
            )
            if resp.status_code == 200:
                return resp.json().get("series")
        resp = requests.get(
            "https://openlibrary.org/search.json",
            params={"title": book.title, "author": book.author, "limit": 1},
            timeout=10,
        )
        if resp.status_code == 200:
            docs = resp.json().get("docs", [])
            if docs:
                return docs[0].get("series")
    except requests.RequestException as e:
        return f"(ошибка сети: {e})"
    return None


def main() -> None:
    args = sys.argv[1:]
    use_ol = "--openlibrary" in args
    author = args[args.index("--author") + 1] if "--author" in args else None

    print("Разведка данных о циклах (задача 89)\n")
    print("Ожидаемые циклы:")
    for surname, series in KNOWN_SERIES:
        print(f"  · {surname} — {series}")
    print()

    stats = {"total": 0, "with_raw": 0, "google_series": 0,
             "number_in_title": 0, "ol_series": 0}

    with Session(database.engine) as session:
        books = _books(session, author)
        for book in books:
            local = _inspect_local(book)
            stats["total"] += 1
            stats["with_raw"] += bool(local["has_raw"])
            stats["google_series"] += bool(local["series_info"])
            stats["number_in_title"] += bool(local["number_in_title"])

            # печатаем только то, где есть хоть какой-то признак серии,
            # либо когда явно сузили выборку автором
            interesting = local["series_info"] or local["number_in_title"] or author
            if not interesting:
                continue

            print(f"— {book.title} · {book.author}")
            if local["series_info"]:
                print(f"    Google seriesInfo: {json.dumps(local['series_info'], ensure_ascii=False)}")
            if local["subtitle"]:
                print(f"    subtitle: {local['subtitle']}")
            if local["number_in_title"]:
                print(f"    номер из названия: {local['number_in_title']}")
            if not local["has_raw"]:
                print("    (raw_metadata пуст — книга не обогащалась)")

            if use_ol:
                series = _openlibrary_series(book)
                if series:
                    stats["ol_series"] += 1
                    print(f"    OpenLibrary series: {series}")
                time.sleep(0.4)   # вежливость к бесплатному API

    print("\n--- Итого ---")
    print(f"Книг просмотрено: {stats['total']}")
    print(f"  с raw_metadata (обогащены): {stats['with_raw']}")
    print(f"  Google отдал seriesInfo:    {stats['google_series']}")
    print(f"  номер тома виден в названии: {stats['number_in_title']}")
    if use_ol:
        print(f"  OpenLibrary отдал series:  {stats['ol_series']}")
    print("\nВывод делаем по цифрам: если Google/OpenLibrary молчат у большинства —")
    print("серии придётся задавать вручную (или AI-подсказкой с подтверждением).")


if __name__ == "__main__":
    main()
