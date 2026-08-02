"""Кладёт папку backend/ в sys.path — чтобы скрипты из scripts/ могли делать
`import database`, `from models import Book` и т.д.

Подключается первой строкой среди импортов:
    import _bootstrap  # noqa: F401 — backend/ в sys.path

Работает при запуске из папки backend/:  python scripts/backup_db.py
(каталог скрипта Python сам кладёт в sys.path, поэтому модуль и находится).

⚠ Задача 105. Раньше запуск из другой папки был опасен молча: относительный
`DATABASE_URL` разрешался от текущей папки, скрипт открывал НЕ рабочую базу
(или создавал рядом пустую) и печатал «0 записей» вместо ошибки. Теперь путь
привязан к `backend/` в `database.anchor_sqlite_path`, поэтому cwd больше
ни на что не влияет. Предупреждение ниже — на случай, когда базы всё-таки нет:
лучше сказать об этом сразу, чем показать пустой отчёт.
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _warn_if_no_database() -> None:
    """Сказать вслух, если файла базы нет. Не падаем: пустая база — законное
    состояние на чистой установке до `alembic upgrade head`."""
    import database  # импортируется здесь: sys.path настроен строкой выше

    url = database.DATABASE_URL
    if not url.startswith("sqlite:///"):
        return
    path = Path(url[len("sqlite:///"):])
    if path.name == ":memory:" or path.exists():
        return
    print(
        f"⚠ Файла базы нет: {path}\n"
        f"  Скрипт отработает на ПУСТОЙ базе — цифры в отчёте ничего не значат.\n"
        f"  Если база должна быть: проверь DATABASE_URL в backend/.env "
        f"или прогони `alembic upgrade head`.",
        file=sys.stderr,
    )


_warn_if_no_database()
