# Рекомендации новых книг (этап 8): генерация по кнопке, дедуп с библиотекой.
from sqlmodel import Session, select

import database
from models import Recommendation
from routers import recommendations as rec_routes
from services.ai_schemas import RecommendationItem, RecommendationsResult


def _fake_generate(
    favorites, exclude, count=5, lang="ru", disliked=None,
    casual=None, skip_authors=None, genres_include=None, genres_exclude=None,
):
    """Мгновенный «AI» от ДВУХ источников (контракт с 20.07):
    - Claude: новая книга + книга, которая уже на полке (дедуп её отбросит);
    - ChatGPT: своя новая книга + повтор совета Claude (дедуп между источниками)."""
    async def run():
        return {
            "Claude": RecommendationsResult(items=[
                RecommendationItem(title="Новая книга", author="Новый Автор",
                                   reason="похожа на ваши любимые"),
                RecommendationItem(title="Test", author="Author",
                                   reason="а это уже есть в библиотеке"),
            ]),
            "ChatGPT": RecommendationsResult(items=[
                RecommendationItem(title="Новая книга", author="Новый Автор",
                                   reason="дубль совета Claude"),
                RecommendationItem(title="Вторая книга", author="Второй Автор",
                                   reason="совет от ChatGPT"),
            ]),
        }
    return run()


def _mock(monkeypatch):
    monkeypatch.setattr(rec_routes, "generate_recommendations", _fake_generate)
    # обложки не ищем — Google Books в тестах не дёргаем
    monkeypatch.setattr(rec_routes, "search_books", lambda q, max_results=3: [])


def _make_favorite(client):
    """Фикстурной книге ставим высокую оценку — иначе рекомендовать не по чему."""
    client.patch("/api/v1/books/1", json={"status": "read", "rating": 9})


def test_recommendations_empty_at_start(client):
    assert client.get("/api/v1/recommendations").json()["recommendations"] == []


def test_generate_without_favorites_spends_nothing(client, monkeypatch):
    """Нет высоко оценённых книг — честно отвечаем, AI не зовём."""
    called = {"n": 0}

    def spy(*args, **kwargs):
        called["n"] += 1
        return _fake_generate(*args, **kwargs)

    monkeypatch.setattr(rec_routes, "generate_recommendations", spy)
    r = client.post("/api/v1/recommendations")
    assert r.status_code == 200
    assert r.json()["recommendations"] == []
    assert r.json()["detail"] == "no_favorites"
    assert called["n"] == 0


def test_generate_and_dedupe(client, monkeypatch):
    _mock(monkeypatch)
    _make_favorite(client)

    r = client.post("/api/v1/recommendations")
    assert r.status_code == 200
    items = r.json()["recommendations"]
    titles = [i["title"] for i in items]
    assert "Новая книга" in titles
    assert "Test" not in titles          # уже в библиотеке → отброшена
    assert items[0]["reason"]

    # сохранилось и читается обычным GET
    assert client.get("/api/v1/recommendations").json()["recommendations"] == items


def test_two_sources_with_cross_dedupe(client, monkeypatch):
    """Две модели, дубли схлопнуты: «Новая книга» предложена обеими — остаётся
    один раз и числится за Claude (он первый в фиксированном порядке)."""
    _mock(monkeypatch)
    _make_favorite(client)

    items = client.post("/api/v1/recommendations").json()["recommendations"]
    titles = [i["title"] for i in items]
    assert titles == ["Новая книга", "Вторая книга"]     # дубль убран
    by_title = {i["title"]: i["source"] for i in items}
    assert by_title["Новая книга"] == "Claude"
    assert by_title["Вторая книга"] == "ChatGPT"


def test_regeneration_replaces_set(client, monkeypatch):
    _mock(monkeypatch)
    _make_favorite(client)
    client.post("/api/v1/recommendations")
    client.post("/api/v1/recommendations")          # второй раз

    with Session(database.engine) as session:
        rows = session.exec(select(Recommendation)).all()
    assert len(rows) == 2                            # набор заменён, не задвоен


