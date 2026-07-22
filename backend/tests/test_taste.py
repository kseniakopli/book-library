# Обратная петля фидбека (задача 26, часть 4): 👍/👎 попадают в промпты.
# У API моделей нет памяти — «профиль вкуса» строим сами и подкладываем.
import json

from sqlmodel import Session

import database
from models import AISelection
from services.taste import atmosphere_taste, disliked_recommendations


def _add_music_selection(book_id=1, source="Claude"):
    with Session(database.engine) as session:
        session.add(AISelection(
            book_id=book_id, category="music", source=source,
            payload=json.dumps([{"title": "Sudno", "artist": "Molchat Doma"}]),
        ))
        session.commit()


def test_atmosphere_taste_collects_likes_and_dislikes(client):
    _add_music_selection(source="Claude")
    _add_music_selection(source="ChatGPT")

    client.post("/api/v1/feedback", json={
        "ref": "atmosphere:1:music:Claude", "verdict": "up", "source": "Claude",
    })
    client.post("/api/v1/feedback", json={
        "ref": "atmosphere:1:music:ChatGPT", "verdict": "down", "source": "ChatGPT",
    })

    with Session(database.engine) as session:
        taste = atmosphere_taste(session, 1, "music")
    assert "Molchat Doma — Sudno" in taste["liked"]
    assert "Molchat Doma — Sudno" in taste["disliked"]


def test_atmosphere_taste_empty_without_feedback(client):
    with Session(database.engine) as session:
        assert atmosphere_taste(session, 1, "music") == {}


def test_orphaned_feedback_ignored(client):
    """Подборку перегенерировали — оценка осиротела, не должна ломать сбор."""
    client.post("/api/v1/feedback", json={
        "ref": "atmosphere:999:music:Claude", "verdict": "up", "source": "Claude",
    })
    with Session(database.engine) as session:
        taste = atmosphere_taste(session, 1, "music")
    assert taste == {"liked": [], "disliked": []}


def test_disliked_recommendations(client):
    client.post("/api/v1/feedback", json={
        "ref": "recommendation:тень ветра|карлос руис сафон",
        "verdict": "down", "source": "Claude",
    })
    client.post("/api/v1/feedback", json={
        "ref": "recommendation:имя розы|умберто эко",
        "verdict": "up", "source": "ChatGPT",   # 👍 в список не идёт
    })
    with Session(database.engine) as session:
        books = disliked_recommendations(session, 1)
    assert books == ["тень ветра — карлос руис сафон"]


def test_taste_reaches_atmosphere_context(client):
    """Профиль вкуса попадает в контекст, который уходит в промпт."""
    from services.atmosphere import build_book_context

    _add_music_selection(source="Claude")
    client.post("/api/v1/feedback", json={
        "ref": "atmosphere:1:music:Claude", "verdict": "up", "source": "Claude",
    })
    with Session(database.engine) as session:
        context = build_book_context(session, 1, "music")
    assert "Molchat Doma — Sudno" in context["liked"]
