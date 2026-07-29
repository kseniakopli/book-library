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


def test_book_string_is_left_intact(client):
    """`Book.author` НАМЕРЕННО остаётся: это строка для показа и печатной
    карточки. Связи добавляются рядом, а не вместо неё."""
    with Session(database.engine) as session:
        book = session.get(Book, 1)
        before = book.author

        link_book(session, book.id, book.author)
        session.commit()

        assert session.get(Book, 1).author == before