def test_disliked_reaches_generation(client, monkeypatch):
    """Задача 26 ч.4: советы с 👎 доезжают до промпта как «уже отклонённое»."""
    captured = {}

    def spy(favorites, exclude, count=5, lang="ru", disliked=None, **kw):
        captured["disliked"] = disliked
        return _fake_generate(favorites, exclude, count, lang)

    monkeypatch.setattr(rec_routes, "generate_recommendations", spy)
    monkeypatch.setattr(rec_routes, "search_books", lambda q, max_results=3: [])
    _make_favorite(client)

    client.post("/api/v1/feedback", json={
        "ref": "recommendation:тень ветра|сафон", "verdict": "down", "source": "Claude",
    })
    client.post("/api/v1/recommendations")

    assert captured["disliked"] == ["тень ветра — сафон"]


# --- настройки подбора (задача 124) ---

def _spy(monkeypatch, captured):
    """Перехват аргументов, уезжающих в промпт."""
    def spy(favorites, exclude, count=5, lang="ru", disliked=None, **kw):
        captured.update(kw, favorites=favorites)
        return _fake_generate(favorites, exclude, count, lang)

    monkeypatch.setattr(rec_routes, "generate_recommendations", spy)
    monkeypatch.setattr(rec_routes, "search_books", lambda q, max_results=3: [])


def test_settings_saved_and_returned(client):
    client.put("/api/v1/books/1/genres", json={"genres": ["Детектив"]})

    r = client.put("/api/v1/recommendations/settings", json={
        "skip_known_authors": True,
        "genres_include": ["детектив"],
        "genres_exclude": [],
    })
    assert r.status_code == 200

    settings = client.get("/api/v1/recommendations").json()["settings"]
    assert settings["skip_known_authors"] is True
    assert settings["genres_include"] == ["детектив"]


def test_unknown_genres_are_dropped(client):
    """Список приходит с клиента, а уезжает в промпт — принимать на веру
    произвольные строки незачем. Неизвестное молча отбрасывается: это
    не ошибка пользователя, а разошедшееся состояние (жанр могли удалить,
    пока страница была открыта)."""
    r = client.put("/api/v1/recommendations/settings", json={
        "skip_known_authors": False,
        "genres_include": ["выдуманный жанр"],
        "genres_exclude": [],
    })
    assert r.json()["settings"]["genres_include"] == []


def test_casual_books_go_in_a_separate_list(client, monkeypatch):
    """⚠ Главное решение задачи 124: оценки 5–6 подаются ОТДЕЛЬНО.

    Это не «понравилось послабее», а другой род чтения — одноразовое,
    для расслабления. Свалив их в `favorites`, мы бы сказали модели,
    что оценка 5 значит «нравится».
    """
    captured = {}
    _spy(monkeypatch, captured)
    client.patch("/api/v1/books/1", json={"status": "read", "rating": 9})
    book_id = client.post("/api/v1/books", json={
        "title": "Лёгкий детектив", "author": "Автор Детективов",
    }).json()["id"]
    client.patch(f"/api/v1/books/{book_id}", json={"status": "read", "rating": 5})

    client.post("/api/v1/recommendations")

    assert any("Волшебная гора" in f or "Test" in f for f in captured["favorites"])
    assert captured["casual"] == ["Лёгкий детектив — Автор Детективов (5/10)"]
    # и наоборот: книга на 5 не попала в «любимое»
    assert not any("Лёгкий детектив" in f for f in captured["favorites"])


def test_low_rated_books_alone_are_enough_to_generate(client, monkeypatch):
    """Раньше без книг с оценкой ≥7 подбор не запускался вовсе. Теперь
    и «читалось для отдыха» — достаточный сигнал."""
    captured = {}
    _spy(monkeypatch, captured)
    client.patch("/api/v1/books/1", json={"status": "read", "rating": 5})

    r = client.post("/api/v1/recommendations")

    assert r.json().get("detail") != "no_favorites"
    assert captured["favorites"] == []
    assert captured["casual"]


