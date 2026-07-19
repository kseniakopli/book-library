# Рекомендации новых книг (этап 8): генерация по кнопке, дедуп с библиотекой.
from sqlmodel import Session, select

import database
from models import Recommendation
from routers import recommendations as rec_routes
from services.ai import RecommendationItem, RecommendationsResult


def _fake_generate(favorites, exclude, count=8, lang="ru"):
    """Мгновенный «AI»: одна новая книга и одна, которая уже есть на полке
    (проверяем, что дедуп её отбросит)."""
    async def run():
        return RecommendationsResult(items=[
            RecommendationItem(title="Новая книга", author="Новый Автор",
                               reason="похожа на ваши любимые"),
            RecommendationItem(title="Test", author="Author",
                               reason="а это уже есть в библиотеке"),
        ])
    return run()


def _mock(monkeypatch):
    monkeypatch.setattr(rec_routes, "generate_recommendations", _fake_generate)
    # обложки не ищем — Google Books в тестах не дёргаем
    monkeypatch.setattr(rec_routes, "search_books", lambda q, max_results=3: [])


def _make_favorite(client):
    """Фикстурной книге ставим высокую оценку — иначе рекомендовать не по чему."""
    client.patch("/api/v1/books/1", json={"status": "read", "rating": 9})


def test_recommendations_empty_at_start(client):
    assert client.get("/api/v1/recommendations").json()["recommendations"] == []


def test_generate_without_favorites_spends_nothing(client, monkeypatch):
    """Нет высоко оценённых книг — честно отвечаем, AI не зовём."""
    called = {"n": 0}

    def spy(*args, **kwargs):
        called["n"] += 1
        return _fake_generate(*args, **kwargs)

    monkeypatch.setattr(rec_routes, "generate_recommendations", spy)
    r = client.post("/api/v1/recommendations")
    assert r.status_code == 200
    assert r.json()["recommendations"] == []
    assert r.json()["detail"] == "no_favorites"
    assert called["n"] == 0


def test_generate_and_dedupe(client, monkeypatch):
    _mock(monkeypatch)
    _make_favorite(client)

    r = client.post("/api/v1/recommendations")
    assert r.status_code == 200
    items = r.json()["recommendations"]
    titles = [i["title"] for i in items]
    assert "Новая книга" in titles
    assert "Test" not in titles          # уже в библиотеке → отброшена
    assert items[0]["reason"]

    # сохранилось и читается обычным GET
    assert client.get("/api/v1/recommendations").json()["recommendations"] == items


def test_regeneration_replaces_set(client, monkeypatch):
    _mock(monkeypatch)
    _make_favorite(client)
    client.post("/api/v1/recommendations")
    client.post("/api/v1/recommendations")          # второй раз

    with Session(database.engine) as session:
        rows = session.exec(select(Recommendation)).all()
    assert len(rows) == 1                            # набор заменён, не задвоен


def test_generate_requires_admin(client, monkeypatch):
    from models import User

    _mock(monkeypatch)
    _make_favorite(client)
    with Session(database.engine) as session:
        user = session.get(User, 1)
        user.is_admin = False
        session.add(user)
        session.commit()

    assert client.post("/api/v1/recommendations").status_code == 403
    # чтение остаётся доступным
    assert client.get("/api/v1/recommendations").status_code == 200
