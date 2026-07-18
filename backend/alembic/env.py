import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

# backend/ в sys.path, чтобы работали импорты database/models/events
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database          # noqa: E402 — отсюда берём URL базы
import models            # noqa: E402, F401 — импорт регистрирует таблицы в metadata
import events            # noqa: E402, F401 — таблица event

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Режим --sql: генерируем SQL без подключения к базе."""
    context.configure(
        url=str(database.engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,   # SQLite не умеет ALTER — Alembic пересоздаёт таблицы сам
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Обычный режим: применяем миграции к базе из database.py."""
    with database.engine.connect() as connection:
        # SQLite: FK-энфорсмент включён глобально (database.py: PRAGMA
        # foreign_keys=ON). На время миграции его нужно ВЫКЛЮЧИТЬ: batch-режим
        # пересоздаёт таблицу через DROP TABLE, а он при включённых FK каскадом
        # удаляет дочерние строки (aiselection, userbook). PRAGMA игнорируется
        # внутри транзакции, поэтому выполняем её в режиме AUTOCOMMIT до начала
        # миграционной транзакции. (Ревизия 0005 дополнительно проверяет это и
        # откажется выполняться, если FK всё-таки включён.)
        if connection.dialect.name == "sqlite":
            connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
