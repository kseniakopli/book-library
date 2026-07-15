# Поиск книг: локальный кэш Catalog (с TTL) + внешний Google Books.
from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlmodel import Session, col, or_, select

import database
from constants import EVENT_SEARCH
from events import log_event
from google_books import search_books
from models import Catalog

router = APIRouter(tags=["search"])

CATALOG_TTL_DAYS = 30   # сколько дней запись каталога считается свежей


@router.get("/search")
def search(q: str):
    q = q.strip()
    if len(q) < 3:                       # от 3 символов — бережём внешний API
        return {"results": []}

    cutoff = datetime.now() - timedelta(days=CATALOG_TTL_DAYS)
    with Session(database.engine) as session:
        pattern = f"%{q}%"
        # берём только свежие записи каталога (TTL) — протухшие игнорируем
        local = session.exec(
            select(Catalog).where(
                Catalog.created_at >= cutoff,
                or_(col(Catalog.title).ilike(pattern), col(Catalog.author).ilike(pattern)),
            ).limit(10)
        ).all()

        results = [
            {"title": c.title, "author": c.author, "cover_url": c.cover_url,
             "external_id": c.external_id}
            for c in local
        ]

        # мало нашли в своём каталоге — идём во внешний источник и кэшируем/обновляем
        if len(results) < 5:
            external = search_books(q)
            seen = {(r["title"].lower(), r["author"].lower()) for r in results}
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
                            title=item["title"],
                            author=item["author"],
                            cover_url=item["cover_url"],
                            source="google",
                            external_id=item["external_id"],
                        ))
                key = (item["title"].lower(), item["author"].lower())
                if key not in seen:
                    results.append({
                        "title": item["title"],
                        "author": item["author"],
                        "cover_url": item["cover_url"],
                        "external_id": item["external_id"],
                    })
                    seen.add(key)
            session.commit()

    log_event(EVENT_SEARCH, detail=f"q={q}; found={len(results)}")
    return {"results": results[:10]}
