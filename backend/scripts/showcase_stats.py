"""Заходы на публичную витрину (задача 96).

Отвечает на вопрос, ради которого всё и заводилось: ходит ли кто-нибудь на
витрину и открывают ли книги — то есть работает ли бумажный канал.

Считаем ВЫЗОВЫ API (`/api/v1/public/...`), а не отдачу HTML: страницу-оболочку
тянут поисковые роботы и превью мессенджеров, а за данными идёт уже браузер
живого человека. Личного не пишем ничего — ни IP, ни User-Agent.

⚠ Заходы владельца тоже считаются: свои визиты на витрину узнать неоткуда,
гость и хозяин для неё одинаковы. Первые дни цифры будут в основном твои.

Запуск из папки backend/:
    python scripts/showcase_stats.py            # за всё время + последние 14 дней
    python scripts/showcase_stats.py 30         # окно в 30 дней

На проде:
    fly ssh console -C "sh -c 'cd /app/backend && python scripts/showcase_stats.py'"
"""

import sys
from collections import Counter
from datetime import datetime, timedelta

from sqlmodel import Session, col, select

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import database
from constants import EVENT_SHOWCASE_BOOK_VIEWED, EVENT_SHOWCASE_VIEWED
from events import Event
from models import Book

WINDOW_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 14


def main() -> None:
    since = datetime.now() - timedelta(days=WINDOW_DAYS)

    with Session(database.engine) as session:
        events = session.exec(
            select(Event).where(
                col(Event.type).in_([EVENT_SHOWCASE_VIEWED, EVENT_SHOWCASE_BOOK_VIEWED])
            )
        ).all()
        titles = {b.id: b.title for b in session.exec(select(Book)).all()}

    if not events:
        print("Заходов пока нет.")
        print("Если витрина уже опубликована — проверь, что задеплоена версия с з.96.")
        return

    views = [e for e in events if e.type == EVENT_SHOWCASE_VIEWED]
    book_views = [e for e in events if e.type == EVENT_SHOWCASE_BOOK_VIEWED]
    recent = [e for e in events if e.created_at >= since]

    print(f"Витрина открывалась:      {len(views)} раз")
    print(f"Книги открывали с неё:    {len(book_views)} раз")
    if views:
        first = min(e.created_at for e in views)
        last = max(e.created_at for e in views)
        print(f"Первый заход: {first:%d.%m.%Y %H:%M}   последний: {last:%d.%m.%Y %H:%M}")

    # Доля дошедших до книги — грубая мера того, цепляет ли оформление
    if views:
        share = round(100 * len(book_views) / len(views))
        print(f"На один заход приходится открытий книг: {share}%")

    print(f"\n--- по дням (последние {WINDOW_DAYS}) ---")
    by_day = Counter(e.created_at.date() for e in recent)
    if not by_day:
        print("за это окно заходов не было")
    for day in sorted(by_day):
        marks = "▪" * min(by_day[day], 40)
        print(f"{day:%d.%m}  {by_day[day]:>3}  {marks}")

    if book_views:
        print("\n--- какие книги открывали ---")
        by_book = Counter(e.book_id for e in book_views)
        for book_id, count in by_book.most_common():
            print(f"{count:>3}  {titles.get(book_id, f'книга {book_id}')}")


if __name__ == "__main__":
    main()
