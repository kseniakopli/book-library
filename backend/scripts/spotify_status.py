"""Проверка: снят ли лимит (бан) Spotify (инцидент 21.07).

Делает ОДИН лёгкий поисковый запрос к Spotify и говорит, отвечает ли он
нормально или всё ещё держит лимит. Куладаун в самом сервисе живёт в памяти
процесса, поэтому этот скрипт спрашивает Spotify напрямую, а не смотрит на
`in_cooldown` работающего бэкенда.

Запуск из папки backend/:
    python scripts/spotify_status.py
"""

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
import services.spotify as sp


def main() -> None:
    if not (sp.CLIENT_ID and sp.CLIENT_SECRET):
        print("Нет ключей SPOTIFY_CLIENT_ID/SECRET в .env — проверить нечем.")
        return

    token = sp._access_token() if sp.has_token() else sp._client_credentials_token()
    if token is None:
        print("Не удалось получить токен Spotify (проверьте ключи/сеть).")
        return

    headers = {"Authorization": f"Bearer {token}"}
    resp = sp.requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers,
        params={"q": "Arvo Part Spiegel im Spiegel", "type": "track", "limit": 1},
        timeout=sp.TIMEOUT,
    )

    if resp.status_code == 200:
        items = resp.json().get("tracks", {}).get("items", [])
        who = items[0]["name"] if items else "—"
        print(f"✓ Spotify отвечает нормально (200). Тестовый трек: {who}")
        print("Бан снят — можно генерировать музыку и собирать плейлисты.")
    elif resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", 0))
        hours = wait / 3600
        print(f"✗ Лимит ещё держится (429). Retry-After: {wait} с (~{hours:.1f} ч).")
        print("Подождите и проверьте снова. Сервис при этом работает — "
              "музыка сохраняется без проверки треков и плейлистов.")
    else:
        print(f"Spotify ответил {resp.status_code}: {resp.text[:200]}")


if __name__ == "__main__":
    main()
