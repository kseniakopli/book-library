# Spotify-плейлисты (этап 10.2). Сеть всегда замокана — токены не тратятся.
import json
import time

import pytest
from sqlmodel import Session

import database
import services.playlist as playlist_service
import services.spotify as spotify_service
import services.track_match as track_match
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

    monkeypatch.setattr(playlist_service, "create_playlist_from_songs", fake_create)

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
        playlist_service, "create_playlist_from_songs",
        lambda name, songs, cover=None: {
            "url": "https://open.spotify.com/playlist/first",
            "found": 1, "not_found": [], "cover_set": False,
        },
    )
    client.post("/api/v1/books/1/playlist")

    def boom(name, songs, cover=None):
        raise AssertionError("плейлист не должен создаваться повторно")

    monkeypatch.setattr(playlist_service, "create_playlist_from_songs", boom)
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
    assert track_match._matches(
        _track("Spiegel im Spiegel", "Arvo Pärt"), "Spiegel im Spiegel", "Arvo Pärt"
    )
    # приписки ремастера/переиздания не должны мешать
    assert track_match._matches(
        _track("Song To The Siren - Remastered", "This Mortal Coil"),
        "Song To The Siren", "This Mortal Coil",
    )
    # трек с несколькими исполнителями — достаточно совпадения с одним
    assert track_match._matches(
        _track("Solas", "Lisa Gerrard", "Patrick Cassidy"), "Solas", "Patrick Cassidy"
    )


def test_matches_accepts_transliterated_cyrillic():
    """Русские исполнители в Spotify часто латиницей — сравнение через транслит."""
    assert track_match._matches(
        _track("Sudno", "Molchat Doma"), "Судно", "Молчат Дома"
    )
    assert track_match._matches(
        _track("Судно (Борис Рыжий)", "Молчат Дома"), "Судно", "Molchat Doma"
    )
    assert track_match._matches(
        _track("Plyazh", "Buerak"), "Пляж", "Буерак"
    )


def test_matches_rejects_foreign_track():
    """Именно так в плейлист попадал случайный популярный трек."""
    assert not track_match._matches(
        _track("1Train", "A$AP Rocky", "Kendrick Lamar"),
        "The Deer's Cry", "Arvo Pärt",
    )
    # название совпало, а исполнитель — нет: это кавер/однофамилец, не берём
    assert not track_match._matches(
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


def test_resolve_songs_substitutes_invented_tracks(client, monkeypatch):
    """Выдуманное НАЗВАНИЕ заменяется реальной записью того же исполнителя.

    Контракт изменился 02.08 (был: «выдумка → None»). Причина — замер: два
    фильтра работали друг против друга. Промпт гнал модель прочь от заезженного
    канона, а проверка в Spotify канон возвращала, потому что у известных
    исполнителей треки находятся всегда, а у неочевидных модель придумывает
    названия. За одну генерацию отсеивалось девять треков подряд, и все —
    у свежих имён. Разнообразие создавалось и тут же уничтожалось верификацией.
    При этом исполнитель был выбран осмысленно, выдумано было только название.

    Гарантия «несуществующий трек в сервис не попадёт» сохранена: подставляется
    реальная запись, а не выдуманная. Изменилось лишь то, что вместо дырки
    в подборке появляется живой трек нужного артиста."""
    _no_user_token(monkeypatch)
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse([_track("Near Light", "Ólafur Arnalds")]),
    )
    resolved = playlist_service.resolve_songs([
        {"title": "Familiar Ground", "artist": "Ólafur Arnalds"},
    ])
    assert resolved[0]["artist"] == "Ólafur Arnalds"
    assert resolved[0]["title"] == "Near Light"     # реальная вещь этого артиста
    assert resolved[0]["uri"] == "uri:Near Light"
    assert len(resolved) == 1                       # результат выровнен по входу


