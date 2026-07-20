import base64
import logging
import os
import secrets
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

import database
import rate_limit
from i18n import msg
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


# --- Basic Auth для внешнего теста (задача 81, план деплоя п.1.1) ---
# Один общий логин/пароль до настоящей авторизации (з.31). Включается, только
# если заданы ОБЕ переменные окружения BASIC_AUTH_USER / BASIC_AUTH_PASSWORD —
# локальная разработка и тесты работают без пароля как раньше.
# /health открыт для мониторинга хостинга. Spotify /callback под паролем:
# браузер сам приложит сохранённые учётные данные при редиректе.
# Читаем env на каждый запрос (а не при импорте): дёшево и тестируемо.

def _basic_auth_ok(header: str | None, user: str, password: str) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
    except Exception:
        return False
    got_user, _, got_password = decoded.partition(":")
    # compare_digest: сравнение за постоянное время (не течёт длина совпадения)
    return secrets.compare_digest(got_user, user) and secrets.compare_digest(
        got_password, password
    )


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    user = os.getenv("BASIC_AUTH_USER")
    password = os.getenv("BASIC_AUTH_PASSWORD")
    if not (user and password) or request.url.path == "/health":
        return await call_next(request)
    if _basic_auth_ok(request.headers.get("Authorization"), user, password):
        return await call_next(request)
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="nocturne"'},
    )


# --- Лимиты частоты на дорогие эндпоинты (задача 39, план деплоя п.1.3) ---
# Правила и настройка — в rate_limit.py. Зарегистрирован ПОСЛЕ basic_auth,
# то есть оборачивает его: лимит считается и для запросов без пароля.
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limit.check(
        request.method, request.url.path, client_ip
    )
    if not allowed:
        log.warning(
            "rate limited",
            extra={"method": request.method, "path": request.url.path, "status": 429},
        )
        return JSONResponse(
            status_code=429,
            content={"detail": msg("rate_limited", "ru")},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


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


# --- Security-заголовки (задача 40, план деплоя п.1.3) ---
# Регистрируется ПОСЛЕДНИМ, то есть оборачивает все остальные middleware:
# заголовки попадают и на 401 (нет пароля), и на 429 (лимит).
# CSP: свои скрипты/стили + шрифты Google + обложки книг (любой https) + data:
# для символов-экслибрисов (SVG рендерится через <img data:>).
# ⚠ Появится Spotify-embed (з.29б) — добавить frame-src https://open.spotify.com.
CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": CSP,
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # /docs и /redoc грузят свои скрипты с CDN — на них CSP не вешаем
    skip_csp = request.url.path in ("/docs", "/redoc") or request.url.path.startswith(
        "/openapi"
    )
    for name, value in SECURITY_HEADERS.items():
        if name == "Content-Security-Policy" and skip_csp:
            continue
        response.headers.setdefault(name, value)
    return response


# --- Раздача собранного фронтенда (задача 81, план деплоя п.1.2) ---
# На проде FastAPI отдаёт и API, и статику из frontend/dist — один origin,
# без CORS. Локально папки dist может не быть (фронт живёт на Vite :5173) —
# тогда отвечаем обычным 404.
# Catch-all объявлен ПОСЛЕ всех роутеров: /api/v1/*, /health и /callback
# матчатся первыми. include_in_schema=False — снимок OpenAPI не меняется.
# Наличие dist проверяем В ЗАПРОСЕ, а не при импорте: иначе сервер, поднятый
# до `npm run build`, отдавал бы 404 до перезапуска.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
async def spa(full_path: str):
    """Файл существует — отдаём его; иначе index.html (SPA-fallback:
    прямые ссылки /books/5, /stats и F5 работают, роутит react-router)."""
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Not Found")

    file = (FRONTEND_DIST / full_path).resolve()
    # защита от ../: отдаём только файлы внутри dist
    if full_path and file.is_file() and file.is_relative_to(FRONTEND_DIST):
        response = FileResponse(file)
        if full_path.startswith("assets/"):
            # у Vite имена ассетов с хэшем — можно кэшировать намертво
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    response = FileResponse(index)
    response.headers["Cache-Control"] = "no-cache"   # свежий index после деплоя
    return response
