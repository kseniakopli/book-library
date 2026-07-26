# Общие зависимости и helpers для роутеров (рефакторинг R3):
# убирают дублирование «проверь lang» и «возьми книгу или 404».
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

import database
from i18n import ALLOWED_LANGS, msg
from models import Book, User, UserBook
from services.auth import SESSION_COOKIE, read_session_token


def get_session():
    """FastAPI-зависимость: сессия БД на время запроса (задача 77).
    Роутеры пишут `session: Session = Depends(get_session)` вместо ручного
    `with Session(database.engine)`.

    ⚠ Не для эндпоинтов с долгими внешними вызовами: генерация атмосферы и
    рекомендаций сознательно открывает КОРОТКУЮ сессию, закрывает её и только
    потом идёт в AI (до 90 с) — иначе соединение висело бы всё это время.

    `database.engine` читается в момент вызова, поэтому подмена движка
    в тестах (in-memory база) продолжает работать."""
    with Session(database.engine) as session:
        yield session


def get_lang(lang: str = "ru") -> str:
    """FastAPI-dependency: валидирует query-параметр lang.
    Использование: lang: str = Depends(get_lang)"""
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=msg("bad_lang", lang))
    return lang


def current_user(
    request: Request, session: Session = Depends(get_session)
) -> User:
    """Этап 9: текущий пользователь из подписанной сессионной куки.

    Пришла на смену константе `CURRENT_USER_ID = 1`. Подключена на уровне
    роутеров (`dependencies=[...]` в main.py), поэтому новый эндпоинт защищён
    по умолчанию — про авторизацию нельзя забыть.
    В тестах подменяется через `app.dependency_overrides` (см. conftest)."""
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    user = session.get(User, user_id) if user_id is not None else None
    if user is None:
        # 401, а не 403: фронт по этому коду отправляет на страницу входа
        raise HTTPException(status_code=401, detail=msg("auth_required", "ru"))
    return user


def current_user_id(user: User = Depends(current_user)) -> int:
    """Ярлык для эндпоинтов, которым нужен только id владельца полки."""
    return user.id


def get_book_or_404(session: Session, book_id: int, lang: str) -> Book:
    """Книга (общий каталог) по id или HTTP 404."""
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail=msg("book_not_found", lang))
    return book


def get_userbook_or_404(
    session: Session, book_id: int, lang: str, user_id: int
) -> UserBook:
    """Запись полки (книга у пользователя) или 404, если книги нет на полке."""
    ub = session.exec(
        select(UserBook).where(
            UserBook.user_id == user_id, UserBook.book_id == book_id
        )
    ).first()
    if ub is None:
        raise HTTPException(status_code=404, detail=msg("book_not_found", lang))
    return ub


def require_admin(session: Session, lang: str, user_id: int) -> User:
    """Проверка прав: правка общих данных книги и перегенерация — только admin.
    Возвращает пользователя или бросает 403."""
    user = session.get(User, user_id)
    if user is None or not user.is_admin:
        raise HTTPException(status_code=403, detail=msg("admin_only", lang))
    return user
