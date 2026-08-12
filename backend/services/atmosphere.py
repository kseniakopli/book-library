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
from services.ai import generate_aroma, generate_design, generate_food, generate_music, start_ai_metrics, take_ai_metrics
from services.aroma_safety import filter_unsafe_aromas
import services.playlist as playlist_service
from services.playlist import resolve_songs
# сборка плейлиста книги переехала в services/playlist.py (R3), контекст
# промпта — в services/prompt_context.py; здесь остались только подборки
from services.prompt_context import _overused_artists, artist_key, build_book_context


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
# Сколько треков затасканных по библиотеке исполнителей допускается в одном
# плейлисте. Не ноль: иногда запрещённый артист книге правда подходит, и
# полный запрет обеднил бы подборку ради статистики.
MAX_OVERUSED_PER_PLAYLIST = 2


def _cap_overused_artists(results: dict, book_id: int) -> None:
    """Ограничить долю затасканных исполнителей в свежем плейлисте. Меняет
    results на месте.

    Зачем кодом, а не промптом (02.08). Разнообразия просили четырьмя способами:
    список запрещённых треков, список запрещённых исполнителей, признак канона
    вместо имён, поле-самоконтроль в схеме. Результат — ноль или ухудшение:
    модель называет замену и всё равно берёт запрещённых, а поле, просившее
    пересказать ограничение, сработало повторным внушением (Agnes Obel 8→9).
    Это ровно тот случай, для которого в проекте уже есть образец: выдуманные
    треки лечатся не просьбой «не выдумывай», а проверкой в Spotify и
    выбрасыванием несуществующих. Код не уговаривает — он отсекает.

    Порядок треков модель выдаёт осмысленный (сначала точные попадания),
    поэтому оставляем ПЕРВЫЕ MAX_OVERUSED_PER_PLAYLIST, а лишние убираем.

    ⚠ Вызывается ДО резолва в Spotify: отсеянное не должно тратить квоту —
    она считается на приложение и 21.07 уже стоила бана на 21 час."""
    with Session(database.engine) as session:
        overused = {
            name.lower() for name in _overused_artists(session, exclude_book_id=book_id)
        }
    if not overused:
        return

    for source, result in results.items():
        kept, dropped, seen = [], [], 0
        for song in result.songs:
            if artist_key(song.artist).lower() in overused:
                seen += 1
                if seen > MAX_OVERUSED_PER_PLAYLIST:
                    dropped.append(f"{song.artist} — {song.title}")
                    continue
            kept.append(song)
        if dropped:
            print(
                f"Атмосфера [{source}]: сверх лимита затасканных "
                f"({MAX_OVERUSED_PER_PLAYLIST}) отброшено: {'; '.join(dropped)}"
            )
        result.songs = kept


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
    _cap_overused_artists(results, book_id)

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
        # Дубли убираем ПОСЛЕ канонизации, а не до. Причины две: модель может
        # выдать один трек дважды в одной подборке (наблюдалось 02.08 —
        # «The Host of Seraphim» две строки подряд), а подстановка по
        # исполнителю способна свести два выдуманных названия к одной реальной
        # записи. До резолва такие пары выглядят разными.
        seen: set[tuple[str, str]] = set()
        for song in result.songs:
            item = unique.get((song.title.strip(), song.artist.strip()))
            if not item:
                continue
            song.title = item["title"]
            song.artist = item["artist"]
            key = (song.title.strip().lower(), song.artist.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            kept.append(song)
        result.songs = kept

    uris = [item["uri"] for item in resolved if item and item.get("uri")]
    await playlist_service.sync_book_playlist(book_id, title, uris)
    return results



async def remove_music_track(
    book_id: int, source: str, title: str, artist: str
) -> dict | None:
    """Точечное удаление трека из подборки (23.07, admin).

    Зачем: даже существующий в Spotify трек может не подходить книге по духу —
    дешевле выкинуть один, чем перегенерировать всю музыку (токены + лотерея).
    Трек убирается из payload ОДНОГО источника (вкладки независимы); плейлист
    пересобирается из оставшихся треков обоих источников — он их объединение.
    Возвращает обновлённый ответ категории или None (источник/трек не найден)."""
    with Session(database.engine) as session:
        row = next(
            (r for r in read_selections(session, book_id, "music")
             if r.source == source),
            None,
        )
        if row is None:
            return None
        try:
            songs = json.loads(row.payload)
        except (TypeError, ValueError):
            return None
        kept = [
            s for s in songs
            if not (s.get("title") == title and s.get("artist") == artist)
        ]
        if len(kept) == len(songs):
            return None
        row.payload = json.dumps(kept, ensure_ascii=False)
        session.add(row)
        session.commit()

        rows = read_selections(session, book_id, "music")
        remaining = []
        for r in rows:
            try:
                remaining.extend(json.loads(r.payload))
            except (TypeError, ValueError):
                continue
        book = session.get(Book, book_id)
        book_title = book.title if book else ""
        response = selections_response(book_id, "music", rows)

    await playlist_service.rebuild_book_playlist(book_id, book_title, remaining)
    return response



# `analysis` (02.08) — рассуждение модели, которое она обязана заполнить ДО
# ответа (reasoning-as-schema). Сохраняем как есть, JSON-строкой: оно не для
# показа читателю, а для разбора качества и замеров. У дизайна отдельного
# поля-анализа нет — там эту роль играет base_mood.
def _analysis_json(result) -> str:
    analysis = getattr(result, "analysis", None)
    if analysis is None:
        return ""
    return analysis.model_dump_json()


CATEGORIES = {
    "music": {
        "generate": generate_music,
        # проверка треков — отдельным async-шагом после генерации (см. выше)
        "postprocess": verify_music_results,
        "payload": lambda r: json.dumps(
            [s.model_dump() for s in r.songs], ensure_ascii=False
        ),
        "explanation": lambda r: r.explanation,
        "analysis": _analysis_json,
        "event": EVENT_AI_MUSIC,
    },
    "design": {
        "generate": _generate_design_selections,
        "payload": lambda r: r.model_dump_json(),
        "explanation": lambda r: r.statement,
        "analysis": lambda r: getattr(r, "base_mood", "") or "",
        "event": EVENT_AI_DESIGN,
    },
    "food": {
        "generate": generate_food,
        "payload": lambda r: json.dumps(
            [i.model_dump() for i in r.items], ensure_ascii=False
        ),
        "explanation": lambda r: r.explanation,
        "analysis": _analysis_json,
        "event": EVENT_AI_FOOD,
    },
    "aroma": {
        "generate": generate_aroma,
        # з.133: отсев небезопасного — код, а не просьба в промпте.
        # Появился как следствие з.129: пока модель выдавала образы, совет
        # был неисполним; теперь она называет покупаемое, и вредное стало
        # исполнимым вместе с полезным (12.08 — «сухая трава · конопля»).
        "postprocess": filter_unsafe_aromas,
        "payload": lambda r: json.dumps(
            [i.model_dump() for i in r.items], ensure_ascii=False
        ),
        "explanation": lambda r: r.explanation,
        "analysis": _analysis_json,
        "event": EVENT_AI_AROMA,
    },
}



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
                # .get: у разовых скриптов (backfill_passports) свой cfg
                analysis=cfg.get("analysis", lambda _r: "")(result),
                verified=verified,
            ))
        session.commit()

        return selections_response(
            book_id, category, read_selections(session, book_id, category)
        )


async def generate_design_in_background(
    book_id: int, lang: str = "ru", user_id: int = 1
) -> None:
    """Задача 57: оформление создаётся фоном при добавлении книги — кнопка не
    нужна, к первому открытию паспорт обычно уже готов.
    Идемпотентно: если оформление уже есть (или книгу успели удалить) — выходим.
    user_id — чей вкус подмешивать в промпт (з.26 ч.4); дефолт оставлен
    для разовых скриптов (backfill_passports и т.п.), где владелец не важен."""
    cfg = CATEGORIES["design"]
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            return
        if read_selections(session, book_id, "design"):
            return
        title, author = book.title, book.author
        context = build_book_context(session, book_id, "design", user_id)

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
