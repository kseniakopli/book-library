# Разбор ответа Google Books: чистка аннотации и общая ветка разбора.
#
# Аннотации приезжают с артефактами вёрстки, и с задачи 30 их читает ГОСТЬ
# с бумажной карточки — «дом»--история» на публичной странице выглядит браком
# сервиса, а не источника (аудит 28.07, находка 9).
import google_books
from google_books import clean_description


def test_double_dash_becomes_dash():
    text = "«Голландский дом»--история о победе любви. И если был--то кто?"
    assert clean_description(text) == (
        "«Голландский дом» — история о победе любви. И если был — то кто?"
    )


def test_tags_are_stripped_and_br_becomes_newline():
    assert clean_description("Первый<br>Второй<p>Третий</p>") == (
        "Первый\nВторойТретий"
    )


def test_entities_and_extra_spaces():
    assert clean_description("Дом&nbsp;&nbsp;и   сад &amp; огород") == (
        "Дом и сад & огород"
    )


def test_empty_stays_empty():
    assert clean_description(None) is None
    assert clean_description("") == ""


def test_dash_inside_word_is_not_touched():
    """Двойной дефис — артефакт вёрстки, а одиночный внутри слова законный."""
    assert clean_description("что-то и кто-нибудь") == "что-то и кто-нибудь"


def test_isbn_match_returns_metadata(monkeypatch):
    """Регрессия 28.07: разбор volumeInfo был вложен в ветку «по названию»,
    поэтому книга, найденная ПО ISBN, возвращала пустой результат — обогащение
    молча тянуло данные вторым запросом или не тянуло вовсе."""
    volume = {
        "title": "Голландский дом",
        "authors": ["Ann Patchett"],
        "description": "Роман--история семьи",
        "imageLinks": {"thumbnail": "http://example.com/cover.jpg"},
        "pageCount": 352,
        "publishedDate": "2022-05-01",
    }
    monkeypatch.setattr(
        google_books, "_books_request", lambda *a, **kw: [{"volumeInfo": volume}]
    )

    info = google_books.fetch_book_info(
        "Голландский дом", "Ann Patchett", isbn="978-5-04-116757-8"
    )

    assert info["page_count"] == 352
    assert info["published_year"] == 2022
    assert info["cover_url"].startswith("https://")   # http → https
    assert info["description"] == "Роман — история семьи"
