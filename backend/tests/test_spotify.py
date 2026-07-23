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

    def fake_create(name, songs, cover=None):
        captured["name"] = name
        captured["songs"] = songs
        return {"url": "https://open.spotify.com/playlist/test123",
                "found": 3, "not_found": [], "cover_set": False}

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
        lambda name, songs, cover=None: {
            "url": "https://open.spotify.com/playlist/first",
            "found": 1, "not_found": [], "cover_set": False,
        },
    )
    client.post("/api/v1/books/1/playlist")

    def boom(name, songs, cover=None):
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


def test_matches_accepts_transliterated_cyrillic():
    """Русские исполнители в Spotify часто латиницей — сравнение через транслит."""
    assert spotify_service._matches(
        _track("Sudno", "Molchat Doma"), "Судно", "Молчат Дома"
    )
    assert spotify_service._matches(
        _track("Судно (Борис Рыжий)", "Молчат Дома"), "Судно", "Molchat Doma"
    )
    assert spotify_service._matches(
        _track("Plyazh", "Buerak"), "Пляж", "Буерак"
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


class FakeResponse:
    """Ответ Spotify: статус проверяется, поэтому мок должен его отдавать."""

    def __init__(self, items=(), status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""
        self._items = list(items)

    def json(self):
        return {"tracks": {"items": self._items}}


def test_search_track_skips_mismatched_candidates(monkeypatch):
    """Первый кандидат чужой — берём следующего подходящего, а не первого подряд."""
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse([
            _track("1Train", "A$AP Rocky"),
            _track("The Deer's Cry", "Arvo Pärt"),
        ]),
    )
    assert (
        spotify_service._search_track({}, "The Deer's Cry", "Arvo Pärt")
        == "uri:The Deer's Cry"
    )


def test_search_track_returns_none_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse([_track("1Train", "A$AP Rocky")]),
    )
    assert spotify_service._search_track({}, "Выдуманный трек", "Никто") is None


# --- один проход поиска: чистая атмосфера + uri для плейлиста (20.07) ---

def _no_user_token(monkeypatch):
    monkeypatch.setattr(spotify_service, "has_token", lambda: False)
    monkeypatch.setattr(
        spotify_service, "_client_credentials_token", lambda: "token"
    )


def test_resolve_songs_marks_invented_tracks(client, monkeypatch):
    """Выдуманный трек не должен попасть в сервис: у Ólafur Arnalds нет
    «Familiar Ground» — Spotify отдаёт другие его вещи, значит None."""
    _no_user_token(monkeypatch)
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse([_track("Near Light", "Ólafur Arnalds")]),
    )
    resolved = spotify_service.resolve_songs([
        {"title": "Near Light", "artist": "Ólafur Arnalds"},
        {"title": "Familiar Ground", "artist": "Ólafur Arnalds"},
    ])
    assert resolved[0]["title"] == "Near Light"
    assert resolved[0]["uri"] == "uri:Near Light"
    assert resolved[1] is None            # выдумка
    assert len(resolved) == 2             # результат выровнен по входу


def test_resolve_songs_uses_canonical_names(client, monkeypatch):
    """У найденных треков названия и исполнители — как в Spotify."""
    _no_user_token(monkeypatch)
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse([_track("Sudno", "Molchat Doma")]),
    )
    resolved = spotify_service.resolve_songs(
        [{"title": "Судно", "artist": "Молчат Дома"}]
    )
    assert resolved[0]["title"] == "Sudno"
    assert resolved[0]["artist"] == "Molchat Doma"


def test_resolve_songs_skipped_without_credentials(client, monkeypatch):
    """Нет ключей Spotify — подборка сохраняется как есть (лучше, чем пустая)."""
    monkeypatch.setattr(spotify_service, "has_token", lambda: False)
    monkeypatch.setattr(spotify_service, "_client_credentials_token", lambda: None)
    songs = [{"title": "Что угодно", "artist": "Кто угодно"}]
    assert spotify_service.resolve_songs(songs) == songs


# --- кэш резолва треков (задача 82, часть 1) ---

def test_resolve_songs_caches_and_reuses(client, monkeypatch):
    """Второй резолв того же трека берётся из кэша — в Spotify не ходим повторно.
    (client-фикстура нужна для таблицы TrackCache в in-memory БД.)"""
    _no_user_token(monkeypatch)
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return FakeResponse([_track("Sea", "This Mortal Coil")])

    monkeypatch.setattr(spotify_service.requests, "get", fake_get)

    first = spotify_service.resolve_songs([{"title": "Sea", "artist": "This Mortal Coil"}])
    assert first[0]["uri"] == "uri:Sea"
    calls_after_first = calls["n"]
    assert calls_after_first > 0

    second = spotify_service.resolve_songs([{"title": "Sea", "artist": "This Mortal Coil"}])
    assert second[0]["uri"] == "uri:Sea"
    assert calls["n"] == calls_after_first        # в Spotify не ходили — кэш


