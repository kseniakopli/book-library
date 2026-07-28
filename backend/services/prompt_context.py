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
AVOID_LIMIT = 25         # столько «уже использованных» пунктов показываем модели
AVOID_MIN_BOOKS = 3      # пункт попадает в список, если встречался у стольких книг


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
                name = f"{item.get('artist', '')} — {item.get('title', '')}".strip(" —")
                key = name.lower()
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

