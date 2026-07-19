# Починка обложек OpenLibrary (19.07).
#
# Проблема: covers.openlibrary.org на несуществующую обложку отдаёт не 404,
# а ПУСТУЮ картинку-заглушку с кодом 200. Браузер считает её загруженной,
# onError не срабатывает — и вместо «Нет обложки» получается пустой серый
# прямоугольник.
#
# Решение: параметр ?default=false заставляет OpenLibrary отвечать 404,
# когда обложки нет. Тогда фронт ловит onError и честно рисует заглушку,
# а реально существующие обложки продолжают работать.
#
# Запуск из backend/:  python fix_openlibrary_covers.py
# Идемпотентно: повторный запуск ничего не сломает.
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "library.db"
MARK = "default=false"


def main():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT id, cover_url FROM book "
        "WHERE cover_url LIKE 'https://covers.openlibrary.org/%'"
    ).fetchall()

    updated = 0
    for book_id, url in rows:
        if MARK in url:
            continue                      # уже поправлено
        sep = "&" if "?" in url else "?"
        con.execute(
            "UPDATE book SET cover_url = ? WHERE id = ?", (f"{url}{sep}{MARK}", book_id)
        )
        updated += 1

    con.commit()
    con.close()
    print(f"Обложек OpenLibrary: {len(rows)}, поправлено: {updated}")
    print("Существующие обложки продолжат грузиться; отсутствующие теперь дадут 404 →")
    print("на полке вместо пустого прямоугольника будет «Нет обложки».")


if __name__ == "__main__":
    main()
