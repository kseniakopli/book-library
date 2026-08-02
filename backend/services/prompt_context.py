# Контекст книги для AI-промптов (вынесено из services/atmosphere.py — R3, 26.07).
#
# Отдельный модуль, потому что это не «атмосфера», а подготовка входа для модели:
# фактические данные книги + защита от повторов + профиль вкуса. Правится он
# по другим поводам (модель опять что-то выдумала) и другими средствами, чем
# хранение подборок.
import colorsys
import json
import re
from collections import Counter

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

    # Паспорта (з.101). Та же болезнь, что с треками, в двух видах сразу:
    # шрифт модель берёт самый вероятный из разрешённых, а цвет сводит
    # к жанровому дефолту. Лечим по-разному, потому что данные разные:
    # шрифты — перечислимы, их можно запретить поимённо; цвета — нет
    # (значения различаются в третьем знаке, а выглядят одинаково),
    # поэтому им отдаём не список, а СТАТИСТИКУ по библиотеке.
    if category == "design":
        context["avoid_fonts"] = _overused_fonts(session, exclude_book_id=book_id)
        context["palette_stats"] = _palette_summary(session, exclude_book_id=book_id)
        # Зерно ротации набора шрифтов (см. ai_schemas._rotate). В промпт
        # не попадает — format_context печатает только известные ему ключи.
        context["seed"] = book_id
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


AVOID_FONT_MIN_BOOKS = 3   # шрифт считается примелькавшимся с этого числа книг
# Доля разрешённого списка, которую нельзя запрещать одновременно. Без потолка
# после массовой пересборки под порог уходит половина набора, и требование
# становится невыполнимым: модель обязана выбрать из списка и обязана его
# избегать. Тогда она либо игнорирует запрет, либо выдаёт что попало.
AVOID_FONT_MAX_SHARE = 0.4


def _design_payloads(session: Session, exclude_book_id: int) -> list[dict]:
    """Разобранные паспорта всех остальных книг."""
    rows = session.exec(
        select(AISelection).where(
            AISelection.category == "design",
            AISelection.book_id != exclude_book_id,
        )
    ).all()
    out = []
    for row in rows:
        try:
            data = json.loads(row.payload)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _overused_fonts(session: Session, exclude_book_id: int) -> list[str]:
    """Шрифты, которые уже стоят у AVOID_FONT_MIN_BOOKS+ книг.

    Зачем (з.101). Закрытый список (`Literal` в ai_schemas) убрал выдуманные
    гарнитуры, но разнообразия не дал: модель берёт самое вероятное имя уже
    ВНУТРИ списка — на выборке из 10 книг 6 ушли на `IBM Plex Serif`, а до
    этого треть библиотеки сидела на Cormorant Garamond. Список перечислим,
    поэтому здесь запрет поимённый работает — в отличие от цветов.

    ⚠ Считаем ТОЛЬКО шрифты из разрешённого списка. В старых паспортах (до
    появления `Literal`) стоят `Source Sans Pro`, `PT Sans`, `EB Garamond`
    и прочие — выбрать их модель всё равно не может, а в запрете они забивают
    место: на живой базе из 21 имени по делу работали два.

    ⚠ И ограничиваем долю: запретить больше AVOID_FONT_MAX_SHARE набора нельзя,
    иначе требование становится противоречивым — «выбери из списка» против
    «не бери из списка»."""
    from services.ai_schemas import DESIGN_SANS_FONTS, DESIGN_SERIF_FONTS

    payloads = _design_payloads(session, exclude_book_id)

    def pick(field: str, allowed: tuple[str, ...]) -> list[str]:
        counter: dict[str, int] = {}
        for data in payloads:
            name = (data.get(field) or "").strip()
            if name in allowed:
                counter[name] = counter.get(name, 0) + 1
        ranked = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)
        over = [name for name, n in ranked if n >= AVOID_FONT_MIN_BOOKS]
        return over[: max(1, int(len(allowed) * AVOID_FONT_MAX_SHARE))]

    # Заголовочный выбирается из засечных, текстовый — из всего набора,
    # поэтому потолки считаются отдельно. Дубли убираем, порядок сохраняем.
    combined = pick("title_font", DESIGN_SERIF_FONTS) + pick(
        "body_font", DESIGN_SERIF_FONTS + DESIGN_SANS_FONTS
    )
    seen: set[str] = set()
    return [f for f in combined if not (f in seen or seen.add(f))]


