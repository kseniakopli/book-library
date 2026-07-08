import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

import main
from main import Book


@pytest.fixture(name="client")
def client_fixture():
    # Своя база в памяти — реальную library.db тесты не трогают.
    test_engine = create_engine(
        "sqlite://",                                 # "" = база живёт в оперативке
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,                        # одно соединение на весь тест
    )
    SQLModel.metadata.create_all(test_engine)
    main.engine = test_engine                        # подменяем движок в приложении

    # Кладём одну книгу-подопытную (получит id = 1).
    with Session(test_engine) as session:
        session.add(Book(title="Test", author="Author", status="want"))
        session.commit()

    yield TestClient(main.app)                        # отдаём тесту готовый клиент


def test_read_and_rating(client):
    # Прочитана + оценка 8 — всё сохраняется.
    r = client.patch("/books/1", json={"status": "read", "rating": 8})
    assert r.status_code == 200
    assert r.json()["status"] == "read"
    assert r.json()["rating"] == 8


def test_rating_cleared_when_leaving_read(client):
    # read -> want: оценка должна обнулиться.
    client.patch("/books/1", json={"status": "read", "rating": 8})
    r = client.patch("/books/1", json={"status": "want"})
    assert r.status_code == 200
    assert r.json()["rating"] is None


def test_rating_out_of_range(client):
    # Оценка вне диапазона 1..10 — ошибка 400.
    r = client.patch("/books/1", json={"status": "read", "rating": 11})
    assert r.status_code == 400


def test_rating_requires_read(client):
    # Оценка для непрочитанной книги — ошибка 400.
    r = client.patch("/books/1", json={"status": "want", "rating": 7})
    assert r.status_code == 400


def test_invalid_status(client):
    # Недопустимый статус — ошибка 400.
    r = client.patch("/books/1", json={"status": "finished"})
    assert r.status_code == 400


def test_book_not_found(client):
    # Нет такой книги — ошибка 404.
    r = client.patch("/books/999", json={"status": "read"})
    assert r.status_code == 404