def test_resolve_songs_substitution_skips_explicit(client, monkeypatch):
    """Омоним не должен притащить в подборку explicit-запись.

    Реальный случай 02.08: Solas — ирландская фолк-группа, но в Spotify есть
    и рэпер Solas, и подстановка взяла у него «Walk Around the Club
    (F**k Everybody)». Имя совпало буквально, сверка по имени такое не ловит.
    Explicit — самый заметный признак «это не тот артист»; у нас литературные
    вечера, мат в подборке невозможен ни при каком совпадении."""
    _no_user_token(monkeypatch)
    rude = _track("Walk Around the Club", "Solas")
    rude["explicit"] = True
    monkeypatch.setattr(
        spotify_service.requests, "get", lambda *a, **kw: FakeResponse([rude])
    )
    resolved = playlist_service.resolve_songs([
        {"title": "The Merry Sisters of Fate", "artist": "Solas"},
    ])
    assert resolved[0] is None


def test_resolve_songs_does_not_substitute_other_artist(client, monkeypatch):
    """Подстановка не должна тащить чужого исполнителя.

    Это главный риск послабления: свободный поиск без сверки уже приводил
    к рэп-треку в плейлисте «Демона из Пустоши» (инцидент 20.07). Сверку
    названия мы сняли намеренно, сверку артиста — нет."""
    _no_user_token(monkeypatch)
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse([_track("Some Rap Song", "Another Artist")]),
    )
    resolved = playlist_service.resolve_songs([
        {"title": "Familiar Ground", "artist": "Ólafur Arnalds"},
    ])
    assert resolved[0] is None


def test_resolve_songs_uses_canonical_names(client, monkeypatch):
    """У найденных треков названия и исполнители — как в Spotify."""
    _no_user_token(monkeypatch)
    monkeypatch.setattr(
        spotify_service.requests, "get",
        lambda *a, **kw: FakeResponse([_track("Sudno", "Molchat Doma")]),
    )
    resolved = playlist_service.resolve_songs(
        [{"title": "Судно", "artist": "Молчат Дома"}]
    )
    assert resolved[0]["title"] == "Sudno"
    assert resolved[0]["artist"] == "Molchat Doma"


def test_resolve_songs_skipped_without_credentials(client, monkeypatch):
    """Нет ключей Spotify — подборка сохраняется как есть (лучше, чем пустая)."""
    monkeypatch.setattr(spotify_service, "has_token", lambda: False)
    monkeypatch.setattr(spotify_service, "_client_credentials_token", lambda: None)
    songs = [{"title": "Что угодно", "artist": "Кто угодно"}]
    assert playlist_service.resolve_songs(songs) == songs


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

    first = playlist_service.resolve_songs([{"title": "Sea", "artist": "This Mortal Coil"}])
    assert first[0]["uri"] == "uri:Sea"
    calls_after_first = calls["n"]
    assert calls_after_first > 0

    second = playlist_service.resolve_songs([{"title": "Sea", "artist": "This Mortal Coil"}])
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

    assert playlist_service.resolve_songs([{"title": "Нет такого", "artist": "Никто"}]) == [None]
    calls_after_first = calls["n"]
    assert playlist_service.resolve_songs([{"title": "Нет такого", "artist": "Никто"}]) == [None]
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
    assert playlist_service.resolve_songs([song]) == [song]

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

    monkeypatch.setattr(playlist_service, "create_playlist_from_songs", fake_create)
    assert client.post("/api/v1/books/1/playlist").status_code == 200
    assert captured["cover"] is None


def test_dedupe_songs_unit():
    songs = [
        {"title": "A", "artist": "X"},
        {"title": "a ", "artist": " x"},
        {"title": "B", "artist": "X"},
    ]
    assert len(playlist_service.dedupe_songs(songs)) == 2


class _PlaylistResponse:
    """Ответ Spotify на создание плейлиста / добавление треков."""

    def __init__(self, payload):
        self.status_code = 200
        self.headers = {}
        self.text = ""
        self._payload = payload

    def json(self):
        return self._payload


