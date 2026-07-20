from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, Session

import database


# --- Событийный лог: append-only запись действий для будущей статистики ---
class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(index=True)            # book_added / status_changed / rated / enriched / ...
    book_id: Optional[int] = Field(default=None, index=True)
    # Задача 80: detail — структура (JSON), а не строка: по ней можно считать.
    # У AI-событий внутри ai_calls: [{provider, latency_ms, input_tokens, output_tokens}].
    # В SQLite колонка физически TEXT — SQLAlchemy сериализует сам (миграция 0007).
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)


def log_event(type: str, book_id: Optional[int] = None, detail: dict | None = None) -> None:
    """Пишем событие в лог отдельной короткой сессией.
    Логирование не должно ронять основную операцию — ошибки глушим."""
    try:
        with Session(database.engine) as session:
            session.add(Event(type=type, book_id=book_id, detail=detail or {}))
            session.commit()
    except Exception as e:
        print("Не удалось записать событие:", e)
