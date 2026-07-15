# AI-«Атмосфера»: обобщённые эндпоинты /books/{id}/atmosphere/{category}.
import pydantic
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

import database
from conftest import fake_generate_design, fake_generate_music
from models import AISelection
from routers import atmosphere as atmosphere_routes
from services.ai import DesignResult


def _mock_music(monkeypatch):
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["music"], "generate", fake_generate_music
    )


def _mock_design(monkeypatch):
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["design"], "generate", fake_generate_design
    )


# --- музыка ---

def test_generate_music_two_sources(client, monkeypatch):
    _mock_music(monkeypatch)
    r = client.post("/books/1/atmosphere/music")
    assert r.status_code == 200
    sources = {s["source"] for s in r.json()["selections"]}
    assert sources == {"Claude", "ChatGPT"}


def test_generated_music_is_persisted(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/books/1/atmosphere/music")
    r = client.get("/books/1/atmosphere/music")
    assert r.status_code == 200
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["payload"][0]["title"] == "Song A"
    assert claude["explanation"] == "Claude explanation"


def test_regenerate_does_not_duplicate(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/books/1/atmosphere/music")
    client.post("/books/1/atmosphere/music")            # второй раз
    r = client.get("/books/1/atmosphere/music")
    assert len(r.json()["selections"]) == 2  # всё ещё 2 варианта, а не 4


def test_generate_music_book_not_found(client, monkeypatch):
    _mock_music(monkeypatch)
    assert client.post("/books/999/atmosphere/music").status_code == 404


def test_generate_music_invalid_lang(client, monkeypatch):
    _mock_music(monkeypatch)
    assert client.post("/books/1/atmosphere/music?lang=fr").status_code == 400


# --- паспорт оформления ---

def test_generate_and_get_design(client, monkeypatch):
    _mock_design(monkeypatch)
    r = client.post("/books/1/atmosphere/design")
    assert r.status_code == 200
    selection = r.json()["selections"][0]
    assert selection["source"] == "Claude"
    assert selection["payload"]["palette"]["accent"] == "#e08b2d"

    r2 = client.get("/books/1/atmosphere/design")
    assert r2.json() == r.json()   # POST и GET отдают один формат


def test_design_absent_is_empty_list(client):
    r = client.get("/books/1/atmosphere/design")
    assert r.status_code == 200
    assert r.json()["selections"] == []


# --- общее ---

def test_unknown_category_404(client):
    assert client.get("/books/1/atmosphere/weather").status_code == 404
    assert client.post("/books/1/atmosphere/weather").status_code == 404


def test_delete_cascades_selections(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/books/1/atmosphere/music")
    client.delete("/books/1")
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection).where(AISelection.book_id == 1)
        ).all()
    assert rows == []


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


def test_design_palette_rejects_non_hex():
    """Задача 37: не-hex цвета из AI отбрасываются на границе."""
    bad = {
        "base_mood": "мрак",
        "palette": {"bg": "url(https://evil.example)", "surface": "#ffffff",
                    "accent": "#ffffff", "text": "#ffffff", "muted": "#ffffff"},
        "title_font": "PT Serif", "body_font": "PT Serif", "statement": "…",
    }
    with pytest.raises(pydantic.ValidationError):
        DesignResult.model_validate(bad)
