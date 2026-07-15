from fastapi import FastAPI

from routers import atmosphere, books, imports, search

app = FastAPI(
    title="Nocturne API",
    description="Персональная библиотека для атмосферных литературных вечеров. "
    "Интерактивная документация: /docs (Swagger) и /redoc.",
)

app.include_router(books.router)       # CRUD книг + ручной enrich
app.include_router(atmosphere.router)  # AI-атмосфера: /books/{id}/atmosphere/{category}
app.include_router(search.router)      # поиск: локальный каталог + Google Books
app.include_router(imports.router)     # импорт CSV и backfill-операции

# Схему базы ведёт Alembic (папка alembic/, команда: alembic upgrade head).
# create_all остался только в тестах — там база одноразовая, in-memory.
