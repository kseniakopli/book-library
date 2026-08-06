# Страница автора (задача 97): все книги одного человека.
#
# ⚠ Роутер ЗАКРЫТ авторизацией (подключается с `dependencies=PROTECTED` в main.py).
# Это сознательно: страница показывает всю полку по автору, включая книги, которых
# нет в витрине. Публичной она стала бы обходным путём к личной библиотеке мимо
# витрины, где показано только отобранное.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from constants import ENRICH_PENDING, ENRICH_READY
from deps import current_user_id, get_lang, get_session, require_admin
from i18n import msg
from models import Author, Book
from schemas import BookRead
from services.atmosphere import generate_design_in_background
from services.authors import books_of, catalog_authors, display_name, link_book
from services.enrichment import enrich_in_background

# Биография — свободный текст, но не бесконечный: поле хранится в общей записи
# автора и показывается всем, а очень длинный текст ломает страницу и раздувает
# ответы списка. 4000 знаков — это несколько абзацев, для справки достаточно.
MAX_BIO_CHARS = 4000


class AuthorUpdate(BaseModel):
    bio: str | None = Field(default=None, max_length=MAX_BIO_CHARS)


class AuthorBookIn(BaseModel):
    """Новая книга автора (задача 123).

    ⚠ Поля `author` здесь нет намеренно: строку берём из самой сущности
    автора, на чьей странице стоим. Присланное имя означало бы, что книгу
    можно завести «у Селютиной, но за авторством Иванова», а привязка всё
    равно пошла бы по строке — и книга уехала бы к другому автору.
    """
    title: str
    cover_url: str | None = None
    # id тома в Google Books: если он есть, описание и обложку подтянем фоном
    external_id: str | None = None


router = APIRouter(tags=["authors"])


def _author_card(session: Session, author: Author, user_id: int) -> dict:
    """Карточка автора — общий ответ для чтения страницы и для добавления книги.

    Добавление отвечает свежей карточкой (как у цикла, `series_card`): фронт
    кладёт её в кэш и не делает второй запрос, а список книг обновляется
    вместе со счётчиками в одном месте.
    """
    found = books_of(session, author.id, user_id)
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
                # задача 121: год показывается у обеих стопок — иначе
                # половина списка выглядит как книги без года
                "published_year": book.published_year,
            }
            for book in found["catalog"]
        ],
    }


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

    return _author_card(session, author, user_id)


@router.post("/authors/{author_id}/books", status_code=201)
def add_book_to_author(
    author_id: int,
    data: AuthorBookIn,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    user_id: int = Depends(current_user_id),
):
    """Завести книгу автора в КАТАЛОГЕ, минуя полку (задача 123).

    Книга попадает в стопку «Есть в каталоге» — то же состояние, в котором
    живут тома циклов, добавленные как «что дальше». `UserBook` не создаётся
    сознательно: страница автора про библиографию, а не про то, что читатель
    завёл у себя. Захочет — положит на полку кнопкой со страницы книги.

    Каталог общий, значит правит его admin — то же основание, что у состава
    цикла (з.90а) и у полей книги.

    ⚠ **Строка автора берётся из сущности, а не из запроса.** Привязка идёт
    по `book.author` через `link_book`, и написание из Google Books
    («Alena Selyutina» рядом с «Алёной Селютиной») завело бы ВТОРОГО автора.
    Плата — потерянное написание источника; связь дороже, а поправить строку
    можно правкой книги.
    """
    author = session.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Автор не найден")
    require_admin(session, lang, user_id)

    title = (data.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail=msg("book_title_required", lang))

    book = Book(
        title=title,
        author=display_name(author),
        cover_url=data.cover_url,
        # без external_id тянуть нечего — книга сразу «готова», иначе она
        # навсегда осталась бы в состоянии «подгружаю» (грабли з.104/105:
        # пустота должна быть явной, а не вечным ожиданием)
        enrich_status=ENRICH_PENDING if data.external_id else ENRICH_READY,
    )
    session.add(book)
    session.flush()

    link_book(session, book.id, book.author)
    session.commit()

    if data.external_id:
        background_tasks.add_task(
            enrich_in_background, book.id, lang, data.external_id
        )
    # ⚠ Паспорт оформления — ОБЯЗАТЕЛЬНО, наравне с обогащением (правка 06.08).
    # 04.08 этой строки не было: эндпоинт писался по образцу добавления книги
    # в цикл, а не по образцу добавления на полку (`routers/books.py`), где
    # фоновых задач две. За два дня через эту кнопку приехало 124 книги,
    # и 102 из них остались без палитры и символа — это видно на полке
    # и на витрине. Книга здесь всегда новая (существующую выбрать нельзя),
    # поэтому условие `is_new` не нужно, а сама задача идемпотентна.
    background_tasks.add_task(
        generate_design_in_background, book.id, lang, user_id
    )

    return _author_card(session, author, user_id)


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
