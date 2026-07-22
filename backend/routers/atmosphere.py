# HTTP-слой «Атмосферы»: разобрать запрос → вызвать сервис → вернуть ответ.
# Доменная логика (CATEGORIES, сохранение подборок, фоновая генерация паспорта)
# живёт в services/atmosphere.py — ревью 19.07, задачи 78/79.
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

import database
import services.spotify as spotify_service
from deps import get_book_or_404, get_lang, require_admin
from events import log_event
from i18n import msg
from services.ai import start_ai_metrics, take_ai_metrics
from services.atmosphere import (
    CATEGORIES,          # ре-экспорт: на него ссылаются тесты и разовые скрипты
    read_selections,
    replace_selections,
    selections_response,
)

router = APIRouter(tags=["atmosphere"])


def _get_category(category: str, lang: str) -> dict:
    cfg = CATEGORIES.get(category)
    if cfg is None:
        raise HTTPException(status_code=404, detail=msg("bad_category", lang))
    return cfg


@router.get("/books/{book_id}/atmosphere/{category}")
def get_atmosphere(book_id: int, category: str, lang: str = Depends(get_lang)):
    _get_category(category, lang)
    with Session(database.engine) as session:
        rows = read_selections(session, book_id, category)
    return selections_response(book_id, category, rows)


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

    # 2) реальные AI-вызовы (токены тратятся здесь); метрики — в событие (з.80)
    start_ai_metrics()
    results = await cfg["generate"](title, author, lang)
    # 2а) постобработка категории: для музыки — один проход поиска в Spotify
    # (выдуманные треки отсеиваются) и сразу сборка/обновление плейлиста (20.07)
    if cfg.get("postprocess"):
        results = await cfg["postprocess"](results, book_id, title)

    # задача 85: музыка, сохранённая при бане Spotify, помечается непроверенной —
    # скрипт reverify_music перепроверит её позже. Прочие категории всегда verified.
    verified = spotify_service.available() if category == "music" else True

    # 3) сохраняем — пустой результат не затирает готовую подборку (задача 74)
    response = replace_selections(book_id, category, cfg, results, verified=verified)
    log_event(cfg["event"], book_id, detail={
        "trigger": "manual",
        "ai_calls": take_ai_metrics(),
    })
    return response
