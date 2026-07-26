# Авторизация через Google (этап 9). Basic Auth — в соседнем test_auth.py.
# Сам поход в Google не тестируем (сеть) — проверяем НАШУ часть: закрыт ли API
# без сессии, правила инвайтов, привязку аккаунта владельца, куку сессии.
import pytest
from sqlmodel import Session, select

import database
from main import app
from models import Invite, User
from services import auth as auth_service


@pytest.fixture(name="anon")
def anon_fixture(client):
    """Клиент без подмены зависимости — то есть неавторизованный.
    conftest по умолчанию входит «за пользователя 1»; здесь снимаем это."""
    app.dependency_overrides.clear()
    return client


def _profile(email="new@example.com", sub="google-123"):
    return {"sub": sub, "email": email, "name": "Новый", "picture": None}


# --- доступ ---

def test_api_requires_login(anon):
    """Без сессии API закрыт целиком: 401, а не пустой список."""
    assert anon.get("/api/v1/books").status_code == 401
    assert anon.get("/api/v1/stats").status_code == 401
    assert anon.post(
        "/api/v1/books", json={"title": "X", "author": "Y"}
    ).status_code == 401


def test_auth_endpoints_are_open(anon):
    """Страница входа должна работать до авторизации."""
    assert anon.get("/api/v1/auth/status").status_code == 200
    assert anon.get("/api/v1/auth/me").status_code == 401   # но «кто я» — 401


def test_me_returns_current_user(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["id"] == 1
    assert r.json()["is_admin"] is True   # по нему фронт прячет админ-кнопки


def test_session_cookie_roundtrip():
    """Кука подписана: свой токен читается, чужой — нет."""
    token = auth_service.create_session_token(42)
    assert auth_service.read_session_token(token) == 42
    assert auth_service.read_session_token("подделка") is None
    assert auth_service.read_session_token(None) is None


# --- инвайты ---

def test_registration_requires_invite(client):
    with Session(database.engine) as session:
        with pytest.raises(auth_service.AuthError) as e:
            auth_service.login_or_register(session, _profile(), "")
        assert str(e.value) == "need_invite"

        with pytest.raises(auth_service.AuthError) as e:
            auth_service.login_or_register(session, _profile(), "нет-такого-кода")
        assert str(e.value) == "bad_invite"


def test_registration_with_invite_creates_user_and_burns_code(client):
    with Session(database.engine) as session:
        session.add(Invite(code="КОД-1", note="подруга"))
        session.commit()

        user = auth_service.login_or_register(session, _profile(), "КОД-1")
        assert user.id != 1                 # новый пользователь, не владелец
        assert user.is_admin is False       # админ только владелец
        assert user.email == "new@example.com"

        invite = session.exec(select(Invite).where(Invite.code == "КОД-1")).one()
        assert invite.used_by_user_id == user.id

        # повторно тот же код не сработает — уже у ДРУГОГО человека
        # (другая почта и другой google_sub, иначе это просто повторный вход)
        with pytest.raises(auth_service.AuthError) as e:
            auth_service.login_or_register(
                session, _profile(email="other@example.com", sub="other"), "КОД-1"
            )
        assert str(e.value) == "invite_used"


def test_second_login_finds_user_by_google_sub(client):
    """Второй вход — без инвайта: аккаунт уже знаком по google_sub."""
    with Session(database.engine) as session:
        session.add(Invite(code="КОД-2"))
        session.commit()
        first = auth_service.login_or_register(session, _profile(), "КОД-2")
        again = auth_service.login_or_register(session, _profile(), "")
        assert again.id == first.id


def test_admin_email_links_owner_account(client, monkeypatch):
    """Владелец: её Google-почта цепляется к СУЩЕСТВУЮЩЕЙ записи админа (id=1),
    иначе после миграции 0013 Ксения вошла бы в пустую чужую полку."""
    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
    with Session(database.engine) as session:
        user = auth_service.login_or_register(
            session, _profile(email="owner@example.com", sub="google-owner"), ""
        )
        assert user.id == 1                 # та самая запись со 202 книгами
        assert user.is_admin is True
        assert user.google_sub == "google-owner"


def test_existing_email_links_without_invite(client):
    """Пользователя завели заранее (скриптом) — вход по совпадению почты."""
    with Session(database.engine) as session:
        session.add(User(display_name="Гость", email="guest@example.com"))
        session.commit()
        user = auth_service.login_or_register(
            session, _profile(email="guest@example.com", sub="google-guest"), ""
        )
        assert user.display_name == "Гость"
        assert user.google_sub == "google-guest"
