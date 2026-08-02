# Контекст книги для AI-промптов (вынесено из services/atmosphere.py — R3, 26.07).
#
# Отдельный модуль, потому что это не «атмосфера», а подготовка входа для модели:
# фактические данные книги + защита от повторов + профиль вкуса. Правится он
# по другим поводам (модель опять что-то выдумала) и другими средствами, чем
# хранение подборок.
import json
import re

from sqlmodel import Session, select

from models import AISelection, Book
from services.taste import atmosphere_taste

MAX_DESCRIPTION = 1200   # символов аннотации в промпт (хватает, не раздувает)
# Замер 02.08 (scripts/explore_avoid.py): порог прошли 40 пунктов, а показывали
# 25 — пятнадцать самых затасканных треков в промпт не уезжали вовсе.
AVOID_LIMIT = 45
AVOID_MIN_BOOKS = 3      # пункт попадает в список, если встречался у стольких книг

# --- Повторы на уровне ИСПОЛНИТЕЛЯ (з.99, разбор 02.08) ---
#
# Замер по 52 плейлистам: Agnes Obel у 12 книг (23% библиотеки), Bon Iver у 8,
# Radiohead / Sia / Portishead / Dead Can Dance по 7. При этом её треки Riverside,
# The Curse и Familiar ВСЕ ТРИ уже лежали в avoid — и не помогали: запрет по
# названию модель обходит следующим треком того же артиста.
# Механизм работал (проверено: вся музыка сгенерирована после его появления
# 22.07), но не на том уровне, на котором сходится модель.
AVOID_ARTIST_MIN_BOOKS = 3
AVOID_ARTIST_LIMIT = 20

# Хвосты канонических названий Spotify: «The Host of Seraphim» и
# «The Host of Seraphim - Remastered» для точного ключа были разными треками,
# и счётчик дробился. Та же болезнь, что с перефразами еды 24.07, только здесь
# её приносит не модель, а каталог.
_SPOTIFY_SUFFIX = re.compile(
    r"\s*-\s*(remaster(ed)?|.*\bremaster(ed)?|.*\bversion|.*\bedit|.*\bmix|"
    r"single|mono|stereo|live|bonus track|deluxe)\b.*$",
    re.IGNORECASE,
)


def build_book_context(
    session: Session, book_id: int, category: str, user_id: int
) -> dict:
    """Фактический контекст книги для промпта (22.07).

    Зачем: модель знает не каждую книгу и для малоизвестных **угадывает по
    названию** — «Капля духов в открытую рану» превратилась у Claude в арабский
    Дубай, хотя книга о московском парфюмерном мире. Аннотация из Google Books
    у нас уже есть — просто не доезжала до промпта.

    `avoid` борется с mode collapse: генерации независимы, и модель не знает,
    что бефстроганов с сельдью она уже советовала в каждой русской книге.
    Показываем ей самое затасканное по библиотеке — с просьбой не повторяться."""
    book = session.get(Book, book_id)
    if book is None:
        return {}

    genres = ""
    try:
        genres = ", ".join((json.loads(book.categories) or [])[:3])
    except (TypeError, ValueError):
        genres = ""

    context = {
        "description": (book.description or "")[:MAX_DESCRIPTION],
        "genres": genres,
        "year": book.published_year,
        "avoid": _overused_items(session, category, exclude_book_id=book_id),
    }
    # Только для музыки: коллапс там сидит на исполнителях, а не на треках.
    if category == "music":
        context["avoid_artists"] = _overused_artists(session, exclude_book_id=book_id)
    # задача 26 ч.4: «память вкуса» — что читателю заходило и не заходило
    # в этой категории. У моделей памяти нет, поэтому подкладываем её сами.
    context.update(atmosphere_taste(session, user_id, category))
    return context


