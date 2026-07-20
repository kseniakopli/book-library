# Бэкап SQLite-базы перед миграцией/операциями (задача 61 из аудита).
# Запуск из backend/:  python backup_db.py
# Кладёт копию в backend/backups/library-YYYYmmdd-HHMMSS.db и чистит старые,
# оставляя 10 последних. Использует sqlite backup API — консистентно даже при
# запущенном сервере (в отличие от простого копирования файла в WAL-режиме).
import sqlite3
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DB = BACKEND / "library.db"
BACKUP_DIR = BACKEND / "backups"
KEEP = 10


def main():
    if not DB.exists():
        print(f"База не найдена: {DB}")
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"library-{stamp}.db"

    src = sqlite3.connect(DB)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)          # консистентный снимок, учитывает WAL
    dst.close()
    src.close()

    # ротация: оставляем KEEP последних
    backups = sorted(BACKUP_DIR.glob("library-*.db"))
    for old in backups[:-KEEP]:
        old.unlink()

    print(f"Бэкап готов: {dest}  ({dest.stat().st_size // 1024} КБ)")
    print(f"Всего копий: {len(backups[-KEEP:])} (храним {KEEP} последних)")


if __name__ == "__main__":
    main()
