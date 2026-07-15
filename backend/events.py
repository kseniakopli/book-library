from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Session

import database


# --- Событийный лог: append-only запись действий для будущей статистики ---
class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(index=True)            # book_added / status_changed / rated / enriched / ...
    book_id: Optional[int] = Field(default=None, index=True)
    detail: str = ""                          # доп. данные (короткий текст или JSON-строка)
    created_at: datetime = Field(default_factory=datetime.now)


def log_event(type: str, book_id: Optional[int] = None, detail: str = "") -> None:
    """Пишем событие в лог отдельной короткой сессией.
    Логирование не должно ронять основную операцию — ошибки глушим."""
    try:
        with Session(database.engine) as session:
            session.add(Event(type=type, book_id=book_id, detail=detail))
            session.commit()
    except Exception as e:
        print("Не удалось записать событие:", e)
