# nocturne — atmospheric literary evenings

A personal library service that builds a whole **evening around a book**. For each book it
composes an "atmosphere": music picks from two sources with short explanations, food &
drink pairings, scent suggestions, and a generated **design passport** — palettes, fonts
and a custom ex-libris symbol that re-theme the book's page to match its mood. It also
tracks reading status and ratings, imports an existing library from CSV, enriches books
with covers and metadata from Google Books, builds Spotify playlists, and prints an A6
card to tuck into a book you give away.

Landing page & waitlist: **https://nocturne-library.netlify.app**

## Features

- **Shared catalog + personal shelves** — a book's intrinsic data (title, author, cover,
  metadata, atmosphere, Spotify playlist) lives once in a shared `book` catalog; each
  user keeps a personal `userbook` shelf entry (status, rating, read date). Adding a book
  that already exists reuses its catalog entry and atmosphere — no regeneration. See
  [documentation/data-model.md](documentation/data-model.md).
- **Reading tracker** — statuses `want` / `reading` / `read`, ratings 1–10 (enforced rule:
  only `read` books can be rated), read dates.
- **Add via search** — local catalog first, then Google Books (search cache, TTL 30 days),
  then manual entry if nothing matches. Covers show instantly, metadata arrives in the
  background (`pending → ready / failed`, polled via a lightweight pending counter).
  Duplicates on your shelf are rejected (409).
- **Atmosphere panel** — one button generates all categories at once:
  - *music*: two playlists (Claude & ChatGPT) with explanations, deduplicated;
  - *food & drinks* and *scents*: same two-source scheme;
  - *design passport*: dark + light palettes, font pair, an SVG ex-libris symbol and a
    short statement explaining it — generated automatically in the background when a book
    is added. Palettes are applied only after a WCAG contrast check.
- **Recommendations** — suggests *new* books (not in the library) based on books rated ≥7,
  each with a personal "why this one" reason. Generated on demand to control token spend.
- **Reading stats** — totals, pages, rating distribution, monthly chart, top authors and
  genres; all numbers are computed by the backend, and AI only interprets the ready-made
  summary (so it has nothing to hallucinate with).
- **Evening scene** — a full-screen `/books/{id}/evening` view in the book's palette:
  symbol, music, treats and scents in one place; swipe between books on mobile.
- **Printable A6 card** — ex-libris face, evening tracks, QR codes for the Spotify
  playlist and the project site; texts editable right on the preview, printed via the
  browser (double-sided A6).
- **Spotify integration** — one click builds a playlist from the book's picks (OAuth once,
  refresh token reused).
- **Shelf view toggle** — real covers or ex-libris symbols on the book's own palette.
- **CSV import** — idempotent (dedup by ISBN and title+author), auto-detected delimiter,
  size/row limits, per-file report. Non-standard column headers are recognized by AI
  (structured output, validated against real headers); standard exports parse without AI.
- **Structured AI outputs everywhere** — Pydantic schemas passed to both providers
  (`messages.parse` / `chat.completions.parse`), validation of colors, fonts and SVG at
  the boundary; empty AI responses never overwrite saved selections.
- **Observability** — structured JSON logs with request ids (`X-Request-ID` response
  header), fail-fast startup check for required API keys, append-only event log storing
  per-call AI metrics (provider, latency, token usage).
- **Light & dark ("evening") themes**, accessibility (keyboard, focus traps, aria,
  contrast fallbacks), bilingual API messages (`ru` / `en`).

## Tech stack

- **Backend:** Python, FastAPI, SQLModel, SQLite (WAL; `DATABASE_URL` env var ready for
  Postgres), Alembic migrations (0001–0007). Data model: `User` / `Book` (shared catalog) /
  `UserBook` (personal shelf).
- **Frontend:** React + Vite, React Query, React Router, recharts (stats page, lazy-loaded).
  Tests: Vitest + Testing Library + MSW; E2E: Playwright; lint: oxlint.
- **External services:** Google Books API; Anthropic Claude & OpenAI (structured outputs);
  Spotify Web API.
- **CI:** GitHub Actions — pytest, vitest, oxlint, OpenAPI contract check
  (`documentation/openapi.json` snapshot diff), dependency audits (pip-audit, npm audit).

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
#   SPOTIFY_CLIENT_ID=... / SPOTIFY_CLIENT_SECRET=...   # optional (playlists)
#   DATABASE_URL=...          # optional, defaults to sqlite:///library.db

