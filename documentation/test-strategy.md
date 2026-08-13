# Test strategy

## Layers

| Layer | Tooling | Where | Runtime deps |
|-------|---------|-------|--------------|
| Static analysis | ruff (`F`, `E9`) · oxlint | `backend/ruff.toml` · `.oxlintrc.json` | none — no code is executed |
| Backend API | pytest + TestClient | `backend/tests/` + `conftest.py` | in-memory SQLite; AI, Google and Spotify mocked |
| Frontend | Vitest + Testing Library + MSW | `frontend/src/test/` | jsdom; MSW mock backend |
| End-to-end | Playwright | `frontend/e2e/smoke.spec.js` | live backend (`ALLOW_DEV_LOGIN=1`) + dev server |
| Visual | Playwright screenshots | `frontend/e2e/visual.spec.js` | mocked API; **local only** (fonts differ per OS) |
| Manual | regression checklist | `documentation/regression-checklist.md` | production + real API keys |

Run: `cd backend && python -m ruff check . && pytest` ·
`cd frontend && npm run lint && npm test` · `npm run e2e` before a deploy.

Counts are deliberately not written down here — they grow every week and the number
would be stale by the next commit. CI (`.github/workflows/ci.yml`) runs static analysis
and both test suites on every push; E2E and visual tests stay local.

## What automation covers

**Backend (by file):**
- `test_books.py` — CRUD; status/rating rules and their localization (ru/en);
  background enrichment (pending → ready / failed, external_id path); https-only cover;
  `raw_metadata` never exposed.
- `test_atmosphere.py` — unified atmosphere endpoints: generation (mocked), persistence,
  regeneration without duplicates, unknown category, cascade delete, DB unique constraint,
  palette hex validation. Also the aroma rules (2026-08-12): an item without a raw
  material is rejected by the schema, unsafe materials are dropped while the selection
  survives, repetition is keyed on the material, and the normaliser merges "ирис" with
  "ирисовый корень" **without** merging "амбра" with "амбретта" — a false merge would
  silently ban a material the model never offered.
- `test_search.py` — min query length, external results (mocked), `external_id` passthrough,
  catalog cache survives an external outage.
- `test_import.py` — import happy path, dedup/skip logic, status & rating edge cases,
  limits (size / rows / encoding).

- `test_public.py` — the showcase boundary: open without a session, only `featured` books,
  nothing personal in the payload, both palettes exposed, visits logged without personal data.
- `test_spotify.py` — track matching, cache behaviour, playlist building, and the cap on
  parallel searches (asserted as an observed *peak* of concurrent calls, not a call count).
- `test_hardening.py` — rate limits and security headers, including the third-party
  permissions the app actually relies on.
- `test_authors.py` — author identity (case, spacing, initials, ё/е), and the rule that
  **unknown strings are never split**: "Гамсун, Кнут" and "Ильф и Петров" both look like
  co-authors and both stay whole. Plus the author page: shelf and catalog kept apart,
  401 without a session, and that newly added books get linked.

**Frontend (by file):**
- `app.test.jsx` — shelves render from API, library filter, routing (click & keyboard).
- `shelf.test.jsx` — pagination arrows, boundary states, empty/placeholder shelves.
- `detail.test.jsx` — status change round-trip, rating appears only for `read`, 404 page.
- `search-add.test.jsx` — debounced search, add flow closes modal and updates shelf,
  Esc closes and returns focus.
- `import.test.jsx` — CSV upload shows the report.
- `showcase.test.jsx` — the public page opens for a guest (401 from `/auth/me` is a state,
  not an error) and explains the service.
- `palette.test.js` / `contrast.test.js` — pure colour logic: which palette a symbol is
  visible on, and nudging an AI accent up to AA.
- `playlist-embed.test.jsx` — playlist id parsing (including junk URLs) and the player
  living in the music tab only.
- `author.test.jsx` — the jump from a book to its author, and the two piles on the author
  page (shelf vs catalog): merged into one, the page would just repeat a shelf search.

## Where tests are blind (a real case, 2026-07-28)

Two calls to names that do not exist survived a refactor **and** a fully green test suite
for two days: `_search_track` (the "create playlist" button returned 500 for every book)
and `_sync_playlist` (rebuilding a playlist after deleting a track failed silently).

Neither was an accident of coverage — both sat in the two places a test suite structurally
cannot see:

1. **A function replaced by a stub in every test that touches it.** All router tests
   monkeypatch `create_playlist_from_songs`, so its body never ran once.
2. **A background task with a swallowed exception.** The failure went to the log; the user
   saw "track deleted" and an unchanged playlist.

`python -m ruff check .` named both in under a second, without running anything. That is
why static analysis is the first layer in the table above rather than a nicety: tests
check what they call, and a linter checks what is written.

Practical rules that follow:
- when a whole function is stubbed in tests, add one test that exercises its body;
- when moving code between modules, trust the linter, not the test run;
- prefer a narrow rule set (`F`, `E9`) — errors, not style, so it never cries wolf.

## When the answer is valid but wrong (2026-08-12)

