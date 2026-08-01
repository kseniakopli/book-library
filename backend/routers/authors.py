# Страница автора (задача 97): все книги одного человека.
#
# ⚠ Роутер ЗАКРЫТ авторизацией (подключается с `dependencies=PROTECTED` в main.py).
# Это сознательно: страница показывает всю полку по автору, включая книги, которых
# нет в витрине. Публичной она стала бы обходным путём к личной библиотеке мимо
# витрины, где показано только отобранное.
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from deps import current_user_id, get_session
from models import Author
from schemas import BookRead
from services.authors import books_of, display_name

router = APIRouter(tags=["authors"])


@router.get("/authors/{author_id}")
def read_author(
    author_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
):
    """Автор и его книги: отдельно полка, отдельно каталог.

    Каталожные книги (тома циклов, которых у читателя нет) отдаются коротким
    словарём, а не `BookRead`: у них нет полки, значит нет ни статуса, ни оценки,
    и притворяться, что есть, — врать контрактом.
    """
    author = session.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Автор не найден")

    found = books_of(session, author_id, user_id)
    return {
        "id": author.id,
        "name": display_name(author),
        "name_ru": author.name_ru,
        "name_original": author.name_original,
        "shelf": [
            BookRead.from_pair(book, user_book)
            for book, user_book in found["shelf"]
        ],
        "catalog": [
            {
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "cover_url": book.cover_url,
                "series_id": book.series_id,
                "series_index": book.series_index,
            }
            for book in found["catalog"]
        ],
    }
