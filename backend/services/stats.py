# Статистика чтения (задачи 24/63). Считаем в Python по выборке нужных колонок:
# библиотека персональная (сотни книг), а SQL-функции дат в SQLite и Postgres
# различаются — так расчёт остаётся переносимым и легко тестируется.
import json
from collections import Counter
from datetime import date

from sqlmodel import Session, select

from constants import STATUS_READ, STATUS_READING, STATUS_WANT
from models import Book, UserBook

MONTHS_BACK = 12
TOP_SIZE = 5


def _month_key(value) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _recent_months(today: date) -> list[str]:
    """Последние MONTHS_BACK месяцев, включая текущий, в порядке возрастания."""
    keys = []
    year, month = today.year, today.month
    for _ in range(MONTHS_BACK):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _streak(by_month: dict[str, int], months: list[str]) -> int:
    """Сколько месяцев подряд читалось хотя бы по одной книге.
    Считаем назад от текущего месяца; если он ещё пустой — не обрываем серию
    (месяц только начался), а начинаем с предыдущего."""
    ordered = list(reversed(months))          # от свежего к старому
    if ordered and by_month.get(ordered[0], 0) == 0:
        ordered = ordered[1:]                 # текущий месяц «в кредит»
    streak = 0
    for key in ordered:
        if by_month.get(key, 0) == 0:
            break
        streak += 1
    return streak


def _genres(categories_json: str | None) -> list[str]:
    """Book.categories хранится JSON-строкой из Google Books (может быть пустым)."""
    if not categories_json:
        return []
    try:
        data = json.loads(categories_json)
    except (TypeError, ValueError):
        return []
    return [str(g) for g in data] if isinstance(data, list) else []


def compute_stats(session: Session, user_id: int, today: date | None = None) -> dict:
    """Сводка по полке пользователя. today — параметр ради предсказуемых тестов."""
    today = today or date.today()

    rows = session.exec(
        select(
            Book.author,
            Book.page_count,
            Book.categories,
            UserBook.status,
            UserBook.rating,
            UserBook.read_at,
        )
        .join(UserBook, UserBook.book_id == Book.id)
        .where(UserBook.user_id == user_id)
    ).all()

    totals = Counter(row.status for row in rows)
    by_month = Counter()
    ratings = Counter()
    pages = 0
    authors = Counter()
    genres = Counter()
    this_year = 0

    for author, page_count, categories, status, rating, read_at in rows:
        if status != STATUS_READ:
            continue
        if rating is not None:
            ratings[rating] += 1
        if page_count:
            pages += page_count
        authors[author] += 1
        for genre in _genres(categories):
            genres[genre] += 1
        if read_at:
            by_month[_month_key(read_at)] += 1
            if read_at.year == today.year:
                this_year += 1

    months = _recent_months(today)
    rated = sum(ratings.values())

    return {
        "totals": {
            "all": len(rows),
            "read": totals.get(STATUS_READ, 0),
            "reading": totals.get(STATUS_READING, 0),
            "want": totals.get(STATUS_WANT, 0),
        },
        "pages_read": pages,
        "average_rating": round(
            sum(n * c for n, c in ratings.items()) / rated, 2
        ) if rated else None,
        "rated_count": rated,
        # распределение оценок: всегда 1..10, включая нули — чтобы ось графика
        # не «плясала» от того, какие оценки уже проставлены
        "ratings": [{"rating": n, "count": ratings.get(n, 0)} for n in range(1, 11)],
        "by_month": [{"month": m, "count": by_month.get(m, 0)} for m in months],
        "this_year": {"year": today.year, "count": this_year},
        "streak_months": _streak(by_month, months),
        "top_authors": [
            {"author": a, "count": c} for a, c in authors.most_common(TOP_SIZE)
        ],
        "top_genres": [
            {"genre": g, "count": c} for g, c in genres.most_common(TOP_SIZE)
        ],
    }


def format_summary(stats: dict) -> str:
    """Сводка текстом для AI-инсайтов: модель толкует ГОТОВЫЕ цифры и ничего
    не считает сама — иначе в наблюдениях появляются выдуманные числа."""
    t = stats["totals"]
    months = ", ".join(
        f"{m['month']}: {m['count']}" for m in stats["by_month"]
    )
    ratings = ", ".join(
        f"{r['rating']}/10 — {r['count']}" for r in stats["ratings"] if r["count"]
    )
    authors = ", ".join(
        f"{a['author']} ({a['count']})" for a in stats["top_authors"]
    )
    genres = ", ".join(f"{g['genre']} ({g['count']})" for g in stats["top_genres"])
    average = stats["average_rating"]

    lines = [
        f"Книг на полке: {t['all']} (прочитано {t['read']}, "
        f"читаю {t['reading']}, хочу прочитать {t['want']}).",
        f"Прочитано страниц: {stats['pages_read']}.",
        f"Средняя оценка: {average} (оценено книг: {stats['rated_count']})."
        if average is not None else "Оценок пока нет.",
        f"Распределение оценок: {ratings}." if ratings else "",
        f"Прочитано по месяцам: {months}.",
        f"В {stats['this_year']['year']} году прочитано: {stats['this_year']['count']}.",
        f"Месяцев подряд с чтением: {stats['streak_months']}.",
        f"Чаще всего читает авторов: {authors}." if authors else "",
        f"Частые жанры: {genres}." if genres else "",
    ]
    return "\n".join(line for line in lines if line)
