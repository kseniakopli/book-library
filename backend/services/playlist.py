# Плейлисты Spotify: резолв треков через кэш и сборка самих плейлистов
# (вынесено из services/spotify.py — R2/задача 88).
#
# Граница простая: `spotify.py` знает, КАК спросить Spotify (токены, HTTP,
# куладаун), а этот модуль — ЧТО мы у него спрашиваем и что делаем с ответом.
# Зависимость односторонняя: playlist → spotify, никогда наоборот.
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from sqlmodel import Session, col, select

import database
from models import TrackCache
# ВАЖНО: импортируем МОДУЛЬ, а не отдельные функции. `from ... import name`
# связывает имя в момент импорта, и подмена `spotify.has_token` в тестах
# (monkeypatch) на нас бы уже не действовала — тест ушёл бы в реальную сеть.
import services.spotify as spotify
from services.track_match import dedupe_songs   # noqa: F401  (ре-экспорт для роутеров)

log = logging.getLogger("nocturne")


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
    token = None if spotify.in_cooldown() else (
        spotify._access_token() if spotify.has_token() else spotify._client_credentials_token()
    )
    if token is None:
        for i, song, _ in misses:
            results[i] = dict(song)
        return results

    # 2) промахи ищем в Spotify (параллельно)
    headers = {"Authorization": f"Bearer {token}"}

    def resolve(item):
        i, song, key = item
        title, artist = song.get("title", ""), song.get("artist", "")
        found = spotify.find_track(headers, title, artist)

        # Модель иногда меняет поля местами: «Moonshine Freeze — This Is the Kit»
        # (This Is the Kit — исполнитель, Moonshine Freeze — альбом). Один
        # дешёвый повтор наоборот ловит такие случаи целиком.
        if found is None:
            found = spotify.find_track(headers, artist, title)

        # Названия у неочевидных исполнителей модель выдумывает чаще, чем
        # у известных, — и без подстановки верификация возвращала бы плейлист
        # к канону (см. find_any_by_artist). Артист был выбран осмысленно,
        # поэтому берём его реальную запись вместо несуществующей.
        if found is None:
            found = spotify.find_any_by_artist(headers, artist)
            if found is not None and found is not spotify.UNRELIABLE:
                print(
                    f"Подстановка: «{artist} — {title}» не найден, "
                    f"взят «{found['name']}» того же исполнителя"
                )
        return i, key, found

    with ThreadPoolExecutor(max_workers=workers) as pool:
        resolved = list(pool.map(resolve, misses))

    # 3) записываем результаты в кэш (в т.ч. отрицательные) одним коммитом.
    #    UNRELIABLE (Spotify не ответил) НЕ кэшируем — иначе временный сбой
    #    навсегда пометил бы существующий трек как «не найден» (инцидент 22.07).
    miss_song = {i: song for i, song, _ in misses}
    with Session(database.engine) as session:
        for i, key, item in resolved:
            if item is spotify.UNRELIABLE:
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
    if spotify.readonly():
        # задача 103: на проде эта же ссылка живёт в QR печатной карточки
        log.warning(
            "SPOTIFY_READONLY=1 — плейлист %s НЕ обновлён (%s треков)",
            playlist_url, len(uris),
        )
        return False
    playlist_id = playlist_url.rstrip("/").split("/")[-1].split("?")[0]
    headers = {"Authorization": f"Bearer {spotify._access_token()}"}
    try:
        # первый запрос заменяет весь список, последующие — дописывают хвост
        first, rest = uris[:MAX_URIS_PER_REQUEST], uris[MAX_URIS_PER_REQUEST:]
        response = requests.put(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
            headers=headers,
            json={"uris": first},
            timeout=spotify.TIMEOUT * 2,
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
                timeout=spotify.TIMEOUT * 2,
            )
        log.info("плейлист обновлён: %s треков", len(uris))
        return True
    except Exception as e:
        log.warning("не удалось обновить плейлист: %s", e)
    return False


def create_playlist_with_uris(name: str, uris: list[str], cover: str | None = None) -> dict:
    """Создать плейлист из уже найденных uri (поиск сделан в resolve_songs).

    ⚠ Задача 103: в режиме `SPOTIFY_READONLY=1` бросаем исключение, а не
    возвращаем пустой результат. Вызывающий код записывает `result["url"]`
    в `Book.spotify_playlist_url`; тихий возврат заглушки положил бы в базу
    пустую ссылку — то есть локальный прогон испортил бы данные вместо того,
    чтобы их не трогать. Исключение здесь ловится вызывающим (плейлист
    необязателен) и попадает в лог понятной строкой.
    """
    if spotify.readonly():
        raise RuntimeError(
            "SPOTIFY_READONLY=1 — создание плейлиста пропущено "
            f"(«{name}», {len(uris)} треков)"
        )
    headers = {"Authorization": f"Bearer {spotify._access_token()}"}
    playlist = requests.post(
        "https://api.spotify.com/v1/me/playlists",
        headers=headers,
        json={"name": name, "public": True},
        timeout=spotify.TIMEOUT,
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
            timeout=spotify.TIMEOUT,
        )
    cover_set = upload_cover(playlist["id"], cover) if cover else False
    return {
        "url": playlist["external_urls"]["spotify"],
        "found": len(uris),
        "cover_set": cover_set,
    }


