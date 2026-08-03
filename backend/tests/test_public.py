# Публичная витрина (задача 30). Главное, что здесь проверяется, —
# ГРАНИЦА: витрина открыта без входа, но отдаёт только отмеченные книги
# и ничего личного.
import json

from sqlmodel import Session, col, select

import database
from events import Event
from main import app
from models import AISelection, User, UserBook


def _publish(slug="ksenia", featured=True, title=None):
    """Завести витрину владельцу и отметить фикстурную книгу."""
    with Session(database.engine) as session:
        user = session.get(User, 1)
        user.public_slug = slug
        user.public_title = title
        session.add(user)
        ub = session.exec(select(UserBook).where(UserBook.book_id == 1)).one()
        ub.featured = featured
        ub.rating = 9
        ub.status = "read"
        session.add(ub)
        session.commit()


def _anon(client):
    """Гость: снимаем подмену входа из conftest."""
    app.dependency_overrides.clear()
    return client


def test_showcase_is_open_without_login(client):
    _publish()
    r = _anon(client).get("/api/v1/public/ksenia")
    assert r.status_code == 200
    assert [b["title"] for b in r.json()["books"]] == ["Test"]


def test_showcase_hides_personal_data(client):
    """Оценка, статус и дата прочтения наружу не уходят — витрина про книги."""
    _publish()
    body = _anon(client).get("/api/v1/public/ksenia").text
    assert "rating" not in body
    assert "read_at" not in body
    assert "status" not in body


def test_only_featured_books_are_shown(client):
    _publish(featured=False)
    r = _anon(client).get("/api/v1/public/ksenia")
    assert r.json()["books"] == []
    # и по прямой ссылке такую книгу не открыть
    assert _anon(client).get("/api/v1/public/ksenia/books/1").status_code == 404


def test_no_slug_no_showcase(client):
    """Публикация — явное действие: без слага витрины не существует."""
    assert _anon(client).get("/api/v1/public/ksenia").status_code == 404


def test_book_page_returns_atmosphere(client):
    """Гость видит оформление и подборки — ради этого витрина и делалась."""
    _publish()
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=1, category="music", source="Claude",
            payload=json.dumps([{"title": "Song A", "artist": "Artist A"}]),
            explanation="Почему эта музыка",
        ))
        session.add(AISelection(
            book_id=1, category="design", source="Claude",
            payload=json.dumps({
                "symbol_svg": "<svg/>",
                "palette_dark": {"bg": "#161311"},
                "statement": "Символ выбран так",
            }),
            explanation="Символ выбран так",
        ))
        session.commit()

    r = _anon(client).get("/api/v1/public/ksenia/books/1")
    assert r.status_code == 200
    body = r.json()
    assert body["design"]["symbol_svg"] == "<svg/>"
    assert body["atmosphere"]["music"]["items"][0]["title"] == "Song A"
    assert "rating" not in r.text


def test_custom_title_is_used(client):
    _publish(title="Полка Ксении")
    assert _anon(client).get("/api/v1/public/ksenia").json()["title"] == "Полка Ксении"


def test_showcase_card_gets_both_palettes(client):
    """Ленте витрины нужны ОБЕ палитры: фон плашки выбирается по контрасту
    с чернилами символа, а не по теме интерфейса (28.07, pickPaletteForSymbol).
    Если наружу уедет одна палитра, светлый символ на светлом фоне пропадёт."""
    _publish()
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=1, category="design", source="Claude",
            payload=json.dumps({
                "base_mood": "туманная меланхолия",
                "symbol_svg": "<svg/>",
                "palette_light": {"bg": "#f2eade"},
                "palette_dark": {"bg": "#171310"},
            }),
            explanation="Символ выбран так",
        ))
        session.commit()

    design = _anon(client).get("/api/v1/public/ksenia").json()["books"][0]["design"]
    assert design["palette_light"] == {"bg": "#f2eade"}
    assert design["palette_dark"] == {"bg": "#171310"}
    # настроение решили не показывать — наружу его не отдаём вовсе
    assert "base_mood" not in design


def test_showcase_understands_old_passport(client):
    """Старый формат паспорта — одно поле `palette` (тёмное). Витрина не должна
    ни падать, ни отдавать пустую палитру: символ негде будет разместить."""
    _publish()
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=1, category="design", source="Claude",
            payload=json.dumps({"symbol_svg": "<svg/>", "palette": {"bg": "#161311"}}),
            explanation="",
        ))
        session.commit()

    design = _anon(client).get("/api/v1/public/ksenia").json()["books"][0]["design"]
    assert design["palette_dark"] == {"bg": "#161311"}
    assert design["palette_light"] is None


def test_visits_are_logged_without_personal_data(client):
    """Задача 96: заход на витрину попадает в событийный лог — иначе про
    единственный канал привлечения (бумажные карточки) не узнать ничего.
    В событии НЕ должно быть ни IP, ни User-Agent: на вопрос «ходят ли туда»
    хватает самого факта, а личное о госте мы не собираем."""
    _publish()
    _anon(client).get("/api/v1/public/ksenia")

    with Session(database.engine) as session:
        events = session.exec(
            select(Event).where(Event.type == "showcase_viewed")
        ).all()

    assert len(events) == 1
    assert events[0].detail == {}
    assert events[0].book_id is None


def test_book_view_is_logged_with_book(client):
    """Открытие книги с витрины пишется отдельным событием и с book_id:
    это сигнал, что оформление зацепило — человек пошёл смотреть дальше."""
    _publish()
    _anon(client).get("/api/v1/public/ksenia/books/1")

    with Session(database.engine) as session:
        events = session.exec(
            select(Event).where(Event.type == "showcase_book_viewed")
        ).all()

    assert [e.book_id for e in events] == [1]


def test_missing_showcase_is_not_counted(client):
    """404 в счётчик не идёт: чужой слаг и опечатки — это не заходы."""
    _anon(client).get("/api/v1/public/no-such-slug")

    with Session(database.engine) as session:
        events = session.exec(
            select(Event).where(col(Event.type).like("showcase%"))
        ).all()

    assert events == []


def test_featured_toggle_is_personal_not_admin(as_reader):
    """Отметка «в витрину» — личное решение владельца полки, не admin-действие."""
    r = as_reader.patch("/api/v1/books/1", json={"featured": True})
    assert r.status_code == 200
    assert r.json()["featured"] is True
