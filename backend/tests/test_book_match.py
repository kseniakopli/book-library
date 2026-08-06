"""Сверка советов модели с каталогом Google Books (задача 126).

Чистые функции — ни сети, ни базы, ни клиента. Здесь проверяется главное
решение задачи: отличить настоящую книгу от выдуманной, не выбросив при
этом настоящую из-за перевода названия или транслита в имени автора.

Повод: 06.08 в рекомендациях приехала «И как только мы вернёмся» некой
Бенедетты Кристофани — книги нет нигде.
"""

from services.book_match import find_match, normalize_author, normalize_title


def _candidate(title, author, cover="https://example.com/c.jpg", ext="gb-1"):
    return {"title": title, "author": author, "cover_url": cover, "external_id": ext}


# --- нормализация ---

def test_subtitle_after_colon_is_cut():
    """«Щегол: роман» и «Щегол» — одна книга. Издатели дописывают жанр
    в подзаголовок, модель его не знает."""
    assert normalize_title("Щегол: роман") == normalize_title("Щегол")


def test_bracketed_notes_are_cut():
    assert normalize_title("Убежище 3/9 (сборник)") == normalize_title("Убежище 3 9")


def test_author_word_order_does_not_matter():
    """Каталоги пишут и «Тана Френч», и «Френч, Тана»."""
    assert normalize_author("Тана Френч") == normalize_author("Френч, Тана")


# --- сверка ---

def test_exact_match_is_confirmed():
    found = find_match([_candidate("Ребекка", "Дафна Дюморье")], "Ребекка", "Дафна Дюморье")
    assert found is not None


def test_transliterated_author_is_confirmed():
    """⚠ Ключевой случай: русскую книгу Google часто знает под английским
    названием и латинским именем. Без транслита она выглядела бы выдумкой
    и была бы отброшена — то есть проверка портила бы выдачу."""
    found = find_match(
        [_candidate("Rebecca", "Daphne du Maurier")], "Ребекка", "Дафна Дюморье",
    )
    assert found is not None


def test_invented_book_is_rejected():
    """Каталог не нашёл ничего похожего — совет не подтверждён."""
    assert find_match([], "И как только мы вернёмся", "Бенедетта Кристофани") is None


def test_unrelated_result_is_rejected():
    """Поиск по выдуманному названию возвращает что-нибудь по отдельным
    словам. Брать первое попавшееся нельзя — ровно эта ошибка была
    в Spotify 20.07, когда в плейлист попал чужой рэп-трек."""
    found = find_match(
        [_candidate("Италия за неделю", "Марко Росси")],
        "И как только мы вернёмся", "Бенедетта Кристофани",
    )
    assert found is None


def test_same_title_other_author_is_rejected():
    """Название совпало, автор чужой — это другая книга."""
    assert find_match(
        [_candidate("Ребекка", "Иван Петров")], "Ребекка", "Дафна Дюморье",
    ) is None


def test_best_candidate_wins_not_the_first():
    """Из нескольких подходящих берём самого похожего, а не первого:
    поиск часто ставит вперёд книги О книге — исследования, путеводители."""
    found = find_match(
        [
            _candidate("Ребекка. Читательский дневник", "Дафна Дюморье", ext="wrong"),
            _candidate("Ребекка", "Дафна Дюморье", ext="right"),
        ],
        "Ребекка", "Дафна Дюморье",
    )
    assert found["external_id"] == "right"


def test_candidate_without_author_needs_near_exact_title():
    """У тома без авторов сверять имя не с чем, поэтому от названия требуем
    почти точного совпадения — иначе подтвердится что угодно похожее."""
    assert find_match([_candidate("Ребекка", "—")], "Ребекка", "Дафна Дюморье")
    assert find_match([_candidate("Ребекка и другие", "—")], "Ребекка", "Дафна Дюморье") is None
