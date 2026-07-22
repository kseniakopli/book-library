"""Дымовой прогон внешних систем перед релизом (задача 83).

Зачем: юнит-тесты гоняют МОКИ, поэтому не ловят изменения контракта внешних
API. За 20–22.07 так проскочили три инцидента Spotify (deprecated `temperature`,
429-бан, устаревший `/tracks`). Этот скрипт бьёт по ЖИВЫМ сервисам одним
лёгким запросом и проверяет, что формат ответа прежний.

НЕ в CI (нужны реальные ключи и сеть) — прогонять руками перед выкладкой
и после подозрительных инцидентов.

Запуск из папки backend/:
    python scripts/smoke_external.py
"""

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import services.spotify as sp
from google_books import _books_request

ok_count = 0
fail_count = 0


def check(name: str, passed: bool, detail: str = "") -> None:
    global ok_count, fail_count
    mark = "✓" if passed else "✗"
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    if passed:
        ok_count += 1
    else:
        fail_count += 1


def check_spotify() -> None:
    print("Spotify:")
    if not (sp.CLIENT_ID and sp.CLIENT_SECRET):
        check("ключи", False, "нет SPOTIFY_CLIENT_ID/SECRET в .env")
        return

    token = sp._access_token() if sp.has_token() else sp._client_credentials_token()
    if token is None:
        check("токен", False, "не выдан (ключи/сеть/бан)")
        return
    check("токен", True)

    resp = sp.requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "Arvo Part Spiegel im Spiegel", "type": "track", "limit": 1},
        timeout=sp.TIMEOUT,
    )
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", 0))
        check("поиск", False, f"лимит 429, Retry-After {wait} с (~{wait / 3600:.1f} ч)")
        return
    if resp.status_code != 200:
        check("поиск", False, f"код {resp.status_code}: {resp.text[:120]}")
        return
    check("поиск", True, "200")

    # контракт ответа: то, на что опирается find_track / resolve_songs
    items = resp.json().get("tracks", {}).get("items", [])
    check("формат: tracks.items", bool(items), f"{len(items)} шт")
    if items:
        track = items[0]
        check("поле name", "name" in track)
        check("поле uri", isinstance(track.get("uri"), str))
        artists = track.get("artists")
        check(
            "поле artists[].name",
            isinstance(artists, list) and artists and "name" in artists[0],
        )


def check_google_books() -> None:
    print("Google Books:")
    try:
        # _books_request возвращает СПИСОК items (или [] при неудаче)
        items = _books_request("Мастер и Маргарита Булгаков", max_results=1)
    except Exception as e:
        check("запрос", False, str(e)[:120])
        return
    check("запрос + формат items", bool(items), f"{len(items)} шт")
    if items:
        info = items[0].get("volumeInfo", {})
        check("поле volumeInfo.title", "title" in info)


def main() -> None:
    print("Дымовой прогон внешних систем\n")
    check_spotify()
    print()
    check_google_books()
    print(f"\nИтог: {ok_count} ок, {fail_count} провалов.")
    if fail_count:
        print("⚠ Есть провалы — проверьте контракт/доступность до релиза.")


if __name__ == "__main__":
    main()