alembic upgrade head         # create / migrate the database
uvicorn main:app --reload    # http://127.0.0.1:8000

# --- Frontend (separate terminal) ---
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

Missing required keys fail the startup with a clear message (`SKIP_KEY_CHECK=1` to bypass).
One-off maintenance scripts live in `backend/scripts/` (run from `backend/`, e.g.
`python scripts/backup_db.py`); see `backend/scripts/README.md`.

## API

Interactive documentation (the source of truth): **http://127.0.0.1:8000/docs** (Swagger)
or `/redoc`; a committed snapshot lives in `documentation/openapi.json`.

All endpoints live under the versioned prefix **`/api/v1`** (except the Spotify
OAuth `/callback`, which is registered externally):

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/v1/books` | List books (`status`, `limit`/`offset`) / add a book |
| GET/PATCH/DELETE | `/api/v1/books/{id}` | Read / update status, rating, read date / delete |
| GET | `/api/v1/books/design-summary` | Symbols + palettes for the symbol shelf view |
| GET | `/api/v1/books/pending-count` | Lightweight counter for enrichment polling |
| POST | `/api/v1/books/{id}/enrich` | Manual re-enrichment from Google Books |
| GET/POST | `/api/v1/books/{id}/atmosphere/{category}` | Get / generate AI picks (`music`, `design`, `food`, `aroma`) |
| POST | `/api/v1/books/{id}/playlist` | Create a Spotify playlist from the book's music |
| GET | `/api/v1/books/{id}/qr` | QR code of the playlist (for the printed card) |
| GET/POST | `/api/v1/recommendations` | Read stored / generate new book recommendations |
| GET | `/api/v1/stats` | Reading statistics (computed server-side) |
| POST | `/api/v1/stats/insights` | AI commentary on the stats summary |
| GET | `/api/v1/search?q=` | Book search: local catalog cache + Google Books |
| POST | `/api/v1/import` | CSV import (limits: 2 MB, 2000 rows) |

All endpoints accept `?lang=ru|en` for localized messages. `GET /health` (outside the
prefix) reports service/DB liveness.

## Tests

```
cd backend && pytest          # in-memory DB, AI & Google mocked
cd frontend && npm test       # MSW mock backend
cd frontend && npm run e2e    # Playwright smoke (needs a running backend)
```

See `documentation/test-strategy.md` for what is (and isn't) covered.

## Project structure

```
book-library/
├── backend/
│   ├── main.py               # app: routers, startup key check, JSON access log
│   ├── routers/              # books, atmosphere, search, imports, spotify,
│   │                         # recommendations, stats — thin HTTP layer
│   ├── services/             # ai.py (generators + call metrics), shelf.py,
│   │                         # atmosphere.py, enrichment.py, spotify.py, stats.py
│   ├── models.py, schemas.py # SQLModel tables / request-response models
│   ├── events.py             # append-only event log (JSON detail)
│   ├── logging_setup.py      # structured logs + request id
│   ├── deps.py, constants.py, i18n.py, google_books.py, database.py
│   ├── alembic/              # migrations (alembic upgrade head)
│   ├── conftest.py, tests/   # pytest suite
│   └── prompt_config.example.py  # prompt template (real prompts are private)
├── frontend/
│   └── src/
│       ├── pages/            # HomePage, BookPage, CardPage, EveningPage, StatsPage
│       ├── components/       # BookCard, Shelf, BookDetail, SearchModal,
│       │                     # AtmosphereSection, RecommendationShelf, ...
│       ├── hooks/            # useTheme, useShelves, useBookDesign, useCsvImport, ...
│       ├── styles/           # design tokens (light/dark) + per-component css
│       ├── api.js, queryKeys.js, lib/ (contrast, palette, svg)
│       └── test/             # Vitest + MSW suite; ../e2e — Playwright
├── landing/                  # public landing page with waitlist (deployed to Netlify)
└── documentation/            # architecture, data model, test strategy,
                              # states & degradation, openapi.json snapshot
```

## Documentation

- [Architecture](documentation/architecture.md) — components, data flows, key decisions.
- [Data model](documentation/data-model.md) — tables, invariants, status lifecycles.
- [States & degradation](documentation/states-and-degradation.md) — book state dimensions
  and behavior when external services fail.
- [Test strategy](documentation/test-strategy.md) and
  [regression checklist](documentation/regression-checklist.md).
