import os
import sqlite3

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

load_dotenv()

# DSN из окружения — задел под Postgres (задача 33): чтобы переехать, достаточно
# положить в backend/.env строку вида
#   DATABASE_URL=postgresql+psycopg://user:password@localhost/nocturne
# и прогнать `alembic upgrade head`. По умолчанию — прежний SQLite-файл.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///library.db")

engine = create_engine(DATABASE_URL)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    """Настройки для SQLite-соединений (проверяем тип соединения, а не URL,
    чтобы это работало и для in-memory движка в тестах):
    - foreign_keys=ON — иначе SQLite не проверяет FK и не каскадит удаления;
    - journal_mode=WAL — читатели не блокируют писателя (фоновое обогащение
      и запросы UI работают параллельно без 'database is locked').
    Для Postgres не выполняется и не нужно."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def create_db_and_tables() -> None:
    """Создаёт таблицы для всех известных моделей.
    Используется ТОЛЬКО в тестах (одноразовая in-memory база);
    рабочую базу ведёт Alembic."""
    SQLModel.metadata.create_all(engine)
