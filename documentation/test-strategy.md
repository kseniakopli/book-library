# Test strategy

## Layers

| Layer | Tooling | Where | Count | Runtime deps |
|-------|---------|-------|-------|--------------|
| Backend API | pytest + TestClient | `backend/tests/` + `conftest.py` | ~40 | in-memory SQLite; AI & Google mocked |
| Frontend | Vitest + Testing Library + MSW | `frontend/src/test/` | 13 | jsdom; MSW mock backend |
| Manual | regression checklist | `documentation/regression-checklist.md` | — | real backend + real API keys |

Run: `cd backend && pytest` · `cd frontend && npm run test`

## What automation covers

**Backend (by file):**
- `test_books.py` — CRUD; status/rating rules and their localization (ru/en);
  background enrichment (pending → ready / failed, external_id path); https-only cover;
  `raw_metadata` never exposed.
- `test_atmosphere.py` — unified atmosphere endpoints: generation (mocked), persistence,
  regeneration without duplicates, unknown category, cascade delete, DB unique constraint,
  palette hex validation.
- `test_search.py` — min query length, external results (mocked), `external_id` passthrough,
  catalog cache survives an external outage.
- `test_import.py` — import happy path, dedup/skip logic, status & rating edge cases,
  limits (size / rows / encoding).

**Frontend (by file):**
- `app.test.jsx` — shelves render from API, library filter, routing (click & keyboard).
- `shelf.test.jsx` — pagination arrows, boundary states, empty/placeholder shelves.
- `detail.test.jsx` — status change round-trip, rating appears only for `read`, 404 page.
- `search-add.test.jsx` — debounced search, add flow closes modal and updates shelf,
  Esc closes and returns focus.
- `import.test.jsx` — CSV upload shows the report.

## What automation deliberately does NOT cover

Verified manually (see regression checklist):

1. **Real AI calls** — structured-outputs behavior of live Claude/OpenAI (schema acceptance,
   token limits, refusals). Mocks cover the contract, not the providers.
2. **Real Google Books matching quality** — the strict title+author matching against live data.
3. **Alembic migrations against a real database copy** — tests use `create_all`.
4. **Visual appearance** — both themes, AI passport rendering, responsive shelves.
5. **Screen reader semantics** — aria attributes are asserted, actual SR behavior is not.

## Conventions

- Backend tests never touch `library.db` (in-memory engine swapped in `conftest.py`).
- No test spends API tokens: AI generators and Google fetchers are always mocked.
- Mock targets after the refactor: `routers.atmosphere.CATEGORIES[cat]["generate"]`,
  `routers.search.search_books`, `services.enrichment.fetch_book_info` / `fetch_volume_by_id`.
- Frontend tests go through the real component tree with MSW at the network boundary —
  no component mocking.
