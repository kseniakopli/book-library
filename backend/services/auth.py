# Аутентификация через Google OAuth (этап 9, задачи 31/32).
#
# Почему так:
# - Паролей у себя НЕ храним — их проверяет Google. Нам достаточно `sub`
#   (стабильный id аккаунта) и почты. Нет хеширования, восстановления пароля,
#   утечки паролей.
# - Сессия — подписанный JWT в httpOnly-куке. httpOnly = скрипты страницы токен
#   не прочитают (защита от XSS-кражи); SameSite=Lax = кука не уходит на чужие
#   сайты, но переживает возврат с Google.
# - Регистрация только по инвайт-коду: каждый пользователь тратит платные
#   AI-вызовы, свободная регистрация = чужие люди за твой счёт.
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
import requests
from dotenv import load_dotenv
from sqlmodel import Session, select

from models import Invite, User

# Читаем backend/.env здесь же: модуль импортируется и из скриптов, где
# services/ai.py (который тоже зовёт load_dotenv) может не подгружаться.
load_dotenv()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

SESSION_COOKIE = "nocturne_session"
SESSION_DAYS = 30          # столько живёт вход без повторной авторизации
STATE_MINUTES = 10         # столько действует «билет» на возврат с Google
ALGORITHM = "HS256"

# Секрет подписи сессионных кук. В проде задаётся переменной окружения
# (fly secrets set SESSION_SECRET=...). Локально, если не задан, генерируем
# случайный на время процесса: вход работает, но после перезапуска придётся
# войти заново — приемлемо для разработки и безопаснее «дефолтного секрета».
_EPHEMERAL_SECRET = secrets.token_urlsafe(32)


def _secret() -> str:
    return os.getenv("SESSION_SECRET") or _EPHEMERAL_SECRET


def oauth_configured() -> bool:
    """Есть ли ключи Google OAuth. Без них вход невозможен — фронт покажет
    понятное сообщение вместо неработающей кнопки."""
    return bool(os.getenv("GOOGLE_OAUTH_CLIENT_ID")) and bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    )


def _redirect_uri() -> str:
    """Должен СОВПАДАТЬ с адресом, зарегистрированным в Google Cloud Console
    (Authorized redirect URIs), иначе Google вернёт redirect_uri_mismatch.

    ⚠ Дефолт указывает на ФРОНТ (5173), а не на бэкенд (8000), хотя обрабатывает
    запрос бэкенд: Vite проксирует /api на него. Причина — кука. Вернись Google
    на 127.0.0.1:8000, кука сессии осталась бы у хоста 127.0.0.1, а приложение
    открыто на localhost — для браузера это РАЗНЫЕ хосты, и куку он бы не прислал.
    Через прокси весь вход происходит на одном origin (localhost:5173)."""
    return os.getenv(
        "GOOGLE_OAUTH_REDIRECT",
        "http://localhost:5173/api/v1/auth/google/callback",
    )


# --- шаг 1: уводим пользователя на Google ---

def build_login_url(invite_code: str | None) -> str:
    """Адрес согласия Google. `state` — подписанный нами билет: он и защищает
    от CSRF (вернуться может только наш же state), и переносит инвайт-код через
    редирект, чтобы не хранить его в сессии на сервере."""
    state = jwt.encode(
        {
            "invite": (invite_code or "").strip(),
            "nonce": secrets.token_urlsafe(8),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_MINUTES),
        },
        _secret(),
        algorithm=ALGORITHM,
    )
    params = {
        "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",   # даём выбрать аккаунт, а не молча войти
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def read_state(state: str) -> dict | None:
    """Разобрать вернувшийся state. Чужая или просроченная подпись → None."""
    try:
        return jwt.decode(state, _secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


# --- шаг 2: меняем код на профиль ---

def exchange_code(code: str) -> dict | None:
    """Обменять одноразовый код на профиль пользователя.

    id_token приходит от Google по HTTPS в ответ на наш запрос с client_secret,
    то есть канал уже доверенный — подпись токена отдельно не проверяем
    (Google это прямо разрешает для authorization-code flow). Проверяем только,
    что токен выдан НАМ (aud) и что почта подтверждена."""
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if response.status_code != 200:
        print("Google OAuth: обмен кода не удался:", response.status_code, response.text[:200])
        return None

    id_token = response.json().get("id_token")
    if not id_token:
        return None
    claims = jwt.decode(id_token, options={"verify_signature": False})

    if claims.get("aud") != os.getenv("GOOGLE_OAUTH_CLIENT_ID"):
        print("Google OAuth: id_token выдан другому приложению")
        return None
    if not claims.get("email") or claims.get("email_verified") is False:
        print("Google OAuth: почта не подтверждена")
        return None

    return {
        "sub": claims["sub"],
        "email": claims["email"],
        "name": claims.get("name") or claims["email"].split("@")[0],
        "picture": claims.get("picture"),
    }


# --- шаг 3: находим или заводим пользователя ---

class AuthError(Exception):
    """Причина отказа во входе — код передаётся фронту в query-параметре."""


def login_or_register(session: Session, profile: dict, invite_code: str) -> User:
    """Вернуть пользователя для профиля Google.

    Порядок поиска: по `google_sub` (аккаунт уже входил) → по email (первый
    вход: почта совпала с заведённой записью — в том числе с твоей исходной
    id=1, ADMIN_EMAIL) → регистрация по инвайт-коду."""
    user = session.exec(
        select(User).where(User.google_sub == profile["sub"])
    ).first()
    if user:
        return _touch(session, user, profile)

    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    by_email = session.exec(
        select(User).where(User.email == profile["email"])
    ).first()
    # владелец сервиса: почта из ADMIN_EMAIL цепляется к существующей
    # записи админа (у неё ещё нет ни email, ни google_sub) — иначе после
    # миграции 0013 хозяин библиотеки не смог бы войти в свою же полку
    if by_email is None and admin_email and profile["email"].lower() == admin_email:
        by_email = session.exec(
            select(User).where(User.is_admin == True, User.google_sub == None)  # noqa: E712,E711
        ).first()
    if by_email:
        by_email.google_sub = profile["sub"]
        return _touch(session, by_email, profile)

    invite = _take_invite(session, invite_code)
    user = User(
        display_name=profile["name"],
        email=profile["email"],
        google_sub=profile["sub"],
        avatar_url=profile["picture"],
        is_admin=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    invite.used_by_user_id = user.id
    invite.used_at = datetime.now()
    session.add(invite)
    session.commit()
    session.refresh(user)
    return user


def _take_invite(session: Session, code: str) -> Invite:
    code = (code or "").strip()
    if not code:
        raise AuthError("need_invite")
    invite = session.exec(select(Invite).where(Invite.code == code)).first()
    if invite is None:
        raise AuthError("bad_invite")
    if invite.used_by_user_id is not None:
        raise AuthError("invite_used")
    return invite


def _touch(session: Session, user: User, profile: dict) -> User:
    """Обновить профиль из Google (сменил аватар/имя — увидим это)."""
    user.email = profile["email"]
    user.avatar_url = profile["picture"]
    if not user.display_name:
        user.display_name = profile["name"]
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# --- сессионная кука ---

def create_session_token(user_id: int) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
        },
        _secret(),
        algorithm=ALGORITHM,
    )


def read_session_token(token: str | None) -> int | None:
    """id пользователя из куки. Подделка, порча или истёкший срок → None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
