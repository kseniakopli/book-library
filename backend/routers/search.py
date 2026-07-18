# Поиск книг для добавления. Порядок (решение 18.07):
#   1) локальный каталог Book — книги, уже известные системе (с готовой атмосферой);
#   2) кэш Catalog + внешний Google Books;
#   3) ручное добавление — на фронте, если ничего не нашлось.
from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy.orm import defer
from sqlmodel import Session, col, delete, select

import database
from constants import EVENT_SEARCH
from deps import CURRENT_USER_ID
from events import log_event
from google_books import search_books
from models import Book, Catalog, UserBook

router = APIRouter(tags=["search"])

CATALOG_TTL_DAYS = 30   # сколько дней запись каталога считается свежей


@router.get("/search")
def search(q: str):
    q = q.strip()
    if len(q) < 3:                       # от 3 символов — бережём внешний API
        return {"results": []}

    cutoff = datetime.now() - timedelta(days=CATALOG_TTL_DAYS)
    q_lower = q.lower()

    def matches(title, author):
        # регистронезависимо по-питоновски: SQLite lower() кириллицу не понижает,
        # поэтому «карризи» не нашёл бы «Карризи» — фильтруем в Python
        return q_lower in (title or "").lower() or q_lower in (author or "").lower()

    with Session(database.engine) as session:
        # гигиена: протухшие записи кэша удаляем (не копим мусор)
        session.exec(delete(Catalog).where(col(Catalog.created_at) < cutoff))
        session.commit()

        # какие книги уже на полке пользователя — пометим, чтобы не предлагать дважды
        shelf_ids = set(
            session.exec(
                select(UserBook.book_id).where(UserBook.user_id == CURRENT_USER_ID)
            ).all()
        )

        # 1) ЛОКАЛЬНЫЙ каталог Book — книги, которые система уже знает.
        # defer(raw_metadata): тяжёлый JSON для поиска не нужен (задача 52)
        all_books = session.exec(
            select(Book).options(defer(Book.raw_metadata))
        ).all()
        local = [b for b in all_books if matches(b.title, b.author)][:10]
        results = [
            {
                "title": b.title,
                "author": b.author,
                "cover_url": b.cover_url,
                "book_id": b.id,          # добавление переиспользует книгу (без генерации)
                "external_id": None,
                "source": "library",
                "on_shelf": b.id in shelf_ids,
            }
            for b in local
        ]
        seen = {(r["title"].lower(), r["author"].lower()) for r in results}

        # 2) кэш Catalog (свежие записи) — внешние подсказки, ещё не заведённые в Book
        cached = [
            c for c in session.exec(
                select(Catalog).where(Catalog.created_at >= cutoff)
            ).all()
            if matches(c.title, c.author)
        ][:10]
        for c in cached:
            key = (c.title.lower(), c.author.lower())
            if key in seen:
                continue
            results.append({
                "title": c.title, "author": c.author, "cover_url": c.cover_url,
                "book_id": None, "external_id": c.external_id, "source": "catalog",
                "on_shelf": False,
            })
            seen.add(key)

        # 3) мало нашли локально — идём в Google Books и кэшируем результат
        if len(results) < 5:
            external = search_books(q)
            for item in external:
                if item["external_id"]:
                    existing = session.exec(
                        select(Catalog).where(Catalog.external_id == item["external_id"])
                    ).first()
                    if existing:
                        existing.created_at = datetime.now()      # обновляем TTL
                        existing.cover_url = item["cover_url"] or existing.cover_url
                        session.add(existing)
                    else:
                        session.add(Catalog(
                            title=item["title"], author=item["author"],
                            cover_url=item["cover_url"], source="google",
                            external_id=item["external_id"],
                        ))
                key = (item["title"].lower(), item["author"].lower())
                if key not in seen:
                    results.append({
                        "title": item["title"], "author": item["author"],
                        "cover_url": item["cover_url"], "book_id": None,
                        "external_id": item["external_id"], "source": "google",
                        "on_shelf": False,
                    })
                    seen.add(key)
            session.commit()

    log_event(EVENT_SEARCH, detail=f"q={q}; found={len(results)}")
    return {"results": results[:10]}
