# Поиск: минимальная длина, внешние результаты, кэш Catalog с TTL.
from conftest import fake_search_books
from routers import search as search_routes


def test_search_too_short(client, monkeypatch):
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    r = client.get("/search?q=аб")            # меньше 3 символов
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_returns_external_results(client, monkeypatch):
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    r = client.get("/search?q=Булгаков")
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()["results"]]
    assert "Мастер и Маргарита" in titles


def test_search_results_include_external_id(client, monkeypatch):
    """external_id нужен фронту для точного обогащения при добавлении."""
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    r = client.get("/search?q=Булгаков")
    master = next(x for x in r.json()["results"] if x["title"] == "Мастер и Маргарита")
    assert master["external_id"] == "ext1"


def test_search_caches_to_catalog(client, monkeypatch):
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    client.get("/search?q=Булгаков")          # 1-й раз: внешний вызов + запись в каталог

    # Ломаем внешний источник — теперь он возвращает пусто
    monkeypatch.setattr(search_routes, "search_books", lambda q, max_results=8: [])
    r = client.get("/search?q=Булгаков")      # должно найтись уже в своём каталоге
    titles = [x["title"] for x in r.json()["results"]]
    assert "Мастер и Маргарита" in titles
