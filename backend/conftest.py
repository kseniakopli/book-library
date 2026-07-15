# Общая обвязка тестов: клиент с in-memory базой + фейки внешних сервисов.
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

import database
from models import Book
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
        session.add(Book(title="Test", author="Author", status="want"))
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
            palette=Palette(
                bg="#161311", surface="#221c17", accent="#e08b2d",
                text="#e9e1d3", muted="#a19585",
            ),
            title_font="PT Serif",
            body_font="PT Serif",
            statement="Тестовое пояснение",
            symbol_svg='<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>',
        )
    }


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