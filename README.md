# Nocturne — Book Library

A personal library service for **atmospheric literary evenings**. For each book, the service
suggests matching music (from Claude and from ChatGPT, with short explanations) and generates
an AI "design passport" — a palette and font pair that re-themes the book card to match the
book's mood. It also tracks reading status and ratings, imports an existing library from CSV,
and enriches books with covers and metadata from Google Books.

> Pet project focused on learning AI-assisted development. In active development.

## Features

- **Reading tracker** — statuses `want` / `reading` / `read`, ratings 1–10 (enforced rule:
  only `read` books can be rated).
- **Add via search** — find a book in Google Books (with a local search cache, TTL 30 days),
  add it in one click; the cover shows instantly, metadata arrives in the background
  (`pending → ready / failed`).
- **CSV import** — idempotent (deduplication by ISBN and by title+author), row limits,
  per-file report (imported / duplicates / skipped).
- **AI atmosphere** — unified API for AI-generated categories:
  - *music*: two playlists (Claude & ChatGPT) with explanations;
  - *design passport*: palette + fonts that restyle the book card (applied only if the
    palette passes a WCAG contrast check);
  - *food & scents*: planned, same scheme.
- **Structured AI outputs** — Pydantic schemas passed to both providers
  (`messages.parse` / `chat.completions.parse`), with validation of colors and font names
  at the boundary.
- **Light & dark ("evening") themes** — design tokens in CSS, toggle in the header.
- **Accessibility** — keyboard navigation, focus trap in modals, `aria` attributes,
  contrast fallback for AI palettes.
- **Event log** — append-only log of user and system events (foundation for future stats).
- **Bilingual API messages** (`ru` / `en`).

## Tech stack

- **Backend:** Python, FastAPI, SQLModel, SQLite (WAL; `DATABASE_URL` env var ready for
  Postgres), Alembic migrations.
- **Frontend:** React + Vite, React Query, React Router. Tests: Vitest + Testing Library + MSW.
- **External services:** Google Books API; Anthropic Claude & OpenAI (structured outputs).

## Getting started

Requires Python 3.12+ and Node 20+. From the repo root:

```
# --- Backend ---
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

cd backend
pip install -r requirements.txt

# Private files (both gitignored):
copy prompt_config.example.py prompt_config.py   # then edit your prompts
# create backend/.env with:
#   ANTHROPIC_API_KEY=...
#   OPENAI_API_KEY=...
#   GOOGLE_BOOKS_API_KEY=...
#   DATABASE_URL=...          # optional, defaults to sqlite:///library.db

alembic upgrade head         # create / migrate the database
uvicorn main:app --reload    # http://127.0.0.1:8000

# --- Frontend (separate terminal) ---
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

## API

Interactive documentation (the source of truth): **http://127.0.0.1:8000/docs** (Swagger)
or `/redoc`. Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/books` | List books / add a book (background enrichment) |
| GET/PATCH/DELETE | `/books/{id}` | Read / update status & rating / delete (cascades) |
| POST | `/books/{id}/enrich` | Manual re-enrichment from Google Books |
| GET/POST | `/books/{id}/atmosphere/{category}` | Get / generate AI picks (`music`, `design`) |
| GET | `/search?q=` | Book search: local catalog cache + Google Books |
| POST | `/import` | CSV import (limits: 2 MB, 2000 rows) |

All endpoints accept `?lang=ru|en` for localized messages.

## Tests

```
cd backend && pytest          # ~40 tests, in-memory DB, AI & Google mocked
cd frontend && npm run test   # 13 tests, MSW mock backend
```

See `documentation/test-strategy.md` for what is (and isn't) covered.

## Project structure

```
book-library/
├── backend/
│   ├── main.py               # app factory: includes routers
│   ├── routers/              # books (CRUD), atmosphere (AI), search, imports
│   ├── services/             # ai.py (Claude/OpenAI generators), enrichment.py
│   ├── models.py             # SQLModel tables: Book, AISelection, Catalog
│   ├── schemas.py            # request/response models (BookCreate, BookRead, ...)
│   ├── events.py             # append-only event log
│   ├── deps.py, constants.py, i18n.py, google_books.py, database.py
│   ├── alembic/              # migrations (alembic upgrade head)
│   ├── conftest.py, tests/   # pytest suite
│   └── prompt_config.example.py  # prompt template (real prompts are private)
├── frontend/
│   └── src/
│       ├── pages/            # HomePage, BookPage
│       ├── components/       # BookCard, Shelf, BookDetail, SearchModal, AtmosphereSection
│       ├── hooks/            # useTheme, useFocusTrap
│       ├── styles/           # design tokens (light/dark) + per-component css
│       ├── api.js, queryKeys.js, constants.js, lib/contrast.js
│       └── test/             # Vitest + MSW suite
└── documentation/            # architecture, data model, test strategy
```

## Documentation

- [Architecture](documentation/architecture.md) — components, data flows, key decisions.
- [Data model](documentation/data-model.md) — tables, invariants, status lifecycles.
- [Test strategy](documentation/test-strategy.md) and
  [regression checklist](documentation/regression-checklist.md).

---

*Built as a learning project with AI assistance.*
