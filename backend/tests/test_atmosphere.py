# AI-«Атмосфера»: обобщённые эндпоинты /books/{id}/atmosphere/{category}.
import pydantic
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

import database
from conftest import fake_generate_design, fake_generate_food, fake_generate_music
from models import AISelection
from routers import atmosphere as atmosphere_routes
from services.ai_schemas import DesignResult


def _mock_music(monkeypatch):
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["music"], "generate", fake_generate_music
    )


def _mock_design(monkeypatch):
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["design"], "generate", fake_generate_design
    )


# --- музыка ---

def test_generate_music_two_sources(client, monkeypatch):
    _mock_music(monkeypatch)
    r = client.post("/api/v1/books/1/atmosphere/music")
    assert r.status_code == 200
    sources = {s["source"] for s in r.json()["selections"]}
    assert sources == {"Claude", "ChatGPT"}


def test_context_passed_to_prompt(client, monkeypatch):
    """22.07: в генерацию уходит фактический контекст книги — аннотация и жанры,
    иначе модель угадывает сюжет по названию (инцидент «Капля духов» → Дубай).

    ⚠ Задача 112 (03.08) сузила «жанры» до НАШИХ, заведённых вручную. Раньше
    здесь ждали «Fiction» из `book.categories` — это рубрикатор магазина,
    одинаковый у половины библиотеки: модель получала шум под видом сигнала.
    Проверка не снята, а перенаправлена: контекст по-прежнему обязан доезжать,
    но теперь из своего источника.
    """
    from sqlmodel import Session

    import database
    from models import Book

    with Session(database.engine) as session:
        book = session.get(Book, 1)
        book.description = "История о парфюмерном мире Москвы"
        book.categories = '["Fiction"]'      # рубрика Google — в промпт не идёт
        session.add(book)
        session.commit()

    client.put("/api/v1/books/1/genres", json={"genres": ["Магический реализм"]})

    captured = {}

    async def spy(title, author, lang="ru", context=None):
        captured["context"] = context
        return await fake_generate_music(title, author, lang)

    monkeypatch.setitem(atmosphere_routes.CATEGORIES["music"], "generate", spy)
    client.post("/api/v1/books/1/atmosphere/music")

    assert "парфюмерном мире Москвы" in captured["context"]["description"]
    assert captured["context"]["genres"] == "Магический реализм"
    assert "Fiction" not in captured["context"]["genres"]
    assert "avoid" in captured["context"]


def test_music_marked_unverified_when_spotify_unavailable(client, monkeypatch):
    """Задача 85: Spotify недоступен (бан/нет ключей) → музыка помечается
    непроверенной (verified=False), чтобы reverify_music её потом догнал."""
    import services.spotify as spotify_service

    _mock_music(monkeypatch)
    monkeypatch.setattr(spotify_service, "available", lambda: False)
    r = client.post("/api/v1/books/1/atmosphere/music")
    assert r.json()["verified"] is False


def test_music_verified_when_spotify_available(client, monkeypatch):
    import services.spotify as spotify_service

    _mock_music(monkeypatch)
    monkeypatch.setattr(spotify_service, "available", lambda: True)
    r = client.post("/api/v1/books/1/atmosphere/music")
    assert r.json()["verified"] is True


