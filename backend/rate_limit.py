"""Ограничение частоты дорогих запросов (задача 39, план деплоя п.1.3).

Зачем: общий пароль пускает всех тестеров разом, а генерация атмосферы — это
реальные токены. Лимит не даёт увлечённому тестеру (или случайному циклу
в браузере) потратить месячный бюджет за вечер.

Почему свой, а не slowapi: нужен один простой счётчик в памяти, без Redis
и новой зависимости. Инстанс на проде один (SQLite на диске), так что
общего хранилища не требуется. При переезде на несколько инстансов
это место придётся заменить на Redis — здесь и заменим.

Счётчик — скользящее окно: помним времена последних запросов по ключу
(IP + «корзина») и считаем те, что попали в окно.
"""

import os
import time
from collections import defaultdict, deque

# (метод, префикс пути) -> (корзина, лимит по умолчанию, окно в секундах)
# Только дорогое: обычный CRUD и чтение не лимитируем.
RULES = (
    ("POST", "/api/v1/books/{id}/atmosphere", "ai", 20, 3600),
    ("POST", "/api/v1/recommendations", "ai", 20, 3600),
    ("POST", "/api/v1/stats/insights", "ai", 20, 3600),
    ("POST", "/api/v1/books/{id}/playlist", "ai", 20, 3600),
    ("POST", "/api/v1/import", "import", 10, 3600),
)

# Общий для всех «дорогих» корзин лимит можно переопределить переменными:
#   RATE_LIMIT_AI=20     — сколько AI-генераций в час с одного IP
#   RATE_LIMIT_IMPORT=10 — сколько импортов в час
# 0 = выключить лимит (например, локально).
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def _limit_for(bucket: str, default: int) -> int:
    raw = os.getenv(f"RATE_LIMIT_{bucket.upper()}")
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _matches(method: str, path: str, rule_method: str, rule_path: str) -> bool:
    if method != rule_method:
        return False
    if "{id}" not in rule_path:
        return path == rule_path
    # /api/v1/books/{id}/atmosphere/music → сравниваем начало и хвост
    head, _, tail = rule_path.partition("{id}")
    return path.startswith(head) and tail.strip("/") in path


def check(method: str, path: str, client_ip: str) -> tuple[bool, int]:
    """Разрешён ли запрос. Возвращает (можно, через_сколько_секунд_повторить)."""
    for rule_method, rule_path, bucket, default, window in RULES:
        if not _matches(method, path, rule_method, rule_path):
            continue
        limit = _limit_for(bucket, default)
        if limit <= 0:                       # лимит отключён
            return True, 0
        now = time.monotonic()
        marks = _hits[(client_ip, bucket)]
        while marks and now - marks[0] > window:   # выкидываем вышедшее из окна
            marks.popleft()
        if len(marks) >= limit:
            return False, int(window - (now - marks[0])) + 1
        marks.append(now)
        return True, 0
    return True, 0


def reset() -> None:
    """Очистить счётчики (используется тестами)."""
    _hits.clear()
