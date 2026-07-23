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
    r = client.post("/api/v1/books/1/atmosphere/music")
    assert r.status_code == 200
    sources = {s["source"] for s in r.json()["selections"]}
    assert sources == {"Claude", "ChatGPT"}


def test_context_passed_to_prompt(client, monkeypatch):
    """22.07: в генерацию уходит фактический контекст книги — аннотация и жанры,
    иначе модель угадывает сюжет по названию (инцидент «Капля духов» → Дубай)."""
    from sqlmodel import Session

    import database
    from models import Book

    with Session(database.engine) as session:
        book = session.get(Book, 1)
        book.description = "История о парфюмерном мире Москвы"
        book.categories = '["Fiction"]'
        session.add(book)
        session.commit()

    captured = {}

    async def spy(title, author, lang="ru", context=None):
        captured["context"] = context
        return await fake_generate_music(title, author, lang)

    monkeypatch.setitem(atmosphere_routes.CATEGORIES["music"], "generate", spy)
    client.post("/api/v1/books/1/atmosphere/music")

    assert "парфюмерном мире Москвы" in captured["context"]["description"]
    assert captured["context"]["genres"] == "Fiction"
    assert "avoid" in captured["context"]


def test_music_marked_unverified_when_spotify_unavailable(client, monkeypatch):
    """Задача 85: Spotify недоступен (бан/нет ключей) → музыка помечается
    непроверенной (verified=False), чтобы reverify_music её потом догнал."""
    import services.spotify as spotify_service

    _mock_music(monkeypatch)
    monkeypatch.setattr(spotify_service, "available", lambda: False)
    r = client.post("/api/v1/books/1/atmosphere/music")
    assert r.json()["verified"] is False


def test_music_verified_when_spotify_available(client, monkeypatch):
    import services.spotify as spotify_service

    _mock_music(monkeypatch)
    monkeypatch.setattr(spotify_service, "available", lambda: True)
    r = client.post("/api/v1/books/1/atmosphere/music")
    assert r.json()["verified"] is True


def test_generated_music_is_persisted(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")
    r = client.get("/api/v1/books/1/atmosphere/music")
    assert r.status_code == 200
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["payload"][0]["title"] == "Song A"
    assert claude["explanation"] == "Claude explanation"


def test_regenerate_does_not_duplicate(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")
    client.post("/api/v1/books/1/atmosphere/music")            # второй раз
    r = client.get("/api/v1/books/1/atmosphere/music")
    assert len(r.json()["selections"]) == 2  # всё ещё 2 варианта, а не 4


def test_failed_regeneration_keeps_old(client, monkeypatch):
    """Защита от потери (инцидент 18.07): неудачная перегенерация (AI вернул
    пустой фолбэк) НЕ должна затирать уже сохранённую атмосферу."""
    from services.ai import MusicResult, Song

    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")   # успешно: Song A / Song B

    async def all_empty(title, author, lang="ru", context=None):
        return {
            "Claude": MusicResult(songs=[], explanation="(не удалось)"),
            "ChatGPT": MusicResult(songs=[], explanation="(не удалось)"),
        }
    monkeypatch.setitem(atmosphere_routes.CATEGORIES["music"], "generate", all_empty)
    client.post("/api/v1/books/1/atmosphere/music")   # провал — не должен стереть

    r = client.get("/api/v1/books/1/atmosphere/music").json()
    assert len(r["selections"]) == 2                  # старые на месте
    claude = next(s for s in r["selections"] if s["source"] == "Claude")
    assert claude["payload"][0]["title"] == "Song A"


def test_first_generation_all_empty_writes_nothing(client, monkeypatch):
    """Первая генерация, если AI не ответил ни одним источником, не плодит
    пустые строки — остаётся «пусто», а не два пустых варианта."""
    from services.ai import MusicResult

    async def all_empty(title, author, lang="ru", context=None):
        return {
            "Claude": MusicResult(songs=[], explanation="(не удалось)"),
            "ChatGPT": MusicResult(songs=[], explanation="(не удалось)"),
        }
    monkeypatch.setitem(atmosphere_routes.CATEGORIES["music"], "generate", all_empty)
    client.post("/api/v1/books/1/atmosphere/music")
    r = client.get("/api/v1/books/1/atmosphere/music").json()
    assert r["selections"] == []


def test_generate_music_book_not_found(client, monkeypatch):
    _mock_music(monkeypatch)
    assert client.post("/api/v1/books/999/atmosphere/music").status_code == 404


def test_generate_music_invalid_lang(client, monkeypatch):
    _mock_music(monkeypatch)
    assert client.post("/api/v1/books/1/atmosphere/music?lang=fr").status_code == 400


# --- точечное удаление трека (admin) ---

def _seed_music(client, monkeypatch):
    """Сгенерировать музыку фейком: Claude — Song A, ChatGPT — Song B."""
    import services.spotify as spotify_service

    _mock_music(monkeypatch)
    # Spotify в тестах не трогаем: и генерация, и пересборка плейлиста мимо него
    monkeypatch.setattr(spotify_service, "available", lambda: False)
    client.post("/api/v1/books/1/atmosphere/music")


def test_remove_track_from_one_source(client, monkeypatch):
    _seed_music(client, monkeypatch)
    r = client.request(
        "DELETE", "/api/v1/books/1/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Song A", "artist": "Artist A"},
    )
    assert r.status_code == 200
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["payload"] == []                    # трек удалён
    chatgpt = next(s for s in r.json()["selections"] if s["source"] == "ChatGPT")
    assert chatgpt["payload"][0]["title"] == "Song B"  # чужой источник не задет
    # удаление сохранилось
    assert client.get("/api/v1/books/1/atmosphere/music").json() == r.json()


def test_remove_track_not_found(client, monkeypatch):
    _seed_music(client, monkeypatch)
    r = client.request(
        "DELETE", "/api/v1/books/1/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Нет такого", "artist": "Никто"},
    )
    assert r.status_code == 404


