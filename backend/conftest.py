# Общая обвязка тестов: клиент с in-memory базой + фейки внешних сервисов.
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

import database
from models import Book, User, UserBook
from main import app
from services.ai import (
    AromaResult,
    AtmosphereItem,
    DesignResult,
    FoodResult,
    MusicResult,
    Palette,
    Song,
)


@pytest.fixture(name="client")
def client_fixture():
    # Своя база в памяти — реальную library.db тесты не трогают.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    database.engine = test_engine            # подменяем движок, которым пользуются эндпоинты

    with Session(test_engine) as session:
        # пользователь-админ (id=1) + книга (id=1) на его полке — как после миграции
        session.add(User(id=1, display_name="Test", is_admin=True))
        session.add(Book(id=1, title="Test", author="Author"))
        session.commit()
        session.add(UserBook(user_id=1, book_id=1, status="want"))
        session.commit()

    yield TestClient(app)


# --- Фейки внешних сервисов (без сети и без токенов) ---

async def fake_generate_music(title, author, lang="ru"):
    """Мгновенный «AI»: две подборки с разным содержимым."""
    return {
        "Claude": MusicResult(
            songs=[Song(title="Song A", artist="Artist A")],
            explanation="Claude explanation",
        ),
        "ChatGPT": MusicResult(
            songs=[Song(title="Song B", artist="Artist B")],
            explanation="ChatGPT explanation",
        ),
    }


async def fake_generate_design(title, author, lang="ru"):
    """Мгновенный «паспорт оформления» — уже в контракте {источник: модель}."""
    return {
        "Claude": DesignResult(
            base_mood="ночная тишина",
            palette_dark=Palette(
                bg="#161311", surface="#221c17", accent="#e08b2d",
                text="#e9e1d3", muted="#a19585",
            ),
            palette_light=Palette(
                bg="#f6f1e7", surface="#fffaf0", accent="#b05e12",
                text="#2a241d", muted="#6d655b",
            ),
            title_font="PT Serif",
            body_font="PT Serif",
            statement="Тестовое пояснение",
            symbol_svg='<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>',
        )
    }


@pytest.fixture(autouse=True)
def _no_basic_auth(monkeypatch):
    """Basic Auth (план деплоя п.1.1) включается переменными окружения.
    Если они остались в терминале после локальной проверки прода, весь прогон
    упирался бы в 401 — снимаем их для тестов. test_auth.py выставляет свои
    значения уже поверх этого."""
    monkeypatch.delenv("BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Счётчики лимитера (план деплоя п.1.3) живут в памяти процесса и общие
    для всех тестов — без сброса длинный прогон упёрся бы в лимит AI-вызовов."""
    import rate_limit

    rate_limit.reset()


@pytest.fixture(autouse=True)
def _no_track_verification(monkeypatch):
    """С 20.07 музыка перед сохранением проверяется в Spotify (verify_songs).
    В тестах это означало бы реальные запросы (в .env есть рабочие ключи) —
    подменяем на «всё существует». Проверка тестируется отдельно
    в test_spotify.py на моках."""
    import services.atmosphere as atmosphere_service

    async def passthrough(results):
        return results

    monkeypatch.setattr(
        atmosphere_service, "verify_songs", lambda songs: (songs, [])
    )
    # постобработка музыки ходит в Spotify — в тестах пропускаем целиком
    monkeypatch.setitem(
        atmosphere_service.CATEGORIES["music"], "postprocess", passthrough
    )
    from routers import atmosphere as atmosphere_router

    monkeypatch.setitem(
        atmosphere_router.CATEGORIES["music"], "postprocess", passthrough
    )


@pytest.fixture(autouse=True)
def _fake_design_generation(monkeypatch):
    """Задача 57: add_book фоном генерирует оформление, а TestClient выполняет
    фоновые задачи синхронно — без этого фейка любой POST /books ушёл бы
    в реальный Claude. Отдельные тесты могут переопределить своим monkeypatch."""
    from routers import atmosphere
    monkeypatch.setitem(
        atmosphere.CATEGORIES["design"], "generate", fake_generate_design
    )


def fake_book_info(title, author, lang="ru", isbn=None):
    """Мгновенный «Google Books» для обогащения."""
    return {
        "cover_url": "http://example.com/c.jpg",
        "description": "desc",
        "page_count": 100,
        "categories": None,
        "published_year": 2000,
        "language": "ru",
        "external_rating": None,
        "raw_metadata": "{}",
    }


def fake_search_books(query, max_results=8):
    """Мгновенный «Google Books» для поиска — два кандидата."""
    return [
        {"title": "Мастер и Маргарита", "author": "Булгаков",
         "cover_url": "http://x/cover.jpg", "external_id": "ext1"},
        {"title": "Собачье сердце", "author": "Булгаков",
         "cover_url": None, "external_id": "ext2"},
    ]
async def fake_generate_food(title, author, lang="ru"):
    return {
        "Claude": FoodResult(
            items=[AtmosphereItem(title="Глинтвейн", description="Тёплый и пряный")],
            explanation="Claude food",
        ),
        "ChatGPT": FoodResult(
            items=[AtmosphereItem(title="Тыквенный суп", description="Осенний")],
            explanation="ChatGPT food",
        ),
    }


async def fake_generate_aroma(title, author, lang="ru"):
    return {
        "Claude": AromaResult(
            items=[AtmosphereItem(title="Сандал", description="Дымный, тёплый")],
            explanation="Claude aroma",
        ),
        "ChatGPT": AromaResult(
            items=[AtmosphereItem(title="Кедр", description="Хвойный")],
            explanation="ChatGPT aroma",
        ),
    }