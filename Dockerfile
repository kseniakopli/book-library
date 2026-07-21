# Образ nocturne: один контейнер отдаёт и API, и собранный фронтенд (з.81).
#
# Этап 1 собирает React (нужен только node), этап 2 — рантайм на Python.
# Так node и node_modules (сотни мегабайт) в финальный образ не попадают.

# --- Этап 1: сборка фронтенда ---
FROM node:20-slim AS frontend
WORKDIR /app/frontend
# сначала манифесты — слой с npm ci переиспользуется, пока зависимости не менялись
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # → /app/frontend/dist

# --- Этап 2: рантайм ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# libcairo2 нужен pycairo (обложки плейлистов) — на Linux колёс нет,
# пакет собирается из исходников
RUN apt-get update \
    && apt-get install -y --no-install-recommends libcairo2-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-cover.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -r backend/requirements-cover.txt

COPY backend/ ./backend/
# main.py ищет фронтенд в ../frontend/dist относительно backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
# start.sh: alembic upgrade head, затем uvicorn (см. комментарий внутри —
# миграции нельзя гонять в release_command Fly, там нет volume).
# chmod: файл мог приехать из Windows без флага исполнения.
RUN chmod +x start.sh
EXPOSE 8080
CMD ["./start.sh"]
