"""Домен циклов книг (задача 89).

Цикл — общая сущность (`Series`), статус чтения — личный (`UserSeries`),
принадлежность книги циклу — свойство книги (`Book.series_id/series_index`).

Ключевая идея (решение Ксении 22.07): книги цикла, которых нет на полке,
это обычные записи каталога `Book` **без** `UserBook`. Отдельной сущности
для «книг, которых у меня нет» не нужно — они и так находятся поиском,
а в цикле показывают, что читать дальше.
"""

import json
from datetime import datetime

from sqlmodel import Session, col, select

from constants import (
    SERIES_STATUS_ORDER,
    STATUS_READ,
)
from models import Book, Series, UserBook, UserSeries


def series_books(session: Session, series_id: int, user_id: int) -> list[dict]:
    """Книги цикла по порядку. У каждой — статус на полке пользователя
    (или `null`, если книги у него нет: тогда это «что дальше»)."""
    books = session.exec(
        select(Book)
        .where(Book.series_id == series_id)
        .order_by(col(Book.series_index).asc().nullslast(), Book.title)
    ).all()
    if not books:
        return []

    shelf = {
        ub.book_id: ub
        for ub in session.exec(
            select(UserBook).where(
                UserBook.user_id == user_id,
                col(UserBook.book_id).in_([b.id for b in books]),
            )
        ).all()
    }

    result = []
    for book in books:
        user_book = shelf.get(book.id)
        result.append({
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "cover_url": book.cover_url,
            "series_index": book.series_index,
            "on_shelf": user_book is not None,
            "status": user_book.status if user_book else None,
            "rating": user_book.rating if user_book else None,
        })
    return result


def series_progress(books: list[dict]) -> dict:
    """«Прочитано X из N»: N — все книги цикла (в том числе не на полке)."""
    total = len(books)
    read = sum(1 for b in books if b["status"] == STATUS_READ)
    on_shelf = sum(1 for b in books if b["on_shelf"])
    # следующая к чтению — первая непрочитанная по порядку
    next_book = next((b for b in books if b["status"] != STATUS_READ), None)
    return {
        "total": total,
        "read": read,
        "on_shelf": on_shelf,
        "next_book": next_book,
    }


def series_card(session: Session, series: Series, user_id: int) -> dict:
    """Карточка цикла для полки и страницы: статус, прогресс, книги."""
    link = session.exec(
        select(UserSeries).where(
            UserSeries.user_id == user_id, UserSeries.series_id == series.id
        )
    ).first()
    books = series_books(session, series.id, user_id)
    # design хранится JSON-строкой (как паспорт книги) — наружу отдаём объектом
    design = None
    if series.design:
        try:
            design = json.loads(series.design)
        except (TypeError, ValueError):
            design = None
    return {
        "id": series.id,
        "name": series.name,
        "author": series.author,
        "description": series.description,
        "design": design,
        "status": link.status if link else None,
        "progress": series_progress(books),
        "books": books,
    }


def list_series(session: Session, user_id: int) -> list[dict]:
    """Циклы пользователя. Сортировка (решение 22.07): читаю → прочитано →
    перестала читать, внутри статуса — по названию."""
    links = session.exec(
        select(UserSeries).where(UserSeries.user_id == user_id)
    ).all()
    if not links:
        return []

    rows = session.exec(
        select(Series).where(col(Series.id).in_([link.series_id for link in links]))
    ).all()
    cards = [series_card(session, series, user_id) for series in rows]
    cards.sort(
        key=lambda c: (SERIES_STATUS_ORDER.get(c["status"], 99), c["name"].lower())
    )
    return cards


def attach_book(
    session: Session, series_id: int, book: Book, index: int | None
) -> None:
    """Привязать книгу к циклу (со страницы цикла). Книга при этом может быть
    и не на полке пользователя — так и задумано."""
    book.series_id = series_id
    book.series_index = index
    session.add(book)


def set_status(
    session: Session, series_id: int, user_id: int, status: str
) -> UserSeries:
    """Поставить/сменить статус цикла у пользователя."""
    link = session.exec(
        select(UserSeries).where(
            UserSeries.user_id == user_id, UserSeries.series_id == series_id
        )
    ).first()
    if link is None:
        link = UserSeries(user_id=user_id, series_id=series_id, status=status)
    else:
        link.status = status
        link.updated_at = datetime.now()
    session.add(link)
    return link
