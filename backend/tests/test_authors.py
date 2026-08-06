# Авторы как сущность (задача 97): тождество имени, разбор строк, связи.
#
# Главная мысль этих тестов: разбор НЕ должен быть умным. Разведка 28.07 нашла
# в 150 строках всего три склеенных, поэтому правило простое — разбираем только
# перечисленные исключения, всё остальное считаем одним человеком. Лучше не
# разделить редкую новую пару соавторов и заметить это глазами, чем разрезать
# пополам настоящее имя.
import pytest
from sqlmodel import Session, select

import database
from main import app
from models import Author, Book, BookAuthor
from services.authors import (
    display_name,
    get_or_create,
    link_book,
    norm_key,
    split_authors,
)


# --- тождество имени ---

@pytest.mark.parametrize(
    "first, second",
    [
        ("Кнут Гамсун", "кнут  гамсун"),          # регистр и двойной пробел
        ("А.С. Пушкин", "А. С. Пушкин"),          # точки в инициалах
        ("Алёна Селютина", "Алена Селютина"),     # ё и е
        (" Тана Френч ", "Тана Френч"),           # крайние пробелы
    ],
)
def test_same_person_gets_same_key(first, second):
    assert norm_key(first) == norm_key(second)


def test_different_people_keep_different_keys():
    assert norm_key("Борис Стругацкий") != norm_key("Аркадий Стругацкий")
    # разные алфавиты ключом не связываются — это работа ORIGINAL_NAMES
    assert norm_key("Ann Patchett") != norm_key("Энн Пэтчетт")


# --- разбор строки книги ---

def test_known_coauthors_are_split():
    assert split_authors("Екатерина Казакова, Алена Харитонова") == [
        "Екатерина Казакова",
        "Алёна Харитонова",
    ]


def test_shared_surname_is_split_by_hand():
    """«Аркадий и Борис Стругацкие» ломает любой разбор по разделителю:
    фамилия стоит один раз и во множественном числе."""
    assert split_authors("Аркадий и Борис Стругацкие") == [
        "Аркадий Стругацкий",
        "Борис Стругацкий",
    ]


@pytest.mark.parametrize(
    "raw",
    [
        "Донато Карризи",
        "Дж. М. Кутзее",              # инициалы — не повод делить
        "Эрих Мария Ремарк",          # три слова, один человек
        "Гамсун, Кнут",               # «фамилия, имя» — НЕ соавторы
        "Ильф и Петров",              # незнакомая пара: лучше не трогать
    ],
)
def test_unknown_strings_are_never_split(raw):
    assert split_authors(raw) == [raw]


def test_empty_author_gives_nothing():
    assert split_authors("") == []
    assert split_authors(None) == []
    assert split_authors("   ") == []


# --- запись в базу ---
#
# Фикстура `client` здесь нужна не ради HTTP: именно она подменяет
# `database.engine` на базу в памяти. Без неё тесты писали бы в настоящую
# library.db.

def test_latin_name_gets_both_fields(client):
    with Session(database.engine) as session:
        author = get_or_create(session, "Ann Patchett")
        session.commit()

        assert author.name_ru == "Энн Пэтчетт"
        assert author.name_original == "Ann Patchett"
        assert display_name(author) == "Энн Пэтчетт"


def test_cyrillic_name_has_no_original(client):
    with Session(database.engine) as session:
        author = get_or_create(session, "Тана Френч")
        session.commit()

        assert author.name_ru == "Тана Френч"
        assert author.name_original is None


def test_get_or_create_is_idempotent(client):
    """Второй заход по-другому написанного имени возвращает ТОГО ЖЕ автора —
    иначе таблица зарастёт дублями при первом же импорте."""
    with Session(database.engine) as session:
        first = get_or_create(session, "Кнут Гамсун")
        session.commit()
        second = get_or_create(session, "кнут  гамсун")
        session.commit()

        assert first.id == second.id
        assert len(session.exec(select(Author)).all()) == 1


def test_link_book_creates_authors_in_cover_order(client):
    with Session(database.engine) as session:
        book = Book(title="Жнецы страданий", author="Екатерина Казакова, Алена Харитонова")
        session.add(book)
        session.commit()

        link_book(session, book.id, book.author)
        session.commit()

        links = session.exec(
            select(BookAuthor).where(BookAuthor.book_id == book.id)
        ).all()
        assert len(links) == 2
        by_position = {link.position: session.get(Author, link.author_id) for link in links}
        assert display_name(by_position[0]) == "Екатерина Казакова"
        assert display_name(by_position[1]) == "Алёна Харитонова"


