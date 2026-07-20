import logging
import os
import time
import uuid

from fastapi import FastAPI, Request
from sqlalchemy import text

import database
from logging_setup import request_id_var, setup_logging
from routers import (
    atmosphere,
    books,
    imports,
    recommendations,
    search,
    spotify,
    stats,
)

setup_logging()
log = logging.getLogger("nocturne")

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


# --- Задача 71: fail-fast проверка ключей на старте ---
# Без неё отсутствие ключа всплывает только при первом AI-вызове/поиске —
# невнятной ошибкой глубоко в стеке. Лучше упасть сразу и сказать, чего не хватает.
# SPOTIFY_* не проверяем: плейлисты — необязательная фича, без ключей просто
# не работает кнопка. Обход проверки (если нужно поднять API без AI):
# SKIP_KEY_CHECK=1.
REQUIRED_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_BOOKS_API_KEY")


@app.on_event("startup")
def check_api_keys():
    if os.getenv("SKIP_KEY_CHECK") == "1":
        return
    missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Не заданы API-ключи: {', '.join(missing)}. "
            "Заполните backend/.env (или SKIP_KEY_CHECK=1, чтобы поднять без AI)."
        )


# --- Задача 71: request id + структурный access-лог ---
# Каждому запросу — короткий id: он в JSON-логах (через contextvar даже
# в записях из глубины кода) и в заголовке ответа X-Request-ID, чтобы
# сопоставить жалобу «не сработало» с конкретными строками лога.
@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    token = request_id_var.set(rid)
    start = time.perf_counter()
    status = 500  # если call_next бросил исключение — логируем как 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000),
            },
        )
        request_id_var.reset(token)


# Задача 55: инфраструктурный эндпоинт (вне /api/v1) — «жив ли сервис и БД».
# Пригодится супервизору/докеру при публикации; 500 = БД недоступна.
@app.get("/health", tags=["infra"])
def health():
    with database.engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
