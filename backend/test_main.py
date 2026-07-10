import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

import database
from models import Book
from main import app
import books
from atmosphere import MusicResult, Song


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