# Доменный слой «Атмосферы» (задачи 78/79 из ревью 19.07).
#
# Раньше всё это жило в routers/atmosphere.py, из-за чего routers/books.py делал
# локальный импорт внутри функции, чтобы обойти круговой импорт. Теперь логика
# здесь, роутеры импортируют её сверху — граница модулей на месте.
#
# Добавление новой категории = генератор в services/ai.py + запись в CATEGORIES.
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


async def _generate_design_selections(title: str, author: str, lang: str = "ru") -> dict:
    """Приводим паспорт к общему контракту генераторов: {источник: модель}."""
    result = await generate_design(title, author, lang)
    return {SOURCE_CLAUDE: result}


# Конфигурация категорий. Контракт генератора: async (title, author, lang) -> {source: BaseModel}.
# payload — что кладём в AISelection.payload (JSON-строка),
# explanation — короткий текст-пояснение для UI.
CATEGORIES = {
    "music": {
        "generate": generate_music,
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
        "selections": [
            {
                "source": row.source,
                "payload": json.loads(row.payload),
                "explanation": row.explanation,
            }
            for row in rows
        ],
    }


def replace_selections(book_id: int, category: str, cfg: dict, results: dict) -> dict:
    """Сохранить результаты генерации, заменив прежние подборки категории —
    ПОИСТОЧНИКОВО. Защита (задача 74): если новый результат источника пуст
    (AI не ответил), старую подборку НЕ трогаем — иначе неудачная перегенерация
    стирала бы готовую атмосферу, как это и случилось при миграции 18.07."""
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

    start_ai_metrics()   # задача 80: латентность и токены — в событие
    try:
        results = await cfg["generate"](title, author, lang)
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
