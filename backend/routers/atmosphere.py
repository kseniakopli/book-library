# AI-«Атмосфера»: обобщённые эндпоинты для всех категорий (рефакторинг R2).
# Добавление новой категории (этап 7: food, aroma) = генератор в atmosphere.py
# + одна запись в CATEGORIES. Эндпоинты и хранение общие.
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

import database
from services.ai import (generate_aroma, generate_design, generate_food,generate_music,)
from constants import (
    EVENT_AI_AROMA,
    EVENT_AI_DESIGN,
    EVENT_AI_FOOD,
    EVENT_AI_MUSIC,
    SOURCE_CLAUDE,
)
from deps import get_book_or_404, get_lang, require_admin
from events import log_event
from i18n import msg
from models import AISelection, Book

router = APIRouter(tags=["atmosphere"])


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


def _get_category(category: str, lang: str) -> dict:
    cfg = CATEGORIES.get(category)
    if cfg is None:
        raise HTTPException(status_code=404, detail=msg("bad_category", lang))
    return cfg


def _selections_response(book_id: int, category: str, rows: list) -> dict:
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


@router.get("/books/{book_id}/atmosphere/{category}")
def get_atmosphere(book_id: int, category: str, lang: str = Depends(get_lang)):
    _get_category(category, lang)
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == category,
            )
        ).all()
    return _selections_response(book_id, category, rows)


@router.post("/books/{book_id}/atmosphere/{category}")
async def generate_atmosphere(
    book_id: int, category: str, lang: str = Depends(get_lang)
):
    cfg = _get_category(category, lang)

    # 1) книга (короткая сессия — не держим её открытой во время AI-вызова).
    # Атмосфера общая для книги и генерится один раз при добавлении; ручная
    # (пере)генерация меняет её для всех — поэтому только admin (решение 18.07).
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        require_admin(session, lang)
        title, author = book.title, book.author

    # 2) реальные AI-вызовы (токены тратятся здесь)
    results = await cfg["generate"](title, author, lang)

    # 3) заменяем прежние подборки категории на свежие
    response = _replace_selections(book_id, category, cfg, results)
    log_event(cfg["event"], book_id)
    return response


def _payload_empty(payload_json: str) -> bool:
    """Пустой результат (AI не ответил → safe_ask вернул фолбэк с пустым списком):
    payload — это `[]`. Для дизайна payload — объект, он пустым не считается."""
    try:
        data = json.loads(payload_json)
    except (TypeError, ValueError):
        return False
    return isinstance(data, list) and len(data) == 0


def _replace_selections(book_id: int, category: str, cfg: dict, results: dict) -> dict:
    """Сохранить результаты генерации, заменив прежние подборки категории —
    ПОИСТОЧНИКОВО. Защита: если новый результат источника пуст (AI не ответил),
    старую подборку НЕ трогаем (иначе неудачная перегенерация стирала бы
    готовую атмосферу — так и потерялись данные при миграции)."""
    with Session(database.engine) as session:
        existing = {
            row.source: row
            for row in session.exec(
                select(AISelection).where(
                    AISelection.book_id == book_id,
                    AISelection.category == category,
                )
            ).all()
        }

        for source, result in results.items():
            payload = cfg["payload"](result)
            # пустой ответ + уже есть сохранённое → сохраняем старое, не затираем
            if _payload_empty(payload) and source in existing:
                continue
            # пустой ответ и сохранённого нет → не плодим пустую строку
            if _payload_empty(payload):
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

        rows = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == category,
            )
        ).all()
        return _selections_response(book_id, category, rows)


async def design_in_background(book_id: int, lang: str = "ru"):
    """Задача 57: оформление создаётся фоном при добавлении книги —
    кнопка не нужна, к первому открытию паспорт обычно уже готов.
    Идемпотентно: если оформление уже есть (или книгу успели удалить) — выходим."""
    cfg = CATEGORIES["design"]
    with Session(database.engine) as session:
        book = session.get(Book, book_id)
        if book is None:
            return
        exists = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == "design",
            )
        ).first()
        if exists:
            return
        title, author = book.title, book.author

    try:
        results = await cfg["generate"](title, author, lang)
    except Exception as e:
        # фон не должен ронять процесс; при открытии книги фронт попробует снова
        print(f"Фоновое оформление книги {book_id} не удалось:", e)
        return
    _replace_selections(book_id, "design", cfg, results)
    log_event(cfg["event"], book_id, detail="auto")