def test_remove_track_requires_admin(client, monkeypatch):
    from models import User

    _seed_music(client, monkeypatch)
    with Session(database.engine) as session:
        user = session.get(User, 1)
        user.is_admin = False
        session.add(user)
        session.commit()
    r = client.request(
        "DELETE", "/api/v1/books/1/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Song A", "artist": "Artist A"},
    )
    assert r.status_code == 403


def test_remove_track_book_not_found(client):
    r = client.request(
        "DELETE", "/api/v1/books/999/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Song A", "artist": "Artist A"},
    )
    assert r.status_code == 404


# --- паспорт оформления ---

def test_generate_and_get_design(client, monkeypatch):
    _mock_design(monkeypatch)
    r = client.post("/api/v1/books/1/atmosphere/design")
    assert r.status_code == 200
    selection = r.json()["selections"][0]
    assert selection["source"] == "Claude"
    # задача 57: паспорт несёт обе палитры — тёмную и светлую
    assert selection["payload"]["palette_dark"]["accent"] == "#e08b2d"
    assert selection["payload"]["palette_light"]["bg"] == "#f6f1e7"

    r2 = client.get("/api/v1/books/1/atmosphere/design")
    assert r2.json() == r.json()   # POST и GET отдают один формат


def test_design_absent_is_empty_list(client):
    r = client.get("/api/v1/books/1/atmosphere/design")
    assert r.status_code == 200
    assert r.json()["selections"] == []


# --- общее ---

def test_unknown_category_404(client):
    assert client.get("/api/v1/books/1/atmosphere/weather").status_code == 404
    assert client.post("/api/v1/books/1/atmosphere/weather").status_code == 404


def test_delete_cascades_selections(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")
    client.delete("/api/v1/books/1")
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
    ok_palette = {"bg": "#ffffff", "surface": "#ffffff", "accent": "#ffffff",
                  "text": "#ffffff", "muted": "#ffffff"}
    bad = {
        "base_mood": "мрак",
        "palette_dark": {**ok_palette, "bg": "url(https://evil.example)"},
        "palette_light": ok_palette,
        "title_font": "PT Serif", "body_font": "PT Serif", "statement": "…",
    }
    with pytest.raises(pydantic.ValidationError):
        DesignResult.model_validate(bad)

def test_generate_food_two_sources_and_persist(client, monkeypatch):
    from conftest import fake_generate_food
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["food"], "generate", fake_generate_food
    )
    r = client.post("/api/v1/books/1/atmosphere/food")
    assert r.status_code == 200
    assert {s["source"] for s in r.json()["selections"]} == {"Claude", "ChatGPT"}
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["payload"][0] == {
        "title": "Глинтвейн", "description": "Тёплый и пряный",
    }
    assert client.get("/api/v1/books/1/atmosphere/food").json() == r.json()


def test_categories_are_independent(client, monkeypatch):
    from conftest import fake_generate_aroma
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["music"], "generate", fake_generate_music
    )
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["aroma"], "generate", fake_generate_aroma
    )
    client.post("/api/v1/books/1/atmosphere/music")
    client.post("/api/v1/books/1/atmosphere/aroma")
    # каждая категория хранит свои 2 подборки и не задевает чужие
    assert len(client.get("/api/v1/books/1/atmosphere/music").json()["selections"]) == 2
    assert len(client.get("/api/v1/books/1/atmosphere/aroma").json()["selections"]) == 2
