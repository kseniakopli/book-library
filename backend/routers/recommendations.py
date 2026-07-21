# Рекомендации новых книг (этап 8).
# Генерируются ПО КНОПКЕ (решение 19.07): LLM смотрит на высоко оценённые книги
# и предлагает те, которых в библиотеке нет. Набор хранится в БД и заменяется
# целиком при следующей генерации — на главной он просто читается.
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

import database
from constants import (
    EVENT_AI_RECOMMENDATIONS,
    SOURCE_CHATGPT,
    SOURCE_CLAUDE,
    STATUS_READ,
)
from deps import CURRENT_USER_ID, get_lang, get_session, require_admin
from events import log_event
from google_books import search_books
from models import Book, Recommendation, UserBook
from services.ai import (
    RecommendationsResult,
    generate_recommendations,
    start_ai_metrics,
    take_ai_metrics,
)

router = APIRouter(tags=["recommendations"])

MIN_RATING = 7        # что считаем «понравилось»
MAX_FAVORITES = 20    # столько любимых книг отдаём модели (промпт не резиновый)
COUNT = 5             # столько советов просим У КАЖДОЙ модели (итого до 10)


def _norm(title: str, author: str) -> tuple[str, str]:
    return title.strip().lower(), author.strip().lower()


def _stored(session: Session) -> dict:
    """Сохранённые рекомендации пользователя в формате ответа."""
    rows = session.exec(
        select(Recommendation)
        .where(Recommendation.user_id == CURRENT_USER_ID)
        .order_by(Recommendation.id)
    ).all()
    return {
        "recommendations": [
            {
                "title": r.title,
                "author": r.author,
                "reason": r.reason,
                "source": r.source,
                "cover_url": r.cover_url,
                "external_id": r.external_id,
            }
            for r in rows
        ]
    }


@router.get("/recommendations")
def list_recommendations(session: Session = Depends(get_session)):
    """Сохранённые рекомендации (пусто — фронт зовёт подобрать)."""
    return _stored(session)


@router.post("/recommendations")
async def generate(lang: str = Depends(get_lang)):
    """Подобрать рекомендации заново. Тратит токены → только admin.
    Сессию открываем вручную КОРОТКИМИ отрезками (не через get_session):
    между ними идёт долгий AI-вызов, держать соединение всё это время не нужно."""
    with Session(database.engine) as session:
        require_admin(session, lang)

        # 1) сигналы: что понравилось (оценка ≥ MIN_RATING), свежее — важнее
        liked = session.exec(
            select(Book, UserBook)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(
                UserBook.user_id == CURRENT_USER_ID,
                UserBook.status == STATUS_READ,
                UserBook.rating.is_not(None),
                UserBook.rating >= MIN_RATING,
            )
            .order_by(UserBook.rating.desc(), UserBook.read_at.desc())
            .limit(MAX_FAVORITES)
        ).all()
        favorites = [f"{b.title} — {b.author} ({ub.rating}/10)" for b, ub in liked]

        # 2) что уже есть на полке — не предлагать повторно
        shelf = session.exec(
            select(Book.title, Book.author)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(UserBook.user_id == CURRENT_USER_ID)
        ).all()
        exclude = [f"{t} — {a}" for t, a in shelf]
        known = {_norm(t, a) for t, a in shelf}

    if not favorites:
        # нечего анализировать — честно говорим, токены не тратим
        return {"recommendations": [], "detail": "no_favorites"}

    start_ai_metrics()   # задача 80: латентность и токены — в событие
    # 20.07: спрашиваем ОБЕ модели, по COUNT советов у каждой
    results = await generate_recommendations(favorites, exclude, COUNT, lang)

    # 3) дедуп: (а) книги с полки — модель могла не заметить список исключений;
    #    (б) советы, совпавшие у обеих моделей — показываем один раз.
    #    Источники перебираем в фиксированном порядке, чтобы у одинакового
    #    набора был предсказуемый результат, а не «кто раньше ответил».
    fresh = []          # [(источник, item)]
    seen = set()
    for source in (SOURCE_CLAUDE, SOURCE_CHATGPT):
        for item in results.get(source, RecommendationsResult(items=[])).items:
            key = _norm(item.title, item.author)
            if key in known or key in seen:
                continue
            seen.add(key)
            fresh.append((source, item))

    # 4) обложки: один поиск в Google Books на книгу (мягко — без обложки тоже ок)
    covers = {}
    for _, item in fresh:
        candidates = search_books(f"{item.title} {item.author}", max_results=3)
        match = next((c for c in candidates if c.get("cover_url")), None)
        if match:
            covers[_norm(item.title, item.author)] = match

    # 5) заменяем набор целиком
    with Session(database.engine) as session:
        for old in session.exec(
            select(Recommendation).where(Recommendation.user_id == CURRENT_USER_ID)
        ).all():
            session.delete(old)
        session.flush()
        for source, item in fresh:
            found = covers.get(_norm(item.title, item.author)) or {}
            session.add(Recommendation(
                user_id=CURRENT_USER_ID,
                title=item.title,
                author=item.author,
                reason=item.reason,
                source=source,
                cover_url=found.get("cover_url"),
                external_id=found.get("external_id"),
                created_at=datetime.now(),
            ))
        session.commit()

    by_source = {
        source: sum(1 for s, _ in fresh if s == source)
        for source in (SOURCE_CLAUDE, SOURCE_CHATGPT)
    }
    log_event(EVENT_AI_RECOMMENDATIONS, detail={
        "count": len(fresh), "by_source": by_source, "ai_calls": take_ai_metrics(),
    })
    with Session(database.engine) as session:
        return _stored(session)
