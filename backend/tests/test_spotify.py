# Spotify-плейлисты (этап 10.2). Сеть всегда замокана — токены не тратятся.
import json

import pytest
from sqlmodel import Session

import database
import services.spotify as spotify_service
from models import AISelection


def _add_music(book_id=1):
    """Кладём в БД две музыкальные подборки (как после генерации атмосферы)."""
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=book_id, category="music", source="Claude",
            payload=json.dumps([
                {"title": "Song A", "artist": "Artist A"},
                {"title": "Song B", "artist": "Artist B"},
            ]),
        ))
        session.add(AISelection(
            book_id=book_id, category="music", source="ChatGPT",
            payload=json.dumps([
                {"title": "song a", "artist": "artist a"},   # дубль в другом регистре
                {"title": "Song C", "artist": "Artist C"},
            ]),
        ))
        session.commit()


def test_playlist_requires_auth(client, monkeypatch):
    monkeypatch.setattr(spotify_service, "has_token", lambda: False)
    r = client.post("/api/v1/books/1/playlist")
    assert r.status_code == 200
    assert r.json()["status"] == "auth_required"
    assert "accounts.spotify.com" in r.json()["auth_url"]
    assert "state=1" in r.json()["auth_url"]


def test_playlist_created_and_saved(client, monkeypatch):
    _add_music()
    monkeypatch.setattr(spotify_service, "has_token", lambda: True)

    captured = {}

    def fake_create(name, songs):
        captured["name"] = name
        captured["songs"] = songs
        return {"url": "https://open.spotify.com/playlist/test123",
                "found": 3, "not_found": []}

    monkeypatch.setattr(spotify_service, "create_playlist_from_songs", fake_create)

    r = client.post("/api/v1/books/1/playlist")
    assert r.status_code == 200
    assert r.json()["status"] == "created"
    assert r.json()["playlist_url"] == "https://open.spotify.com/playlist/test123"
    # дедуп: 4 трека из двух источников → 3 уникальных
    assert len(captured["songs"]) == 3
    assert "Test" in captured["name"]   # имя книги в названии плейлиста

    # ссылка сохранилась у книги и видна в API
    assert (
        client.get("/api/v1/books/1").json()["spotify_playlist_url"]
        == "https://open.spotify.com/playlist/test123"
    )


def test_playlist_existing_returned_without_recreation(client, monkeypatch):
    _add_music()
    monkeypatch.setattr(spotify_service, "has_token", lambda: True)
    monkeypatch.setattr(
        spotify_service, "create_playlist_from_songs",
        lambda name, songs: {"url": "https://open.spotify.com/playlist/first",
                             "found": 1, "not_found": []},
    )
    client.post("/api/v1/books/1/playlist")

    def boom(name, songs):
        raise AssertionError("плейлист не должен создаваться повторно")

    monkeypatch.setattr(spotify_service, "create_playlist_from_songs", boom)
    r = client.post("/api/v1/books/1/playlist")
    assert r.json() == {
        "status": "exists",
        "playlist_url": "https://open.spotify.com/playlist/first",
    }


def test_playlist_without_music_rejected(client, monkeypatch):
    monkeypatch.setattr(spotify_service, "has_token", lambda: True)
    r = client.post("/api/v1/books/1/playlist")
    assert r.status_code == 400


def test_playlist_book_not_found(client, monkeypatch):
    monkeypatch.setattr(spotify_service, "has_token", lambda: True)
    assert client.post("/api/v1/books/999/playlist").status_code == 404


def _set_playlist_url(url="https://open.spotify.com/playlist/test123"):
    from models import Book
    with Session(database.engine) as session:
        book = session.get(Book, 1)
        book.spotify_playlist_url = url
        session.add(book)
        session.commit()


def test_qr_requires_playlist(client):
    assert client.get("/api/v1/books/1/qr").status_code == 404


def test_qr_returns_png(client):
    pytest.importorskip("qrcode")   # пропускаем, пока qrcode не установлен
    _set_playlist_url()
    r = client.get("/api/v1/books/1/qr")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"   # магические байты PNG


# --- проверка совпадения найденного трека (инцидент 20.07) ---

def _track(name, *artists):
    return {"name": name, "artists": [{"name": a} for a in artists], "uri": f"uri:{name}"}


def test_matches_accepts_exact_and_remastered():
    assert spotify_service._matches(
        _track("Spiegel im Spiegel", "Arvo Pärt"), "Spiegel im Spiegel", "Arvo Pärt"
    )
    # приписки ремастера/переиздания не должны мешать
    assert spotify_service._matches(
        _track("Song To The Siren - Remastered", "This Mortal Coil"),
        "Song To The Siren", "This Mortal Coil",
    )
    # трек с несколькими исполнителями — достаточно совпадения с одним
    assert spotify_service._matches(
        _track("Solas", "Lisa Gerrard", "Patrick Cassidy"), "Solas", "Patrick Cassidy"
    )


def test_matches_rejects_foreign_track():
    """Именно так в плейлист попадал случайный популярный трек."""
    assert not spotify_service._matches(
        _track("1Train", "A$AP Rocky", "Kendrick Lamar"),
        "The Deer's Cry", "Arvo Pärt",
    )
    # название совпало, а исполнитель — нет: это кавер/однофамилец, не берём
    assert not spotify_service._matches(
        _track("History", "Kings of Leon"), "History", "Ólafur Arnalds"
    )


def test_search_track_skips_mismatched_candidates(monkeypatch):
    """Первый кандидат чужой — берём следующего подходящего, а не первого подряд."""
    class FakeResponse:
        @staticmethod
        def json():
            return {"tracks": {"items": [
                _track("1Train", "A$AP Rocky"),
                _track("The Deer's Cry", "Arvo Pärt"),
            ]}}

    monkeypatch.setattr(
        spotify_service.requests, "get", lambda *a, **kw: FakeResponse()
    )
    uri = spotify_service._search_track({}, "The Deer's Cry", "Arvo Pärt")
    assert uri == "uri:The Deer's Cry"


def test_search_track_returns_none_when_nothing_matches(monkeypatch):
    class FakeResponse:
        @staticmethod
        def json():
            return {"tracks": {"items": [_track("1Train", "A$AP Rocky")]}}

    monkeypatch.setattr(
        spotify_service.requests, "get", lambda *a, **kw: FakeResponse()
    )
    assert spotify_service._search_track({}, "Выдуманный трек", "Никто") is None


def test_dedupe_songs_unit():
    songs = [
        {"title": "A", "artist": "X"},
        {"title": "a ", "artist": " x"},
        {"title": "B", "artist": "X"},
    ]
    assert len(spotify_service.dedupe_songs(songs)) == 2
