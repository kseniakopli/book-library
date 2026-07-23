# Spotify-интеграция (этап 10.2). Портировано из проекта book-playlist,
# доработки: refresh_token сохраняется в gitignored-файл → авторизация один раз,
# дальше плейлисты создаются без участия браузера.
import json
import logging
import os
import random
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlmodel import Session, col, select

import database
from models import TrackCache

log = logging.getLogger("nocturne")

# Модуль большой и делится на разделы (навигация; полное вынесение резолва
# и плейлистов в отдельный модуль — задача 88, отложена до крупного захода):
#   1. Конфиг и OAuth-токены
#   2. Матчинг треков (нормализация, похожесть, транслит)
#   3. Куладаун (предохранитель против бана Spotify)
#   4. Поиск и резолв с кэшем (TrackCache)
#   5. Плейлисты (создание/замена, обложка)

# ============================================================
# 1. Конфиг и OAuth-токены
# ============================================================

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


# ============================================================
# 2. Матчинг треков (нормализация, похожесть, транслит)
# ============================================================

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


# ============================================================
# 3. Куладаун (предохранитель против бана Spotify)
# ============================================================

# Предохранитель против «залипания» на лимите Spotify (инцидент 21.07).
# Spotify при серьёзном превышении квоты приложения отдаёт 429 с ОГРОМНЫМ
# Retry-After (наблюдали 78285 с ≈ 21 час). Ждать столько бессмысленно, а
# продолжать долбить — вредно: каждый трек занимал воркер, и сервер переставал
# отвечать даже на GET /books. Решение: как только Spotify просит ждать дольше
# COOLDOWN_THRESHOLD, помечаем сервис «в куладауне» и до его конца в Spotify
# вообще не ходим — резолв просто пропускается (атмосфера сохраняется как есть).
COOLDOWN_THRESHOLD = 30      # с: Retry-After больше — уходим в куладаун целиком
MAX_WAIT = 5                 # с: максимум, сколько вообще ждём на одной попытке
_cooldown_until = 0.0        # monotonic-время, до которого Spotify не трогаем


def in_cooldown() -> bool:
    return time.monotonic() < _cooldown_until


def available() -> bool:
    """Можно ли сейчас резолвить треки: Spotify не в куладауне и есть чем
    авторизоваться (задача 85 — отличить «проверено» от «сохранено при бане»)."""
    if in_cooldown():
        return False
    return has_token() or bool(CLIENT_ID and CLIENT_SECRET)


def _enter_cooldown(seconds: float) -> None:
    global _cooldown_until
    _cooldown_until = time.monotonic() + seconds
    log.warning(
        "Spotify в куладауне на %s с — резолв треков временно отключён", int(seconds)
    )


# ============================================================
# 4. Поиск и резолв с кэшем (TrackCache)
# ============================================================


def _search_request(headers: dict, query: str, attempts: int = 3) -> list | None:
    """Один поиск в Spotify. Уважает Retry-After, ретраит 429/5xx.

    ⚠ Различаем «Spotify ответил» и «не смогли спросить» (инцидент 22.07 —
    ложные негативы в кэше):
      - список (возможно пустой) — Spotify достоверно ответил (200);
      - None — спросить не удалось (куладаун, исчерпанные 429/5xx, сеть).
    Вызывающая сторона по None НЕ кэширует «не найдено»."""
    if in_cooldown():
        return None
    for attempt in range(attempts):
        try:
            response = requests.get(
                "https://api.spotify.com/v1/search",
                headers=headers,
                params={"q": query, "type": "track", "limit": SEARCH_LIMIT},
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            log.warning("поиск трека: сеть недоступна (%s)", e)
            time.sleep(1 + attempt)
            continue

        if response.status_code == 200:
            return response.json().get("tracks", {}).get("items", [])

        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 2 + attempt * 2))
            if wait > COOLDOWN_THRESHOLD:
                # долгий бан: не ждём и не повторяем — уходим в куладаун
                _enter_cooldown(wait)
                return None
            log.warning("поиск трека: лимит Spotify, ждём %s с", wait)
            time.sleep(min(wait, MAX_WAIT) + random.uniform(0, 0.5))
            continue

        if 500 <= response.status_code < 600:
            time.sleep(1 + attempt)
            continue

        log.warning(
            "поиск трека: Spotify ответил %s (%s)",
            response.status_code, response.text[:150],
        )
        return []      # 4xx (кроме 429): Spotify ответил — это достоверное «нет»
    log.warning("поиск трека: исчерпаны попытки для запроса %r", query)
    return None        # не смогли спросить — НЕ кэшируем как «не найдено»


