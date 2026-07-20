# Разовый скрипт: заливает найденные обложки из docs/covers_found.json в БД.
# Запуск из backend/:  python apply_covers.py
# Обновляет только книги, у которых обложки до сих пор нет (безопасно повторять).
# Перед запуском можно открыть covers_found.json и удалить неподходящие записи.
import json
import sqlite3
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent.parent / "docs"
DB = Path(__file__).resolve().parent.parent / "library.db"


def main():
    found = json.loads((DOCS / "covers_found.json").read_text(encoding="utf-8"))["found"]
    con = sqlite3.connect(DB)
    updated = 0
    for item in found:
        cur = con.execute(
            "UPDATE book SET cover_url = ? "
            "WHERE id = ? AND (cover_url IS NULL OR cover_url = '')",
            (item["cover_url"], item["id"]),
        )
        updated += cur.rowcount
    con.commit()
    con.close()
    print(f"Обновлено книг: {updated} из {len(found)} в файле.")


if __name__ == "__main__":
    main()
