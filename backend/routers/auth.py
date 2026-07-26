# HTTP-слой авторизации (этап 9). Логика — в services/auth.py.
#
# Поток входа целиком:
#   1. фронт ведёт пользователя на /auth/google/login?invite=КОД
#   2. мы редиректим на согласие Google (state несёт инвайт-код и защищает от CSRF)
#   3. Google возвращает пользователя на /auth/google/callback?code=...&state=...
#   4. меняем код на профиль, находим/заводим пользователя, ставим куку
#   5. редиректим на «/» — фронт спрашивает /auth/me и видит вошедшего
import os

from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from deps import current_user, get_session
from models import User
from services.auth import (
    SESSION_COOKIE,
    SESSION_DAYS,
    AuthError,
    build_login_url,
    create_session_token,
    exchange_code,
    login_or_register,
    oauth_configured,
    read_state,
)

router = APIRouter(tags=["auth"])


def _secure_cookies() -> bool:
    """На проде кука только по HTTPS. Локально (http://127.0.0.1) флаг Secure
    запретил бы её вовсе, поэтому включаем по переменной окружения."""
    return os.getenv("COOKIE_SECURE", "0") == "1"


@router.get("/auth/google/login")
def google_login(invite: str = ""):
    """Шаг 1: уводим на согласие Google."""
    if not oauth_configured():
        return RedirectResponse("/login?error=oauth_not_configured", status_code=303)
    return RedirectResponse(build_login_url(invite), status_code=303)


@router.get("/auth/google/callback")
def google_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    session: Session = Depends(get_session),
):
    """Шаг 2: возврат от Google. Любая осечка — редирект на /login с причиной
    (страница входа покажет человеческий текст), а не голый JSON с 4xx."""
    if error or not code:
        return RedirectResponse("/login?error=cancelled", status_code=303)

    payload = read_state(state)
    if payload is None:
        # чужой или просроченный state — возможная CSRF-попытка
        return RedirectResponse("/login?error=bad_state", status_code=303)

    profile = exchange_code(code)
    if profile is None:
        return RedirectResponse("/login?error=google_failed", status_code=303)

    try:
        user = login_or_register(session, profile, payload.get("invite", ""))
    except AuthError as e:
        return RedirectResponse(f"/login?error={e}", status_code=303)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id),
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,          # скрипты страницы токен не прочитают
        samesite="lax",         # не уходит на чужие сайты, но переживает возврат с Google
        secure=_secure_cookies(),
        path="/",
    )
    return response


@router.post("/auth/logout")
def logout(response: Response):
    """Выход: гасим куку. Токен без неё предъявить нечем."""
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    """Кто я. Фронт зовёт при загрузке: 401 → страница входа.
    `is_admin` нужен, чтобы прятать админские кнопки (задачи 32/90)."""
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "is_admin": user.is_admin,
    }


@router.get("/auth/status")
def status():
    """Настроен ли вход через Google — чтобы страница входа не показывала
    кнопку, которая заведомо не сработает. Без авторизации (её ещё нет)."""
    return {"oauth_configured": oauth_configured()}
