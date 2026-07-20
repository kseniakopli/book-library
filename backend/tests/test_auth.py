# Basic Auth для внешнего теста (задача 81, план деплоя п.1.1).
# Включается только когда заданы обе env-переменные — поэтому остальные
# тесты проекта работают без пароля.
import base64


def _basic(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_auth_disabled_without_env(client):
    assert client.get("/api/v1/books").status_code == 200


def test_auth_rejects_without_credentials(client, monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_USER", "tester")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "secret")
    r = client.get("/api/v1/books")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"].startswith("Basic")


def test_auth_rejects_wrong_password(client, monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_USER", "tester")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "secret")
    assert client.get("/api/v1/books", headers=_basic("tester", "wrong")).status_code == 401


def test_auth_accepts_valid_credentials(client, monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_USER", "tester")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "secret")
    assert client.get("/api/v1/books", headers=_basic("tester", "secret")).status_code == 200


def test_health_open_even_with_auth(client, monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_USER", "tester")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "secret")
    assert client.get("/health").status_code == 200
