import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select
from fastapi.testclient import TestClient

import database
from models import Book,AISelection
from main import app
import books
from atmosphere import MusicResult, Song
from sqlalchemy.exc import IntegrityError



@pytest.fixture(name="client")
def client_fixture():
    # Своя база в памяти — реальную library.db тесты не трогают.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    database.engine = test_engine            # подменяем движок, которым пользуются эндпоинты

    with Session(test_engine) as session:
        session.add(Book(title="Test", author="Author", status="want"))
        session.commit()

    yield TestClient(app)


def test_read_and_rating(client):
    r = client.patch("/books/1", json={"status": "read", "rating": 8})
    assert r.status_code == 200
    assert r.json()["status"] == "read"
    assert r.json()["rating"] == 8


def test_rating_cleared_when_leaving_read(client):
    client.patch("/books/1", json={"status": "read", "rating": 8})
    r = client.patch("/books/1", json={"status": "want"})
    assert r.status_code == 200
    assert r.json()["rating"] is None


def test_rating_out_of_range(client):
    r = client.patch("/books/1", json={"status": "read", "rating": 11})
    assert r.status_code == 400


def test_rating_requires_read(client):
    r = client.patch("/books/1", json={"status": "want", "rating": 7})
    assert r.status_code == 400


def test_invalid_status(client):
    r = client.patch("/books/1", json={"status": "finished"})
    assert r.status_code == 400


def test_book_not_found(client):
    r = client.patch("/books/999", json={"status": "read"})
    assert r.status_code == 404