def _palette_summary(session: Session, exclude_book_id: int) -> str:
    """Распределение палитр по библиотеке — ОДНОЙ фразой, без списка цветов.

    Почему не список, как со шрифтами (з.101). Перечислять цвета бесполезно
    и вредно сразу по двум причинам. Бесполезно: `#f3ecdd` и `#f4efe4` —
    формально разные значения и один и тот же кремовый, запрет по строке
    ничего не ловит (152 «уникальных» фона на 201 книгу при 75% оранжевых).
    Вредно: замер 02.08 на музыке показал, что перечень запрещённого работает
    подсказкой — названное возвращается в ответ.
    Поэтому отдаём модели ФАКТ о библиотеке и просим его уравновесить.
    Пусто, если паспортов слишком мало, чтобы говорить о перекосе."""
    # Три оси, а не одна. После пересборки 157 книг (02.08) светлый фон
    # выровнялся, а перекос переехал туда, где мы не смотрели: акцент
    # 48% оранжевых, тёмный фон 42 зелёных из 157. Что не измеряется —
    # то и собирает на себя коллапс.
    hues: dict[str, list[str]] = {"light": [], "dark": [], "accent": []}
    for data in _design_payloads(session, exclude_book_id):
        light = data.get("palette_light") or data.get("palette") or {}
        dark = data.get("palette_dark") or {}
        for key, value in (
            ("light", light.get("bg", "")),
            ("dark", dark.get("bg", "")),
            ("accent", light.get("accent", "")),
        ):
            hsl = _hex_to_hsl(value)
            if hsl is not None:
                hues[key].append(_hue_name(*hsl[:2]))

    total = len(hues["light"])
    if total < 10:
        return ""

    # ⚠ Называем ОДИН, самый сильный перекос, а не все сразу. Причины две.
    # Первая: длинный список требований модель выполняет частично и буквально
    # (проверено 02.08 — «не бери тёплое» дало 40% зелёных вместо тёплых).
    # Вторая: перекосы уходят по очереди, и по одному за раз видно, что помогло.
    worst = None
    for axis, label in (
        ("light", "светлый фон"),
        ("dark", "тёмный фон"),
        ("accent", "акцентный цвет"),
    ):
        values = hues[axis]
        if not values:
            continue
        name, count = Counter(values).most_common(1)[0]
        share = round(count * 100 / len(values))
        if share >= 30 and (worst is None or share > worst[0]):
            worst = (share, label, name)

    if worst is None:
        return ""
    share, label, name = worst
    return (
        f"Замер по библиотеке: у {share}% книг {label} — {name}. "
        f"Это перекос генерации, а не стиль сервиса. Выбирай гамму от мира "
        f"ЭТОЙ книги; если она приводит к тому же оттенку — так и оставь, "
        f"но не бери его по умолчанию. В противоположную крайность тоже "
        f"не уходи: цель — разнообразие, а не смена одного любимого цвета "
        f"на другой."
    )


def _hue_name(hue: float, sat: float) -> str:
    """Тон человеческим словом. У серого тон бессмыслен, поэтому низкая
    насыщенность — отдельная категория, а не «красный» по остатку."""
    if sat < 10:
        return "серый, почти без цвета"
    for edge, name in (
        (15, "красный"), (45, "оранжевый"), (70, "жёлтый"), (100, "лаймовый"),
        (160, "зелёный"), (200, "бирюзовый"), (250, "синий"),
        (290, "фиолетовый"), (330, "пурпурный"), (361, "красный"),
    ):
        if hue < edge:
            return name
    return "красный"


def _hex_to_hsl(value: str):
    """#rrggbb → (тон 0–360, насыщенность 0–100, светлота 0–100) или None."""
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        return None
    try:
        r, g, b = (int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return hue * 360, sat * 100, light * 100


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