def test_generated_music_is_persisted(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")
    r = client.get("/api/v1/books/1/atmosphere/music")
    assert r.status_code == 200
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["payload"][0]["title"] == "Song A"
    assert claude["explanation"] == "Claude explanation"


def test_regenerate_does_not_duplicate(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")
    client.post("/api/v1/books/1/atmosphere/music")            # второй раз
    r = client.get("/api/v1/books/1/atmosphere/music")
    assert len(r.json()["selections"]) == 2  # всё ещё 2 варианта, а не 4


def test_failed_regeneration_keeps_old(client, monkeypatch):
    """Защита от потери (инцидент 18.07): неудачная перегенерация (AI вернул
    пустой фолбэк) НЕ должна затирать уже сохранённую атмосферу."""
    from services.ai_schemas import MusicResult

    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")   # успешно: Song A / Song B

    async def all_empty(title, author, lang="ru", context=None):
        return {
            "Claude": MusicResult(songs=[], explanation="(не удалось)"),
            "ChatGPT": MusicResult(songs=[], explanation="(не удалось)"),
        }
    monkeypatch.setitem(atmosphere_routes.CATEGORIES["music"], "generate", all_empty)
    client.post("/api/v1/books/1/atmosphere/music")   # провал — не должен стереть

    r = client.get("/api/v1/books/1/atmosphere/music").json()
    assert len(r["selections"]) == 2                  # старые на месте
    claude = next(s for s in r["selections"] if s["source"] == "Claude")
    assert claude["payload"][0]["title"] == "Song A"


def test_first_generation_all_empty_writes_nothing(client, monkeypatch):
    """Первая генерация, если AI не ответил ни одним источником, не плодит
    пустые строки — остаётся «пусто», а не два пустых варианта."""
    from services.ai_schemas import MusicResult

    async def all_empty(title, author, lang="ru", context=None):
        return {
            "Claude": MusicResult(songs=[], explanation="(не удалось)"),
            "ChatGPT": MusicResult(songs=[], explanation="(не удалось)"),
        }
    monkeypatch.setitem(atmosphere_routes.CATEGORIES["music"], "generate", all_empty)
    client.post("/api/v1/books/1/atmosphere/music")
    r = client.get("/api/v1/books/1/atmosphere/music").json()
    assert r["selections"] == []


def test_generate_music_book_not_found(client, monkeypatch):
    _mock_music(monkeypatch)
    assert client.post("/api/v1/books/999/atmosphere/music").status_code == 404


def test_generate_music_invalid_lang(client, monkeypatch):
    _mock_music(monkeypatch)
    assert client.post("/api/v1/books/1/atmosphere/music?lang=fr").status_code == 400


# --- «затасканные» пункты (avoid) ---

def test_overused_items_catch_paraphrased_titles(client):
    """24.07: модели перефразируют названия блюд («Яблочный пирог с корицей» /
    «по-ирландски» / «со сливками»), и точный счётчик повторов их не ловил —
    порог AVOID_MIN_BOOKS не срабатывал никогда. Теперь ключ — первые два слова,
    в avoid идёт самое короткое название."""
    import json as _json

    from models import Book
    from services.prompt_context import build_book_context

    variants = [
        "Яблочный пирог",
        "Яблочный пирог с корицей",
        "Яблочный пирог по-ирландски",
    ]
    with Session(database.engine) as session:
        for i, title in enumerate(variants, start=2):
            session.add(Book(id=i, title=f"Книга {i}", author="Автор"))
            session.commit()
            session.add(AISelection(
                book_id=i, category="food", source="Claude",
                payload=_json.dumps(
                    [{"title": title, "description": ""}], ensure_ascii=False
                ),
            ))
        session.commit()
        context = build_book_context(session, 1, "food", 1)

    assert "Яблочный пирог" in context["avoid"]   # 3 вариации = один пункт
    # сами вариации отдельными пунктами не дублируются
    assert sum("пирог" in a.lower() for a in context["avoid"]) == 1


# --- точечное удаление трека (admin) ---

def _seed_music(client, monkeypatch):
    """Сгенерировать музыку фейком: Claude — Song A, ChatGPT — Song B."""
    import services.spotify as spotify_service

    _mock_music(monkeypatch)
    # Spotify в тестах не трогаем: и генерация, и пересборка плейлиста мимо него
    monkeypatch.setattr(spotify_service, "available", lambda: False)
    client.post("/api/v1/books/1/atmosphere/music")


def test_remove_track_from_one_source(client, monkeypatch):
    _seed_music(client, monkeypatch)
    r = client.request(
        "DELETE", "/api/v1/books/1/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Song A", "artist": "Artist A"},
    )
    assert r.status_code == 200
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["payload"] == []                    # трек удалён
    chatgpt = next(s for s in r.json()["selections"] if s["source"] == "ChatGPT")
    assert chatgpt["payload"][0]["title"] == "Song B"  # чужой источник не задет
    # удаление сохранилось
    assert client.get("/api/v1/books/1/atmosphere/music").json() == r.json()


def test_remove_track_not_found(client, monkeypatch):
    _seed_music(client, monkeypatch)
    r = client.request(
        "DELETE", "/api/v1/books/1/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Нет такого", "artist": "Никто"},
    )
    assert r.status_code == 404


