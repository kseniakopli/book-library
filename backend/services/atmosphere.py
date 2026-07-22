# Доменный слой «Атмосферы» (задачи 78/79 из ревью 19.07).
#
# Раньше всё это жило в routers/atmosphere.py, из-за чего routers/books.py делал
# локальный импорт внутри функции, чтобы обойти круговой импорт. Теперь логика
# здесь, роутеры импортируют её сверху — граница модулей на месте.
#
# Добавление новой категории = генератор в services/ai.py + запись в CATEGORIES.
import asyncio
import json

from sqlmodel import Session, select

import database
from constants import (
    EVENT_AI_AROMA,
    EVENT_AI_DESIGN,
    EVENT_AI_FOOD,
    EVENT_AI_MUSIC,
    SOURCE_CLAUDE,
)
from events import log_event
from models import AISelection, Book, UserBook
from services.ai import (
    generate_aroma,
    generate_design,
    generate_food,
    generate_music,
    start_ai_metrics,
    take_ai_metrics,
)
import services.spotify as spotify_service
from deps import CURRENT_USER_ID
from services.cover_art import build_cover
from services.spotify import resolve_songs
from services.taste import atmosphere_taste


async def _generate_design_selections(
    title: str, author: str, lang: str = "ru", context: dict | None = None
) -> dict:
    """Приводим паспорт к общему контракту генераторов: {источник: модель}.
    Контекст книги (аннотация/жанры) помогает и здесь: символ и палитра
    по реальному сюжету точнее, чем по одному названию."""
    result = await generate_design(title, author, lang, context)
    return {SOURCE_CLAUDE: result}


# Конфигурация категорий. Контракт генератора: async (title, author, lang) -> {source: BaseModel}.
# payload — что кладём в AISelection.payload (JSON-строка),
# explanation — короткий текст-пояснение для UI.
async def verify_music_results(results: dict, book_id: int, title: str) -> dict:
    """Постобработка музыки (20.07, идея Ксении): ОДИН проход поиска в Spotify
    и сразу — готовый плейлист.

    Зачем: модели выдумывают правдоподобные названия («Familiar Ground»
    у Ólafur Arnalds не существует). Такой трек нельзя пускать в сервис —
    он оказался бы и на странице книги, и в печатной карточке. Раньше поиск
    шёл дважды: сначала проверка атмосферы, потом создание плейлиста по кнопке.
    Теперь один проход даёт и канонические названия для полки, и `uri` для
    плейлиста, а кнопка на странице сразу «Открыть плейлист».

    Плейлист уже был — заменяем его содержимое: ссылка (и QR на печатной
    карточке) остаётся прежней. Пользовательской авторизации нет — просто
    отсеиваем несуществующее (поиск работает и по ключам приложения),
    плейлист создастся потом кнопкой."""
    unique: dict[tuple[str, str], dict | None] = {}
    for result in results.values():
        for song in result.songs:
            unique.setdefault((song.title.strip(), song.artist.strip()), None)
    if not unique:
        return results

    keys = list(unique)
    songs = [{"title": t, "artist": a} for t, a in keys]
    # sync-функция (requests в нескольких потоках) уезжает из цикла событий;
    # результат выровнен по входу: карточка Spotify или None
    resolved = await asyncio.to_thread(resolve_songs, songs)
    unique = dict(zip(keys, resolved))

    missing = [f"{a} — {t}" for (t, a), item in unique.items() if item is None]
    if missing:
        print(f"Атмосфера: отброшены несуществующие треки: {'; '.join(missing)}")

    for result in results.values():
        kept = []
        for song in result.songs:
            item = unique.get((song.title.strip(), song.artist.strip()))
            if item:
                song.title = item["title"]
                song.artist = item["artist"]
                kept.append(song)
        result.songs = kept

    uris = [item["uri"] for item in resolved if item and item.get("uri")]
    await _sync_playlist(book_id, title, uris)
    return results