# Отличаем «Spotify достоверно не нашёл» от «спросить не удалось» — второе НЕ
# кэшируется как «не найдено» (инцидент 22.07: ложные негативы от сбоев Spotify).
UNRELIABLE = object()


def find_track(headers: dict, title: str, artist: str):
    """Ищет трек. Возвращает:
      - карточку трека (dict) — найден и совпал по названию+исполнителю;
      - None — Spotify достоверно ответил, но подходящего нет;
      - UNRELIABLE — спросить не удалось (куладаун/лимит/сеть), результат неясен.
    Строго: `_matches` (никаких подстановок), выдумки отсекаются на входе."""
    any_reliable = False
    for q in (f"track:{title} artist:{artist}", f"{artist} {title}"):
        items = _search_request(headers, q)
        if items is None:
            continue                       # недостоверно — пробуем второй запрос
        any_reliable = True
        for item in items:
            if _matches(item, title, artist):
                return item
    return None if any_reliable else UNRELIABLE


def _search_track(headers: dict, title: str, artist: str) -> str | None:
    item = find_track(headers, title, artist)
    if item is UNRELIABLE or item is None:
        return None
    return item["uri"]


# --- Проверка треков ПЕРЕД сохранением атмосферы (20.07) ---
# Модели выдумывают правдоподобные названия («Familiar Ground» у Ólafur Arnalds
# не существует). Решение: не пускать выдумки в сервис вообще — иначе они
# попадут и на страницу книги, и в печатную карточку, и в сцену вечера,
# а плейлист окажется вдвое короче списка.
#
# Для проверки хватает client credentials (ключи приложения): пользовательская
# авторизация нужна только для создания плейлистов. Значит, атмосфера
# валидируется даже до первого входа в Spotify.
_client_token: dict = {"value": None, "expires": 0.0}


def _client_credentials_token() -> str | None:
    """Токен приложения для поиска (без участия пользователя). Кэшируем до
    истечения срока. Нет ключей или отказ — None, проверка тогда пропускается."""
    if not (CLIENT_ID and CLIENT_SECRET):
        return None
    if _client_token["value"] and time.time() < _client_token["expires"]:
        return _client_token["value"]
    try:
        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=TIMEOUT,
        ).json()
    except requests.RequestException as e:
        log.warning("проверка треков: не удалось получить токен (%s)", e)
        return None
    token = resp.get("access_token")
    if not token:
        log.warning("проверка треков: Spotify не выдал токен приложения: %s", resp)
        return None
    _client_token["value"] = token
    _client_token["expires"] = time.time() + resp.get("expires_in", 3600) - 60
    return token




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


def _cache_key(song: dict) -> str:
    """Ключ кэша: нормализованный «артист|название» из запроса модели.
    По нему ищем ранее зарезолвленное — атмосферные подборки сильно пересекаются."""
    artist = (song.get("artist") or "").strip().lower()
    title = (song.get("title") or "").strip().lower()
    return f"{artist}|{title}"


def _card(row) -> dict:
    return {"title": row.title, "artist": row.artist, "uri": row.uri}


def resolve_songs(songs: list[dict], workers: int = 6) -> list[dict | None]:
    """Один проход поиска. Результат ВЫРОВНЕН по входному списку: на месте
    каждого трека либо карточка `{title, artist, uri}` с каноническими данными
    Spotify, либо None (такого трека нет).

    Задача 82 (часть 1): перед запросом к Spotify смотрим в кэш `TrackCache` —
    каждый трек резолвится один раз на всю систему (квота Spotify — на приложение).
    Кэшируем и «не найдено», чтобы выдумки моделей не долбили Spotify повторно.
    БД-операции — вне потоков (SQLite + threads не дружат); в Spotify параллельно
    ходим только за промахами кэша.

    Одного прохода хватает и для атмосферы, и для плейлиста (идея Ксении, 20.07).
    Нет ключей / Spotify в куладауне — промахи возвращаем как есть
    (лучше непроверенная атмосфера, чем пустая); в кэш их НЕ пишем."""
    keys = [_cache_key(s) for s in songs]

    # 1) читаем кэш одним запросом
    with Session(database.engine) as session:
        cached = {
            row.query_key: row
            for row in session.exec(
                select(TrackCache).where(col(TrackCache.query_key).in_(keys))
            ).all()
        }

    results: list[dict | None] = [None] * len(songs)
    misses = []   # (индекс, song, key) — чего нет в кэше
    for i, (song, key) in enumerate(zip(songs, keys)):
        row = cached.get(key)
        if row is not None:
            results[i] = _card(row) if row.found else None
        else:
            misses.append((i, song, key))

    if not misses:
        return results

    # Spotify недоступен — промахи оставляем непроверенными, кэш не портим
    token = None if in_cooldown() else (
        _access_token() if has_token() else _client_credentials_token()
    )
    if token is None:
        for i, song, _ in misses:
            results[i] = dict(song)
        return results

    # 2) промахи ищем в Spotify (параллельно)
    headers = {"Authorization": f"Bearer {token}"}

    def resolve(item):
        i, song, key = item
        found = find_track(headers, song.get("title", ""), song.get("artist", ""))
        return i, key, found

    with ThreadPoolExecutor(max_workers=workers) as pool:
        resolved = list(pool.map(resolve, misses))

    # 3) записываем результаты в кэш (в т.ч. отрицательные) одним коммитом.
    #    UNRELIABLE (Spotify не ответил) НЕ кэшируем — иначе временный сбой
    #    навсегда пометил бы существующий трек как «не найден» (инцидент 22.07).
    miss_song = {i: song for i, song, _ in misses}
    with Session(database.engine) as session:
        for i, key, item in resolved:
            if item is UNRELIABLE:
                results[i] = dict(miss_song[i])   # непроверено, оставляем как есть
                continue
            if item is not None:
                card = {
                    "title": item["name"],
                    "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                    "uri": item["uri"],
                }
                results[i] = card
                session.add(TrackCache(query_key=key, found=True, **card))
            else:
                results[i] = None
                session.add(TrackCache(query_key=key, found=False))
        session.commit()

    return results


