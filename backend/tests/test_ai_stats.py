# Задача 84: расход на AI и acceptance rate подборок. Считает КОД — модель
# к этим цифрам не подключается, поэтому тесты обходятся без моков провайдеров.
from datetime import datetime, timedelta

from sqlmodel import Session

import database
from constants import EVENT_AI_MUSIC, EVENT_IMPORT, SOURCE_CHATGPT, SOURCE_CLAUDE
from events import Event
from models import Feedback
from services.ai_stats import compute_ai_stats

URL = "/api/v1/stats/ai"


def _add_event(type_, calls, when=None):
    with Session(database.engine) as session:
        event = Event(type=type_, detail={"ai_calls": calls})
        if when:
            event.created_at = when
        session.add(event)
        session.commit()


def _stats(days=None):
    with Session(database.engine) as session:
        return compute_ai_stats(session, days)


def test_usage_sums_tokens_and_latency(client):
    _add_event(EVENT_AI_MUSIC, [
        {"provider": SOURCE_CLAUDE, "latency_ms": 1000,
         "input_tokens": 100, "output_tokens": 50},
        {"provider": SOURCE_CHATGPT, "latency_ms": 3000,
         "input_tokens": 200, "output_tokens": 80},
    ])
    _add_event(EVENT_IMPORT, [
        {"provider": SOURCE_CLAUDE, "latency_ms": 2000,
         "input_tokens": 10, "output_tokens": 5},
    ])

    usage = _stats()["usage"]
    claude = next(p for p in usage["providers"] if p["provider"] == SOURCE_CLAUDE)
    assert claude["calls"] == 2
    assert claude["input_tokens"] == 110
    assert claude["output_tokens"] == 55
    assert claude["avg_latency_ms"] == 1500
    assert usage["calls"] == 3


def test_failed_call_counted_with_its_latency(client):
    """Ошибка тоже стоит времени. Если её выкинуть из счётчика, провайдер,
    который чаще падает, будет выглядеть самым быстрым."""
    _add_event(EVENT_AI_MUSIC, [
        {"provider": SOURCE_CLAUDE, "latency_ms": 5000, "error": "APITimeoutError"},
    ])
    claude = next(
        p for p in _stats()["usage"]["providers"] if p["provider"] == SOURCE_CLAUDE
    )
    assert claude["calls"] == 1
    assert claude["errors"] == 1
    assert claude["input_tokens"] == 0        # токенов у неудачи нет
    assert claude["avg_latency_ms"] == 5000


def test_period_filter_cuts_old_events(client):
    _add_event(EVENT_AI_MUSIC, [
        {"provider": SOURCE_CLAUDE, "latency_ms": 100, "input_tokens": 1,
         "output_tokens": 1},
    ], when=datetime.now() - timedelta(days=40))

    assert _stats(days=7)["usage"]["calls"] == 0
    assert _stats()["usage"]["calls"] == 1     # без окна — всё время


def test_events_without_ai_calls_are_ignored(client):
    """Событий витрины больше тысячи — они не должны попадать в расход."""
    with Session(database.engine) as session:
        session.add(Event(type="showcase_viewed", detail={}))
        session.commit()
    assert _stats()["usage"]["calls"] == 0


def test_acceptance_rate_by_source(client):
    with Session(database.engine) as session:
        session.add(Feedback(user_id=1, ref="music:Claude:1",
                             source=SOURCE_CLAUDE, verdict="up"))
        session.add(Feedback(user_id=1, ref="music:Claude:2",
                             source=SOURCE_CLAUDE, verdict="up"))
        session.add(Feedback(user_id=1, ref="music:Claude:3",
                             source=SOURCE_CLAUDE, verdict="down"))
        session.add(Feedback(user_id=1, ref="music:ChatGPT:1",
                             source=SOURCE_CHATGPT, verdict="down"))
        session.commit()

    sources = {s["source"]: s for s in _stats()["feedback"]["sources"]}
    assert sources[SOURCE_CLAUDE]["acceptance"] == 0.67
    assert sources[SOURCE_CLAUDE]["total"] == 3
    assert sources[SOURCE_CHATGPT]["acceptance"] == 0.0


def test_acceptance_is_none_without_feedback(client):
    """Ноль означал бы «всё плохо», а не «данных нет» — по такой цифре легко
    начать чинить промпт на пустом месте."""
    summary = _stats()["feedback"]
    assert summary["total"] == 0
    assert summary["sources"] == []


def test_endpoint_requires_admin(client):
    """Цифры по сервису целиком: события всех пользователей и вся обратная
    связь. Обычному тестеру их видеть незачем."""
    from models import User

    with Session(database.engine) as session:
        user = session.get(User, 1)
        user.is_admin = False
        session.add(user)
        session.commit()

    assert client.get(URL).status_code == 403


def test_endpoint_returns_both_sections(client):
    body = client.get(URL).json()
    assert "usage" in body and "feedback" in body
