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


def test_csp_allows_embedded_third_parties(client):
    """CSP должна пропускать ровно то, что мы встроили, и не больше.

    Оба разрешения появились из-за реальных фич, и оба ломаются МОЛЧА: локально
    Vite отдаёт страницу без CSP, поэтому промах виден только на проде —
    пустая рамка вместо плеера и неотправляемая форма без единой ошибки.
    """
    csp = client.get("/api/v1/books").headers["Content-Security-Policy"]

    assert "frame-src https://open.spotify.com" in csp   # з.29б, плеер плейлиста
    assert "https://formspree.io" in csp                 # з.30, лист ожидания
    # чужие фреймы по-прежнему запрещены
    assert "frame-ancestors 'none'" in csp


def test_csp_restricts_form_action(client):
    """`form-action` не наследуется от `default-src` — его легко забыть.

    Без директивы форму с нашей страницы можно отправить на чужой адрес.
    Лист ожидания уходит через `fetch`, поэтому 'self' безопасен; если когда-то
    появится настоящий сабмит на сторонний приёмник, этот тест напомнит,
    что адрес надо внести сюда явно."""
    csp = client.get("/api/v1/books").headers["Content-Security-Policy"]

    assert "form-action 'self'" in csp


def test_hsts_present_and_not_overlong(client):
    """HSTS есть, но срок короткий.

    `force_https` в fly.toml — только редирект: первый запрос по http уходит
    открытым. HSTS его убирает, но за это браузер запоминает домен, и годичный
    `max-age` при переезде на домен без сертификата сделал бы сайт недоступным
    для всех, кто уже заходил. Поднимать срок — осознанно, вместе с переездом,
    поэтому верхняя граница проверяется тестом."""
    value = client.get("/api/v1/books").headers["Strict-Transport-Security"]

    assert value.startswith("max-age=")
    assert 0 < int(value.split("=", 1)[1]) <= 604_800   # не больше недели


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
