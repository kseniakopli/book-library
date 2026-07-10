# Book Library

A personal library service for **atmospheric literary evenings**. For each book, the service
suggests matching music, food & drinks, and scents — in two variants (from Claude and from
ChatGPT) with short explanations — and also tracks reading status, ratings, and
recommendations.

> Pet project focused on learning AI-assisted development and web development. Currently in
> active MVP development.

## Features

**Available now**

- Store books in a database.
- Add a book by title and author, with automatic cover and description lookup via the Google
  Books API (the book is still saved if nothing is found or the service is unavailable).
- List all books.
- Change reading status (`want` / `reading` / `read`) and set a rating (1–10), with the rule:
  a rating is only allowed for books with status `read`; leaving `read` clears the rating.
- Language-aware requests (`ru` / `en`): external lookups and server messages follow the
  requested language.
- AI music picks: for a book, Claude and ChatGPT each suggest an atmospheric playlist with an
  explanation; both variants are stored per source.

**Planned**

- Bilingual interface (RU / EN) with a language switcher.
- AI "Atmosphere" picks for food and scents (same two-variant scheme as music).
- Import books with ratings from CSV.
- Recommendations based on reading history.
- Statistics and reading tracking; authentication and multi-user support.

## Tech stack

- **Backend:** Python, FastAPI, SQLModel, SQLite
- **Frontend (planned):** React
- **External services:** Google Books API; Anthropic Claude and OpenAI ChatGPT (AI picks)

## Getting started

Requires Python 3. Run from the repo root:

```
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 2. Move into the backend and install dependencies
cd backend
pip install -r requirements.txt

# 3. Set up private files (both are gitignored)
copy prompt_config.example.py prompt_config.py   # then edit your prompts
# create backend/.env with your API keys:
#   ANTHROPIC_API_KEY=...
#   OPENAI_API_KEY=...

# 4. Run the development server
uvicorn main:app --reload
```

Then open the interactive API docs at http://127.0.0.1:8000/docs

## API endpoints

| Method | Path                    | Description                                             |
|--------|-------------------------|---------------------------------------------------------|
| POST   | `/books`                | Add a book (title, author); auto-fills cover & description |
| GET    | `/books`                | List all books                                          |
| PATCH  | `/books/{id}`           | Update status and/or rating (rating only for `read`)    |
| POST   | `/books/{id}/music`     | Generate music picks (Claude + ChatGPT) and store them  |
| GET    | `/books/{id}/music`     | Get stored music picks for a book                       |

Endpoints accept an optional `lang` query parameter (`ru` by default, or `en`).

## Running tests

```
cd backend
pip install pytest httpx
pytest -v
```

Tests use an in-memory database (they don't touch `library.db`) and mock the AI calls, so they
spend no API tokens. A `backend/.env` file must exist, because the AI clients are created on
import.

## Project structure

```
book-library/
├── backend/
│   ├── main.py                   # entry point: creates the app, includes the router
│   ├── books.py                  # API endpoints (APIRouter)
│   ├── models.py                 # SQLModel tables (Book, AISelection)
│   ├── schemas.py                # Pydantic request models
│   ├── database.py               # engine and table creation
│   ├── i18n.py                   # RU / EN messages
│   ├── google_books.py           # Google Books enrichment
│   ├── atmosphere.py             # AI music module (Claude + ChatGPT)
│   ├── prompt_config.example.py  # prompt template (real prompt_config.py is private)
│   ├── test_main.py              # pytest tests
│   ├── requirements.txt          # dependencies
│   └── library.db                # SQLite database (created on first run)
├── frontend/                     # React app (planned)
├── docs/                         # spec and phased plan (kept locally)
└── README.md
```

## Roadmap

The MVP covers the book database, add-with-enrichment, list and detail views, statuses and
ratings, and the first AI pick (music). Next comes the React frontend with an atmospheric
book card, followed by CSV import, food and scent picks, and recommendations.

---

*Built as a learning project with AI assistance.*
