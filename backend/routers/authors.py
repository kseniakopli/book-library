# Страница автора (задача 97): все книги одного человека.
#
# ⚠ Роутер ЗАКРЫТ авторизацией (подключается с `dependencies=PROTECTED` в main.py).
# Это сознательно: страница показывает всю полку по автору, включая книги, которых
# нет в витрине. Публичной она стала бы обходным путём к личной библиотеке мимо
# витрины, где показано только отобранное.
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from deps import current_user_id, get_lang, get_session, require_admin
from models import Author
from schemas import BookRead
from services.authors import books_of, catalog_authors, display_name

# Биография — свободный текст, но не бесконечный: поле хранится в общей записи
# автора и показывается всем, а очень длинный текст ломает страницу и раздувает
# ответы списка. 4000 знаков — это несколько абзацев, для справки достаточно.
MAX_BIO_CHARS = 4000


class AuthorUpdate(BaseModel):
    bio: str | None = Field(default=None, max_length=MAX_BIO_CHARS)

router = APIRouter(tags=["authors"])


@router.get("/authors")
def read_authors(session: Session = Depends(get_session)):
    """Справочник авторов сервиса (задача 111).

    Считается по ОБЩЕМУ каталогу, а не по полке спрашивающего: раздел отвечает
    на вопрос «что вообще есть в библиотеке». Поэтому `user_id` здесь не нужен —
    ответ одинаков для всех. Вход всё равно обязателен: роутер подключён
    с `dependencies=PROTECTED`, и наружу каталог не отдаётся.

    ⚠ Объявлен ДО `/authors/{author_id}`: FastAPI подбирает маршруты по порядку,
    и при обратном порядке `/authors` попал бы в маршрут с параметром, а `"—"`
    не превращается в int — вместо списка пришла бы 422.
    """
    return {"authors": catalog_authors(session)}


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
        "bio": author.bio,
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


@router.patch("/authors/{author_id}")
def update_author(
    author_id: int,
    data: AuthorUpdate,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Правка биографии (задача 111) — только admin.

    Биография ОБЩАЯ: автор один на всю базу, и его справка видна каждому
    читателю. Это то же основание, по которому под admin закрыта правка полей
    книги (`apply_book_fields`), — личное живёт в `userbook`, общее правит
    владелец каталога.

    Пустая строка означает «очистить»: иначе заполненную по ошибке биографию
    нельзя было бы убрать, не трогая базу руками.
    """
    author = session.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Автор не найден")
    require_admin(session, lang, user_id)

    if data.bio is not None:
        author.bio = data.bio.strip() or None
        session.add(author)
        session.commit()
        session.refresh(author)

    return {"id": author.id, "bio": author.bio}
