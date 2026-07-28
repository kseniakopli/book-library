# Spotify-интеграция (этап 10.2). Портировано из проекта book-playlist,
# доработки: refresh_token сохраняется в gitignored-файл → авторизация один раз,
# дальше плейлисты создаются без участия браузера.
import json
import logging
import os
import random
import threading
import time
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv

from services.track_match import _matches

log = logging.getLogger("nocturne")

# После разделения (R2/задача 88, 26.07) здесь осталось только «как спросить
# Spotify»:
#   1. Конфиг и OAuth-токены
#   2. Куладаун (предохранитель против бана Spotify)
#   3. Поиск трека (HTTP + ретраи)
# Сопоставление названий — services/track_match.py (чистые функции),
# резолв с кэшем и плейлисты — services/playlist.py.

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

# refresh_token живёт рядом с .env и так же не попадает в git.
# ⚠ На проде путь ОБЯЗАН указывать на volume (`SPOTIFY_TOKEN_FILE=/data/...`):
# рядом с кодом файл лежит внутри образа, а образ пересобирается при каждом
# деплое — авторизация Spotify молча слетала бы, и плейлисты переставали
# создаваться до ручной переавторизации (найдено 28.07 при подготовке з.81а).
TOKEN_FILE = Path(
    os.getenv("SPOTIFY_TOKEN_FILE")
    or Path(__file__).resolve().parent.parent / "spotify_token.json"
)

API = "https://api.spotify.com/v1"
TIMEOUT = 10
SEARCH_LIMIT = 5     # смотрим несколько кандидатов, а не только первого


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
    # каталог может не существовать (свой путь через SPOTIFY_TOKEN_FILE)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
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


# --- Глобальный ограничитель параллелизма (задача 82, часть 4) ---
#
# Проблема: квота Spotify считается НА ПРИЛОЖЕНИЕ, а `resolve_songs` поднимает
# по 6 потоков НА КАЖДЫЙ вызов. Две одновременные генерации атмосферы — уже 12
# параллельных запросов, десять тестеров — шестьдесят. Именно так 21.07 приехал
# бан на 21 час (тогда — от массовой пересборки скриптом).
#
# Очередь с персистентностью не нужна: на Fly одна машина и ОДИН воркер uvicorn,
# то есть все походы в Spotify живут в одном процессе — хватает семафора.
# ⚠ Появятся несколько воркеров или машин — этого станет мало, тогда понадобится
# внешний координатор (Redis) или очередь.
#
# Число подобрано с запасом вниз: реальные лимиты Spotify не документированы,
# окно скользящее. Ошибиться в меньшую сторону дёшево (резолв чуть медленнее),
# в большую — бан на часы. Настраивается через SPOTIFY_MAX_PARALLEL.
#
# Ограничиваем ПОИСК: он и есть горячий путь (15 треков на каждую генерацию
# музыки). Создание плейлиста и загрузка обложки — это 2–3 запроса на действие
# пользователя, они всплеска не дают, и заворачивать их смысла нет.
MAX_PARALLEL = int(os.getenv("SPOTIFY_MAX_PARALLEL", "4"))
_slots = threading.Semaphore(MAX_PARALLEL)
# счётчик запросов — чтобы потом посмотреть на РЕАЛЬНУЮ нагрузку, а не гадать
_calls = 0
_calls_lock = threading.Lock()


def calls_made() -> int:
    """Сколько запросов ушло в Spotify с момента старта процесса."""
    return _calls


def _count_call() -> None:
    global _calls
    with _calls_lock:
        _calls += 1


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
            # семафор — на сам поход в сеть: сколько бы потоков ни резолвило
            # треки, одновременно в Spotify уходит не больше MAX_PARALLEL
            with _slots:
                _count_call()
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