def test_lang_default_is_russian(client):
    # Без ?lang — по умолчанию русский.
    r = client.patch("/books/999", json={"status": "read"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Книга не найдена"


def test_lang_en_book_not_found(client):
    # ?lang=en — то же сообщение по-английски.
    r = client.patch("/books/999?lang=en", json={"status": "read"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Book not found"


def test_lang_en_invalid_status(client):
    # Локализуется и ошибка неверного статуса.
    r = client.patch("/books/1?lang=en", json={"status": "finished"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Status must be want, reading or read"


def test_lang_en_rating_needs_read(client):
    # И правило «оценка только для read» — тоже на английском.
    r = client.patch("/books/1?lang=en", json={"status": "want", "rating": 7})
    assert r.status_code == 400
    assert r.json()["detail"] == "Rating is only allowed for books with status 'read'"


def test_invalid_lang_rejected(client):
    # Неизвестный язык отклоняется; сообщение откатывается на русский.
    r = client.patch("/books/1?lang=fr", json={})
    assert r.status_code == 400
    assert r.json()["detail"] == "lang должен быть ru или en"

async def fake_generate_music(title, author, lang="ru"):
    # Мгновенный «AI» без сети: две подборки с разным содержимым.
    return {
        "Claude": MusicResult(
            songs=[Song(title="Song A", artist="Artist A")],
            explanation="Claude explanation",
        ),
        "ChatGPT": MusicResult(
            songs=[Song(title="Song B", artist="Artist B")],
            explanation="ChatGPT explanation",
        ),
    }


def test_generate_music_two_sources(client, monkeypatch):
    monkeypatch.setattr(books, "generate_music", fake_generate_music)
    r = client.post("/books/1/music")
    assert r.status_code == 200
    sources = {s["source"] for s in r.json()["selections"]}
    assert sources == {"Claude", "ChatGPT"}


def test_generated_music_is_persisted(client, monkeypatch):
    monkeypatch.setattr(books, "generate_music", fake_generate_music)
    client.post("/books/1/music")
    r = client.get("/books/1/music")
    assert r.status_code == 200
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["songs"][0]["title"] == "Song A"
    assert claude["explanation"] == "Claude explanation"


def test_regenerate_does_not_duplicate(client, monkeypatch):
    monkeypatch.setattr(books, "generate_music", fake_generate_music)
    client.post("/books/1/music")
    client.post("/books/1/music")            # второй раз
    r = client.get("/books/1/music")
    assert len(r.json()["selections"]) == 2  # всё ещё 2 варианта, а не 4


def test_generate_music_book_not_found(client, monkeypatch):
    monkeypatch.setattr(books, "generate_music", fake_generate_music)
    r = client.post("/books/999/music")
    assert r.status_code == 404


def test_generate_music_invalid_lang(client, monkeypatch):
    monkeypatch.setattr(books, "generate_music", fake_generate_music)
    r = client.post("/books/1/music?lang=fr")
    assert r.status_code == 400

def fake_search_books(query, max_results=8):
    # Мгновенный «Google Books» без сети — два кандидата.
    return [
        {"title": "Мастер и Маргарита", "author": "Булгаков",
         "cover_url": "http://x/cover.jpg", "external_id": "ext1"},
        {"title": "Собачье сердце", "author": "Булгаков",
         "cover_url": None, "external_id": "ext2"},
    ]


def test_search_too_short(client, monkeypatch):
    monkeypatch.setattr(books, "search_books", fake_search_books)
    r = client.get("/search?q=аб")            # меньше 3 символов
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_returns_external_results(client, monkeypatch):
    monkeypatch.setattr(books, "search_books", fake_search_books)
    r = client.get("/search?q=Булгаков")
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()["results"]]
    assert "Мастер и Маргарита" in titles


def test_search_caches_to_catalog(client, monkeypatch):
    monkeypatch.setattr(books, "search_books", fake_search_books)
    client.get("/search?q=Булгаков")          # 1-й раз: внешний вызов + запись в каталог

    # Ломаем внешний источник — теперь он возвращает пусто
    monkeypatch.setattr(books, "search_books", lambda q, max_results=8: [])
    r = client.get("/search?q=Булгаков")      # должно найтись уже в своём каталоге
    titles = [x["title"] for x in r.json()["results"]]
    assert "Мастер и Маргарита" in titles

def _upload(client, csv_text):
    return client.post(
        "/import",
        files={"file": ("books.csv", csv_text.encode("utf-8"), "text/csv")},
    )


def test_import_creates_books(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Тестовая книга,Тестовый Автор,Июль 2026 г.,7,111\n"
        "Другая книга,Другой Автор,Июнь 2026 г.,3,222\n"
    )
    r = _upload(client, csv_text)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2 and body["skipped"] == 0
    titles = [b["title"] for b in client.get("/books").json()]
    assert "Тестовая книга" in titles


def test_import_sets_read_status_and_rating(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Книга с оценкой,Автор,Май 2026 г.,8,333\n"
    )
    _upload(client, csv_text)
    book = next(b for b in client.get("/books").json() if b["title"] == "Книга с оценкой")
    assert book["status"] == "read"
    assert book["rating"] == 8


def test_import_skips_invalid_rows(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Валидная,Автор,Июль 2026 г.,5,1\n"
        ",Автор без названия,Июль 2026 г.,5,2\n"
        "Название без автора,,Июль 2026 г.,5,3\n"
    )
    assert _upload(client, csv_text).json() == {"imported": 1, "duplicates": 0, "skipped": 2}


def test_import_rating_and_status_edge_cases(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Без оценки,Автор,Июль 2026 г.,,9\n"      # оценки нет, но есть дата → read
        "Кривая оценка,Автор,,абв,10\n"           # не число и без даты → want
    )
    _upload(client, csv_text)
    books = client.get("/books").json()
    b1 = next(b for b in books if b["title"] == "Без оценки")
    assert b1["rating"] is None and b1["status"] == "read"
    b2 = next(b for b in books if b["title"] == "Кривая оценка")
    assert b2["rating"] is None and b2["status"] == "want"   

def test_delete_book(client):
    response = client.delete("/books/1")
    assert response.status_code == 200
    assert client.get("/books/1/music").status_code == 200  # музыка пустая, но книга…
    assert client.patch("/books/1", json={"status": "read"}).status_code == 404


def test_delete_book_not_found(client):
    assert client.delete("/books/999").status_code == 404

def test_delete_cascades_selections(client, monkeypatch):
    monkeypatch.setattr(books, "generate_music", fake_generate_music)
    client.post("/books/1/music")
    client.delete("/books/1")
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection).where(AISelection.book_id == 1)
        ).all()
    assert rows == []

def test_get_book(client):
    r = client.get("/books/1")
    assert r.status_code == 200
    assert r.json()["title"] == "Test"


def test_get_book_not_found(client):
    assert client.get("/books/999").status_code == 404

def test_aiselection_unique_constraint(client):
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=1, category="music", source="Claude", payload="[]",
        ))
        session.commit()
        session.add(AISelection(
            book_id=1, category="music", source="Claude", payload="[]",
        ))
        with pytest.raises(IntegrityError):
            session.commit()

def fake_book_info(title, author, lang="ru", isbn=None):
    return {
        "cover_url": "http://example.com/c.jpg",
        "description": "desc",
        "page_count": 100,
        "categories": None,
        "published_year": 2000,
        "language": "ru",
        "external_rating": None,
        "raw_metadata": "{}",
    }


def test_add_book_enriches_in_background(client, monkeypatch):
    monkeypatch.setattr(books, "fetch_book_info", fake_book_info)
    r = client.post("/books", json={"title": "New", "author": "Auth"})
    assert r.status_code == 200
    assert r.json()["enrich_status"] == "pending"   # ответ ушёл до обогащения
    book_id = r.json()["id"]
    r2 = client.get(f"/books/{book_id}")            # фон уже отработал
    assert r2.json()["enrich_status"] == "ready"
    assert r2.json()["cover_url"] == "http://example.com/c.jpg"


def test_add_book_enrichment_failure_sets_failed(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(books, "fetch_book_info", boom)
    r = client.post("/books", json={"title": "New2", "author": "Auth"})
    book_id = r.json()["id"]
    r2 = client.get(f"/books/{book_id}")
    assert r2.json()["enrich_status"] == "failed"

def test_add_book_with_external_id(client, monkeypatch):
    monkeypatch.setattr(books, "fetch_volume_by_id", lambda vid: fake_book_info("t", "a"))
    r = client.post("/books", json={
        "title": "T", "author": "A",
        "cover_url": "https://example.com/candidate.jpg",
        "external_id": "abc123",
    })
    assert r.json()["cover_url"] == "https://example.com/candidate.jpg"  # видна сразу
    book_id = r.json()["id"]
    r2 = client.get(f"/books/{book_id}")
    assert r2.json()["enrich_status"] == "ready"
    assert r2.json()["description"] == "desc"   # доехало из fetch_volume_by_id

def test_add_book_rejects_non_https_cover(client):
    r = client.post("/books", json={
        "title": "T", "author": "A", "cover_url": "javascript:alert(1)",
    })
    assert r.status_code == 422


def test_design_palette_rejects_non_hex():
    import pydantic
    from atmosphere import DesignResult
    bad = {
        "base_mood": "мрак",
        "palette": {"bg": "url(https://evil.example)", "surface": "#ffffff",
                    "accent": "#ffffff", "text": "#ffffff", "muted": "#ffffff"},
        "title_font": "PT Serif", "body_font": "PT Serif", "statement": "…",
    }
    with pytest.raises(pydantic.ValidationError):
        DesignResult.model_validate(bad)


def test_import_rejects_bad_encoding(client):
    data = "Название,Автор\nКнига,Кто-то".encode("cp1251")
    r = client.post("/import", files={"file": ("books.csv", data, "text/csv")})
    assert r.status_code == 400


def test_import_rejects_huge_file(client):
    data = b"a" * (2 * 1024 * 1024 + 10)
    r = client.post("/import", files={"file": ("books.csv", data, "text/csv")})
    assert r.status_code == 400


def test_import_rejects_too_many_rows(client):
    rows = "\n".join(f"Книга {i},Автор" for i in range(2101))
    data = ("Название,Автор\n" + rows).encode("utf-8")
    r = client.post("/import", files={"file": ("books.csv", data, "text/csv")})
    assert r.status_code == 400