def test_resolve_songs_caches_negative(client, monkeypatch):
    """«Не найдено» тоже кэшируется: выдумка не должна долбить Spotify каждый раз."""
    _no_user_token(monkeypatch)
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return FakeResponse([])       # ничего не нашлось

    monkeypatch.setattr(spotify_service.requests, "get", fake_get)

    assert spotify_service.resolve_songs([{"title": "Нет такого", "artist": "Никто"}]) == [None]
    calls_after_first = calls["n"]
    assert spotify_service.resolve_songs([{"title": "Нет такого", "artist": "Никто"}]) == [None]
    assert calls["n"] == calls_after_first        # отрицательный результат из кэша


def test_unreliable_result_not_cached(client, monkeypatch):
    """Инцидент 22.07: если Spotify НЕ ответил (429/5xx исчерпаны), результат
    не кэшируется как «не найдено» — иначе реальный трек (Woodkid — Run Boy Run)
    навсегда бы отбрасывался."""
    _no_user_token(monkeypatch)
    monkeypatch.setattr(spotify_service.time, "sleep", lambda *_: None)

    # Spotify всё время отдаёт 5xx — достоверного ответа нет
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse(status_code=503),
    )
    song = {"title": "Run Boy Run", "artist": "Woodkid"}
    # трек остаётся непроверенным (как есть), НЕ None
    assert spotify_service.resolve_songs([song]) == [song]

    from models import TrackCache
    from sqlmodel import Session, select

    import database
    with Session(database.engine) as session:
        assert session.exec(select(TrackCache)).all() == []   # ничего не закэшировано


def test_search_retries_on_rate_limit(monkeypatch):
    """429 не должен превращаться в «трек не найден» (инцидент 20.07):
    ждём Retry-After и повторяем."""
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(status_code=429, headers={"Retry-After": "0"})
        return FakeResponse([_track("Sea", "This Mortal Coil")])

    monkeypatch.setattr(spotify_service.requests, "get", fake_get)
    monkeypatch.setattr(spotify_service.time, "sleep", lambda *_: None)

    assert spotify_service._search_track({}, "Sea", "This Mortal Coil") == "uri:Sea"
    assert calls["n"] == 2       # первая попытка + повтор после паузы


def test_search_survives_server_error(monkeypatch):
    """5xx — тоже повод повторить, а не молча потерять трек."""
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(status_code=503)
        return FakeResponse([_track("Loon", "Múm")])

    monkeypatch.setattr(spotify_service.requests, "get", fake_get)
    monkeypatch.setattr(spotify_service.time, "sleep", lambda *_: None)

    assert spotify_service._search_track({}, "Loon", "Múm") == "uri:Loon"


# --- обложка плейлиста из символа-экслибриса (20.07) ---

DESIGN_PAYLOAD = json.dumps({
    "symbol_svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                  '<circle cx="50" cy="50" r="40" fill="#e08b2d"/></svg>',
    "palette_dark": {"bg": "#161311", "surface": "#221c17", "accent": "#e08b2d",
                     "text": "#e9e1d3", "muted": "#a19585"},
})


def test_build_cover_returns_base64_jpeg():
    """Символ превращается в JPEG в пределах лимита Spotify (256 КБ base64)."""
    pytest.importorskip("svglib")
    import base64

    from services.cover_art import MAX_BASE64, build_cover, rasterizer_available

    if not rasterizer_available():
        pytest.skip("нет бэкенда растеризации (pip install rlPyCairo)")

    encoded = build_cover(DESIGN_PAYLOAD)
    assert encoded is not None
    assert len(encoded) <= MAX_BASE64
    assert base64.b64decode(encoded)[:2] == b"\xff\xd8"   # маркер JPEG


def test_build_cover_handles_bad_payload():
    """Кривой паспорт не должен ронять создание плейлиста."""
    from services.cover_art import build_cover

    assert build_cover("не json") is None
    assert build_cover(json.dumps({"palette_dark": {}})) is None   # нет символа


def test_playlist_created_without_cover_when_no_design(client, monkeypatch):
    """Паспорта у книги нет — плейлист всё равно создаётся, cover=None."""
    _add_music()
    monkeypatch.setattr(spotify_service, "has_token", lambda: True)
    captured = {}

    def fake_create(name, songs, cover=None):
        captured["cover"] = cover
        return {"url": "https://open.spotify.com/playlist/x", "found": 1,
                "not_found": [], "cover_set": False}

    monkeypatch.setattr(spotify_service, "create_playlist_from_songs", fake_create)
    assert client.post("/api/v1/books/1/playlist").status_code == 200
    assert captured["cover"] is None


def test_dedupe_songs_unit():
    songs = [
        {"title": "A", "artist": "X"},
        {"title": "a ", "artist": " x"},
        {"title": "B", "artist": "X"},
    ]
    assert len(spotify_service.dedupe_songs(songs)) == 2
