# Циклы книг (задача 89). HTTP-слой тонкий, домен — в services/series.py.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

import database
from constants import (
    ALLOWED_SERIES_STATUSES,
    ENRICH_PENDING,
    EVENT_AI_DESIGN,
    SERIES_READING,
)
from deps import (
    CURRENT_USER_ID,
    get_book_or_404,
    get_lang,
    get_session,
    require_admin,
)
from events import log_event
from i18n import msg
from models import Book, Series
from services.ai import generate_series_design, start_ai_metrics, take_ai_metrics
from services.enrichment import enrich_in_background
from services.series import attach_book, list_series, series_card, set_status

router = APIRouter(tags=["series"])


class SeriesCreate(BaseModel):
    name: str
    author: str | None = None
    description: str | None = None
    status: str = SERIES_READING


class SeriesUpdate(BaseModel):
    name: str | None = None
    author: str | None = None
    description: str | None = None
    status: str | None = None


class SeriesBookIn(BaseModel):
    """Привязка книги к циклу: либо существующая книга (`book_id`), либо новая
    по названию — тогда заводим запись в КАТАЛОГЕ, не кладя на полку. Так в цикле
    появляются будущие книги («что дальше»): они есть в каталоге, но не у читателя.
    `cover_url`/`external_id` приходят из поиска (Google Books) — по ним книга
    получает обложку и фоновое обогащение."""
    book_id: int | None = None
    title: str | None = None
    author: str | None = None
    cover_url: str | None = None
    external_id: str | None = None
    series_index: int | None = None


def _get_series_or_404(session: Session, series_id: int, lang: str) -> Series:
    series = session.get(Series, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail=msg("series_not_found", lang))
    return series


def _check_status(status: str, lang: str) -> None:
    if status not in ALLOWED_SERIES_STATUSES:
        raise HTTPException(status_code=400, detail=msg("bad_series_status", lang))


@router.get("/series")
def read_series(session: Session = Depends(get_session)):
    """Полка циклов: читаю → прочитано → перестала читать."""
    return {"series": list_series(session, CURRENT_USER_ID)}


@router.post("/series")
def create_series(
    data: SeriesCreate,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    """Создать цикл. Сразу кладём его на полку пользователя со статусом."""
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail=msg("series_name_required", lang))
    _check_status(data.status, lang)

    series = Series(
        name=name,
        author=(data.author or "").strip() or None,
        description=(data.description or "").strip() or None,
    )
    session.add(series)
    session.commit()
    session.refresh(series)

    set_status(session, series.id, CURRENT_USER_ID, data.status)
    session.commit()
    return series_card(session, series, CURRENT_USER_ID)


@router.get("/series/{series_id}")
def read_one(
    series_id: int,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    series = _get_series_or_404(session, series_id, lang)
    return series_card(session, series, CURRENT_USER_ID)


@router.patch("/series/{series_id}")
def update_series(
    series_id: int,
    data: SeriesUpdate,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    """Правка цикла и/или смена статуса (кнопки «Читаю» / «Прочитан» / «Брошен»)."""
    series = _get_series_or_404(session, series_id, lang)

    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail=msg("series_name_required", lang))
        series.name = name
    if data.author is not None:
        series.author = data.author.strip() or None
    if data.description is not None:
        series.description = data.description.strip() or None
    session.add(series)

    if data.status is not None:
        _check_status(data.status, lang)
        set_status(session, series_id, CURRENT_USER_ID, data.status)

    session.commit()
    session.refresh(series)
    return series_card(session, series, CURRENT_USER_ID)


@router.delete("/series/{series_id}")
def delete_series(
    series_id: int,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    """Удалить цикл. Книги остаются в каталоге — просто теряют привязку."""
    series = _get_series_or_404(session, series_id, lang)
    for book in session.exec(select(Book).where(Book.series_id == series_id)).all():
        book.series_id = None
        book.series_index = None
        session.add(book)
    session.delete(series)
    session.commit()
    return {"deleted": series_id}


@router.post("/series/{series_id}/design")
async def generate_design(series_id: int, lang: str = Depends(get_lang)):
    """Сгенерировать экслибрис цикла (задача 89). Тратит токены → только admin,
    по кнопке. Опирается на описание цикла — поэтому имеет смысл сначала его
    заполнить.
    Сессию держим КОРОТКО: между чтением и записью идёт долгий AI-вызов."""
    with Session(database.engine) as session:
        series = _get_series_or_404(session, series_id, lang)
        require_admin(session, lang)
        name, author, description = series.name, series.author, series.description

    start_ai_metrics()
    result = await generate_series_design(name, author, description, lang)

    with Session(database.engine) as session:
        series = _get_series_or_404(session, series_id, lang)
        series.design = result.model_dump_json()
        session.add(series)
        session.commit()
        session.refresh(series)
        card = series_card(session, series, CURRENT_USER_ID)

    log_event(EVENT_AI_DESIGN, detail={
        "target": "series", "series_id": series_id, "ai_calls": take_ai_metrics(),
    })
    return card


@router.post("/series/{series_id}/books")
def add_book_to_series(
    series_id: int,
    data: SeriesBookIn,
    background_tasks: BackgroundTasks,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    """Привязать книгу к циклу (со страницы цикла).
    Книга может отсутствовать на полке пользователя — тогда в цикле она
    показывается как «что дальше»."""
    _get_series_or_404(session, series_id, lang)

    if data.book_id is not None:
        book = get_book_or_404(session, data.book_id, lang)
    else:
        title = (data.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail=msg("book_title_required", lang))
        # новая книга — только в каталог, без UserBook: читатель её ещё не читает
        book = Book(
            title=title,
            author=(data.author or "").strip() or "—",
            cover_url=data.cover_url,
            enrich_status=ENRICH_PENDING if data.external_id else "ready",
        )
        session.add(book)
        session.flush()
        # метаданные подтянем фоном — у книги появятся описание и обложка
        if data.external_id:
            background_tasks.add_task(
                enrich_in_background, book.id, lang, data.external_id
            )

    attach_book(session, series_id, book, data.series_index)
    session.commit()
    series = session.get(Series, series_id)
    return series_card(session, series, CURRENT_USER_ID)


@router.delete("/series/{series_id}/books/{book_id}")
def remove_book_from_series(
    series_id: int,
    book_id: int,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    series = _get_series_or_404(session, series_id, lang)
    book = get_book_or_404(session, book_id, lang)
    if book.series_id == series_id:
        book.series_id = None
        book.series_index = None
        session.add(book)
        session.commit()
    return series_card(session, series, CURRENT_USER_ID)
