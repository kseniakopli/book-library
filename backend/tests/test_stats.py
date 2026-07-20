# Статистика чтения (задачи 24/63): расчёт метрик и AI-инсайты по кнопке.
import json
from datetime import date

from sqlmodel import Session

import database
from models import Book, UserBook
from routers import stats as stats_routes
from services.ai import InsightsResult
from services.stats import compute_stats, format_summary

TODAY = date(2026, 7, 19)   # фиксируем «сегодня»: иначе тест протухнет со временем


def _seed(rows):
    """rows: (title, author, status, rating, read_at, page_count, genres)."""
    with Session(database.engine) as session:
        for i, (title, author, status, rating, read_at, pages, genres) in enumerate(
            rows, start=100
        ):
            session.add(Book(
                id=i, title=title, author=author, page_count=pages,
                categories=json.dumps(genres, ensure_ascii=False) if genres else None,
            ))
            session.commit()
            session.add(UserBook(
                user_id=1, book_id=i, status=status, rating=rating, read_at=read_at,
            ))
            session.commit()


def _stats():
    with Session(database.engine) as session:
        return compute_stats(session, 1, today=TODAY)


def test_empty_shelf_gives_no_average(client):
    """Фикстурная книга одна и без оценки — средней быть не должно (не ноль)."""
    s = _stats()
    assert s["average_rating"] is None
    assert s["totals"] == {"all": 1, "read": 0, "reading": 0, "want": 1}


def test_totals_and_pages(client):
    _seed([
        ("A", "Автор 1", "read", 8, date(2026, 7, 1), 300, ["Роман"]),
        ("B", "Автор 1", "read", 6, date(2026, 6, 5), 200, ["Роман", "Драма"]),
        ("C", "Автор 2", "reading", None, None, 400, None),
    ])
    s = _stats()
    assert s["totals"] == {"all": 4, "read": 2, "reading": 1, "want": 1}
    assert s["pages_read"] == 500          # страницы только прочитанного
    assert s["average_rating"] == 7.0
    assert s["rated_count"] == 2


def test_ratings_scale_is_always_full(client):
    """Ось графика фиксированная: 10 делений, даже если оценок мало."""
    _seed([("A", "Автор", "read", 9, date(2026, 7, 1), None, None)])
    ratings = _stats()["ratings"]
    assert [r["rating"] for r in ratings] == list(range(1, 11))
    assert next(r["count"] for r in ratings if r["rating"] == 9) == 1


def test_by_month_covers_last_year(client):
    _seed([
        ("A", "Автор", "read", 8, date(2026, 7, 3), None, None),
        ("B", "Автор", "read", 8, date(2026, 7, 15), None, None),
        ("C", "Автор", "read", 8, date(2020, 1, 1), None, None),   # вне окна
    ])
    s = _stats()
    assert len(s["by_month"]) == 12
    assert s["by_month"][-1] == {"month": "2026-07", "count": 2}
    assert s["by_month"][0]["month"] == "2025-08"
    assert s["this_year"] == {"year": 2026, "count": 2}


def test_streak_counts_consecutive_months(client):
    _seed([
        ("A", "Автор", "read", 8, date(2026, 7, 2), None, None),
        ("B", "Автор", "read", 8, date(2026, 6, 2), None, None),
        ("C", "Автор", "read", 8, date(2026, 5, 2), None, None),
        ("D", "Автор", "read", 8, date(2026, 3, 2), None, None),   # после разрыва
    ])
    assert _stats()["streak_months"] == 3


def test_streak_survives_empty_current_month(client):
    """Месяц только начался — серию не обрываем, считаем с предыдущего."""
    _seed([
        ("A", "Автор", "read", 8, date(2026, 6, 2), None, None),
        ("B", "Автор", "read", 8, date(2026, 5, 2), None, None),
    ])
    assert _stats()["streak_months"] == 2


def test_top_authors_and_genres(client):
    _seed([
        ("A", "Толстой", "read", 8, date(2026, 7, 1), None, ["Роман"]),
        ("B", "Толстой", "read", 8, date(2026, 6, 1), None, ["Роман"]),
        ("C", "Чехов", "read", 8, date(2026, 5, 1), None, ["Пьесы"]),
        ("D", "Чехов", "want", None, None, None, ["Пьесы"]),   # не прочитано — мимо
    ])
    s = _stats()
    assert s["top_authors"][0] == {"author": "Толстой", "count": 2}
    assert s["top_genres"][0] == {"genre": "Роман", "count": 2}
    assert {"genre": "Пьесы", "count": 1} in s["top_genres"]


def test_broken_categories_json_does_not_crash(client):
    """В базе есть записи с мусором в categories — статистика не должна падать."""
    with Session(database.engine) as session:
        session.add(Book(id=200, title="X", author="Автор", categories="не json"))
        session.commit()
        session.add(UserBook(user_id=1, book_id=200, status="read",
                             read_at=date(2026, 7, 1)))
        session.commit()
    assert _stats()["top_genres"] == []


def test_stats_endpoint(client):
    r = client.get("/api/v1/stats")
    assert r.status_code == 200
    assert "by_month" in r.json() and "totals" in r.json()


def test_summary_has_no_invented_numbers(client):
    """Сводку для модели собираем сами — она содержит только реальные цифры."""
    _seed([("A", "Автор", "read", 9, date(2026, 7, 1), 250, ["Роман"])])
    text = format_summary(_stats())
    assert "Прочитано страниц: 250" in text
    assert "Средняя оценка: 9.0" in text
    assert "2026-07: 1" in text


def test_insights_without_read_books_spends_nothing(client, monkeypatch):
    """Нечего толковать — AI не зовём."""
    called = {"n": 0}

    async def spy(summary, lang="ru"):
        called["n"] += 1
        return InsightsResult(observations=["не должно случиться"])

    monkeypatch.setattr(stats_routes, "generate_insights", spy)
    r = client.post("/api/v1/stats/insights")
    assert r.status_code == 200
    assert r.json() == {"observations": [], "detail": "no_data"}
    assert called["n"] == 0


def test_insights_generated(client, monkeypatch):
    _seed([("A", "Автор", "read", 9, date(2026, 7, 1), 250, ["Роман"])])
    seen = {}

    async def fake(summary, lang="ru"):
        seen["summary"] = summary
        return InsightsResult(observations=["Летом читается больше."])

    monkeypatch.setattr(stats_routes, "generate_insights", fake)
    r = client.post("/api/v1/stats/insights")
    assert r.status_code == 200
    assert r.json()["observations"] == ["Летом читается больше."]
    assert "Книг на полке" in seen["summary"]   # модель получила готовые цифры
