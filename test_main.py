import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

import database
from models import Book
from main import app


@pytest.fixture(name="client")
def client_fixture():
    # Своя база в памяти — реальную library.db тесты не трогают.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    database.engine = test_engine            # подменяем движок, которым пользуются эндпоинты

    with Session(test_engine) as session:
        session.add(Book(title="Test", author="Author", status="want"))
        session.commit()

    yield TestClient(app)


def test_read_and_rating(client):
    r = client.patch("/books/1", json={"status": "read", "rating": 8})
    assert r.status_code == 200
    assert r.json()["status"] == "read"
    assert r.json()["rating"] == 8


def test_rating_cleared_when_leaving_read(client):
    client.patch("/books/1", json={"status": "read", "rating": 8})
    r = client.patch("/books/1", json={"status": "want"})
    assert r.status_code == 200
    assert r.json()["rating"] is None


def test_rating_out_of_range(client):
    r = client.patch("/books/1", json={"status": "read", "rating": 11})
    assert r.status_code == 400


def test_rating_requires_read(client):
    r = client.patch("/books/1", json={"status": "want", "rating": 7})
    assert r.status_code == 400


def test_invalid_status(client):
    r = client.patch("/books/1", json={"status": "finished"})
    assert r.status_code == 400


def test_book_not_found(client):
    r = client.patch("/books/999", json={"status": "read"})
    assert r.status_code == 404