def create_playlist_from_songs(name: str, songs: list[dict], cover: str | None = None) -> dict:
    """Ищет треки, создаёт публичный плейлист, возвращает
    {"url", "found", "not_found": [...]}. Ссылка постоянна, пока плейлист жив.

    Резолв идёт через `resolve_songs` — то есть ЧЕРЕЗ КЭШ `TrackCache` (з.82 ч.1),
    а не отдельным поиском на каждый трек. Так эта кнопка не тратит квоту Spotify
    заново: атмосфера уже проверялась при генерации, результаты лежат в кэше.

    ⚠ 28.07: здесь жил вызов `_search_track(...)` без префикса модуля — функция
    осталась в `services/spotify.py` при рефакторинге 26.07, и любое нажатие
    «Создать плейлист» падало с NameError → 500. Тесты не поймали: во всех
    тестах роутера сама `create_playlist_from_songs` подменена заглушкой.
    """
    unique = dedupe_songs(songs)
    resolved = resolve_songs(unique)

    uris = []
    not_found = []
    for song, card in zip(unique, resolved):
        uri = (card or {}).get("uri")
        if uri:
            if uri not in uris:
                uris.append(uri)
        else:
            not_found.append(f"{song.get('artist', '')} — {song.get('title', '')}")

    result = create_playlist_with_uris(name, uris, cover=cover)
    result["not_found"] = not_found
    return result


def upload_cover(playlist_id: str, jpeg_base64: str) -> bool:
    """Своя обложка плейлиста (символ книги). Spotify ждёт base64-JPEG в теле,
    до 256 КБ; успех — 202. Обложка не критична: ошибки только логируем.
    Частый случай отказа (403) — токен выдан без scope ugc-image-upload,
    то есть авторизация была до 20.07: помогает переавторизация."""
    if spotify.readonly():   # задача 103: обложка — тоже запись в чужой аккаунт
        log.warning("SPOTIFY_READONLY=1 — обложка плейлиста %s не загружена", playlist_id)
        return False
    try:
        response = requests.put(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/images",
            headers={
                "Authorization": f"Bearer {spotify._access_token()}",
                "Content-Type": "image/jpeg",
            },
            data=jpeg_base64,
            timeout=spotify.TIMEOUT * 3,   # картинка грузится дольше обычного запроса
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



# ============================================================
# Плейлист книги: создание/обновление по её подборке музыки
# (переехало из services/atmosphere.py — R3, 26.07: это Spotify, а не атмосфера)
# ============================================================
import asyncio                                    # noqa: E402

from models import Book                           # noqa: E402
from services.cover_art import build_cover        # noqa: E402


async def sync_book_playlist(book_id: int, title: str, uris: list[str]) -> None:
    """Создать плейлист книги или обновить существующий. Ошибки не критичны:
    музыка уже сохранена, плейлист можно собрать кнопкой позже."""
    # Spotify в куладауне (лимит) — не дёргаем его, плейлист соберётся позже
    if not uris or not spotify.has_token() or spotify.in_cooldown():
        return
    try:
        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            existing = book.spotify_playlist_url if book else None

        if existing:
            await asyncio.to_thread(
                replace_playlist_items, existing, uris
            )
            return

        design = None
        # локальный импорт: atmosphere импортирует playlist, обратная связь
        # на уровне модуля дала бы круговой импорт
        from services.atmosphere import read_selections

        with Session(database.engine) as session:
            rows = read_selections(session, book_id, "design")
            design = rows[0].payload if rows else None
        cover = build_cover(design) if design else None

        result = await asyncio.to_thread(
            create_playlist_with_uris,
            f"nocturne · {title}", uris, cover,
        )
        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            if book is not None:
                book.spotify_playlist_url = result["url"]
                session.add(book)
                session.commit()
    except Exception as e:
        print(f"Плейлист для книги {book_id} не собрался:", e)



async def rebuild_book_playlist(book_id: int, title: str, songs: list[dict]) -> None:
    """Пересобрать плейлист из уже сохранённых (канонических) треков.
    Резолв идёт через TrackCache — все эти треки уже резолвились при генерации,
    так что походов в Spotify почти нет. Spotify недоступен — тихо выходим:
    подборка уже обновлена, плейлист догонится при следующей генерации.
    Если треков не осталось — плейлист не опустошаем (редкий случай; замена
    пустым списком через /items невозможна, и старый QR полезнее пустого)."""
    if not songs or not spotify.available():
        return
    unique = list({
        (s.get("title", ""), s.get("artist", "")): s for s in songs
    }.values())
    resolved = await asyncio.to_thread(resolve_songs, unique)
    uris = [item["uri"] for item in resolved if item and item.get("uri")]
    # ⚠ 28.07: здесь стояло `_sync_playlist` — имя, которого в модуле нет
    # (второй такой же хвост рефакторинга 26.07). Пересборка плейлиста после
    # удаления трека молча падала: вызов идёт фоновой задачей, исключение
    # оставалось в логе, а пользователь видел «трек удалён» и старый плейлист.
    await sync_book_playlist(book_id, title, uris)

