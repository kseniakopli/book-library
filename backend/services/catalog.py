"""Общая механика справочников каталога (ревью 03.08, пункт Б1).

Авторы (з.97/111) и жанры (з.112) устроены одинаково: сущность каталога,
таблица связи с книгой, справочник «имя + число книг» и страница
«книги на полке / книги в каталоге». Различаются они только моделью и полем
связи — до этого модуля обе пары функций существовали построчными копиями
в `services/authors.py` и `services/genres.py`.

⚠ Оба запроса считают по ОБЩЕМУ каталогу, а не по полке спрашивающего
(решение Ксении 03.08): справочник отвечает на вопрос «что есть в библиотеке».
Личное появляется только в `books_split`, где полка идёт отдельной стопкой.

Здесь намеренно НЕТ знания о конкретных сущностях: ни `display_name`,
ни `Author`, ни `Genre`. Имя для показа передаёт вызывающий — у автора оно
собирается из двух полей, у жанра лежит в одном, и тащить это различие сюда
значило бы вернуть развилку, ради устранения которой модуль и появился.
"""

from typing import Callable

from sqlmodel import Session, col, func, select

from models import Book, UserBook


def entity_directory(
    session: Session,
    entity,
    link,
    link_entity_field,
    order_field,
    name_of: Callable[[object], str],
) -> list[dict]:
    """Справочник: сущности с числом связанных книг.

    `entity` — модель (Author/Genre), `link` — таблица связи
    (BookAuthor/BookGenre), `link_entity_field` — колонка связи, ссылающаяся
    на сущность, `order_field` — по чему сортировать (у обеих это ключ
    тождества, а не имя: так «ёлка» и «елка» стоят рядом).

    Одним запросом с группировкой: авторов уже 155, и отдельный COUNT
    на каждого превратился бы в полторы сотни обращений к базе.
    """
    rows = session.exec(
        select(entity, func.count(col(link.book_id)))
        .join(link, link_entity_field == entity.id)
        .group_by(entity.id)
        .order_by(order_field)
    ).all()
    return [
        {"id": item.id, "name": name_of(item), "books": count}
        for item, count in rows
    ]


def books_split(
    session: Session,
    link,
    link_entity_field,
    entity_id: int,
    user_id: int,
) -> dict:
    """Книги сущности, разложенные на две стопки.

    `shelf` — то, что у читателя на полке (со статусом и оценкой),
    `catalog` — остальные книги из общей базы: тома циклов и книги, заведённые
    другими читателями. Ради второй стопки страницы автора и жанра
    и задумывались — иначе они повторяли бы поиск по своей полке.

    `isouter=True` обязателен: книга может быть в каталоге и не быть ни у кого
    на полке. Внутренний JOIN молча выкинул бы ровно то, что нужно показать.
    """
    rows = session.exec(
        select(Book, UserBook)
        .join(link, link.book_id == Book.id)
        .join(
            UserBook,
            (UserBook.book_id == Book.id) & (UserBook.user_id == user_id),
            isouter=True,
        )
        .where(link_entity_field == entity_id)
        .order_by(Book.title)
    ).all()

    return {
        "shelf": [(book, ub) for book, ub in rows if ub is not None],
        "catalog": [book for book, ub in rows if ub is None],
    }
