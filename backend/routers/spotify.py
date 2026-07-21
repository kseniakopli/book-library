# Spotify-плейлисты (этап 10.2): создание плейлиста по музыкальной атмосфере книги.
# + QR-код плейлиста для печатной карточки (этап 10.4).
import io
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlmodel import Session, select

import database
import services.spotify as spotify_service
from constants import EVENT_PLAYLIST_CREATED
from deps import get_book_or_404, get_lang
from events import log_event
from i18n import msg
from models import AISelection, Book
from services.cover_art import build_cover

router = APIRouter(tags=["spotify"])

# Задача 34: /callback живёт БЕЗ префикса /api/v1 — этот адрес зарегистрирован
# как redirect URI в кабинете Spotify, менять его там не хотим
callback_router = APIRouter(tags=["spotify"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def _collect_songs(session: Session, book_id: int) -> list[dict]:
    """Все треки музыкальной атмосферы книги (оба AI-источника, с дедупликацией)."""
    rows = session.exec(
        select(AISelection).where(
            AISelection.book_id == book_id,
            AISelection.category == "music",
        )
    ).all()
    songs = []
    for row in rows:
        songs.extend(json.loads(row.payload))
    return spotify_service.dedupe_songs(songs)


def _book_cover(session: Session, book_id: int) -> str | None:
    """base64-JPEG обложки плейлиста из символа паспорта (20.07).
    Паспорта нет или растеризация не удалась — вернём None, плейлист
    создастся с обычной мозаикой обложек треков."""
    design = session.exec(
        select(AISelection).where(
            AISelection.book_id == book_id,
            AISelection.category == "design",
        )
    ).first()
    return build_cover(design.payload) if design else None


def _create_and_save(session: Session, book, lang: str) -> dict:
    songs = _collect_songs(session, book.id)
    if not songs:
        raise HTTPException(status_code=400, detail=msg("no_music_for_playlist", lang))
    result = spotify_service.create_playlist_from_songs(
        f"nocturne · {book.title}", songs, cover=_book_cover(session, book.id)
    )
    book.spotify_playlist_url = result["url"]
    session.add(book)
    session.commit()
    log_event(EVENT_PLAYLIST_CREATED, book.id, detail={
        "found": result["found"],
        "cover_set": result.get("cover_set", False),
        # какие треки не нашлись — видно, где промахивается поиск (з.80)
        "not_found": result["not_found"],
    })
    return {
        "status": "created",
        "playlist_url": result["url"],
        "found": result["found"],
        "not_found": result["not_found"],
    }


@router.post("/books/{book_id}/playlist")
def create_book_playlist(book_id: int, lang: str = Depends(get_lang)):
    """Создать Spotify-плейлист по музыке книги. Если авторизации ещё не было —
    возвращает ссылку на окно Spotify (фронт откроет её в новой вкладке)."""
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)

        if book.spotify_playlist_url:
            return {"status": "exists", "playlist_url": book.spotify_playlist_url}

        if not spotify_service.has_token():
            return {
                "status": "auth_required",
                "auth_url": spotify_service.auth_url(state=str(book_id)),
            }

        return _create_and_save(session, book, lang)


@router.get("/books/{book_id}/qr")
def playlist_qr(book_id: int, lang: str = Depends(get_lang)):
    """QR-код со ссылкой на Spotify-плейлист книги (для печатной карточки).
    QR статичен: кодирует постоянный URL плейлиста, «протухнуть» не может."""
    with Session(database.engine) as session:
        book = get_book_or_404(session, book_id, lang)
        url = book.spotify_playlist_url
    if not url:
        raise HTTPException(status_code=404, detail=msg("no_playlist_for_qr", lang))

    import qrcode  # импорт внутри: библиотека нужна только этому эндпоинту

    img = qrcode.make(url, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@callback_router.get("/callback")
def spotify_callback(code: str, state: str = "", lang: str = "ru"):
    """Возврат из окна Spotify: сохраняем refresh_token (одноразовая авторизация),
    сразу создаём плейлист для книги из state и возвращаем на её страницу."""
    spotify_service.exchange_code(code)

    if state.isdigit():
        with Session(database.engine) as session:
            book = session.get(Book, int(state))
            if book is not None and not book.spotify_playlist_url:
                try:
                    _create_and_save(session, book, lang)
                except HTTPException:
                    pass  # нет музыки — просто вернём на страницу книги
        return RedirectResponse(f"{FRONTEND_URL}/books/{state}")
    return RedirectResponse(FRONTEND_URL)
