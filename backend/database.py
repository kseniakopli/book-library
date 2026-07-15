from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

# Движок БД. Другие модули берут его отсюда.
engine = create_engine("sqlite:///library.db")


@event.listens_for(Engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    """SQLite: включаем проверку внешних ключей для каждого соединения."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()    

def create_db_and_tables() -> None:
    """Создаёт таблицы для всех известных моделей."""
    SQLModel.metadata.create_all(engine)