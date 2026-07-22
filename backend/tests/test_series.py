# Циклы книг (задача 89): создание, привязка книг, статусы, прогресс.
# Ключевой сценарий: книга цикла может НЕ быть на полке пользователя —
# тогда она показывается как «что дальше» (решение Ксении 22.07).
from sqlmodel import Session

import database
from models import Book


def _create_series(client, name="Неаполитанский квартет", **extra):
    return client.post("/api/v1/series", json={"name": name, **extra}).json()


def _add_catalog_book(title, author="Элена Ферранте") -> int:
    """Книга в каталоге БЕЗ UserBook — как книга цикла, которой нет на полке."""
    with Session(database.engine) as session:
        book = Book(title=title, author=author)
        session.add(book)
        session.commit()
        session.refresh(book)
        return book.id


def test_create_series(client):
    data = _create_series(client, author="Элена Ферранте")
    assert data["name"] == "Неаполитанский квартет"
    assert data["status"] == "reading"          # по умолчанию «читаю»
    assert data["books"] == []
    assert data["progress"]["total"] == 0


def test_series_appears_in_list(client):
    _create_series(client)
    series = client.get("/api/v1/series").json()["series"]
    assert len(series) == 1
    assert series[0]["name"] == "Неаполитанский квартет"


def test_attach_book_from_shelf(client):
    series = _create_series(client)
    # книга 1 из фикстуры — она на полке пользователя
    client.post(
        f"/api/v1/series/{series['id']}/books",
        json={"book_id": 1, "series_index": 1},
    )
    data = client.get(f"/api/v1/series/{series['id']}").json()
    assert len(data["books"]) == 1
    assert data["books"][0]["on_shelf"] is True
    assert data["books"][0]["series_index"] == 1


def test_book_outside_shelf_shows_as_next(client):
    """Книга цикла, которой нет на полке, — это «что читать дальше»."""
    series = _create_series(client)
    catalog_id = _add_catalog_book("История о пропавшем ребенке")

    client.post(f"/api/v1/series/{series['id']}/books",
                json={"book_id": 1, "series_index": 1})
    client.post(f"/api/v1/series/{series['id']}/books",
                json={"book_id": catalog_id, "series_index": 2})

    data = client.get(f"/api/v1/series/{series['id']}").json()
    assert data["progress"]["total"] == 2
    assert data["progress"]["on_shelf"] == 1        # вторая книга не на полке
    not_mine = next(b for b in data["books"] if b["id"] == catalog_id)
    assert not_mine["on_shelf"] is False
    assert not_mine["status"] is None


def test_progress_counts_read(client):
    series = _create_series(client)
    client.post(f"/api/v1/series/{series['id']}/books",
                json={"book_id": 1, "series_index": 1})
    catalog_id = _add_catalog_book("Вторая книга")
    client.post(f"/api/v1/series/{series['id']}/books",
                json={"book_id": catalog_id, "series_index": 2})

    client.patch("/api/v1/books/1", json={"status": "read", "rating": 9})

    progress = client.get(f"/api/v1/series/{series['id']}").json()["progress"]
    assert progress["read"] == 1
    assert progress["total"] == 2
    # следующая к чтению — первая непрочитанная по порядку
    assert progress["next_book"]["id"] == catalog_id


def test_books_ordered_by_index(client):
    series = _create_series(client)
    third = _add_catalog_book("Третья")
    second = _add_catalog_book("Вторая")
    client.post(f"/api/v1/series/{series['id']}/books",
                json={"book_id": third, "series_index": 3})
    client.post(f"/api/v1/series/{series['id']}/books",
                json={"book_id": second, "series_index": 2})
    client.post(f"/api/v1/series/{series['id']}/books",
                json={"book_id": 1, "series_index": 1})

    books = client.get(f"/api/v1/series/{series['id']}").json()["books"]
    assert [b["series_index"] for b in books] == [1, 2, 3]


def test_add_future_book_by_title(client):
    """Книгу, которой ещё нет в каталоге, можно добавить в цикл по названию —
    она попадёт в каталог, но НЕ на полку («что дальше»)."""
    series = _create_series(client)
    r = client.post(
        f"/api/v1/series/{series['id']}/books",
        json={"title": "Те, кто уходит", "author": "Элена Ферранте", "series_index": 3},
    )
    assert r.status_code == 200
    book = next(b for b in r.json()["books"] if b["title"] == "Те, кто уходит")
    assert book["on_shelf"] is False

    # на полке пользователя её нет
    shelf = [b["title"] for b in client.get("/api/v1/books").json()]
    assert "Те, кто уходит" not in shelf


def test_add_book_from_search_enriches(client, monkeypatch):
    """Книга, выбранная в поиске (есть external_id), заводится в каталоге
    с обложкой и уходит на фоновое обогащение — но НЕ на полку."""
    import services.enrichment as enrichment
    from conftest import fake_book_info

    monkeypatch.setattr(enrichment, "fetch_volume_by_id", lambda ext: fake_book_info(None, None))
    series = _create_series(client)

    r = client.post(
        f"/api/v1/series/{series['id']}/books",
        json={
            "title": "История о пропавшем ребенке",
            "author": "Элена Ферранте",
            "cover_url": "https://example.com/cover.jpg",
            "external_id": "ext-123",
            "series_index": 4,
        },
    )
    assert r.status_code == 200
    book = next(b for b in r.json()["books"] if b["series_index"] == 4)
    assert book["cover_url"] == "https://example.com/cover.jpg"
    assert book["on_shelf"] is False       # в каталоге, но не у читателя


