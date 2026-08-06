# Сопоставление названий треков (вынесено из services/spotify.py — R2/задача 88).
#
# Здесь только ЧИСТЫЕ функции: ни сети, ни базы, ни ключей. Поэтому раздел
# тестируется без моков и правится отдельно от всего остального — а правится он
# чаще прочего Spotify-кода (каждый раз, когда очередной исполнитель
# не находится из-за транслита или приписки в названии).
import re

from services.text_match import similarity

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


# ⚠ Транслит и сама мера похожести уехали в `services/text_match.py`
# (задача 126): та же механика понадобилась книгам, а две копии значили бы
# две правки там, где нужна одна. Здесь остаётся нормализация — она у треков
# своя, из-за приписок вроде «- Remastered 2011» и «(feat. X)».
def _similar(a: str, b: str) -> float:
    """Похожесть названий треков: нормализуем по-своему, меряем общим ядром."""
    return similarity(_normalize(a), _normalize(b))


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

