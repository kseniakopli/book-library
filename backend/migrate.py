import sqlite3

# Одноразовая миграция: добавляем новые колонки в таблицу book,
# не теряя уже сохранённые данные.
NEW_COLUMNS = {
    "page_count": "INTEGER",
    "categories": "TEXT",
    "published_year": "INTEGER",
    "language": "TEXT",
    "external_rating": "REAL",
    "raw_metadata": "TEXT",
}

conn = sqlite3.connect("library.db")
existing = {row[1] for row in conn.execute("PRAGMA table_info(book)")}
for name, sql_type in NEW_COLUMNS.items():
    if name not in existing:
        conn.execute(f"ALTER TABLE book ADD COLUMN {name} {sql_type}")
        print(f"добавлена колонка: {name}")
conn.commit()
conn.close()
print("миграция завершена")