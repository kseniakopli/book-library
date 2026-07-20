from fastapi import FastAPI
from sqlalchemy import text

import database
from routers import (
    atmosphere,
    books,
    imports,
    recommendations,
    search,
    spotify,
    stats,
)

app = FastAPI(
    title="nocturne API",
    description="Персональная библиотека для атмосферных литературных вечеров. "
    "Интерактивная документация: /docs (Swagger) и /redoc.",
)

# Задача 34: всё API — под версионированным префиксом
API_V1 = "/api/v1"
app.include_router(books.router, prefix=API_V1)       # CRUD книг + ручной enrich
app.include_router(atmosphere.router, prefix=API_V1)  # AI-атмосфера
app.include_router(search.router, prefix=API_V1)      # поиск: каталог + Google Books
app.include_router(imports.router, prefix=API_V1)     # импорт CSV и backfill
app.include_router(recommendations.router, prefix=API_V1)  # этап 8: советы книг
app.include_router(spotify.router, prefix=API_V1)     # плейлисты и QR
app.include_router(stats.router, prefix=API_V1)       # задачи 24/63: статистика
# /callback — без префикса: адрес зарегистрирован в кабинете Spotify
app.include_router(spotify.callback_router)

# Схему базы ведёт Alembic (папка alembic/, команда: alembic upgrade head).
# create_all остался только в тестах — там база одноразовая, in-memory.


# Задача 55: инфраструктурный эндпоинт (вне /api/v1) — «жив ли сервис и БД».
# Пригодится супервизору/докеру при публикации; 500 = БД недоступна.
@app.get("/health", tags=["infra"])
def health():
    with database.engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
