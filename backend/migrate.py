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

# --- Миграция 2: пересоздаём aiselection с ON DELETE CASCADE ---
conn = sqlite3.connect("library.db")
fk_sql = conn.execute(
    "SELECT sql FROM sqlite_master WHERE name='aiselection'"
).fetchone()[0]
if "ON DELETE CASCADE" not in fk_sql:
    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN;
        CREATE TABLE aiselection_new (
            id INTEGER PRIMARY KEY,
            book_id INTEGER NOT NULL REFERENCES book(id) ON DELETE CASCADE,
            category VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            payload VARCHAR NOT NULL,
            explanation VARCHAR NOT NULL,
            created_at DATETIME NOT NULL
        );
        INSERT INTO aiselection_new SELECT * FROM aiselection;
        DROP TABLE aiselection;
        ALTER TABLE aiselection_new RENAME TO aiselection;
        CREATE INDEX ix_aiselection_book_id ON aiselection(book_id);
        COMMIT;
        PRAGMA foreign_keys=ON;
    """)
    print("aiselection пересоздана с ON DELETE CASCADE")
else:
    print("aiselection уже с каскадом")
conn.close()