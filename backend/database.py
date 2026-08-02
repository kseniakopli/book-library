import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent


def anchor_sqlite_path(url: str) -> str:
    """Относительный путь к SQLite-файлу — от папки `backend/`, а не от cwd.

    Задача 105. `sqlite:///library.db` — путь относительно ТЕКУЩЕЙ папки,
    поэтому скрипт, запущенный из `backend/scripts/`, открывал не рабочую базу,
    а создавал рядом с собой новую пустую — и бодро печатал «0 записей» вместо
    того, чтобы упасть. Так пустая база попала даже в Docker-образ (найдено
    02.08 в `fly ssh`). Разведочный скрипт, отвечающий «данных нет», когда
    данные есть, — худший вид поломки: по нему принимают решения.

    Лечим не проверкой, а устранением самой возможности: куда бы ни указывал
    cwd, относительный путь ведёт в `backend/`.

    Не трогаем: абсолютные пути (на проде `sqlite:////data/library.db` —
    четыре слэша), `:memory:` в тестах и любые не-SQLite DSN (Postgres, з.33).
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    tail = url[len(prefix):]
    if not tail or tail.startswith(":memory:"):
        return url
    if _is_absolute_anywhere(tail):
        return url
    return prefix + (BACKEND_DIR / tail).as_posix()


# ⚠ НЕ `Path(...).is_absolute()`: результат зависит от платформы, а строка
# у нас одна на всех. На Windows `/data/library.db` абсолютным НЕ считается
# (нет буквы диска) — и прод-путь `sqlite:////data/library.db`, где лежит
# volume, локально переписывался в `sqlite:///C:/data/library.db`.
# Поймано тестом 02.08. Разработка на Windows, прод на Linux — платформенная
# семантика в общем коде обязана быть явной.
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def _is_absolute_anywhere(path: str) -> bool:
    """Абсолютный ли путь по правилам ЛЮБОЙ из платформ: POSIX (`/data/...`)
    или Windows (`C:/...`, `C:\\...`)."""
    return path.startswith("/") or bool(_WINDOWS_DRIVE.match(path))


# DSN из окружения — задел под Postgres (задача 33): чтобы переехать, достаточно
# положить в backend/.env строку вида
#   DATABASE_URL=postgresql+psycopg://user:password@localhost/nocturne
# и прогнать `alembic upgrade head`. По умолчанию — прежний SQLite-файл.
DATABASE_URL = anchor_sqlite_path(os.getenv("DATABASE_URL", "sqlite:///library.db"))

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
