"""Структурные логи (задача 71): JSON-строки в stdout + request id.

Зачем: обычные print-строки нельзя фильтровать и агрегировать. JSON-лог
разбирается любым инструментом (jq, Loki, CloudWatch), а request_id связывает
все записи одного HTTP-запроса — при публикации это первое, что понадобится.

Использование:
    from logging_setup import setup_logging, request_id_var
    setup_logging()                      # один раз при старте (main.py)
    log = logging.getLogger("nocturne")  # обычный logging, формат уже JSON

request_id_var — contextvars.ContextVar: middleware в main.py кладёт туда id
запроса, и он автоматически попадает в каждую запись изнутри этого запроса
(включая фоновые задачи, стартованные из него).
"""

import contextvars
import json
import logging
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

# Поля, которые можно передать через logging extra={...} и они попадут в JSON
EXTRA_FIELDS = ("method", "path", "status", "duration_ms", "client")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                entry[field] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """Вешает JSON-формат на root-логгер. Идемпотентно (перезапуск reload)."""
    root = logging.getLogger()
    root.setLevel(level)
    # не плодим хендлеры при --reload: заменяем формат у существующих
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(JsonFormatter())
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
