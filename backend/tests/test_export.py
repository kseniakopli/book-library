# Экспорт полки в CSV (задачи 35 и 42).
import csv
import io
from datetime import datetime

from sqlmodel import Session, select

import database
from models import Book, User, UserBook
from services.export import desanitize

URL = "/api/v1/export/shelf.csv"


def _seed(rows):
    """rows: (book_id, title, author, status, rating, read_at, isbn)."""
    with Session(database.engine) as session:
        for book_id, title, author, status, rating, read_at, isbn in rows:
            session.add(Book(id=book_id, title=title, author=author, isbn=isbn))
            session.commit()
            session.add(UserBook(
                user_id=1, book_id=book_id, status=status,
                rating=rating, read_at=read_at,
            ))
            session.commit()


def _parse(body: str) -> list[dict]:
    """Разбор ответа так, как это сделает Excel: BOM снимаем, разделитель ';'."""
    return list(csv.DictReader(io.StringIO(body.lstrip("﻿")), delimiter=";"))


def test_export_returns_csv_attachment(client):
    r = client.get(URL)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert ".csv" in r.headers["content-disposition"]


def test_export_has_bom_for_excel(client):
    """Без BOM Excel на Windows открывает кириллицу кракозябрами."""
    assert client.get(URL).text.startswith("﻿")


def test_export_contains_shelf_rows(client):
    _seed([
        (10, "Мастер и Маргарита", "Булгаков", "read", 10,
         datetime(2026, 7, 1), "9785000000000"),
    ])
    rows = _parse(client.get(URL).text)
    row = next(r for r in rows if r["Название"] == "Мастер и Маргарита")
    assert row["Автор"] == "Булгаков"
    assert row["Моя оценка"] == "10"
    assert row["Дата прочтения"] == "2026-07-01"
    assert row["ISBN"] == "9785000000000"
    assert row["Статус"] == "Прочитана"


def test_export_leaves_missing_date_empty(client):
    """Задача 98: даты может не быть — пустая ячейка, а не сегодняшнее число."""
    _seed([(11, "Гарри Поттер", "Роулинг", "read", 9, None, None)])
    row = next(r for r in _parse(client.get(URL).text) if r["Название"] == "Гарри Поттер")
    assert row["Дата прочтения"] == ""
    assert row["ISBN"] == ""


def test_export_escapes_formula_injection(client):
    """Задача 42: ячейка, начинающаяся с =, +, - или @, в Excel исполняется
    как формула. Предваряем апострофом — значение остаётся текстом."""
    _seed([
        (12, "=1+1", "@Автор", "want", None, None, None),
        (13, "+79990000000", "-Минус", "want", None, None, None),
    ])
    body = client.get(URL).text
    rows = {r["Название"]: r for r in _parse(body)}

    assert "'=1+1" in rows
    assert rows["'=1+1"]["Автор"] == "'@Автор"
    assert "'+79990000000" in rows
    assert rows["'+79990000000"]["Автор"] == "'-Минус"
    # ни одна ячейка не начинается с опасного символа
    for row in _parse(body):
        for value in row.values():
            assert not (value or "").startswith(("=", "+", "-", "@", "\t", "\r"))


def test_normal_titles_are_not_touched(client):
    """Апостроф не должен появляться у обычных названий — иначе экспорт
    портит данные ради защиты, которая тут не нужна."""
    _seed([(14, "Война и мир", "Толстой", "read", 8, datetime(2026, 6, 1), None)])
    row = next(r for r in _parse(client.get(URL).text) if r["Автор"] == "Толстой")
    assert row["Название"] == "Война и мир"


def test_export_shows_only_own_shelf(client):
    """Выгружается своя полка: чужие книги в файл не попадают."""
    with Session(database.engine) as session:
        # второго пользователя надо завести явно: у userbook.user_id есть FK,
        # и без строки в user вставка падает на IntegrityError, а не проверяет
        # то, ради чего написан тест
        session.add(User(id=2, display_name="Другой"))
        session.add(Book(id=20, title="Чужая", author="Кто-то"))
        session.commit()
        session.add(UserBook(user_id=2, book_id=20, status="read"))
        session.commit()

    assert "Чужая" not in client.get(URL).text


def test_export_reimports_cleanly(client, monkeypatch):
    """Круг замкнут: выгруженный файл читается нашим же импортом, и защитный
    апостроф при этом снимается. Это же контрольный образец для импорта —
    если формат разъедется, тест упадёт здесь, а не у Ксении в Excel."""
    import services.enrichment as enrichment
    from conftest import fake_book_info
    monkeypatch.setattr(enrichment, "fetch_book_info", fake_book_info)

    _seed([
        (30, "=Формула", "Автор", "read", 7, datetime(2026, 5, 1), None),
        (31, "Обычная", "Автор", "read", 8, datetime(2026, 4, 1), None),
    ])
    body = client.get(URL).text

    # чистим полку — иначе импорт увидит те же книги дублями
    with Session(database.engine) as session:
        for ub in session.exec(select(UserBook)).all():
            session.delete(ub)
        session.commit()

    r = client.post(
        "/api/v1/import",
        files={"file": ("shelf.csv", body.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["imported"] >= 2

    titles = [b["title"] for b in client.get("/api/v1/books").json()]
    assert "=Формула" in titles      # апостроф снят при импорте
    assert "Обычная" in titles


def test_desanitize_keeps_real_apostrophe():
    """Название, честно начинающееся с апострофа, не портим: снимаем его
    только перед опасным символом, где он заведомо наш."""
    assert desanitize("'=1+1") == "=1+1"
    assert desanitize("'Тихий Дон'") == "'Тихий Дон'"
    assert desanitize("") == ""
    assert desanitize(None) is None
