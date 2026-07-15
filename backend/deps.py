# Общие зависимости и helpers для роутеров (рефакторинг R3):
# убирают дублирование «проверь lang» и «возьми книгу или 404».
from fastapi import HTTPException
from sqlmodel import Session

from i18n import ALLOWED_LANGS, msg
from models import Book


def get_lang(lang: str = "ru") -> str:
    """FastAPI-dependency: валидирует query-параметр lang.
    Использование: lang: str = Depends(get_lang)"""
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))
    return lang


def get_book_or_404(session: Session, book_id: int, lang: str) -> Book:
    """Книга по id или HTTP 404 с локализованным сообщением."""
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail=msg("book_not_found", lang))
    return book