def test_changed_author_string_replaces_links(client):
    """Баг 28.07 на проде: у «Года магического мышления» строка сменилась
    с «Джоан Дидион» на «Joan Didion», новая связь добавилась, старая осталась —
    и на странице книги имя показывалось дважды.

    Строка книги — источник истины: связей должно быть ровно столько,
    сколько имён в ней сейчас."""
    with Session(database.engine) as session:
        book = Book(title="Год магического мышления", author="Джоан Дидион")
        session.add(book)
        session.commit()

        link_book(session, book.id, book.author)
        session.commit()

        book.author = "Joan Didion"          # правка в интерфейсе
        session.add(book)
        link_book(session, book.id, book.author)
        session.commit()

        links = session.exec(
            select(BookAuthor).where(BookAuthor.book_id == book.id)
        ).all()
        assert len(links) == 1
        assert display_name(session.get(Author, links[0].author_id)) == "Джоан Дидион"


def test_author_without_books_is_removed(client):
    """Автор, потерявший последнюю книгу, удаляется — как книга-сирота при
    снятии с полки. Иначе по прямой ссылке открывалась бы пустая страница."""
    with Session(database.engine) as session:
        book = Book(title="Временная", author="Никому Не Нужный")
        session.add(book)
        session.commit()

        link_book(session, book.id, book.author)
        session.commit()
        orphan_id = session.exec(
            select(Author).where(Author.sort_key == norm_key("Никому Не Нужный"))
        ).one().id

        book.author = "Другой Автор"
        session.add(book)
        link_book(session, book.id, book.author)
        session.commit()

        assert session.get(Author, orphan_id) is None


def test_coauthor_kept_when_one_of_them_changes(client):
    """Убрали одного соавтора — второй остаётся и не теряет книгу."""
    with Session(database.engine) as session:
        book = Book(title="Жнецы страданий", author="Екатерина Казакова, Алена Харитонова")
        session.add(book)
        session.commit()
        link_book(session, book.id, book.author)
        session.commit()

        book.author = "Екатерина Казакова"
        session.add(book)
        link_book(session, book.id, book.author)
        session.commit()

        links = session.exec(
            select(BookAuthor).where(BookAuthor.book_id == book.id)
        ).all()
        assert len(links) == 1
        assert display_name(session.get(Author, links[0].author_id)) == "Екатерина Казакова"


def test_relinking_does_not_duplicate(client):
    """Скрипт заполнения запускают повторно — он не должен плодить связи."""
    with Session(database.engine) as session:
        book = Book(title="Брокен-Харбор", author="Тана Френч")
        session.add(book)
        session.commit()

        link_book(session, book.id, book.author)
        session.commit()
        link_book(session, book.id, book.author)
        session.commit()

        links = session.exec(
            select(BookAuthor).where(BookAuthor.book_id == book.id)
        ).all()
        assert len(links) == 1


# --- страница автора ---

def _author_with_books(client):
    """Автор с двумя книгами: одна на полке, одна только в каталоге
    (том цикла, который добавили как «что дальше»)."""
    client.post("/api/v1/books", json={"title": "Брокен-Харбор", "author": "Тана Френч"})
    with Session(database.engine) as session:
        catalog_only = Book(title="Дублинский отдел убийств", author="Тана Френч")
        session.add(catalog_only)
        session.commit()
        link_book(session, catalog_only.id, catalog_only.author)
        session.commit()
        author = session.exec(
            select(Author).where(Author.sort_key == norm_key("Тана Френч"))
        ).one()
        return author.id


def test_author_page_splits_shelf_and_catalog(client):
    """Ради второй стопки страница и задумывалась: книги автора, которых у тебя
    нет, но которые есть в базе (тома циклов). Смешать их с полкой нельзя —
    у каталожных нет ни статуса, ни оценки."""
    author_id = _author_with_books(client)

    body = client.get(f"/api/v1/authors/{author_id}").json()

    assert body["name"] == "Тана Френч"
    assert [b["title"] for b in body["shelf"]] == ["Брокен-Харбор"]
    assert [b["title"] for b in body["catalog"]] == ["Дублинский отдел убийств"]


def test_author_page_catalog_books_carry_year(client):
    """Задача 121: год есть у ОБЕИХ стопок.

    Книги с полки собираются `BookRead` и год несут сами, а каталожные
    отдаются коротким словарём — там поле легко забыть, и тогда половина
    списка на странице выглядит как книги без года. Это ровно тот случай,
    который тест и стережёт: контракты у двух стопок разные.
    """
    author_id = _author_with_books(client)
    with Session(database.engine) as session:
        book = session.exec(
            select(Book).where(Book.title == "Дублинский отдел убийств")
        ).one()
        book.published_year = 2007
        session.add(book)
        session.commit()

    body = client.get(f"/api/v1/authors/{author_id}").json()

    assert body["catalog"][0]["published_year"] == 2007


