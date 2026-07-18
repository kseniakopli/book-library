# Поиск: минимальная длина, внешние результаты, кэш Catalog с TTL.
from conftest import fake_search_books
from routers import search as search_routes


def test_search_too_short(client, monkeypatch):
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    r = client.get("/api/v1/search?q=аб")            # меньше 3 символов
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_returns_external_results(client, monkeypatch):
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    r = client.get("/api/v1/search?q=Булгаков")
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()["results"]]
    assert "Мастер и Маргарита" in titles


def test_search_results_include_external_id(client, monkeypatch):
    """external_id нужен фронту для точного обогащения при добавлении."""
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    r = client.get("/api/v1/search?q=Булгаков")
    master = next(x for x in r.json()["results"] if x["title"] == "Мастер и Маргарита")
    assert master["external_id"] == "ext1"


def test_search_deletes_stale_catalog_rows(client, monkeypatch):
    """Протухшие записи каталога (старше TTL) удаляются при поиске."""
    from datetime import datetime, timedelta

    from sqlmodel import Session, select

    import database
    from models import Catalog

    stale_date = datetime.now() - timedelta(days=search_routes.CATALOG_TTL_DAYS + 1)
    with Session(database.engine) as session:
        session.add(Catalog(title="Протухшая книга", author="Автор",
                            cover_url=None, source="google",
                            external_id="stale1", created_at=stale_date))
        session.commit()

    monkeypatch.setattr(search_routes, "search_books", lambda q, max_results=8: [])
    r = client.get("/api/v1/search?q=Протухшая")
    assert r.status_code == 200
    assert r.json()["results"] == []          # протухшее не выдаём

    with Session(database.engine) as session:  # и физически удалили
        assert session.exec(select(Catalog).where(
            Catalog.external_id == "stale1")).first() is None


def test_search_caches_to_catalog(client, monkeypatch):
    monkeypatch.setattr(search_routes, "search_books", fake_search_books)
    client.get("/api/v1/search?q=Булгаков")          # 1-й раз: внешний вызов + запись в каталог

    # Ломаем внешний источник — теперь он возвращает пусто
    monkeypatch.setattr(search_routes, "search_books", lambda q, max_results=8: [])
    r = client.get("/api/v1/search?q=Булгаков")      # должно найтись уже в своём каталоге
    titles = [x["title"] for x in r.json()["results"]]
    assert "Мастер и Маргарита" in titles