def _item_key(name: str) -> str:
    """Ключ повтора для еды/ароматов: первые два слова названия.

    Зачем (24.07): модели перефразируют названия — «Яблочный пирог с корицей»,
    «Яблочный пирог по-ирландски», «Яблочный пирог со сливками» для точного
    счётчика были тремя разными блюдами «у одной книги каждое», и порог
    AVOID_MIN_BOOKS не срабатывал никогда (замер по базе: «яблочный пирог»
    у 5 книг из 19, в avoid — ни разу). Обрезка до двух слов ловит главный
    паттерн перефраза — стабильное начало + разные хвосты."""
    return " ".join(re.findall(r"\w+", name.lower())[:2])


def track_key(artist: str, title: str) -> tuple[str, str]:
    """Отображаемое имя трека и ключ повтора для него.

    Вынесено наружу (02.08), чтобы разведочный скрипт `explore_avoid.py` не
    держал СВОЮ копию правила: он её уже держал, и после правки ключа его отчёт
    показывал старую картину. Считать и мерить обязано одно и то же место."""
    name = f"{artist or ''} — {title or ''}".strip(" —")
    return name, _SPOTIFY_SUFFIX.sub("", name).lower().strip()


def artist_key(artist: str) -> str:
    """Первый исполнитель трека. Spotify отдаёт коллаборации через запятую
    («The Cinematic Orchestra, Patrick Watson»), и без обрезки каждая пара
    считалась бы отдельным артистом."""
    return (artist or "").split(",")[0].strip()


def _overused_items(session: Session, category: str, exclude_book_id: int) -> list[str]:
    """Названия, которые уже примелькались в этой категории по всей библиотеке
    (встречаются у AVOID_MIN_BOOKS+ книг). Для музыки — «Исполнитель — Трек»
    точным совпадением (названия канонизирует Spotify); для еды/ароматов —
    по нормализованному ключу (_item_key), в список идёт самое короткое из
    встреченных названий («Яблочный пирог» обобщает свои вариации)."""
    if category not in ("music", "food", "aroma"):
        return []

    rows = session.exec(
        select(AISelection).where(
            AISelection.category == category,
            AISelection.book_id != exclude_book_id,
        )
    ).all()

    books_by_item: dict[str, dict] = {}
    for row in rows:
        try:
            items = json.loads(row.payload)
        except (TypeError, ValueError):
            continue
        for item in items:
            if category == "music":
                name, key = track_key(item.get("artist", ""), item.get("title", ""))
            else:
                name = (item.get("title") or "").strip()
                key = _item_key(name)
            if not key:
                continue
            entry = books_by_item.setdefault(key, {"books": set(), "name": name})
            entry["books"].add(row.book_id)
            if len(name) < len(entry["name"]):
                entry["name"] = name

    ranked = sorted(books_by_item.values(), key=lambda e: len(e["books"]), reverse=True)
    return [e["name"] for e in ranked if len(e["books"]) >= AVOID_MIN_BOOKS][:AVOID_LIMIT]


def _overused_artists(session: Session, exclude_book_id: int) -> list[str]:
    """Исполнители, примелькавшиеся по библиотеке (у AVOID_ARTIST_MIN_BOOKS+ книг).

    Считаем ПЕРВОГО исполнителя трека: в поле artist Spotify отдаёт всех
    участников через запятую («The Cinematic Orchestra, Patrick Watson»),
    и коллаборации иначе считались бы отдельными артистами.
    Имя для промпта берём в исходном написании — самое частое из встреченных,
    чтобы не показывать модели «agnes obel» строчными."""
    rows = session.exec(
        select(AISelection).where(
            AISelection.category == "music",
            AISelection.book_id != exclude_book_id,
        )
    ).all()

    books_by_artist: dict[str, dict] = {}
    for row in rows:
        try:
            items = json.loads(row.payload)
        except (TypeError, ValueError):
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            artist = artist_key(item.get("artist", ""))
            if not artist:
                continue
            entry = books_by_artist.setdefault(
                artist.lower(), {"books": set(), "name": artist}
            )
            entry["books"].add(row.book_id)

    ranked = sorted(books_by_artist.values(), key=lambda e: len(e["books"]), reverse=True)
    return [
        e["name"] for e in ranked if len(e["books"]) >= AVOID_ARTIST_MIN_BOOKS
    ][:AVOID_ARTIST_LIMIT]

