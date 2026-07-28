# Публичная витрина (задача 30) — ЕДИНСТВЕННЫЙ роутер без авторизации,
# кроме /auth. Сюда ведут QR печатных карточек, поэтому страница должна
# открываться у человека, который про сервис ещё ничего не знает.
#
# Что показываем: отобранные книги (`userbook.featured`) с их атмосферой —
# символ, палитра, музыка, угощения, ароматы.
# Чего НЕ показываем НИКОГДА: оценки, даты прочтения, статусы чтения,
# статистику, 👍/👎, почту и прочее личное. Витрина — про книги, а не про
# читателя, и ответы здесь собираются вручную, а не через BookRead:
# случайно добавленное в общую схему поле иначе утекло бы наружу.
import json

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

import database
from models import AISelection, Book, User, UserBook

router = APIRouter(tags=["public"])

# категории атмосферы, которые показываем гостю (design идёт отдельно — это оформление)
PUBLIC_CATEGORIES = ("music", "food", "aroma")


def _owner_or_404(session: Session, slug: str) -> User:
    user = session.exec(select(User).where(User.public_slug == slug)).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Витрина не найдена")
    return user


def _design_of(session: Session, book_id: int) -> dict | None:
    """Паспорт оформления книги: символ и палитры — витрина ими и красива."""
    row = session.exec(
        select(AISelection).where(
            AISelection.book_id == book_id,
            AISelection.category == "design",
        )
    ).first()
    if row is None:
        return None
    try:
        payload = json.loads(row.payload)
    except (TypeError, ValueError):
        return None
    return {
        "symbol_svg": payload.get("symbol_svg"),
        "palette_dark": payload.get("palette_dark") or payload.get("palette"),
        "palette_light": payload.get("palette_light"),
        "statement": payload.get("statement"),
        # base_mood наружу НЕ отдаём: 28.07 попробовали показывать его в карточке
        # ленты — формулы у разных книг вышли от трёх слов до трёх строк, ровный
        # ряд рассыпался. Решение Ксении: в ленте только название и автор.
    }


@router.get("/public/{slug}")
def showcase(slug: str):
    """Витрина: заголовок и отобранные книги с обложкой/символом."""
    with Session(database.engine) as session:
        user = _owner_or_404(session, slug)
        rows = session.exec(
            select(Book, UserBook)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(UserBook.user_id == user.id, UserBook.featured == True)  # noqa: E712
            .order_by(Book.title)
        ).all()

        books = []
        for book, _ub in rows:
            books.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "cover_url": book.cover_url,
                "design": _design_of(session, book.id),
            })

    return {
        "title": user.public_title or f"Библиотека: {user.display_name}",
        "intro": user.public_intro,
        "books": books,
    }


@router.get("/public/{slug}/books/{book_id}")
def showcase_book(slug: str, book_id: int):
    """Страница книги в витрине: описание, оформление и атмосфера.

    Книга обязана быть отмеченной (`featured`) именно у владельца витрины —
    иначе по прямой ссылке можно было бы посмотреть любую книгу с его полки."""
    with Session(database.engine) as session:
        user = _owner_or_404(session, slug)
        pair = session.exec(
            select(Book, UserBook)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(
                UserBook.user_id == user.id,
                UserBook.featured == True,  # noqa: E712
                Book.id == book_id,
            )
        ).first()
        if pair is None:
            raise HTTPException(status_code=404, detail="Книга не найдена в витрине")
        book, _ub = pair

        atmosphere = {}
        for category in PUBLIC_CATEGORIES:
            rows = session.exec(
                select(AISelection).where(
                    AISelection.book_id == book.id,
                    AISelection.category == category,
                )
            ).all()
            # гостю показываем ОДИН вариант (первый по источнику): выбор между
            # Claude и ChatGPT — внутренняя кухня, посетителю она ни о чём
            if rows:
                row = sorted(rows, key=lambda r: r.source)[0]
                try:
                    atmosphere[category] = {
                        "items": json.loads(row.payload),
                        "explanation": row.explanation,
                    }
                except (TypeError, ValueError):
                    continue

        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "cover_url": book.cover_url,
            "description": book.description,
            "published_year": book.published_year,
            "spotify_playlist_url": book.spotify_playlist_url,
            "design": _design_of(session, book.id),
            "atmosphere": atmosphere,
            "showcase_title": user.public_title or f"Библиотека: {user.display_name}",
        }
