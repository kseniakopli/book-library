# Заполнение данных (задача 113): сколько в каталоге незаполненного.
from sqlmodel import Session

import database
from models import AISelection, Author, Book, User

SUMMARY = "/api/v1/admin/data-gaps"


def _demote(client):
    with Session(database.engine) as session:
        user = session.get(User, 1)
        user.is_admin = False
        session.add(user)
        session.commit()


def _add_book(book_id, **fields):
    with Session(database.engine) as session:
        session.add(Book(id=book_id, title=f"Книга {book_id}", author="Автор", **fields))
        session.commit()


def test_summary_counts_missing_description(client):
    _add_book(70, description="Есть описание")
    _add_book(71)                                  # нет вовсе
    _add_book(72, description="   ")               # пробелы — тоже пусто

    body = client.get(SUMMARY).json()
    # фикстурная книга 1 тоже без описания
    assert body["books"]["no_description"] == 3
    assert body["books_total"] == 4


def test_summary_counts_missing_cover(client):
    _add_book(73, cover_url="https://example.com/c.jpg")
    _add_book(74)

    body = client.get(SUMMARY).json()
    assert body["books"]["no_cover"] == 2          # книга 74 и фикстурная


def test_summary_counts_books_without_genres(client):
    _add_book(75)
    client.put("/api/v1/books/75/genres", json={"genres": ["Детектив"]})

    body = client.get(SUMMARY).json()
    assert body["books"]["no_genres"] == 1         # только фикстурная


def test_summary_counts_books_without_design(client):
    """Серый фон карточки на витрине (з.94) даёт отсутствие паспорта —
    считаем именно `AISelection` категории design."""
    _add_book(76)
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=76, category="design", source="Claude", payload="{}",
        ))
        session.commit()

    body = client.get(SUMMARY).json()
    assert body["books"]["no_design"] == 1         # фикстурная книга


def test_summary_counts_authors_without_bio(client):
    with Session(database.engine) as session:
        session.add(Author(id=80, name_ru="Без биографии", sort_key="без биографии"))
        session.add(Author(
            id=81, name_ru="С биографией", sort_key="с биографией", bio="Текст",
        ))
        session.commit()

    body = client.get(SUMMARY).json()
    assert body["authors"]["no_bio"] == 1
    assert body["authors_total"] == 2


def test_items_list_links_to_objects(client):
    _add_book(82)
    body = client.get(f"{SUMMARY}/no_description").json()

    assert body["kind"] == "no_description"
    ids = [item["id"] for item in body["items"]]
    assert 82 in ids
    assert all(item["kind"] == "book" for item in body["items"])


def test_items_for_authors_marked_as_authors(client):
    """Ссылка ведёт на разные страницы, поэтому вид объекта должен приходить
    с бэкенда, а не угадываться фронтом по имени ключа."""
    with Session(database.engine) as session:
        session.add(Author(id=83, name_ru="Пустой", sort_key="пустой"))
        session.commit()

    items = client.get(f"{SUMMARY}/no_bio").json()["items"]
    assert items[0]["kind"] == "author"


def test_unknown_kind_is_404(client):
    assert client.get(f"{SUMMARY}/no_such_gap").status_code == 404


def test_section_requires_admin(client):
    """Цифры по общему каталогу; ссылки ведут на правку общих данных,
    которая обычному читателю всё равно запрещена."""
    _demote(client)
    assert client.get(SUMMARY).status_code == 403
    assert client.get(f"{SUMMARY}/no_description").status_code == 403


# --- догенерация паспортов (задача 116) ---

def test_backfill_design_schedules_books_without_passport(client, monkeypatch):
    """Импорт CSV не вызывает фоновую генерацию вовсе — у нового пользователя
    после импорта вся полка была бы серой."""
    from conftest import fake_generate_design
    from routers import atmosphere as atmosphere_routes

    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["design"], "generate", fake_generate_design
    )
    _add_book(90)

    r = client.post("/api/v1/admin/backfill-design")
    assert r.status_code == 200
    assert r.json()["scheduled"] == 2               # книга 90 и фикстурная

    # TestClient выполняет фоновые задачи синхронно — паспорта уже на месте
    assert client.get(SUMMARY).json()["books"]["no_design"] == 0


def test_backfill_design_is_idempotent(client, monkeypatch):
    """Повторное нажатие не тратит токены: генератор сам выходит, если паспорт
    уже есть."""
    from conftest import fake_generate_design
    from routers import atmosphere as atmosphere_routes

    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["design"], "generate", fake_generate_design
    )
    client.post("/api/v1/admin/backfill-design")

    r = client.post("/api/v1/admin/backfill-design")
    assert r.json()["scheduled"] == 0


def test_backfill_design_batch_is_capped(client):
    """Партия маленькая намеренно: каждый паспорт — вызов Claude, а книг
    без оформления могут быть сотни."""
    r = client.post("/api/v1/admin/backfill-design?limit=50")
    assert r.status_code == 422


def test_backfill_design_requires_admin(client):
    _demote(client)
    assert client.post("/api/v1/admin/backfill-design").status_code == 403


def test_summary_and_list_agree(client):
    """Одно место для условий: если сводка и список разойдутся, цифра
    перестанет отвечать за содержимое, и доверять ей будет нельзя."""
    _add_book(84)
    _add_book(85, description="Есть")

    body = client.get(SUMMARY).json()
    items = client.get(f"{SUMMARY}/no_description").json()["items"]

    assert body["books"]["no_description"] == len(items)