def test_design_prompt_has_no_personal_taste(client, monkeypatch):
    """Задача 117: паспорт ОБЩИЙ — палитру и символ видят все, включая гостей
    витрины. Подмешивать туда 👍/👎 того, кто первым добавил книгу, значит
    закреплять его вкус в общем оформлении. У музыки и угощений результат
    личный по духу, там профиль остаётся."""
    from sqlmodel import Session

    import database
    from models import Feedback

    with Session(database.engine) as session:
        session.add(Feedback(
            user_id=1, ref="atmosphere:1:design:Claude",
            source="Claude", verdict="down",
        ))
        session.commit()

    captured = {}

    async def spy_design(title, author, lang="ru", context=None):
        captured["design"] = context
        return await fake_generate_design(title, author, lang)

    async def spy_music(title, author, lang="ru", context=None):
        captured["music"] = context
        return await fake_generate_music(title, author, lang)

    monkeypatch.setitem(atmosphere_routes.CATEGORIES["design"], "generate", spy_design)
    monkeypatch.setitem(atmosphere_routes.CATEGORIES["music"], "generate", spy_music)
    client.post("/api/v1/books/1/atmosphere/design")
    client.post("/api/v1/books/1/atmosphere/music")

    assert "liked" not in captured["design"]
    assert "disliked" not in captured["design"]

    # Контрольный образец: у музыки тот же механизм ОБЯЗАН работать.
    # Без этой половины тест был бы зелёным и в случае, когда профиль вкуса
    # сломался целиком, — то есть отличал бы правку от поломки никак
    # (см. `Уроки.md`, раздел 2).
    with Session(database.engine) as session:
        session.add(Feedback(
            user_id=1, ref="atmosphere:1:music:Claude",
            source="Claude", verdict="up",
        ))
        session.commit()
    client.post("/api/v1/books/1/atmosphere/music")
    assert "liked" in captured["music"]


# --- права на генерацию (жалоба тестировщика 02.08) ---

def test_first_generation_allowed_for_any_user(as_reader, monkeypatch):
    """Книга без атмосферы была тупиком: фоном генерится только паспорт,
    а кнопка и эндпоинт требовали admin. Первое создание чужого не портит —
    до него здесь пусто."""
    _mock_music(monkeypatch)

    r = as_reader.post("/api/v1/books/1/atmosphere/music")
    assert r.status_code == 200
    assert len(r.json()["selections"]) == 2


def test_regeneration_still_requires_admin(client, demote, monkeypatch):
    """Перегенерация переписывает атмосферу для ВСЕХ, включая витринные книги,
    чьи плейлисты уехали в печатные QR."""
    _mock_music(monkeypatch)
    assert client.post("/api/v1/books/1/atmosphere/music").status_code == 200

    demote()          # права снимаются ПОСЛЕ первой генерации — в этом суть
    assert client.post("/api/v1/books/1/atmosphere/music").status_code == 403


def test_permission_is_per_category(client, demote, monkeypatch):
    """Заполненная музыка не должна запирать пустые угощения: право считается
    по своей категории, а не по книге целиком."""
    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["food"], "generate", fake_generate_food
    )
    demote()

    assert client.post("/api/v1/books/1/atmosphere/music").status_code == 403
    assert client.post("/api/v1/books/1/atmosphere/food").status_code == 200


def test_remove_track_requires_admin(client, demote, monkeypatch):
    # трек добавляет админ, а удалить пробует уже обычный читатель
    _seed_music(client, monkeypatch)
    demote()
    r = client.request(
        "DELETE", "/api/v1/books/1/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Song A", "artist": "Artist A"},
    )
    assert r.status_code == 403


def test_remove_track_book_not_found(client):
    r = client.request(
        "DELETE", "/api/v1/books/999/atmosphere/music/tracks",
        json={"source": "Claude", "title": "Song A", "artist": "Artist A"},
    )
    assert r.status_code == 404


# --- паспорт оформления ---