# --- добавление книги автору (задача 123) ---

def test_book_added_to_author_lands_in_catalog_not_shelf(client):
    """Книга заводится в КАТАЛОГЕ и на полку не попадает.

    Это и есть смысл задачи: страница автора показывает библиографию,
    а не то, что читатель у себя держит. `UserBook` не создаётся, поэтому
    книга приходит во вторую стопку.
    """
    author_id = _author_with_books(client)

    r = client.post(
        f"/api/v1/authors/{author_id}/books", json={"title": "Ведьмин вяз"}
    )
    assert r.status_code == 201

    body = r.json()
    assert "Ведьмин вяз" in [b["title"] for b in body["catalog"]]
    assert "Ведьмин вяз" not in [b["title"] for b in body["shelf"]]


def test_added_book_gets_author_name_from_the_page(client):
    """⚠ Строка автора берётся из СУЩНОСТИ, а не из запроса.

    Привязка идёт по `book.author` через `link_book`, и написание из Google
    Books («Tana French» рядом с «Таной Френч») завело бы второго автора.
    Поэтому поля `author` во входной схеме нет вовсе, а присланное имя
    игнорируется — проверяем именно это.
    """
    author_id = _author_with_books(client)

    client.post(
        f"/api/v1/authors/{author_id}/books",
        json={"title": "Ведьмин вяз", "author": "Tana French"},
    )

    with Session(database.engine) as session:
        book = session.exec(select(Book).where(Book.title == "Ведьмин вяз")).one()
        assert book.author == "Тана Френч"
        # и связь ведёт к тому же автору, а не к новому
        links = session.exec(
            select(BookAuthor).where(BookAuthor.book_id == book.id)
        ).all()
        assert [link.author_id for link in links] == [author_id]


def test_added_book_gets_design_passport(client):
    """Книга, заведённая у автора, получает паспорт оформления — как и книга,
    добавленная на полку.

    ⚠ Регресс 04–06.08, из-за которого тест и появился. Эндпоинт писался
    по образцу добавления книги в ЦИКЛ, где паспорт не генерируется, а не по
    образцу `routers/books.py`, где фоновых задач две. За два дня через эту
    кнопку приехало 124 книги, и 102 остались без палитры и символа — то есть
    с серой заглушкой на полке и на витрине.
    Урок тот же, что в `Уроки.md` 2.5: «устроено похоже» — не «устроено так же».
    """
    author_id = _author_with_books(client)

    body = client.post(
        f"/api/v1/authors/{author_id}/books", json={"title": "Ведьмин вяз"}
    ).json()
    book_id = next(b["id"] for b in body["catalog"] if b["title"] == "Ведьмин вяз")

    design = client.get(f"/api/v1/books/{book_id}/atmosphere/design").json()
    assert design["selections"], "у книги нет паспорта — фоновая задача не запускалась"


def test_added_book_without_external_id_is_ready(client):
    """Без `external_id` тянуть нечего — книга сразу «готова».

    Иначе она навсегда осталась бы в состоянии «подгружаю обложку»:
    фоновой задачи нет, а статус ждёт её вечно (та же болезнь, что
    в з.104/105 — пустота должна быть явной).
    """
    author_id = _author_with_books(client)

    client.post(f"/api/v1/authors/{author_id}/books", json={"title": "Ведьмин вяз"})

    with Session(database.engine) as session:
        book = session.exec(select(Book).where(Book.title == "Ведьмин вяз")).one()
        assert book.enrich_status == "ready"


def test_empty_title_rejected(client):
    author_id = _author_with_books(client)
    r = client.post(f"/api/v1/authors/{author_id}/books", json={"title": "   "})
    assert r.status_code == 400


def test_unknown_author_cannot_get_books(client):
    assert client.post("/api/v1/authors/9999/books", json={"title": "X"}).status_code == 404


def test_adding_book_to_author_requires_admin(client, demote):
    """Каталог общий: заведённую книгу увидят все читатели — значит admin,
    то же основание, что у состава цикла (з.90а) и биографии."""
    author_id = _author_with_books(client)   # книги заводит ещё админ
    demote()

    r = client.post(f"/api/v1/authors/{author_id}/books", json={"title": "Ведьмин вяз"})
    assert r.status_code == 403


# --- список авторов (задача 111) ---

def test_author_list_counts_whole_catalog(client):
    """Раздел справочный: он про то, что есть в БАЗЕ, а не на полке
    спрашивающего (решение Ксении 03.08). У Тана Френч две книги — одна
    на полке, вторая только в каталоге, — и в списке должно стоять «2»."""
    _author_with_books(client)

    body = client.get("/api/v1/authors").json()
    френч = next(a for a in body["authors"] if a["name"] == "Тана Френч")

    assert френч["books"] == 2


