from fastapi import FastAPI

from routers import atmosphere, books, imports, search, spotify

app = FastAPI(
    title="Nocturne API",
    description="Персональная библиотека для атмосферных литературных вечеров. "
    "Интерактивная документация: /docs (Swagger) и /redoc.",
)

# Задача 34: всё API — под версионированным префиксом
API_V1 = "/api/v1"
app.include_router(books.router, prefix=API_V1)       # CRUD книг + ручной enrich
app.include_router(atmosphere.router, prefix=API_V1)  # AI-атмосфера
app.include_router(search.router, prefix=API_V1)      # поиск: каталог + Google Books
app.include_router(imports.router, prefix=API_V1)     # импорт CSV и backfill
app.include_router(spotify.router, prefix=API_V1)     # плейлисты и QR
# /callback — без префикса: адрес зарегистрирован в кабинете Spotify
app.include_router(spotify.callback_router)

# Схему базы ведёт Alembic (папка alembic/, команда: alembic upgrade head).
# create_all остался только в тестах — там база одноразовая, in-memory.
