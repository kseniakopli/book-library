# Data model

Schema is owned by Alembic (`backend/alembic/`). Current revision: `0001_initial_schema`.

```mermaid
erDiagram
    BOOK ||--o{ AISELECTION : "has (CASCADE on delete)"
    BOOK {
        int id PK
        int user_id "always 1 for now (future multi-user)"
        string title
        string author
        string cover_url "https only from clients"
        string description
        string status "want | reading | read"
        int rating "1..10, only when status=read"
        datetime created_at
        int page_count
        string categories "JSON array as string"
        int published_year
        string language
        float external_rating
        string raw_metadata "full Google volumeInfo; never exposed via API"
        string isbn
        string enrich_status "pending | ready | failed"
    }
    AISELECTION {
        int id PK
        int book_id FK "ON DELETE CASCADE, indexed"
        string category "music | design (stage 7: food, aroma)"
        string source "Claude | ChatGPT"
        string payload "JSON string: songs list / design passport"
        string explanation
        datetime created_at
    }
    CATALOG {
        int id PK
        string title "indexed"
        string author "indexed"
        string cover_url
        string source "google"
        string external_id "Google volume id"
        datetime created_at "TTL 30 days for search cache"
    }
    EVENT {
        int id PK
        string type "indexed; see constants.py EVENT_*"
        int book_id "nullable, indexed, no FK (log survives deletion)"
        string detail
        datetime created_at
    }
```

## Invariants

Enforced in code and/or schema:

1. **Rating only for `read`** — PATCH rejects rating otherwise; leaving `read` clears the
   rating (routers/books.py). Not yet a DB CHECK (backlog #7).
2. **One selection per (book, category, source)** — DB unique constraint
   `uq_aiselection_book_category_source`; regeneration replaces rows
   (delete → flush → insert).
3. **Deleting a book cascades to its AISelection rows** — FK `ON DELETE CASCADE`
   (requires `PRAGMA foreign_keys=ON`, set per-connection in database.py).
4. **Events are append-only** — never updated or deleted; `book_id` has no FK so history
   survives book deletion.
5. **`cover_url` from clients must be `https://`** (schemas.py); AI palette colors must be
   hex, font names alphanumeric (services/ai.py validators).

## Status lifecycles

`Book.enrich_status`:

```
pending ──(background fetch ok / miss)──► ready
   │                                        ▲
   └──(exception in background)──► failed ──┘ (manual "Refresh info")
```

- New books via API start at `pending`; CSV-imported and legacy books are `ready`.
- Frontend polls the list every 2 s while any book is `pending`.

`Book.status` (user-controlled): `want ↔ reading ↔ read`, any transition allowed;
`rating` survives only inside `read`.
