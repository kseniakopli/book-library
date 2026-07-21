# Spotify-интеграция (этап 10.2). Портировано из проекта book-playlist,
# доработки: refresh_token сохраняется в gitignored-файл → авторизация один раз,
# дальше плейлисты создаются без участия браузера.
import json
import logging
import os
import re
import urllib.parse
from difflib import SequenceMatcher
from pathlib import Path

import requests
from dotenv import load_dotenv

log = logging.getLogger("nocturne")

load_dotenv()
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
# Тот же redirect, что был зарегистрирован для book-playlist — ничего менять в
# кабинете Spotify не нужно (бэкенды оба живут на 127.0.0.1:8000)
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
# ugc-image-upload (20.07) — своя обложка плейлиста из символа-экслибриса.
# ⚠ Scope добавлен позже: старый refresh_token его НЕ содержит. Чтобы обложки
# заработали, авторизацию надо пройти заново (удалить spotify_token.json).
SCOPE = "playlist-modify-public playlist-modify-private ugc-image-upload"

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


# Кириллица → латиница. Нужна, потому что русские исполнители в Spotify часто
# записаны транслитом: «Молчат Дома» → Molchat Doma, «Буерак» → Buerak,
# «Судно» → Sudno. Без этого сравнение кириллицы с латиницей даёт 0 сходства,
# и половина русской подборки отсеивалась как «не найдено» (инцидент 20.07).
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _translit(text: str) -> str:
    return "".join(TRANSLIT.get(char, char) for char in text)


def _similar(a: str, b: str) -> float:
    """Похожесть с учётом возможного транслита: сравниваем и как есть,
    и обе строки в латинице — берём лучший результат."""
    first, second = _normalize(a), _normalize(b)
    return max(
        SequenceMatcher(None, first, second).ratio(),
        SequenceMatcher(None, _translit(first), _translit(second)).ratio(),
    )


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


def upload_cover(playlist_id: str, jpeg_base64: str) -> bool:
    """Своя обложка плейлиста (символ книги). Spotify ждёт base64-JPEG в теле,
    до 256 КБ; успех — 202. Обложка не критична: ошибки только логируем.
    Частый случай отказа (403) — токен выдан без scope ugc-image-upload,
    то есть авторизация была до 20.07: помогает переавторизация."""
    try:
        response = requests.put(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/images",
            headers={
                "Authorization": f"Bearer {_access_token()}",
                "Content-Type": "image/jpeg",
            },
            data=jpeg_base64,
            timeout=TIMEOUT * 3,   # картинка грузится дольше обычного запроса
        )
        if response.status_code in (200, 201, 202):
            return True
        log.warning(
            "обложка плейлиста не принята Spotify: %s %s",
            response.status_code, response.text[:200],
        )
    except Exception as e:
        log.warning("обложка плейлиста: запрос не удался: %s", e)
    return False


def create_playlist_from_songs(name: str, songs: list[dict], cover: str | None = None) -> dict:
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

    # своя обложка (символ книги) — украшение: не вышло, плейлист всё равно живой
    cover_set = upload_cover(playlist["id"], cover) if cover else False

    return {
        "url": playlist["external_urls"]["spotify"],
        "found": len(uris),
        "not_found": not_found,
        "cover_set": cover_set,
    }
