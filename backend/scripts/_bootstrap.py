"""Кладёт папку backend/ в sys.path — чтобы скрипты из scripts/ могли делать
`import database`, `from models import Book` и т.д.

Подключается первой строкой среди импортов:
    import _bootstrap  # noqa: F401 — backend/ в sys.path

Работает при запуске из папки backend/:  python scripts/backup_db.py
(каталог скрипта Python сам кладёт в sys.path, поэтому модуль и находится).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