def test_generate_and_get_design(client, monkeypatch):
    _mock_design(monkeypatch)
    r = client.post("/api/v1/books/1/atmosphere/design")
    assert r.status_code == 200
    selection = r.json()["selections"][0]
    assert selection["source"] == "Claude"
    # задача 57: паспорт несёт обе палитры — тёмную и светлую
    assert selection["payload"]["palette_dark"]["accent"] == "#e08b2d"
    assert selection["payload"]["palette_light"]["bg"] == "#f6f1e7"

    r2 = client.get("/api/v1/books/1/atmosphere/design")
    assert r2.json() == r.json()   # POST и GET отдают один формат


def test_design_absent_is_empty_list(client):
    r = client.get("/api/v1/books/1/atmosphere/design")
    assert r.status_code == 200
    assert r.json()["selections"] == []


# --- общее ---

def test_unknown_category_404(client):
    assert client.get("/api/v1/books/1/atmosphere/weather").status_code == 404
    assert client.post("/api/v1/books/1/atmosphere/weather").status_code == 404


def test_delete_cascades_selections(client, monkeypatch):
    _mock_music(monkeypatch)
    client.post("/api/v1/books/1/atmosphere/music")
    client.delete("/api/v1/books/1")
    with Session(database.engine) as session:
        rows = session.exec(
            select(AISelection).where(AISelection.book_id == 1)
        ).all()
    assert rows == []


def test_aiselection_unique_constraint(client):
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=1, category="music", source="Claude", payload="[]",
        ))
        session.commit()
        session.add(AISelection(
            book_id=1, category="music", source="Claude", payload="[]",
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_design_palette_rejects_non_hex():
    """Задача 37: не-hex цвета из AI отбрасываются на границе."""
    ok_palette = {"bg": "#ffffff", "surface": "#ffffff", "accent": "#ffffff",
                  "text": "#ffffff", "muted": "#ffffff"}
    bad = {
        "base_mood": "мрак",
        "palette_dark": {**ok_palette, "bg": "url(https://evil.example)"},
        "palette_light": ok_palette,
        "title_font": "PT Serif", "body_font": "PT Serif", "statement": "…",
    }
    with pytest.raises(pydantic.ValidationError):
        DesignResult.model_validate(bad)

def test_generate_food_two_sources_and_persist(client, monkeypatch):
    from conftest import fake_generate_food
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["food"], "generate", fake_generate_food
    )
    r = client.post("/api/v1/books/1/atmosphere/food")
    assert r.status_code == 200
    assert {s["source"] for s in r.json()["selections"]} == {"Claude", "ChatGPT"}
    claude = next(s for s in r.json()["selections"] if s["source"] == "Claude")
    assert claude["payload"][0] == {
        "title": "Глинтвейн", "description": "Тёплый и пряный",
    }
    assert client.get("/api/v1/books/1/atmosphere/food").json() == r.json()


def test_categories_are_independent(client, monkeypatch):
    from conftest import fake_generate_aroma
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["music"], "generate", fake_generate_music
    )
    monkeypatch.setitem(
        atmosphere_routes.CATEGORIES["aroma"], "generate", fake_generate_aroma
    )
    client.post("/api/v1/books/1/atmosphere/music")
    client.post("/api/v1/books/1/atmosphere/aroma")
    # каждая категория хранит свои 2 подборки и не задевает чужие
    assert len(client.get("/api/v1/books/1/atmosphere/music").json()["selections"]) == 2
    assert len(client.get("/api/v1/books/1/atmosphere/aroma").json()["selections"]) == 2


# --- Ароматы: слой «что это на самом деле» (з.129, 12.08) ---------------
#
# Тесты закрывают не код, а ПРАВИЛО: подборка ароматов обязана называть
# покупаемое сырьё. До 12.08 схема принимала любой текст, и модель отдавала
# выдуманные товары («Крахмальный воротничок») — купить их нельзя.
# Разбор: `Архив_решений.md` → «Выдуманные ароматы», правило: `Уроки.md` 1.6.


def test_aroma_item_requires_material_and_form():
    from services.ai_schemas import AromaItem

    # Ровно то, что модель отдавала раньше: только образ, вещества нет.
    with pytest.raises(pydantic.ValidationError):
        AromaItem(title="Крахмальный воротничок", description="Чистое бельё")