# ============================================================
# 5. Плейлисты (создание/замена; обложка — upload_cover выше)
# ============================================================

MAX_URIS_PER_REQUEST = 100   # ограничение Spotify на один запрос


def replace_playlist_items(playlist_url: str, uris: list[str]) -> bool:
    """Заменить содержимое существующего плейлиста (атмосферу перегенерировали).
    Плейлист и его ссылка остаются прежними — QR на печатной карточке не портится.

    ⚠ Путь именно `/items`: старый `/tracks` помечен deprecated, и замена по нему
    молча не срабатывала — в плейлисте оставались прежние треки (20.07)."""
    playlist_id = playlist_url.rstrip("/").split("/")[-1].split("?")[0]
    headers = {"Authorization": f"Bearer {_access_token()}"}
    try:
        # первый запрос заменяет весь список, последующие — дописывают хвост
        first, rest = uris[:MAX_URIS_PER_REQUEST], uris[MAX_URIS_PER_REQUEST:]
        response = requests.put(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
            headers=headers,
            json={"uris": first},
            timeout=TIMEOUT * 2,
        )
        if response.status_code not in (200, 201):
            log.warning(
                "не удалось обновить плейлист: %s %s",
                response.status_code, response.text[:200],
            )
            return False

        while rest:
            chunk, rest = rest[:MAX_URIS_PER_REQUEST], rest[MAX_URIS_PER_REQUEST:]
            requests.post(
                f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
                headers=headers,
                json={"uris": chunk},
                timeout=TIMEOUT * 2,
            )
        log.info("плейлист обновлён: %s треков", len(uris))
        return True
    except Exception as e:
        log.warning("не удалось обновить плейлист: %s", e)
    return False


def create_playlist_with_uris(name: str, uris: list[str], cover: str | None = None) -> dict:
    """Создать плейлист из уже найденных uri (поиск сделан в resolve_songs)."""
    headers = {"Authorization": f"Bearer {_access_token()}"}
    playlist = requests.post(
        "https://api.spotify.com/v1/me/playlists",
        headers=headers,
        json={"name": name, "public": True},
        timeout=TIMEOUT,
    ).json()
    if "external_urls" not in playlist:
        raise RuntimeError(f"Spotify не создал плейлист: {playlist}")

    rest = uris
    while rest:   # Spotify принимает не больше 100 uri за запрос
        chunk, rest = rest[:MAX_URIS_PER_REQUEST], rest[MAX_URIS_PER_REQUEST:]
        requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist['id']}/items",
            headers=headers,
            json={"uris": chunk},
            timeout=TIMEOUT,
        )
    cover_set = upload_cover(playlist["id"], cover) if cover else False
    return {
        "url": playlist["external_urls"]["spotify"],
        "found": len(uris),
        "cover_set": cover_set,
    }


def create_playlist_from_songs(name: str, songs: list[dict], cover: str | None = None) -> dict:
    """Ищет треки, создаёт публичный плейлист, возвращает
    {"url", "found", "not_found": [...]}. Ссылка постоянна, пока плейлист жив."""
    access = _access_token()
    headers = {"Authorization": f"Bearer {access}"}

    uris = []
    not_found = []
    for song in dedupe_songs(songs):
        uri = _search_track(headers, song["title"], song["artist"])
        if uri and uri not in uris:
            uris.append(uri)
        elif not uri:
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
