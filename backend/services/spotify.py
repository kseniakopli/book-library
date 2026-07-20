# Spotify-интеграция (этап 10.2). Портировано из проекта book-playlist,
# доработки: refresh_token сохраняется в gitignored-файл → авторизация один раз,
# дальше плейлисты создаются без участия браузера.
import json
import os
import re
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
# Тот же redirect, что был зарегистрирован для book-playlist — ничего менять в
# кабинете Spotify не нужно (бэкенды оба живут на 127.0.0.1:8000)
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
SCOPE = "playlist-modify-public playlist-modify-private"

# refresh_token живёт рядом с .env и так же не попадает в git
TOKEN_FILE = Path(__file__).resolve().parent.parent / "spotify_token.json"

TIMEOUT = 10


def auth_url(state: str = "") -> str:
    """Ссылка на окно авторизации Spotify; state вернётся в callback (book_id)."""
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)


def exchange_code(code: str) -> None:
    """Меняем одноразовый код на токены и сохраняем refresh_token."""
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=TIMEOUT,
    ).json()
    if "refresh_token" not in resp:
        raise RuntimeError(f"Spotify не выдал refresh_token: {resp}")
    TOKEN_FILE.write_text(
        json.dumps({"refresh_token": resp["refresh_token"]}), encoding="utf-8"
    )


def has_token() -> bool:
    return TOKEN_FILE.exists()


def _access_token() -> str:
    """Свежий access_token по сохранённому refresh_token (живёт ~час, берём каждый раз).
    Spotify иногда присылает новый refresh_token — тогда пересохраняем."""
    refresh = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))["refresh_token"]
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=TIMEOUT,
    ).json()
    if "access_token" not in resp:
        raise RuntimeError(f"Не удалось обновить токен Spotify: {resp}")
    if resp.get("refresh_token"):
        TOKEN_FILE.write_text(
            json.dumps({"refresh_token": resp["refresh_token"]}), encoding="utf-8"
        )
    return resp["access_token"]


# Пороги похожести при проверке найденного трека (инцидент 20.07 — см. _matches).
TITLE_RATIO = 0.72
ARTIST_RATIO = 0.6
SEARCH_LIMIT = 5     # смотрим несколько кандидатов, а не только первого


def _normalize(value: str) -> str:
    """Приводим название/исполнителя к сравнимому виду: нижний регистр, без
    приписок вроде «- Remastered 2011», «(feat. X)», «[Live]» и без пунктуации.
    Без этого «Song To The Siren - Remastered» не совпало бы с оригиналом."""
    text = value.lower()
    text = re.split(r"\s+-\s+|\s*[\(\[]", text)[0]      # хвост после «-» или скобки
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _matches(item: dict, title: str, artist: str) -> bool:
    """Действительно ли найденное — тот трек, который просили.

    Инцидент 20.07: в плейлист «Демона из Пустоши» попал рэп-трек. Причина —
    свободный поиск брал ПЕРВЫЙ результат без проверки: если выдуманного моделью
    трека в Spotify нет, поиск возвращает что-нибудь популярное по отдельным
    словам. Теперь сверяем название и исполнителя, и лучше не добавить трек,
    чем добавить чужой."""
    if _similar(item.get("name", ""), title) < TITLE_RATIO:
        return False
    # у трека может быть несколько исполнителей — достаточно совпадения с одним
    return any(
        _similar(performer.get("name", ""), artist) >= ARTIST_RATIO
        for performer in item.get("artists", [])
    )


def _search_track(headers: dict, title: str, artist: str):
    """Поиск трека: строгий запрос по полям, затем свободный.
    Кандидаты проверяются `_matches` — непохожие отбрасываются."""
    for q in (f"track:{title} artist:{artist}", f"{artist} {title}"):
        found = requests.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params={"q": q, "type": "track", "limit": SEARCH_LIMIT},
            timeout=TIMEOUT,
        ).json().get("tracks", {}).get("items", [])
        for item in found:
            if _matches(item, title, artist):
                return item["uri"]
    return None


def dedupe_songs(songs: list[dict]) -> list[dict]:
    """Убираем дубли по (артист, название) без учёта регистра (из book-playlist)."""
    seen = set()
    unique = []
    for s in songs:
        key = (s["artist"].strip().lower(), s["title"].strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def create_playlist_from_songs(name: str, songs: list[dict]) -> dict:
    """Ищет треки, создаёт публичный плейлист, возвращает
    {"url", "found", "not_found": [...]}. Ссылка постоянна, пока плейлист жив."""
    access = _access_token()
    headers = {"Authorization": f"Bearer {access}"}

    uris = []
    not_found = []
    for song in dedupe_songs(songs):
        uri = _search_track(headers, song["title"], song["artist"])
        if uri:
            uris.append(uri)
        else:
            not_found.append(f"{song['artist']} — {song['title']}")

    playlist = requests.post(
        "https://api.spotify.com/v1/me/playlists",
        headers=headers,
        json={"name": name, "public": True},
        timeout=TIMEOUT,
    ).json()
    if "external_urls" not in playlist:
        raise RuntimeError(f"Spotify не создал плейлист: {playlist}")

    if uris:
        requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist['id']}/items",
            headers=headers,
            json={"uris": uris},
            timeout=TIMEOUT,
        )

    return {
        "url": playlist["external_urls"]["spotify"],
        "found": len(uris),
        "not_found": not_found,
    }