def test_aroma_form_is_a_closed_list():
    from services.ai_schemas import AromaItem

    # Форма выпуска — перечень; «аромат вечера» формой не является.
    with pytest.raises(pydantic.ValidationError):
        AromaItem(
            material="ветивер", form="аромат вечера",
            title="Сырой ветер", description="Земляной",
        )


def test_aroma_material_is_normalised_and_gives_a_search_query():
    from services.ai_schemas import AromaItem

    # Модель склонна Капитализировать и закавычивать — так сырьё читается
    # как бренд. На этикетке оно строчными.
    item = AromaItem(
        material="«Ветивер»", form="эфирное масло",
        title="Сырой ветер с холмов", description="Земляной, горьковатый",
    )
    assert item.material == "ветивер"
    assert item.search_query == "эфирное масло ветивер"


def test_aroma_material_may_not_repeat_the_image():
    from services.ai_schemas import AromaItem

    # Вырожденный обход: поле заполнено, но тем же образом — слоя опять нет.
    with pytest.raises(pydantic.ValidationError):
        AromaItem(
            material="Крахмальный воротничок", form="свеча",
            title="Крахмальный воротничок", description="Чистое бельё",
        )


# --- Отсев небезопасного (з.133, 12.08) --------------------------------
#
# ⚠ Задача появилась как СЛЕДСТВИЕ з.129: пока модель выдавала образы,
# совет был неисполним и безвреден; потребовали называть покупаемое —
# и первая перегенерация предложила «сухая трава · конопля».
# Правило: `Уроки.md` 1.11. Разбор: `Архив_решений.md` → «Выдуманные ароматы».


def test_unsafe_materials_are_recognised():
    from services.aroma_safety import is_unsafe

    assert is_unsafe("конопля")
    assert is_unsafe("семена конопли")          # ловим по основе, не по слову
    assert is_unsafe("", "Благовония с коноплёй")  # запрет может приехать в title
    assert is_unsafe("белёна") == "белена"      # ё/е схлопываем (как в norm_slug)
    assert is_unsafe("хлорка")
    assert is_unsafe("бензин")


def test_real_materials_are_not_touched():
    from services.aroma_safety import is_unsafe

    # ⚠ Главный тест модуля. Ложное срабатывание здесь дороже пропуска:
    # оно молча выбрасывает нормальный аромат, и заметить это нечем.
    # «бензоин» и «мак» — намеренные ловушки на слишком короткую основу
    # («бензол»/«бензин» и «опийный мак» рядом), «кокосовое масло» — на «кока».
    for material in (
        "ветивер", "полынь", "можжевельник", "табак", "белый мускус",
        "бензоин", "мак", "макадамия", "кокосовое масло", "камфора",
        "берёзовый дёготь", "дубовый мох", "лабданум", "стиракс",
    ):
        assert is_unsafe(material) is None, material


def test_unsafe_items_are_dropped_from_selection():
    # ⚠ Через asyncio.run, а не `async def`: pytest-asyncio в проекте нет
    # и заводить его ради одного теста незачем — вся асинхронность тут
    # в одной строке.
    import asyncio

    from services.ai_schemas import AromaItem, AromaResult
    from services.aroma_safety import (
        filter_unsafe_aromas, start_unsafe_drops, take_unsafe_drops,
    )

    start_unsafe_drops()
    results = {
        "Claude": AromaResult(
            items=[
                AromaItem(material="ветивер", form="эфирное масло",
                          title="Сырой ветер", description="Земляной"),
                AromaItem(material="конопля", form="сухая трава",
                          title="Зелёная тяжесть зарослей", description="Травяной"),
            ],
            explanation="x",
        )
    }
    asyncio.run(filter_unsafe_aromas(results, book_id=1, title="Книга"))

    kept = [i.material for i in results["Claude"].items]
    assert kept == ["ветивер"]          # безопасное осталось, подборка жива
    dropped = take_unsafe_drops()
    # ⚠ В событие пишем НАЗВАНИЕ и сработавшую основу, а не только счётчик:
    # иначе «модель лезет в запрещённое» и «фильтр режет нормальное»
    # неразличимы — пункта просто нет на экране.
    assert len(dropped) == 1 and "конопля" in dropped[0]
