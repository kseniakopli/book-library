# CRUD книг: статусы, оценки, локализация, удаление, фоновое обогащение.
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

import database
from conftest import fake_book_info
from models import Book


# --- статусы и оценки ---

def test_read_and_rating(client):
    r = client.patch("/api/v1/books/1", json={"status": "read", "rating": 8})
    assert r.status_code == 200
    assert r.json()["status"] == "read"
    assert r.json()["rating"] == 8


def test_rating_cleared_when_leaving_read(client):
    client.patch("/api/v1/books/1", json={"status": "read", "rating": 8})
    r = client.patch("/api/v1/books/1", json={"status": "want"})
    assert r.status_code == 200
    assert r.json()["rating"] is None


def test_rating_out_of_range(client):
    assert client.patch("/api/v1/books/1", json={"status": "read", "rating": 11}).status_code == 400


def test_rating_requires_read(client):
    assert client.patch("/api/v1/books/1", json={"status": "want", "rating": 7}).status_code == 400


def test_invalid_status(client):
    assert client.patch("/api/v1/books/1", json={"status": "finished"}).status_code == 400


def test_book_not_found(client):
    assert client.patch("/api/v1/books/999", json={"status": "read"}).status_code == 404


# --- задача 3: ручная правка полей ---

def test_edit_book_fields(client):
    r = client.patch("/api/v1/books/1", json={
        "title": "  Новое название  ",
        "author": "Новый автор",
        "isbn": "978-5-00-000000-0",
        "cover_url": "https://example.com/cover.jpg",
        "description": "Новое описание",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Новое название"          # пробелы обрезаны
    assert body["author"] == "Новый автор"
    assert body["isbn"] == "978-5-00-000000-0"
    assert body["cover_url"] == "https://example.com/cover.jpg"
    assert body["description"] == "Новое описание"


def test_edit_empty_title_rejected(client):
    assert client.patch("/api/v1/books/1", json={"title": "   "}).status_code == 400
    assert client.patch("/api/v1/books/1", json={"author": ""}).status_code == 400


def test_edit_cover_requires_https(client):
    r = client.patch("/api/v1/books/1", json={"cover_url": "http://insecure.com/x.jpg"})
    assert r.status_code == 422    # валидатор схемы (та же политика, что в POST)


def test_edit_empty_strings_clear_optional_fields(client):
    client.patch("/api/v1/books/1", json={
        "isbn": "978-5-00-000000-0",
        "cover_url": "https://example.com/cover.jpg",
        "description": "Описание",
    })
    r = client.patch("/api/v1/books/1", json={"isbn": "", "cover_url": "", "description": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["isbn"] is None
    assert body["cover_url"] is None
    assert body["description"] is None


def test_read_at_set_and_cleared_with_status(client):
    """Задача 1: стал read без даты — ставится «сейчас»; ушёл из read — чистится."""
    r = client.patch("/api/v1/books/1", json={"status": "read"})
    assert r.json()["read_at"] is not None

    r = client.patch("/api/v1/books/1", json={"status": "want"})
    assert r.json()["read_at"] is None


def test_read_at_explicit_value_accepted(client):
    r = client.patch(
        "/api/v1/books/1", json={"status": "read", "read_at": "2026-05-01T00:00:00"}
    )
    assert r.json()["read_at"].startswith("2026-05-01")


def test_db_enforces_rating_only_for_read(client):
    """Задача 7: CHECK в БД отбивает оценку у непрочитанной книги,
    даже если какой-то будущий код забудет про инвариант.
    После рефакторинга инвариант живёт на userbook (личная полка)."""
    from models import UserBook
    with Session(database.engine) as session:
        book = Book(title="X", author="Y")
        session.add(book)
        session.commit()
        session.refresh(book)
        session.add(UserBook(user_id=1, book_id=book.id, status="want", rating=7))
        with pytest.raises(IntegrityError):
            session.commit()


# --- локализация ---

def test_lang_default_is_russian(client):
    r = client.patch("/api/v1/books/999", json={"status": "read"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Книга не найдена"


def test_lang_en_book_not_found(client):
    r = client.patch("/api/v1/books/999?lang=en", json={"status": "read"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Book not found"


def test_lang_en_invalid_status(client):
    r = client.patch("/api/v1/books/1?lang=en", json={"status": "finished"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Status must be want, reading or read"


def test_lang_en_rating_needs_read(client):
    r = client.patch("/api/v1/books/1?lang=en", json={"status": "want", "rating": 7})
    assert r.status_code == 400
    assert r.json()["detail"] == "Rating is only allowed for books with status 'read'"


def test_invalid_lang_rejected(client):
    r = client.patch("/api/v1/books/1?lang=fr", json={})
    assert r.status_code == 400
    assert r.json()["detail"] == "lang должен быть ru или en"


# --- чтение и удаление ---

def test_get_book(client):
    r = client.get("/api/v1/books/1")
    assert r.status_code == 200
    assert r.json()["title"] == "Test"


def test_list_books_pagination(client, monkeypatch):
    """Задача 34: limit/offset поддерживаются; без них — вся библиотека."""
    import services.enrichment as enrichment
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)
    client.post("/api/v1/books", json={"title": "Вторая", "author": "А"})
    client.post("/api/v1/books", json={"title": "Третья", "author": "Б"})

    assert len(client.get("/api/v1/books").json()) == 3
    page = client.get("/api/v1/books?limit=1&offset=1").json()
    assert len(page) == 1
    assert page[0]["title"] == "Вторая"


def test_get_book_not_found(client):
    assert client.get("/api/v1/books/999").status_code == 404


def test_delete_book(client):
    assert client.delete("/api/v1/books/1").status_code == 200
    assert client.patch("/api/v1/books/1", json={"status": "read"}).status_code == 404


def test_delete_book_not_found(client):
    assert client.delete("/api/v1/books/999").status_code == 404


# --- добавление с фоновым обогащением ---

def test_add_book_enriches_in_background(client, monkeypatch):
    import services.enrichment as enrichment
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)
    r = client.post("/api/v1/books", json={"title": "New", "author": "Auth"})
    assert r.status_code == 200
    assert r.json()["enrich_status"] == "pending"   # ответ ушёл до обогащения
    book_id = r.json()["id"]
    r2 = client.get(f"/api/v1/books/{book_id}")            # TestClient уже выполнил фон
    assert r2.json()["enrich_status"] == "ready"
    assert r2.json()["cover_url"] == "http://example.com/c.jpg"


def test_add_book_enrichment_failure_sets_failed(client, monkeypatch):
    import services.enrichment as enrichment

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(enrichment, "fetch_book_info", boom)
    r = client.post("/api/v1/books", json={"title": "New2", "author": "Auth"})
    book_id = r.json()["id"]
    assert client.get(f"/api/v1/books/{book_id}").json()["enrich_status"] == "failed"


def test_add_book_with_external_id(client, monkeypatch):
    import services.enrichment as enrichment
    monkeypatch.setattr(
        enrichment, "fetch_volume_by_id", lambda vid: fake_book_info("t", "a")
    )
    r = client.post("/api/v1/books", json={
        "title": "T", "author": "A",
        "cover_url": "https://example.com/candidate.jpg",
        "external_id": "abc123",
    })
    assert r.json()["cover_url"] == "https://example.com/candidate.jpg"  # видна сразу
    book_id = r.json()["id"]
    r2 = client.get(f"/api/v1/books/{book_id}")
    assert r2.json()["enrich_status"] == "ready"
    assert r2.json()["description"] == "desc"   # доехало из fetch_volume_by_id


def test_add_book_with_status_and_date(client, monkeypatch):
    """Задача 18: статус и дата прочтения задаются при добавлении."""
    import services.enrichment as enrichment
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)
    r = client.post("/api/v1/books", json={
        "title": "Прочитанная", "author": "Автор",
        "status": "read", "read_at": "2026-06-01T00:00:00",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "read"
    assert r.json()["read_at"].startswith("2026-06-01")


def test_add_book_read_without_date_gets_now(client, monkeypatch):
    import services.enrichment as enrichment
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)
    r = client.post("/api/v1/books", json={
        "title": "Недавняя", "author": "Автор", "status": "read",
    })
    assert r.json()["read_at"] is not None


def test_add_book_bad_status_rejected(client):
    r = client.post("/api/v1/books", json={
        "title": "X", "author": "Y", "status": "finished",
    })
    assert r.status_code == 400


def test_add_book_rejects_non_https_cover(client):
    r = client.post("/api/v1/books", json={
        "title": "T", "author": "A", "cover_url": "javascript:alert(1)",
    })
    assert r.status_code == 422


def test_raw_metadata_not_exposed(client, monkeypatch):
    """R4/задача 34: внутренний raw_metadata не должен уходить в API-ответы."""
    import services.enrichment as enrichment
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)
    r = client.post("/api/v1/books", json={"title": "New", "author": "Auth"})
    book_id = r.json()["id"]
    body = client.get(f"/api/v1/books/{book_id}").json()
    assert "raw_metadata" not in body
    assert all("raw_metadata" not in b for b in client.get("/api/v1/books").json())


# --- рефакторинг User/Book/UserBook (18.07) ---

def test_add_duplicate_on_shelf_returns_409(client, monkeypatch):
    """Одна книга на полке пользователя — один раз (UNIQUE user+book)."""
    import services.enrichment as enrichment
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)
    client.post("/api/v1/books", json={"title": "Дубль", "author": "Автор"})
    r = client.post("/api/v1/books", json={"title": "Дубль", "author": "Автор"})
    assert r.status_code == 409


def test_add_existing_catalog_book_is_reused(client):
    """Книга уже в каталоге (но не на полке) → переиспользуется, дубля нет
    и оформление заново не генерится (design-фейк не понадобится)."""
    from sqlmodel import func, select
    from models import UserBook
    with Session(database.engine) as session:
        b = Book(title="Каталожная", author="Автор", enrich_status="ready")
        session.add(b)
        session.commit()
        session.refresh(b)
        cat_id = b.id

    r = client.post(
        "/api/v1/books",
        json={"title": "Каталожная", "author": "Автор", "book_id": cat_id},
    )
    assert r.status_code == 200
    assert r.json()["id"] == cat_id                 # та же книга, не новый дубль
    with Session(database.engine) as session:
        total_books = session.exec(select(func.count()).select_from(Book)).one()
        on_shelf = session.exec(
            select(UserBook).where(UserBook.book_id == cat_id)
        ).first()
    assert total_books == 2                          # Test + Каталожная, третьей не создано
    assert on_shelf is not None                      # книга легла на полку


def test_book_field_edit_requires_admin(client):
    """Правка общих полей книги — только admin; личные поля доступны всем."""
    from models import User
    with Session(database.engine) as session:
        user = session.get(User, 1)
        user.is_admin = False
        session.add(user)
        session.commit()

    # общее поле книги (название) — 403 для не-админа
    assert client.patch("/api/v1/books/1", json={"title": "Новое"}).status_code == 403
    # личное поле полки (статус) — по-прежнему можно
    assert client.patch("/api/v1/books/1", json={"status": "reading"}).status_code == 200


def test_health(client):
    """Задача 55: инфраструктурный эндпоинт жив и видит БД."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_add_book_generates_design_in_background(client, monkeypatch):
    """Задача 57: оформление создаётся фоном сразу при добавлении книги."""
    import services.enrichment as enrichment
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)

    r = client.post("/api/v1/books", json={"title": "Ночь", "author": "Автор"})
    book_id = r.json()["id"]

    design = client.get(f"/api/v1/books/{book_id}/atmosphere/design").json()
    assert len(design["selections"]) == 1
    payload = design["selections"][0]["payload"]
    assert "palette_dark" in payload and "palette_light" in payload


def test_background_design_is_idempotent(client, monkeypatch):
    """Повторный вызов фона не перезаписывает уже готовое оформление."""
    import asyncio
    import services.enrichment as enrichment
    from routers.atmosphere import design_in_background
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)

    book_id = client.post(
        "/api/v1/books", json={"title": "Ночь", "author": "Автор"}
    ).json()["id"]
    first = client.get(f"/api/v1/books/{book_id}/atmosphere/design").json()

    asyncio.run(design_in_background(book_id))   # второй заход — должен выйти сразу
    second = client.get(f"/api/v1/books/{book_id}/atmosphere/design").json()
    assert first == second
