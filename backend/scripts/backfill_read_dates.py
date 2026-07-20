# Разовый бэкфилл дат прочтения из CSV LiveLib в БД (задача: даты не подтянулись
# при импорте). Обновляет UserBook.read_at у уже добавленных книг — то, что
# обычный импорт не делает (он пропускает дубли).
#
# Запуск из backend/:
#   python backfill_read_dates.py путь/к/livelib.csv
#   (по умолчанию ищет livelib-read.csv рядом со скриптом)
#
# Перед запуском сделай бэкап: python backup_db.py
# CSV LiveLib — разделитель ';', колонки: Название;Автор;Дата прочтения;Моя оценка;ISBN
import csv
import sqlite3
import sys
from pathlib import Path

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
from dates import parse_read_date

BACKEND = Path(__file__).resolve().parent.parent
DB = BACKEND / "library.db"
USER_ID = 1


def norm_isbn(value):
    """Первый ISBN из списка, без дефисов и пробелов."""
    if not value:
        return None
    return value.split(",")[0].replace("-", "").replace(" ", "").strip() or None


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND / "livelib-read.csv"
    if not csv_path.exists():
        print(f"CSV не найден: {csv_path}")
        print("Укажи путь: python backfill_read_dates.py путь/к/файлу.csv")
        return

    con = sqlite3.connect(DB)
    # Каталог книг: ключ → book_id. Сравнение по-питоновски (SQLite lower()
    # кириллицу не понижает).
    books = con.execute("SELECT id, title, author, isbn FROM book").fetchall()
    by_isbn = {norm_isbn(isbn): bid for bid, _, _, isbn in books if isbn}
    by_key = {
        (t.strip().lower(), a.strip().lower()): bid for bid, t, a, _ in books
    }

    updated = 0
    no_date = 0
    unmatched = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")   # LiveLib: разделитель ';'
        for row in reader:
            title = (row.get("Название") or "").strip()
            author = (row.get("Автор") or "").strip()
            if not title:
                continue
            isbn = norm_isbn(row.get("ISBN"))
            book_id = (isbn and by_isbn.get(isbn)) or by_key.get(
                (title.lower(), author.lower())
            )
            if not book_id:
                unmatched.append(f"{title} — {author}")
                continue

            read_at = parse_read_date((row.get("Дата прочтения") or "").strip())
            if read_at is None:
                no_date += 1
                continue

            cur = con.execute(
                "UPDATE userbook SET read_at = ?, status = 'read' "
                "WHERE user_id = ? AND book_id = ?",
                (read_at.isoformat(sep=" "), USER_ID, book_id),
            )
            updated += cur.rowcount

    con.commit()
    con.close()

    print(f"Обновлено дат: {updated}")
    print(f"Строк без распознанной даты: {no_date}")
    print(f"Не нашлось в базе: {len(unmatched)}")
    for u in unmatched[:20]:
        print("   ·", u)
    if len(unmatched) > 20:
        print(f"   … и ещё {len(unmatched) - 20}")


if __name__ == "__main__":
    main()