Aromas were named "Крахмальный воротничок" and "Камень и известь" — evocative, fitting,
and impossible to buy, because no such products exist. **Not one test could have caught
this, and no test was missing.** Against the schema the answer was flawless: two non-empty
strings. The defect was in what we asked for, and correctness of *form* says nothing about
correctness of *substance*.

Two things followed from that, and both are now the pattern for AI features here:

1. **Constrain the shape so the wrong answer is unrepresentable.** `material` was split
   out as its own field and declared before `title`; with structured outputs the order of
   fields is the order of generation, so the model must name a substance before inventing
   an image. Tests then have something to assert — an item without `material` is rejected.
2. **Measure the stored output, not the code path.** `scripts/aroma_audit.py` reads what
   is actually in the database and sorts names into buckets. It found that of 377 stored
   items exactly **one** looked like an ordinary raw material — a number no unit test
   would ever have produced.

⚠ The audit script classifies by a crude signal (word count and capitalisation) and says
so in its own output. It is a way to *narrow where to look*, not a verdict: "дубовый мох"
lands in the suspicious bucket while being a perfectly real material. A measurement whose
imprecision is undocumented is worse than none — see the section below.

⚠ The fix then created a defect of its own: once answers became actionable, harmful
answers became actionable too (the model suggested cannabis for a book about smuggling),
and the repetition counter — keyed on the now-always-unique `title` — silently stopped
working. **When a value moves to a new field, find everything that read the old one.**

## When the measurement lies (2026-08-01 / 02)

A worse failure than an untested branch is a check that reports confidently on the wrong
thing. Four in two days, each one costing an hour of chasing the wrong cause:

1. **A font preview loaded eight families in one Google Fonts request.** `css2` is
   all-or-nothing, so one bad entry returned 400, nothing loaded, and the page reported
   "no Cyrillic" for all eight — including families that certainly have it.
2. **The layout audit measured after taking the screenshot.** A `fullPage` screenshot
   resets `Emulation.setEmulatedMedia`, so `pointer: coarse` was gone by measuring time and
   `@media (pointer: coarse)` rules never applied. 35 "tap targets under 44px" were an
   artefact. The giveaway: exactly the three pages with `fullPage: false` reported
   `pointerCoarse: true`.
3. **A diversity report aggregated the whole corpus.** Ten freshly regenerated records
   dissolved among two hundred old ones; the effect of the change was unreadable either way.
4. **A colour metric counted distinct strings.** `#f3ecdd` and `#f4efe4` are different
   values and the same cream; "152 unique backgrounds out of 201" hid the fact that 75% of
   the library was one colour.

What these have in common: each check answered a question adjacent to the one being asked,
and none of them could fail loudly. Rules that came out of it:

- **give every check a control sample with a known answer.** The font preview now tests
  PT Serif alongside the candidates: if the control reports "no Cyrillic", the instrument is
  broken, not the fonts.
- **separate "the object is broken" from "the tool is broken"** in the output. The same
  preview now distinguishes "the stylesheet never loaded" from "loaded, but this family has
  no Cyrillic" — those demand opposite fixes.
- **measure the delta, not the state.** Reports that answer "what do we have" cannot answer
  "what did the change do"; add a filter by date or by batch from the start.
- **let a diagnostic script call production code, never a copy of it.** `explore_avoid.py`
  reimplemented the repeat key, and after the key changed it kept printing the old picture.
  `track_key`/`artist_key` were extracted so counting and measuring share one definition.
- **check the seam between stages.** The prompt pushed the model away from the overused
  canon and Spotify verification pushed it back; both components worked exactly as
  specified, and no test of either could have shown it.

## What automation deliberately does NOT cover

Verified manually (see regression checklist):

1. **Real AI calls** — structured-outputs behavior of live Claude/OpenAI (schema acceptance,
   token limits, refusals). Mocks cover the contract, not the providers.
2. **Real Google Books matching quality** — the strict title+author matching against live data.
3. **Alembic migrations against a real database copy** — tests use `create_all`.
4. **Visual appearance** — both themes, AI passport rendering, responsive shelves.
5. **Screen reader semantics** — aria attributes are asserted, actual SR behavior is not.
6. **CSP and anything else that only exists in production.** Vite serves pages without
   security headers, so a missing `frame-src` / `connect-src` looks perfectly fine locally
   and silently breaks the Spotify player or the waitlist form on the deployed site. The
   header content is asserted in `test_hardening.py`; that it actually *works* is a
   production checklist item.
7. **Layout that depends on real measurements.** jsdom reports zero sizes, so carousel
   arrows, overflow and tap targets cannot be asserted there — they are measured in a real
   browser by `frontend/scripts/layout-audit.mjs` (screenshots + numbers at 390/768/1440).

## Conventions

- Backend tests never touch `library.db` (in-memory engine swapped in `conftest.py`).
- No test spends API tokens: AI generators and Google fetchers are always mocked.
- Mock targets after the refactor: `routers.atmosphere.CATEGORIES[cat]["generate"]`,
  `routers.search.search_books`, `services.enrichment.fetch_book_info` / `fetch_volume_by_id`.
- Frontend tests go through the real component tree with MSW at the network boundary —
  no component mocking.
