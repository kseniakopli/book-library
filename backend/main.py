from fastapi import FastAPI

from books import router   # импорт роутера подтягивает модели → они регистрируются

app = FastAPI()
app.include_router(router)   # подключаем эндпоинты из books.py

# Схему базы теперь ведёт Alembic (папка alembic/, команда: alembic upgrade head).
# create_all остался только в тестах (test_main.py) — там база одноразовая, in-memory.