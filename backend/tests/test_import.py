# Импорт CSV: создание книг, дедуп, кривые строки, лимиты (задача 38),
# разбор даты прочтения (задача 1).
from datetime import datetime

from dates import parse_read_date


def _upload(client, csv_text):
    return client.post(
        "/import",
        files={"file": ("books.csv", csv_text.encode("utf-8"), "text/csv")},
    )


def test_import_creates_books(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Тестовая книга,Тестовый Автор,Июль 2026 г.,7,111\n"
        "Другая книга,Другой Автор,Июнь 2026 г.,3,222\n"
    )
    r = _upload(client, csv_text)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2 and body["skipped"] == 0
    titles = [b["title"] for b in client.get("/books").json()]
    assert "Тестовая книга" in titles


def test_import_sets_read_status_and_rating(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Книга с оценкой,Автор,Май 2026 г.,8,333\n"
    )
    _upload(client, csv_text)
    book = next(b for b in client.get("/books").json() if b["title"] == "Книга с оценкой")
    assert book["status"] == "read"
    assert book["rating"] == 8


def test_import_skips_invalid_rows(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Валидная,Автор,Июль 2026 г.,5,1\n"
        ",Автор без названия,Июль 2026 г.,5,2\n"
        "Название без автора,,Июль 2026 г.,5,3\n"
    )
    assert _upload(client, csv_text).json() == {"imported": 1, "duplicates": 0, "skipped": 2}


def test_import_rating_and_status_edge_cases(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Без оценки,Автор,Июль 2026 г.,,9\n"      # оценки нет, но есть дата → read
        "Кривая оценка,Автор,,абв,10\n"           # не число и без даты → want
    )
    _upload(client, csv_text)
    books = client.get("/books").json()
    b1 = next(b for b in books if b["title"] == "Без оценки")
    assert b1["rating"] is None and b1["status"] == "read"
    b2 = next(b for b in books if b["title"] == "Кривая оценка")
    assert b2["rating"] is None and b2["status"] == "want"


# --- дата прочтения (задача 1) ---

def test_parse_read_date_formats():
    assert parse_read_date("Июль 2026 г.") == datetime(2026, 7, 1)
    assert parse_read_date("2026-07-14") == datetime(2026, 7, 14)
    assert parse_read_date("14.07.2026") == datetime(2026, 7, 14)
    assert parse_read_date("2024") == datetime(2024, 1, 1)
    assert parse_read_date("март 2025") == datetime(2025, 3, 1)
    assert parse_read_date("когда-то давно") is None
    assert parse_read_date("") is None


def test_import_saves_read_at(client):
    csv_text = (
        "Название,Автор,Дата прочтения,Моя оценка,ISBN\n"
        "Датированная,Автор,Июль 2026 г.,7,555\n"
    )
    _upload(client, csv_text)
    book = next(
        b for b in client.get("/books").json() if b["title"] == "Датированная"
    )
    assert book["read_at"].startswith("2026-07-01")


# --- фоновый дозаполнитель метаданных (задача 12) ---

def test_backfill_metadata_runs_in_background(client, monkeypatch):
    import services.enrichment as enrichment
    from conftest import fake_book_info

    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)
    # книга из фикстуры — без метаданных
    r = client.post("/books/backfill-metadata")
    assert r.status_code == 200
    assert r.json() == {"scheduled": 1, "remaining": 0}

    # TestClient уже выполнил фон — книга обогащена и снова ready
    book = client.get("/books/1").json()
    assert book["enrich_status"] == "ready"
    assert book["page_count"] == 100


def test_backfill_metadata_failure_marks_failed(client, monkeypatch):
    import services.enrichment as enrichment

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(enrichment, "fetch_book_info", boom)
    client.post("/books/backfill-metadata")
    assert client.get("/books/1").json()["enrich_status"] == "failed"


# --- лимиты (задача 38) ---

def test_import_rejects_bad_encoding(client):
    data = "Название,Автор\nКнига,Кто-то".encode("cp1251")
    r = client.post("/import", files={"file": ("books.csv", data, "text/csv")})
    assert r.status_code == 400


def test_import_rejects_huge_file(client):
    data = b"a" * (2 * 1024 * 1024 + 10)
    r = client.post("/import", files={"file": ("books.csv", data, "text/csv")})
    assert r.status_code == 400


def test_import_rejects_too_many_rows(client):
    rows = "\n".join(f"Книга {i},Автор" for i in range(2101))
    data = ("Название,Автор\n" + rows).encode("utf-8")
    r = client.post("/import", files={"file": ("books.csv", data, "text/csv")})
    assert r.status_code == 400
