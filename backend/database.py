from sqlmodel import SQLModel, create_engine

# Движок БД. Другие модули берут его отсюда.
engine = create_engine("sqlite:///library.db")


def create_db_and_tables() -> None:
    """Создаёт таблицы для всех известных моделей."""
    SQLModel.metadata.create_all(engine)