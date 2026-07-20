# Статистика чтения (задачи 24/63). HTTP-слой тонкий: расчёт — в services/stats.py.
from fastapi import APIRouter, Depends
from sqlmodel import Session

import database
from constants import EVENT_AI_INSIGHTS
from deps import CURRENT_USER_ID, get_lang, get_session, require_admin
from events import log_event
from services.ai import generate_insights, start_ai_metrics, take_ai_metrics
from services.stats import compute_stats, format_summary

router = APIRouter(tags=["stats"])


@router.get("/stats")
def read_stats(session: Session = Depends(get_session)):
    """Цифры по полке. Считается на лету: библиотека персональная, запрос дешёвый,
    а кэш пришлось бы сбрасывать на каждое изменение статуса или оценки."""
    return compute_stats(session, CURRENT_USER_ID)


@router.post("/stats/insights")
async def create_insights(lang: str = Depends(get_lang)):
    """Наблюдения о привычках чтения. Тратит токены → только admin, по кнопке.
    Не сохраняем: цифры меняются с каждой прочитанной книгой, и устаревший
    комментарий хуже, чем его отсутствие.
    Сессию открываем вручную КОРОТКИМ отрезком (не через get_session) — дальше
    идёт долгий AI-вызов, держать соединение всё это время не нужно."""
    with Session(database.engine) as session:
        require_admin(session, lang)
        stats = compute_stats(session, CURRENT_USER_ID)

    if not stats["totals"]["read"]:
        # нечего толковать — честно говорим, токены не тратим
        return {"observations": [], "detail": "no_data"}

    start_ai_metrics()   # задача 80: латентность и токены — в событие
    result = await generate_insights(format_summary(stats), lang)
    log_event(EVENT_AI_INSIGHTS, detail={
        "count": len(result.observations), "ai_calls": take_ai_metrics(),
    })
    return {"observations": result.observations}
