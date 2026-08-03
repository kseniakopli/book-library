# Жанры как сущность (задача 112). Заводятся ВРУЧНУЮ: Google Books отдаёт
# рубрикатор магазина, а не жанры, поэтому источника для агрегации здесь нет.
import json

from sqlmodel import Session, select

import database
from models import Book, BookGenre, Genre, UserBook
from services.genres import norm_slug, set_book_genres


def _set(client, book_id, genres):
    return client.put(f"/api/v1/books/{book_id}/genres", json={"genres": genres})


# --- тождество жанра ---

def test_same_genre_written_differently_is_one():
    """«Тёмное фэнтези», «тёмное фэнтези» и «Темное  фэнтези» — один жанр.
    Без ключа тождества список через месяц зарос бы дублями."""
    assert norm_slug("Тёмное фэнтези") == norm_slug("темное  фэнтези")
    assert norm_slug(" Детектив ") == norm_slug("детектив")


def test_display_name_keeps_original_spelling(client):
    """Ищем по ключу, показываем как ввели: «Тёмное фэнтези» с ё и заглавной."""
    _set(client, 1, ["Тёмное фэнтези"])
    names = [g["name"] for g in client.get("/api/v1/genres").json()["genres"]]
    assert names == ["Тёмное фэнтези"]


def test_case_variants_do_not_create_duplicates(client):
    _set(client, 1, ["Детектив"])
    with Session(database.engine) as session:
        book = Book(id=50, title="Вторая", author="Автор")
        session.add(book)
        session.commit()
        session.add(UserBook(user_id=1, book_id=50, status="want"))
        session.commit()
    _set(client, 50, ["детектив"])

    with Session(database.engine) as session:
        assert len(session.exec(select(Genre)).all()) == 1


# --- правка жанров книги ---

def test_put_replaces_whole_set(client):
    """PUT, а не «добавить»: интерфейс показывает все жанры разом, значит
    снятая метка обязана исчезать (тот же урок, что с авторами 28.07)."""
    _set(client, 1, ["Детектив", "Триллер"])
    _set(client, 1, ["Детектив"])

    genres = client.get("/api/v1/books/1").json()["genres"]
    assert [g["name"] for g in genres] == ["Детектив"]


def test_genre_without_books_is_removed(client):
    """Жанр живёт ради связей: пустой — это мусор в списке и пустая страница
    по прямой ссылке."""
    _set(client, 1, ["Однодневка"])
    _set(client, 1, [])

    with Session(database.engine) as session:
        assert session.exec(select(Genre)).all() == []


def test_genre_kept_while_another_book_uses_it(client):
    with Session(database.engine) as session:
        session.add(Book(id=51, title="Вторая", author="Автор"))
        session.commit()
        session.add(UserBook(user_id=1, book_id=51, status="want"))
        session.commit()

    _set(client, 1, ["Детектив"])
    _set(client, 51, ["Детектив"])
    _set(client, 1, [])          # снимаем у первой книги

    names = [g["name"] for g in client.get("/api/v1/genres").json()["genres"]]
    assert names == ["Детектив"]


def test_blank_names_are_ignored(client):
    _set(client, 1, ["  ", "Детектив", ""])
    genres = client.get("/api/v1/books/1").json()["genres"]
    assert [g["name"] for g in genres] == ["Детектив"]


def test_too_many_genres_rejected(client):
    """Больше пяти — это уже облако тегов, а не жанр книги."""
    r = _set(client, 1, ["а", "б", "в", "г", "д", "е"])
    assert r.status_code == 400


def test_setting_genres_requires_admin(as_reader):
    """Книга одна на всю базу, её жанры видят все читатели."""
    assert _set(as_reader, 1, ["Детектив"]).status_code == 403


def test_genres_for_unknown_book_is_404(client):
    assert _set(client, 999, ["Детектив"]).status_code == 404


# --- справочник и страница жанра ---

def test_genre_directory_counts_whole_catalog(client):
    """Как и авторы: раздел про базу сервиса, а не про полку спрашивающего."""
    with Session(database.engine) as session:
        session.add(Book(id=60, title="Только в каталоге", author="Автор"))
        session.commit()

    _set(client, 1, ["Детектив"])
    _set(client, 60, ["Детектив"])

    genre = client.get("/api/v1/genres").json()["genres"][0]
    assert genre["books"] == 2      # вторая книга ни у кого не на полке


def test_genre_page_splits_shelf_and_catalog(client):
    with Session(database.engine) as session:
        session.add(Book(id=61, title="Каталожная", author="Автор"))
        session.commit()

    _set(client, 1, ["Детектив"])
    _set(client, 61, ["Детектив"])
    genre_id = client.get("/api/v1/genres").json()["genres"][0]["id"]

    body = client.get(f"/api/v1/genres/{genre_id}").json()
    assert [b["title"] for b in body["shelf"]] == ["Test"]
    assert [b["title"] for b in body["catalog"]] == ["Каталожная"]


def test_unknown_genre_is_404(client):
    assert client.get("/api/v1/genres/999").status_code == 404


# --- связь с промптом (з.112) ---

def test_prompt_context_uses_own_genres_not_google(client):
    """Раньше в промпт уезжал `book.categories` — «Fiction / General» и прочий
    рубрикатор магазина. Он одинаков у половины библиотеки и ровнял генерации."""
    from services.prompt_context import build_book_context

    with Session(database.engine) as session:
        book = session.get(Book, 1)
        book.categories = json.dumps(["Fiction", "General"])
        session.add(book)
        session.commit()

    _set(client, 1, ["Магический реализм"])

    with Session(database.engine) as session:
        context = build_book_context(session, 1, "music", 1)

    assert context["genres"] == "Магический реализм"
    assert "Fiction" not in context["genres"]


def test_prompt_context_is_empty_without_own_genres(client):
    """Жанра нет — не передаём ничего: пустая строка честнее, чем «Fiction»."""
    from services.prompt_context import build_book_context

    with Session(database.engine) as session:
        book = session.get(Book, 1)
        book.categories = json.dumps(["Fiction"])
        session.add(book)
        session.commit()
        context = build_book_context(session, 1, "music", 1)

    assert context["genres"] == ""


def test_deleting_book_removes_links(client):
    """FK ON DELETE CASCADE: связи уходят вместе с книгой."""
    _set(client, 1, ["Детектив"])
    client.delete("/api/v1/books/1")

    with Session(database.engine) as session:
        assert session.exec(select(BookGenre)).all() == []


def test_set_book_genres_is_idempotent(client):
    """Повторный вызов с тем же набором ничего не дублирует."""
    with Session(database.engine) as session:
        set_book_genres(session, 1, ["Детектив"])
        session.commit()
        set_book_genres(session, 1, ["Детектив"])
        session.commit()
        links = session.exec(select(BookGenre).where(BookGenre.book_id == 1)).all()
        assert len(links) == 1