def test_author_list_includes_catalog_only_authors(client):
    """Автор, чьих книг нет ни у кого на полке, всё равно в справочнике:
    его книги существуют в каталоге, и раздел обязан их показывать."""
    with Session(database.engine) as session:
        book = Book(title="Только в каталоге", author="Никому Неизвестный")
        session.add(book)
        session.commit()
        link_book(session, book.id, book.author)
        session.commit()

    names = [a["name"] for a in client.get("/api/v1/authors").json()["authors"]]
    assert "Никому Неизвестный" in names


def test_author_list_is_sorted(client):
    client.post("/api/v1/books", json={"title": "Раз", "author": "Яков Яковлев"})
    client.post("/api/v1/books", json={"title": "Два", "author": "Анна Аннова"})

    names = [a["name"] for a in client.get("/api/v1/authors").json()["authors"]]
    assert names.index("Анна Аннова") < names.index("Яков Яковлев")


# --- биография (задача 111) ---

def test_bio_is_empty_until_filled(client):
    author_id = _author_with_books(client)
    assert client.get(f"/api/v1/authors/{author_id}").json()["bio"] is None


def test_admin_can_write_bio(client):
    author_id = _author_with_books(client)

    r = client.patch(
        f"/api/v1/authors/{author_id}",
        json={"bio": "Ирландская писательница, автор «Дублинского отдела убийств»."},
    )
    assert r.status_code == 200
    assert client.get(f"/api/v1/authors/{author_id}").json()["bio"].startswith(
        "Ирландская"
    )


def test_empty_bio_clears_the_field(client):
    """Иначе заполненную по ошибке биографию нельзя убрать, не трогая базу."""
    author_id = _author_with_books(client)
    client.patch(f"/api/v1/authors/{author_id}", json={"bio": "Текст"})

    client.patch(f"/api/v1/authors/{author_id}", json={"bio": "   "})
    assert client.get(f"/api/v1/authors/{author_id}").json()["bio"] is None


def test_bio_requires_admin(client, demote):
    """Автор один на всю базу: его справку видит каждый читатель, значит правка
    общая — то же основание, что у полей книги."""
    author_id = _author_with_books(client)   # книги заводит ещё админ
    demote()

    r = client.patch(f"/api/v1/authors/{author_id}", json={"bio": "Чужой текст"})
    assert r.status_code == 403


def test_too_long_bio_rejected(client):
    author_id = _author_with_books(client)
    r = client.patch(f"/api/v1/authors/{author_id}", json={"bio": "а" * 4001})
    assert r.status_code == 422


def test_bio_on_unknown_author_is_404(client):
    assert client.patch("/api/v1/authors/999", json={"bio": "X"}).status_code == 404


def test_author_list_requires_login(client):
    app.dependency_overrides.clear()
    assert client.get("/api/v1/authors").status_code == 401


def test_author_page_requires_login(client):
    """Страница показывает всю полку по автору, включая книги вне витрины.
    Публичной она стала бы обходным путём к личной библиотеке."""
    author_id = _author_with_books(client)
    app.dependency_overrides.clear()          # снимаем подмену входа

    assert client.get(f"/api/v1/authors/{author_id}").status_code == 401


def test_unknown_author_is_404(client):
    assert client.get("/api/v1/authors/999").status_code == 404


def test_book_response_carries_author_links(client):
    """Имя на странице книги должно стать ссылкой — значит в ответе нужен id."""
    author_id = _author_with_books(client)
    book_id = client.get("/api/v1/books?status=want").json()[0]["id"]

    authors = client.get(f"/api/v1/books/{book_id}").json()["authors"]

    assert [a["id"] for a in authors] == [author_id]
    assert authors[0]["name"] == "Тана Френч"


def test_added_book_gets_linked(client):
    """Книга, добавленная после бэкфилла, тоже попадает к автору — иначе
    таблица застыла бы на дне переноса."""
    client.post("/api/v1/books", json={"title": "Новая", "author": "Свежий Автор"})

    with Session(database.engine) as session:
        author = session.exec(
            select(Author).where(Author.sort_key == norm_key("Свежий Автор"))
        ).first()
        assert author is not None
        links = session.exec(
            select(BookAuthor).where(BookAuthor.author_id == author.id)
        ).all()
        assert len(links) == 1


def test_book_string_is_left_intact(client):
    """`Book.author` НАМЕРЕННО остаётся: это строка для показа и печатной
    карточки. Связи добавляются рядом, а не вместо неё."""
    with Session(database.engine) as session:
        book = session.get(Book, 1)
        before = book.author

        link_book(session, book.id, book.author)
        session.commit()

        assert session.get(Book, 1).author == before
