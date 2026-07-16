# Spotify-плейлисты (этап 10.2): создание плейлиста по музыкальной атмосфере книги.
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

import database
import services.spotify as spotify_service
from constants import EVENT_PLAYLIST_CREATED
from deps import get_book_or_404, get_lang
from events import log_event
from i18n import msg
from models import AISelection, Book

router = APIRouter(tags=["spotify"])

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


def _create_and_save(session: Session, book, lang: str) -> dict:
    songs = _collect_songs(session, book.id)
    if not songs:
        raise HTTPException(status_code=400, detail=msg("no_music_for_playlist", lang))
    result = spotify_service.create_playlist_from_songs(
        f"Nocturne · {book.title}", songs
    )
    book.spotify_playlist_url = result["url"]
    session.add(book)
    session.commit()
    log_event(EVENT_PLAYLIST_CREATED, book.id, detail=f"found={result['found']}")
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


@router.get("/callback")
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
