"""«Профиль вкуса» из обратной связи (задача 26, часть 4).

API моделей не имеет памяти: каждый запрос независим, Claude и ChatGPT не помнят
прошлых генераций и не учатся от нас. Поэтому «память» о вкусе читателя живёт
здесь: мы копим 👍/👎 (таблица Feedback) и **подкладываем сводку в промпт**
следующей генерации.

Что собираем:
  - для атмосферы — названия из подборок, которые понравились и не понравились
    (оценка ставится на подборку категория+источник, значит её содержимое —
    сигнал целиком);
  - для рекомендаций — книги-советы с 👎 («не предлагай похожее»).

Всё ограничено по объёму: промпт не резиновый, а сигнал важен агрегатом,
а не полным логом.
"""

import json

from sqlmodel import Session, col, select

from models import AISelection, Feedback

MAX_ITEMS = 10        # столько названий каждого знака отдаём модели
MAX_BOOKS = 12        # столько «не понравившихся» книг-советов


def _selection_titles(payload: str, category: str) -> list[str]:
    try:
        items = json.loads(payload)
    except (TypeError, ValueError):
        return []
    names = []
    for item in items:
        if category == "music":
            name = f"{item.get('artist', '')} — {item.get('title', '')}".strip(" —")
        else:
            name = (item.get("title") or "").strip()
        if name:
            names.append(name)
    return names


def atmosphere_taste(session: Session, user_id: int, category: str) -> dict:
    """{'liked': [...], 'disliked': [...]} — что заходило и не заходило в этой
    категории по всей библиотеке. Основано на оценках подборок (ref вида
    `atmosphere:{book_id}:{category}:{source}`)."""
    rows = session.exec(
        select(Feedback).where(
            Feedback.user_id == user_id,
            col(Feedback.ref).like(f"atmosphere:%:{category}:%"),
        )
    ).all()
    if not rows:
        return {}

    liked: list[str] = []
    disliked: list[str] = []
    for row in rows:
        parts = row.ref.split(":")
        if len(parts) != 4:
            continue
        _, book_id, cat, source = parts
        if not book_id.isdigit():
            continue
        selection = session.exec(
            select(AISelection).where(
                AISelection.book_id == int(book_id),
                AISelection.category == cat,
                AISelection.source == source,
            )
        ).first()
        if selection is None:
            continue      # подборку перегенерировали — оценка осиротела
        bucket = liked if row.verdict == "up" else disliked
        bucket.extend(_selection_titles(selection.payload, cat))

    # дедуп с сохранением порядка, срез по лимиту
    def _uniq(values: list[str]) -> list[str]:
        seen, result = set(), []
        for value in values:
            key = value.lower()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result[:MAX_ITEMS]

    return {"liked": _uniq(liked), "disliked": _uniq(disliked)}


def disliked_recommendations(session: Session, user_id: int) -> list[str]:
    """Книги-советы с 👎 — «такое читателю не заходит».
    ref вида `recommendation:{title}|{author}`."""
    rows = session.exec(
        select(Feedback).where(
            Feedback.user_id == user_id,
            Feedback.verdict == "down",
            col(Feedback.ref).like("recommendation:%"),
        )
    ).all()

    books = []
    for row in rows:
        _, _, rest = row.ref.partition(":")
        title, sep, author = rest.partition("|")
        if not title:
            continue
        books.append(f"{title.strip()} — {author.strip()}" if sep else title.strip())
    return books[:MAX_BOOKS]
