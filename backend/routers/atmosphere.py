# AI-«Атмосфера»: обобщённые эндпоинты для всех категорий (рефакторинг R2).
# Добавление новой категории (этап 7: food, aroma) = генератор в atmosphere.py
# + одна запись в CATEGORIES. Эндпоинты и хранение общие.
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

import database
from services.ai import generate_design, generate_music
from constants import EVENT_AI_DESIGN, EVENT_AI_MUSIC, SOURCE_CLAUDE
from deps import get_book_or_404, get_lang
from events import log_event
from i18n import msg
from models import AISelection

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
    # этап 7: "food": {...}, "aroma": {...}
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

    # 1) книга (короткая сессия — не держим её открытой во время AI-вызова)
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        title, author = book.title, book.author

    # 2) реальные AI-вызовы (токены тратятся здесь)
    results = await cfg["generate"](title, author, lang)

    # 3) заменяем прежние подборки категории на свежие
    with Session(database.engine) as session:
        old = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == category,
            )
        ).all()
        for row in old:
            session.delete(row)
        session.flush()   # DELETE до INSERT — иначе упрёмся в unique constraint

        for source, result in results.items():
            session.add(AISelection(
                book_id=book_id,
                category=category,
                source=source,
                payload=cfg["payload"](result),
                explanation=cfg["explanation"](result),
            ))
        session.commit()

        rows = session.exec(
            select(AISelection).where(
                AISelection.book_id == book_id,
                AISelection.category == category,
            )
        ).all()
        response = _selections_response(book_id, category, rows)

    log_event(cfg["event"], book_id)
    return response