def _shelf_book_with_author(client, author: str = "Донато Карризи") -> None:
    """Книга на полке с ПРИВЯЗАННЫМ автором-сущностью.

    ⚠ Через API, а не прямой записью в базу: `link_book` вызывается только
    в `add_to_shelf`, и книга, созданная в обход, авторов не получает —
    фильтр по авторам на ней бы не сработал, а тест показал бы «всё хорошо».
    """
    book_id = client.post(
        "/api/v1/books", json={"title": "Моя книга", "author": author}
    ).json()["id"]
    client.patch(f"/api/v1/books/{book_id}", json={"status": "read", "rating": 9})


def _suggest(monkeypatch, *items):
    def spy(favorites, exclude, count=5, lang="ru", disliked=None, **kw):
        async def run():
            return {
                "Claude": RecommendationsResult(items=list(items)),
                "ChatGPT": RecommendationsResult(items=[]),
            }
        return run()

    monkeypatch.setattr(rec_routes, "generate_recommendations", spy)
    monkeypatch.setattr(rec_routes, "search_books", lambda q, max_results=3: [])


def test_known_authors_are_filtered_out_of_the_answer(client, monkeypatch):
    """⚠ Просьба в промпте — не гарантия. Имена авторов мы знаем, значит
    проверяем ответ кодом, а не надеемся (Уроки 1.1).

    Мок специально советует автора, который уже есть на полке: с включённым
    чекбоксом такой совет обязан быть отброшен.
    """
    _suggest(
        monkeypatch,
        RecommendationItem(title="Другая книга", author="Донато Карризи",
                           reason="тот же автор, что на полке"),
        RecommendationItem(title="Хорошая книга", author="Чужой Автор",
                           reason="новый автор"),
    )
    _shelf_book_with_author(client)
    client.put("/api/v1/recommendations/settings", json={
        "skip_known_authors": True, "genres_include": [], "genres_exclude": [],
    })

    titles = [
        r["title"] for r in client.post("/api/v1/recommendations").json()["recommendations"]
    ]
    assert "Хорошая книга" in titles
    assert "Другая книга" not in titles     # автор уже на полке


def test_known_authors_kept_when_checkbox_is_off(client, monkeypatch):
    """Контрольный образец к тесту выше: без чекбокса тот же совет проходит.
    Иначе тест не отличал бы работающий фильтр от сломанного мока —
    оба случая выглядели бы как «книги нет в ответе»."""
    _suggest(
        monkeypatch,
        RecommendationItem(title="Другая книга", author="Донато Карризи",
                           reason="тот же автор"),
    )
    _shelf_book_with_author(client)

    titles = [
        r["title"] for r in client.post("/api/v1/recommendations").json()["recommendations"]
    ]
    assert "Другая книга" in titles


def test_genre_settings_reach_the_prompt(client, monkeypatch):
    """Жанры проверить на выходе нечем (у советов нет наших жанров),
    поэтому единственное, что можно гарантировать, — что они доехали."""
    captured = {}
    _spy(monkeypatch, captured)
    client.put("/api/v1/books/1/genres", json={"genres": ["Детектив", "Мистика"]})
    client.patch("/api/v1/books/1", json={"status": "read", "rating": 9})
    client.put("/api/v1/recommendations/settings", json={
        "skip_known_authors": False,
        "genres_include": ["детектив"],
        "genres_exclude": ["мистика"],
    })

    client.post("/api/v1/recommendations")

    # в промпт уезжают ИМЕНА, а не slug: модель читает по-человечески
    assert captured["genres_include"] == ["Детектив"]
    assert captured["genres_exclude"] == ["Мистика"]


def test_generate_allowed_for_any_logged_in_user(client, demote, monkeypatch):
    """Этап 9: рекомендации личные (по своим оценкам), поэтому подбирать их
    может каждый вошедший, не только админ. Раньше стоял require_admin —
    при одном пользователе это было неотличимо, а с тестерами кнопка у них
    всегда отвечала бы 403. Расходы держат rate limit и капы провайдеров."""
    _mock(monkeypatch)
    _make_favorite(client)     # оценку ставит ещё админ
    demote()

    assert client.post("/api/v1/recommendations").status_code == 200
    assert client.get("/api/v1/recommendations").status_code == 200
