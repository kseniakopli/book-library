Book Library

A personal library service for atmospheric literary evenings. For each book, the service
suggests matching music, food & drinks, and scents — in two variants (from Claude and from
ChatGPT) with short explanations — and also tracks reading status, ratings, and
recommendations.


Features

Available now


Store books in a database.
Add a book by title and author, with automatic cover and description lookup via the Google
Books API (the book is still saved if nothing is found or the service is unavailable).
List all books.
Change reading status (want / reading / read) and set a rating (1–10), with the rule:
a rating is only allowed for books with status read; leaving read clears the rating.


Planned (see docs/)


Bilingual interface (RU / EN) with a language switcher; external requests aware of language.
AI-generated "Atmosphere" picks: music, food, scents — Claude vs ChatGPT variants.
Import books with ratings from CSV.
Recommendations based on reading history.
Statistics and reading tracking; authentication and multi-user support.


Tech stack


Backend: Python, FastAPI, SQLModel, SQLite
Frontend (planned): React
External services: Google Books API; Claude and ChatGPT (AI picks)


Getting started

Requires Python 3.

# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the development server
uvicorn main:app --reload

Then open the interactive API docs at http://127.0.0.1:8000/docs

API endpoints

MethodPathDescriptionPOST/booksAdd a book (title, author); auto-fills cover & descriptionGET/booksList all booksPATCH/books/{id}Update status and/or rating (rating only for read)

Running tests

pip install pytest httpx
pytest -v

Tests use an in-memory database and do not touch library.db.

Project structure

book-library/
├── main.py            # FastAPI app: Book model, endpoints, Google Books enrichment
├── test_main.py       # pytest tests for the status/rating rule
├── requirements.txt   # dependencies
├── library.db         # SQLite database (created on first run)
└── docs/              # technical spec and phased implementation plan

Roadmap

The full technical specification and the phased implementation plan (with timeline) live in
the docs/ folder. The MVP covers the book database, add-with-enrichment, list and detail
views, statuses and ratings, and the first AI pick (music).
