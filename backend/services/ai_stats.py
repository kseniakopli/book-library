"""Что нам стоят AI-вызовы и как часто их результат нравится (задача 84).

Данные копятся с задачи 80, но их никто не смотрел. Здесь два независимых
среза, и оба считает КОД — модель к этой странице не подключается вовсе:

  1. `usage` — из событийного лога. Каждый AI-вызов пишет в `Event.detail`
     список `ai_calls`: провайдер, латентность, токены. Это фактические цифры
     наших запросов.
  2. `feedback` — из таблицы `Feedback`: доля 👍 у Claude и у ChatGPT
     (acceptance rate). Показывает, чьи подборки принимают чаще.

⚠ Стоимость НЕ переводится в деньги намеренно. Цена за токен живёт в
прайс-листах провайдеров и меняется без нашего участия; зашитый коэффициент
превратился бы в уверенно выглядящую и незаметно устаревшую цифру. Токены —
факт, рубли — прогноз. Понадобится сумма — умножать на актуальный прайс
в момент чтения.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from sqlmodel import Session, col, func, select

from constants import (
    EVENT_AI_AROMA,
    EVENT_AI_DESIGN,
    EVENT_AI_FOOD,
    EVENT_AI_INSIGHTS,
    EVENT_AI_MUSIC,
    EVENT_AI_RECOMMENDATIONS,
    EVENT_IMPORT,
)
from events import Event
from models import Feedback

# События, в detail которых бывает ai_calls. Перечисляем явно, а не сканируем
# весь лог: событий витрины уже больше тысячи, и фильтр по типу — дешёвая
# выборка по индексу вместо чтения всех строк.
AI_EVENT_TYPES = [
    EVENT_AI_MUSIC,
    EVENT_AI_DESIGN,
    EVENT_AI_FOOD,
    EVENT_AI_AROMA,
    EVENT_AI_RECOMMENDATIONS,
    EVENT_AI_INSIGHTS,
    EVENT_IMPORT,          # AI-маппинг колонок CSV (задача 28)
]


def _empty_provider() -> dict:
    return {
        "calls": 0,
        "errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "latency_total": 0,
        "latency_count": 0,
    }


def compute_ai_usage(session: Session, days: int | None = None) -> dict:
    """Расход по провайдерам за период (None — за всё время)."""
    query = select(Event).where(col(Event.type).in_(AI_EVENT_TYPES))
    if days:
        query = query.where(Event.created_at >= datetime.now() - timedelta(days=days))

    by_provider: dict[str, dict] = defaultdict(_empty_provider)
    for event in session.exec(query).all():
        for call in (event.detail or {}).get("ai_calls") or []:
            provider = call.get("provider") or "—"
            row = by_provider[provider]
            row["calls"] += 1
            # У неудачного вызова есть латентность, но нет токенов: ошибка тоже
            # стоит времени, и прятать её из счётчика нельзя — иначе провайдер,
            # который часто падает, выглядит самым быстрым.
            if call.get("error"):
                row["errors"] += 1
            row["input_tokens"] += call.get("input_tokens") or 0
            row["output_tokens"] += call.get("output_tokens") or 0
            if call.get("latency_ms") is not None:
                row["latency_total"] += call["latency_ms"]
                row["latency_count"] += 1

    providers = []
    for name, row in sorted(by_provider.items()):
        providers.append({
            "provider": name,
            "calls": row["calls"],
            "errors": row["errors"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "avg_latency_ms": (
                round(row["latency_total"] / row["latency_count"])
                if row["latency_count"] else None
            ),
        })
    return {
        "providers": providers,
        "calls": sum(p["calls"] for p in providers),
        "input_tokens": sum(p["input_tokens"] for p in providers),
        "output_tokens": sum(p["output_tokens"] for p in providers),
    }


def compute_feedback_summary(session: Session) -> dict:
    """Доля 👍 по источникам подборок.

    ⚠ `acceptance` — None, когда оценок нет вовсе. Ноль здесь означал бы
    «всё плохо», а не «данных нет», и по такой цифре легко принять решение
    о промпте на пустом месте.
    """
    rows = session.exec(
        select(Feedback.source, Feedback.verdict, func.count())
        .group_by(Feedback.source, Feedback.verdict)
    ).all()

    tally: dict[str, dict] = defaultdict(lambda: {"up": 0, "down": 0})
    for source, verdict, count in rows:
        tally[source or "—"][verdict] = count

    sources = []
    for name, counts in sorted(tally.items()):
        total = counts["up"] + counts["down"]
        sources.append({
            "source": name,
            "up": counts["up"],
            "down": counts["down"],
            "total": total,
            "acceptance": round(counts["up"] / total, 2) if total else None,
        })
    return {
        "sources": sources,
        "total": sum(s["total"] for s in sources),
    }


def compute_ai_stats(session: Session, days: int | None = None) -> dict:
    return {
        "period_days": days,
        "usage": compute_ai_usage(session, days),
        "feedback": compute_feedback_summary(session),
    }
