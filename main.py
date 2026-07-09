from fastapi import FastAPI

from database import create_db_and_tables
from books import router   # импорт роутера подтягивает модели → они регистрируются

app = FastAPI()
app.include_router(router)   # подключаем эндпоинты из books.py
create_db_and_tables()       # модели уже известны — создаём таблицы