async def _sync_playlist(book_id: int, title: str, uris: list[str]) -> None:
    """Создать плейлист книги или обновить существующий. Ошибки не критичны:
    музыка уже сохранена, плейлист можно собрать кнопкой позже."""
    # Spotify в куладауне (лимит) — не дёргаем его, плейлист соберётся позже
    if not uris or not spotify_service.has_token() or spotify_service.in_cooldown():
        return
    try:
        with Session(database.engine) as session:
            book = session.get(Book, book_id)
            existing = book.spotify_playlist_url if book else None

        if existing:
            await asyncio.to_thread(
                spotify_service.replace_playlist_items, existing, uris
            )
            return

        design = None
        with Session(database.engine) as session:
            rows = read_selections(session, book_id, "design")
            design = rows[0].payload if rows else None
        cover = build_cover(design) if design else None

        result = await asyncio.to_thread(
            spotify_service.create_playlist_with_uris,
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


CATEGORIES = {
    "music": {
        "generate": generate_music,
        # проверка треков — отдельным async-шагом после генерации (см. выше)
        "postprocess": verify_music_results,
        "payload": lambda r: json.dumps(
            [s.model_dump() for s in r.songs], ensure_ascii=False
        ),
        "explanation": lambda r: r.explanation,
        "event": EVENT_AI_MUSIC,
    },
    "design": {
        "generate": _generate_design_selections,
        "payload": lambda r: r.model_dump_json(),
        "explanation": lambda r: r.statement,
        "event": EVENT_AI_DESIGN,
    },
    "food": {
        "generate": generate_food,
        "payload": lambda r: json.dumps(
            [i.model_dump() for i in r.items], ensure_ascii=False
        ),
        "explanation": lambda r: r.explanation,
        "event": EVENT_AI_FOOD,
    },
    "aroma": {
        "generate": generate_aroma,
        "payload": lambda r: json.dumps(
            [i.model_dump() for i in r.items], ensure_ascii=False
        ),
        "explanation": lambda r: r.explanation,
        "event": EVENT_AI_AROMA,
    },
}


MAX_DESCRIPTION = 1200   # символов аннотации в промпт (хватает, не раздувает)
AVOID_LIMIT = 25         # столько «уже использованных» пунктов показываем модели
AVOID_MIN_BOOKS = 3      # пункт попадает в список, если встречался у стольких книг


def build_book_context(session: Session, book_id: int, category: str) -> dict:
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
    context.update(atmosphere_taste(session, CURRENT_USER_ID, category))
    return context


def _overused_items(session: Session, category: str, exclude_book_id: int) -> list[str]:
    """Названия, которые уже примелькались в этой категории по всей библиотеке
    (встречаются у AVOID_MIN_BOOKS+ книг). Для музыки — «Исполнитель — Трек»."""
    if category not in ("music", "food", "aroma"):
        return []

    rows = session.exec(
        select(AISelection).where(
            AISelection.category == category,
            AISelection.book_id != exclude_book_id,
        )
    ).all()

    books_by_item: dict[str, set[int]] = {}
    for row in rows:
        try:
            items = json.loads(row.payload)
        except (TypeError, ValueError):
            continue
        for item in items:
            if category == "music":
                name = f"{item.get('artist', '')} — {item.get('title', '')}".strip(" —")
            else:
                name = (item.get("title") or "").strip()
            if name:
                books_by_item.setdefault(name.lower(), set()).add(row.book_id)

    ranked = sorted(books_by_item.items(), key=lambda kv: len(kv[1]), reverse=True)
    return [name for name, books in ranked if len(books) >= AVOID_MIN_BOOKS][:AVOID_LIMIT]


def payload_empty(payload_json: str) -> bool:
    """Пустой результат (AI не ответил → safe_ask вернул фолбэк с пустым списком):
    payload — это `[]`. Для дизайна payload — объект, он пустым не считается."""
    try:
        data = json.loads(payload_json)
    except (TypeError, ValueError):
        return False
    return isinstance(data, list) and len(data) == 0


def read_selections(session: Session, book_id: int, category: str) -> list[AISelection]:
    return session.exec(
        select(AISelection).where(
            AISelection.book_id == book_id,
            AISelection.category == category,
        )
    ).all()


def selections_response(book_id: int, category: str, rows: list) -> dict:
    """Единый формат ответа GET и POST: payload уже распарсен в объект/список."""
    return {
        "book_id": book_id,
        "category": category,
        # задача 85: музыка непроверена, если хоть одна строка сохранена при бане
        "verified": all(row.verified for row in rows) if rows else True,
        "selections": [
            {
                "source": row.source,
                "payload": json.loads(row.payload),
                "explanation": row.explanation,
            }
            for row in rows
        ],
    }


def replace_selections(
    book_id: int, category: str, cfg: dict, results: dict, verified: bool = True
) -> dict:
    """Сохранить результаты генерации, заменив прежние подборки категории —
    ПОИСТОЧНИКОВО. Защита (задача 74): если новый результат источника пуст
    (AI не ответил), старую подборку НЕ трогаем — иначе неудачная перегенерация
    стирала бы готовую атмосферу, как это и случилось при миграции 18.07.
    `verified` (задача 85): False для музыки, сохранённой при бане Spotify."""
    with Session(database.engine) as session:
        existing = {
            row.source: row
            for row in read_selections(session, book_id, category)
        }

        for source, result in results.items():
            payload = cfg["payload"](result)
            # пустой ответ: сохранённое не трогаем, нового пустого не плодим
            if payload_empty(payload):
                continue

            old = existing.get(source)
            if old is not None:
                session.delete(old)
                session.flush()   # DELETE до INSERT — иначе unique constraint
            session.add(AISelection(
                book_id=book_id,
                category=category,
                source=source,
                payload=payload,
                explanation=cfg["explanation"](result),
                verified=verified,
            ))
        session.commit()

        return selections_response(
            book_id, category, read_selections(session, book_id, category)
        )


async def generate_design_in_background(book_id: int, lang: str = "ru") -> None:
    """Задача 57: оформление создаётся фоном при добавлении книги — кнопка не
    нужна, к первому открытию паспорт обычно уже готов.
    Идемпотентно: если оформление уже есть (или книгу успели удалить) — выходим."""
    cfg = CATEGORIES["design"]
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            return
        if read_selections(session, book_id, "design"):
            return
        title, author = book.title, book.author
        context = build_book_context(session, book_id, "design")

    start_ai_metrics()   # задача 80: латентность и токены — в событие
    try:
        results = await cfg["generate"](title, author, lang, context)
        if cfg.get("postprocess"):
            results = await cfg["postprocess"](results, book_id, title)
    except Exception as e:
        # фон не должен ронять процесс; при открытии книги фронт попробует снова
        print(f"Фоновое оформление книги {book_id} не удалось:", e)
        return
    replace_selections(book_id, "design", cfg, results)
    log_event(cfg["event"], book_id, detail={
        "trigger": "auto",
        "ai_calls": take_ai_metrics(),
    })


def read_design_summary(session: Session, user_id: int) -> list[dict]:
    """Символьный режим полки (задача 66): экслибрис и палитры паспорта по всем
    книгам пользователя разом — чтобы полка не догружала паспорт по каждой."""
    rows = session.exec(
        select(AISelection)
        .join(UserBook, UserBook.book_id == AISelection.book_id)
        .where(
            UserBook.user_id == user_id,
            AISelection.category == "design",
        )
    ).all()

    designs = []
    for row in rows:
        payload = json.loads(row.payload)
        designs.append({
            "book_id": row.book_id,
            "symbol_svg": payload.get("symbol_svg"),
            # старый формат паспорта — одно поле palette (тёмное)
            "palette_dark": payload.get("palette_dark") or payload.get("palette"),
            "palette_light": payload.get("palette_light"),
        })
    return designs