def test_add_book_without_title_rejected(client):
    series = _create_series(client)
    assert client.post(
        f"/api/v1/series/{series['id']}/books", json={"title": "  "}
    ).status_code == 400


def test_update_description(client):
    """Описание цикла — вход для генерации экслибриса, его должно быть можно править."""
    series = _create_series(client)
    r = client.patch(
        f"/api/v1/series/{series['id']}",
        json={"description": "Четыре книги о дружбе двух женщин из Неаполя"},
    )
    assert r.json()["description"].startswith("Четыре книги")


def test_generate_series_design(client, monkeypatch):
    """Экслибрис цикла: генерируется по названию и описанию, сохраняется
    в Series.design и отдаётся объектом."""
    import routers.series as series_routes
    from conftest import fake_generate_design

    async def fake(name, author=None, description=None, lang="ru"):
        result = await fake_generate_design(name, author or "", lang)
        return result["Claude"]

    monkeypatch.setattr(series_routes, "generate_series_design", fake)
    series = _create_series(client)
    client.patch(f"/api/v1/series/{series['id']}",
                 json={"description": "О дружбе двух женщин"})

    r = client.post(f"/api/v1/series/{series['id']}/design")
    assert r.status_code == 200
    design = r.json()["design"]
    assert design["palette_dark"]["bg"] == "#161311"
    assert design["statement"]

    # сохранилось и приходит при обычном чтении
    assert client.get(f"/api/v1/series/{series['id']}").json()["design"]["statement"]


def test_change_status(client):
    series = _create_series(client)
    r = client.patch(f"/api/v1/series/{series['id']}", json={"status": "dropped"})
    assert r.json()["status"] == "dropped"


def test_invalid_status_rejected(client):
    series = _create_series(client)
    assert client.patch(
        f"/api/v1/series/{series['id']}", json={"status": "почти"}
    ).status_code == 400


def test_series_sorted_by_status(client):
    """Полка: читаю → прочитано → перестала читать."""
    reading = _create_series(client, name="Б читаю")
    read = _create_series(client, name="А прочитан")
    dropped = _create_series(client, name="В брошен")
    client.patch(f"/api/v1/series/{read['id']}", json={"status": "read"})
    client.patch(f"/api/v1/series/{dropped['id']}", json={"status": "dropped"})

    names = [s["name"] for s in client.get("/api/v1/series").json()["series"]]
    assert names == ["Б читаю", "А прочитан", "В брошен"]


def test_remove_book_from_series(client):
    series = _create_series(client)
    client.post(f"/api/v1/series/{series['id']}/books", json={"book_id": 1})
    client.delete(f"/api/v1/series/{series['id']}/books/1")
    assert client.get(f"/api/v1/series/{series['id']}").json()["books"] == []


def test_delete_series_keeps_books(client):
    """Удаление цикла не трогает книги — они остаются в каталоге и на полке."""
    series = _create_series(client)
    client.post(f"/api/v1/series/{series['id']}/books", json={"book_id": 1})
    client.delete(f"/api/v1/series/{series['id']}")

    assert client.get(f"/api/v1/series/{series['id']}").status_code == 404
    assert client.get("/api/v1/books/1").status_code == 200


# --- права (з.90а): общие данные цикла — admin, личный статус — всем ---

def _make_regular_user():
    from sqlmodel import Session as S

    from models import User

    with S(database.engine) as session:
        user = session.get(User, 1)
        user.is_admin = False
        session.add(user)
        session.commit()


def test_shared_edits_require_admin(client):
    """Название/автор/описание — общие данные цикла: правит только admin."""
    series = _create_series(client)
    _make_regular_user()

    assert client.patch(
        f"/api/v1/series/{series['id']}", json={"name": "Другое имя"}
    ).status_code == 403
    assert client.patch(
        f"/api/v1/series/{series['id']}", json={"description": "текст"}
    ).status_code == 403


def test_status_change_allowed_for_everyone(client):
    """А статус — личное действие читателя, доступно и не-админу."""
    series = _create_series(client)
    _make_regular_user()

    r = client.patch(f"/api/v1/series/{series['id']}", json={"status": "read"})
    assert r.status_code == 200
    assert r.json()["status"] == "read"


def test_series_structure_requires_admin(client):
    """Создание, состав и удаление цикла — тоже общие данные."""
    series = _create_series(client)
    _make_regular_user()

    assert client.post("/api/v1/series", json={"name": "Новый"}).status_code == 403
    assert client.post(
        f"/api/v1/series/{series['id']}/books", json={"book_id": 1}
    ).status_code == 403
    assert client.delete(f"/api/v1/series/{series['id']}").status_code == 403


def test_empty_name_rejected(client):
    assert client.post("/api/v1/series", json={"name": "  "}).status_code == 400
