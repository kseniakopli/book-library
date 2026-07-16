# Spotify-интеграция (этап 10.2). Портировано из проекта book-playlist,
# доработки: refresh_token сохраняется в gitignored-файл → авторизация один раз,
# дальше плейлисты создаются без участия браузера.
import json
import os
import urllib.parse
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


def _search_track(headers: dict, title: str, artist: str):
    """Поиск трека: сначала строгий по полям, затем свободный (из book-playlist)."""
    for q in (f"track:{title} artist:{artist}", f"{artist} {title}"):
        found = requests.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params={"q": q, "type": "track", "limit": 1},
            timeout=TIMEOUT,
        ).json().get("tracks", {}).get("items", [])
        if found:
            return found[0]["uri"]
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
