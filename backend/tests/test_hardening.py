# Прод-обвязка (план деплоя п.1.3): лимиты частоты, security-заголовки,
# admin-гейт на массовые backfill-операции.
import pytest

import rate_limit


@pytest.fixture(autouse=True)
def _clean_counters():
    """Счётчики лимитера живут в памяти процесса — чистим между тестами."""
    rate_limit.reset()
    yield
    rate_limit.reset()


# --- лимиты частоты (задача 39) ---

def test_ai_endpoint_rate_limited(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AI", "2")
    # генерацию не гоняем по-настоящему: важен сам счётчик, а не результат
    for _ in range(2):
        client.post("/api/v1/stats/insights")
    r = client.post("/api/v1/stats/insights")
    assert r.status_code == 429
    assert r.headers["Retry-After"].isdigit()


def test_reads_are_not_limited(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AI", "1")
    client.post("/api/v1/stats/insights")
    # чтение списка книг под лимит не попадает, сколько бы раз ни звали
    for _ in range(5):
        assert client.get("/api/v1/books").status_code == 200


def test_limit_can_be_disabled(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AI", "0")
    for _ in range(4):
        assert client.post("/api/v1/stats/insights").status_code != 429


# --- security-заголовки (задача 40) ---

def test_security_headers_present(client):
    r = client.get("/api/v1/books")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_security_headers_on_errors(client):
    """Заголовки должны быть и на ошибочных ответах (middleware — самый внешний)."""
    r = client.get("/api/v1/books/999")
    assert r.status_code == 404
    assert r.headers["X-Content-Type-Options"] == "nosniff"


# --- admin-гейт на backfill (план деплоя п.1.3) ---

def test_backfill_requires_admin(client, monkeypatch):
    from sqlmodel import Session

    import database
    from models import User

    with Session(database.engine) as session:
        user = session.get(User, 1)
        user.is_admin = False          # обычный тестер, не админ
        session.add(user)
        session.commit()

    assert client.post("/api/v1/books/backfill-metadata").status_code == 403
    assert client.post("/api/v1/books/backfill-covers").status_code == 403
