# Жанры (задача 112): справочник каталога и правка жанров книги.
#
# ⚠ Роутер ЗАКРЫТ авторизацией (`dependencies=PROTECTED` в main.py) — как
# и авторы: страница жанра показывает книги общей базы, включая те, что вне
# витрины. Публичной она стала бы обходом витрины.
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from deps import current_user_id, get_book_or_404, get_lang, get_session, require_admin
from models import Genre
from schemas import BookRead
from services.genres import books_of, catalog_genres, set_book_genres

router = APIRouter(tags=["genres"])

MAX_GENRES_PER_BOOK = 5   # больше пяти — это уже не жанр, а облако тегов


class BookGenresIn(BaseModel):
    genres: list[str]


@router.get("/genres")
def read_genres(session: Session = Depends(get_session)):
    """Справочник жанров: считается по общему каталогу, ответ одинаков для всех
    (то же правило, что у авторов — решение Ксении 03.08)."""
    return {"genres": catalog_genres(session)}


@router.get("/genres/{genre_id}")
def read_genre(
    genre_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
):
    """Книги жанра: отдельно полка, отдельно каталог.

    Каталожные книги отдаются коротким словарём, а не `BookRead`: у них нет
    полки, значит нет ни статуса, ни оценки, и притворяться, что есть, —
    врать контрактом (то же решение, что на странице автора).
    """
    genre = session.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status_code=404, detail="Жанр не найден")

    found = books_of(session, genre_id, user_id)
    return {
        "id": genre.id,
        "name": genre.name,
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
            }
            for book in found["catalog"]
        ],
    }


@router.put("/books/{book_id}/genres")
def set_genres(
    book_id: int,
    data: BookGenresIn,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Заменить набор жанров книги — только admin.

    Жанры ОБЩИЕ: книга одна на всю базу, и её жанры видят все читатели.
    То же основание, что у правки полей книги (`apply_book_fields`).

    PUT, а не PATCH: приходит полный набор, и это не оговорка — интерфейс
    показывает все жанры книги разом, значит и сохранять надо целиком,
    иначе снятую галочку нечем снять.
    """
    get_book_or_404(session, book_id, lang)
    require_admin(session, lang, user_id)

    if len(data.genres) > MAX_GENRES_PER_BOOK:
        raise HTTPException(
            status_code=400,
            detail=f"Не больше {MAX_GENRES_PER_BOOK} жанров у книги",
        )

    genres = set_book_genres(session, book_id, data.genres)
    session.commit()
    return {
        "book_id": book_id,
        "genres": [{"id": g.id, "name": g.name} for g in genres],
    }
