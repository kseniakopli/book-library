"""Удаление сохранённой AI-атмосферы (чтобы сгенерировать заново).

Зачем: после переноса проверки треков в момент генерации (20.07) старые
подборки содержат выдуманные названия. Иногда проще стереть и сгенерировать
заново, чем чистить (`verify_music.py`).

Что удаляется по умолчанию: только **музыка**. Угощения и ароматы к проблеме
треков отношения не имеют, а паспорт оформления (design) трогать особенно
не стоит — он генерируется автоматически при открытии книги, то есть удаление
у 200 книг обернётся 200 запросами к Claude.

Запуск из папки backend/:
    python scripts/clear_atmosphere.py --dry-run        # посмотреть объём
    python scripts/clear_atmosphere.py                  # удалить музыку у всех
    python scripts/clear_atmosphere.py --book 42        # у одной книги
    python scripts/clear_atmosphere.py --category food  # другая категория
    python scripts/clear_atmosphere.py --all            # музыка+угощения+ароматы
    python scripts/clear_atmosphere.py --with-design    # ⚠ включая паспорта

⚠ Перед прогоном сделайте бэкап: python scripts/backup_db.py
"""

import sys

import _bootstrap  # noqa: F401 — кладёт backend/ в sys.path
from sqlmodel import Session, col, select

import database
from models import AISelection

SAFE_CATEGORIES = ["music", "food", "aroma"]


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args

    if "--with-design" in args:
        categories = SAFE_CATEGORIES + ["design"]
    elif "--all" in args:
        categories = SAFE_CATEGORIES
    elif "--category" in args:
        categories = [args[args.index("--category") + 1]]
    else:
        categories = ["music"]

    book_id = int(args[args.index("--book") + 1]) if "--book" in args else None

    with Session(database.engine) as session:
        query = select(AISelection).where(col(AISelection.category).in_(categories))
        if book_id is not None:
            query = query.where(AISelection.book_id == book_id)
        rows = session.exec(query).all()

        by_category = {}
        for row in rows:
            by_category[row.category] = by_category.get(row.category, 0) + 1

        scope = f"книга {book_id}" if book_id is not None else "все книги"
        print(f"Категории: {', '.join(categories)} | {scope}")
        for category, count in sorted(by_category.items()):
            print(f"  {category}: {count} подборок")
        print(f"Всего к удалению: {len(rows)}")

        if dry_run:
            print("Пробный прогон — ничего не удалено.")
            return
        if not rows:
            return

        if "design" in categories:
            print("⚠ Паспорта оформления будут перегенерированы при открытии книг "
                  "(это запросы к Claude).")

        for row in rows:
            session.delete(row)
        session.commit()
        print(f"Удалено: {len(rows)}. Атмосферу можно генерировать заново "
              "кнопкой на странице книги.")


if __name__ == "__main__":
    main()