def test_create_playlist_from_songs_builds_uris_and_reports_missing(monkeypatch):
    """Регрессия 28.07: внутри функции вызывался `_search_track` без префикса
    модуля — функция осталась в services/spotify.py после рефакторинга 26.07,
    и КАЖДОЕ нажатие «Создать плейлист» падало с NameError → 500.

    Мимо тестов прошло потому, что во всех тестах роутера подменялась сама
    `create_playlist_from_songs` — её тело не выполнялось ни разу. Этот тест
    гоняет именно тело: резолв (через кэш) + сборка uri + отчёт о ненайденных.
    """
    songs = [
        {"title": "Song A", "artist": "Artist A"},
        {"title": "Выдумка", "artist": "Никто"},
    ]
    # резолв возвращает карточки, выровненные по входу: вторая — «не найдено»
    monkeypatch.setattr(
        playlist_service,
        "resolve_songs",
        lambda items, **kw: [
            {"title": "Song A", "artist": "Artist A", "uri": "spotify:track:a"},
            None,
        ],
    )
    monkeypatch.setattr(spotify_service, "_access_token", lambda: "token")

    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent[url] = json
        if url.endswith("/me/playlists"):
            return _PlaylistResponse({
                "id": "pl1",
                "external_urls": {"spotify": "https://open.spotify.com/playlist/pl1"},
            })
        return _PlaylistResponse({})

    monkeypatch.setattr(playlist_service.requests, "post", fake_post)

    result = playlist_service.create_playlist_from_songs("nocturne · Книга", songs)

    assert result["url"] == "https://open.spotify.com/playlist/pl1"
    assert result["found"] == 1
    assert result["not_found"] == ["Никто — Выдумка"]
    # найденный трек действительно ушёл в плейлист
    assert sent["https://api.spotify.com/v1/playlists/pl1/items"] == {
        "uris": ["spotify:track:a"]
    }


def test_parallel_searches_are_capped(monkeypatch):
    """Задача 82 ч.4: сколько бы потоков ни резолвило треки, одновременно
    в Spotify уходит не больше MAX_PARALLEL запросов.

    Квота Spotify считается НА ПРИЛОЖЕНИЕ, а `resolve_songs` поднимает 6 потоков
    на КАЖДЫЙ вызов: две одновременные генерации — уже 12 запросов, десять
    тестеров — шестьдесят. Так 21.07 приехал бан на 21 час.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    now = 0  # сколько запросов «в полёте» прямо сейчас
    peak = 0           # максимум за прогон — это и проверяем
    lock = threading.Lock()

    def fake_get(*a, **kw):
        nonlocal now, peak
        with lock:
            now += 1
            peak = max(peak, now)
        time.sleep(0.02)          # держим слот, чтобы потоки успели столкнуться
        with lock:
            now -= 1
        return FakeResponse([])

    monkeypatch.setattr(spotify_service.requests, "get", fake_get)
    before = spotify_service.calls_made()

    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(lambda _: spotify_service._search_request({}, "q"), range(20)))

    assert peak <= spotify_service.MAX_PARALLEL, (
        f"одновременно ушло {peak} запросов при лимите {spotify_service.MAX_PARALLEL}"
    )
    # счётчик считает реальные походы в сеть — по нему потом смотрим нагрузку
    assert spotify_service.calls_made() - before == 20


def test_token_saved_to_configured_path(tmp_path, monkeypatch):
    """refresh_token пишется по TOKEN_FILE, создавая каталог при необходимости.

    На проде путь ведёт на volume (`SPOTIFY_TOKEN_FILE=/data/spotify_token.json`):
    рядом с кодом файл жил бы внутри образа и пропадал при каждом деплое —
    авторизация Spotify молча слетала бы (28.07).
    """
    target = tmp_path / "data" / "spotify_token.json"   # каталога ещё нет
    monkeypatch.setattr(spotify_service, "TOKEN_FILE", target)
    monkeypatch.setattr(
        spotify_service.requests,
        "post",
        lambda *a, **kw: type("R", (), {"json": lambda self: {"refresh_token": "r1"}})(),
    )

    assert spotify_service.has_token() is False
    spotify_service.exchange_code("code-from-callback")

    assert spotify_service.has_token() is True
    assert json.loads(target.read_text(encoding="utf-8"))["refresh_token"] == "r1"
