# Статистика чтения (задачи 24/63). HTTP-слой тонкий: расчёт — в services/stats.py.
from fastapi import APIRouter, Depends
from sqlmodel import Session

import database
from constants import EVENT_AI_INSIGHTS
from deps import current_user_id, get_lang, get_session, require_admin
from events import log_event
from services.ai import generate_insights, start_ai_metrics, take_ai_metrics
from services.ai_stats import compute_ai_stats
from services.stats import compute_stats, format_summary

router = APIRouter(tags=["stats"])


@router.get("/stats")
def read_stats(session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
):
    """Цифры по полке. Считается на лету: библиотека персональная, запрос дешёвый,
    а кэш пришлось бы сбрасывать на каждое изменение статуса или оценки."""
    return compute_stats(session, user_id)


@router.get("/stats/ai")
def read_ai_stats(
    days: int | None = None,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Задача 84: расход на AI и acceptance rate подборок.

    Только admin: это цифры по СЕРВИСУ целиком (события всех пользователей
    и вся обратная связь), а не личная статистика полки. Тестеру они ничего
    не говорят, а расход показывать посторонним незачем.

    `days` — окно в днях; без параметра считаем за всё время.
    """
    require_admin(session, lang, user_id)
    return compute_ai_stats(session, days)


@router.post("/stats/insights")
async def create_insights(lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Наблюдения о привычках чтения — по кнопке (тратит токены).

    Этап 9: доступно КАЖДОМУ вошедшему, а не только админу. Статистика личная
    (считается по своей полке), и запрещать её тестерам бессмысленно — иначе
    кнопка у них всегда отвечала бы 403. Расходы держат лимиты частоты
    (rate_limit.py, 20 AI-запросов в час) и капы у провайдеров (з.36).
    Не сохраняем: цифры меняются с каждой прочитанной книгой, и устаревший
    комментарий хуже, чем его отсутствие.
    Сессию открываем вручную КОРОТКИМ отрезком (не через get_session) — дальше
    идёт долгий AI-вызов, держать соединение всё это время не нужно."""
    with Session(database.engine) as session:
        stats = compute_stats(session, user_id)

    if not stats["totals"]["read"]:
        # нечего толковать — честно говорим, токены не тратим
        return {"observations": [], "detail": "no_data"}

    start_ai_metrics()   # задача 80: латентность и токены — в событие
    result = await generate_insights(format_summary(stats), lang)
    log_event(EVENT_AI_INSIGHTS, detail={
        "count": len(result.observations), "ai_calls": take_ai_metrics(),
    })
    return {"observations": result.observations}
