# Manual regression checklist

Run before merging a large feature or "release". Needs both servers running and real API
keys in `backend/.env`. ~15 minutes.

## Setup
- [ ] `cd backend && pytest` — all green
- [ ] `cd frontend && npm run test` — all green
- [ ] `alembic upgrade head` on a **copy** of `library.db` — no errors, no changes on
      an up-to-date database

## Sign-in (stage 9)
- [ ] Signed out (private window): any page shows the login screen, no library data
- [ ] Owner signs in with the `ADMIN_EMAIL` account without an invite code and lands on
      the existing shelf; the header shows the name and the "админ" badge
- [ ] Invite flow: `python scripts/make_invite.py "test"` → sign in with a second Google
      account and that code → empty shelf with onboarding; the code cannot be reused
      (`--list` shows it as taken)
- [ ] Non-admin: no "Редактировать" / "Обновить информацию" / "Обновить атмосферу" /
      track ✕ / series ex-libris buttons; personal actions (status, rating, delete from
      own shelf, recommendations, stats insights) all work
- [ ] Shelves are isolated: the tester does not see the owner's books; adding a book that
      already exists in the catalog brings its atmosphere along (no AI spend)
- [ ] "Выйти" returns to the login screen; the session does not survive it

## Public showcase (task 30) — check **in production**, in a private window
The showcase is what strangers see after scanning a printed card, and two of its
dependencies fail *silently* in a way local development cannot reveal: CSP only exists
in production (Vite serves pages without security headers).
- [ ] `/u/{slug}` opens **without signing in**; no ratings, statuses or reading dates
      anywhere in the response
- [ ] Book symbols are visible on every tile — a symbol drawn in light ink must land on
      a dark tile, not disappear into a light one
- [ ] Waitlist form: submit an address → "Готово!" and the mail actually arrives.
      A silent failure here means `connect-src` lost Formspree
- [ ] Book page in the showcase: the Spotify player renders — an **empty frame** means
      `frame-src https://open.spotify.com` is missing from CSP
- [ ] Scan the printed card with a phone: the QR leads to the current showcase URL
      (regenerate with `python scripts/make_landing_qr.py` after changing the slug — the
      "landing" in that name is historical, the landing page was removed on 2026-08-01 and
      the QR has pointed at the showcase since 2026-07-28)
- [ ] `python scripts/showcase_stats.py` counts the visits just made
- [ ] **Interface fonts arrived** — DevTools → Network → filter `gstatic`, expect 200s.
      This cannot be checked locally: Vite serves pages without CSP, so a wrong `font-src`
      shows up only in production, and a missing font fails silently — `<link>` raises
      nothing and the whole interface quietly falls back to Georgia

## Music generation (task 99, since 2026-08-02)
- [ ] Generate music for a book and read the server log: `Подстановка: … взят … того же
      исполнителя` lines are expected — that is an invented title being replaced by a real
      recording, not an error
- [ ] **Read those substitutions.** A namesake artist can slip through: Solas is an Irish
      folk band and also a rapper. Explicit tracks are filtered and the name must match
      exactly, but a same-genre namesake would pass
- [ ] No duplicate tracks inside one selection (the model repeats itself, and two invented
      titles can collapse onto one real recording after substitution)
- [ ] ⚠ **Dev and production share one Spotify account.** Playlists are rebuilt in place, so
      regenerating music locally rewrites the playlists production links to: the track list
      on the page stays old while the embedded player already shows the new one. After a
      local regeneration, carry the rows over with
      `scripts/sync_music_to_prod.py` — do **not** replace the whole database, production
      holds real users, invites and showcase events

## Aroma generation (tasks 129/133/134, since 2026-08-12)
- [ ] Generate aromas for a book: under each evocative name there is a "form · material"
      line ("благовония · сандал"). The material must be a substance you could type into a
      shop search — not an image ("мокрый камень") and not a product name in quotes
- [ ] **Open a book whose aromas were generated before 2026-08-12** (272 such items were in
      production on that date): the "form · material" line is simply absent — no
      "undefined", no empty separator. No migration was run, and there is no plan to run one
- [ ] Read the materials across several books: **the same one should not appear
      everywhere.** Iris, frankincense and oakmoss each stood in 10 of 22 selections before
      task 134, because repetition was keyed on the (now always unique) evocative title
- [ ] Form distribution is not skewed to raw forms: candles and essential oils are the
      widely stocked products, resins and hydrosols are specialist. `scripts/aroma_audit.py`
      prints the distribution
- [ ] ⚠ **Nothing illegal or unbreathable.** The filter is a backstop, not the primary
      defence — the prompt is. If `dropped_unsafe` in the `ai_aroma_generated` event is
      non-empty, the prompt stopped working and needs looking at, even though the user saw
      a clean result

## Library basics
- [ ] Home page loads; shelves show correct counts
- [ ] Shelf pagination: arrows page through; position survives opening a book and returning
- [ ] Shelf lazy loading: paging past the first 30 books fetches more (mobile: swipe to
      the end of the row); the "1–5 из N" range shows the full shelf size
- [ ] Library search (3+ chars) finds books on the shelf and in the catalog; adding one
      with "+ На полку" closes the search and shows the book on "Хочу прочитать"
- [ ] Book page opens by click; direct URL `/books/N` works; **F5 shows the app, not raw
      API JSON** (Vite proxy bypass for text/html); browser Back works

## Authors (task 97)
- [ ] Book page: the author's name is a link; a book with co-authors shows each of them
      as a separate link
- [ ] Author page lists shelf books and, separately, books by the same author that are
      in the catalog but not on the shelf (cycle volumes)
- [ ] Add a new book → its author appears on the author page (linking happens on add,
      not only in the backfill script)
- [ ] Signed out (private window): `/authors/1` shows the login screen, not a list

## Add & import
- [ ] Search modal: results appear after 3+ chars; candidate with cover adds instantly
      with the cover visible; description arrives within seconds without F5
- [ ] Add a book Google can't match → book stays, no error, status becomes `ready`
- [ ] Import a real CSV → report shows imported/duplicates/skipped; re-import → all duplicates
- [ ] Delete a book → confirmation → returns home; its selections are gone

## AI (spends tokens — one book is enough)
- [ ] "Подобрать атмосферу": music, food and aromas fill in one click; aroma items carry
      a "form · material" line (details in the aroma section above)
- [ ] "Подобрать музыку": two tabs (Claude / ChatGPT), sensible playlists, explanations
- [ ] "Оформить под книгу": card re-themes; text readable (contrast fallback silently
      keeps base theme if not)
- [ ] Regenerate both → still one variant per source (no duplicates)
- [ ] Stop backend mid-generation → error message with readable text, no white screen

## Themes & accessibility
- [ ] Toggle ☾/☀: evening theme applies everywhere (home, book page, modal); survives F5
- [ ] AI passport looks correct in **both** themes
- [ ] Keyboard only: Tab reaches cards, Enter opens a book, modal traps focus,
      Esc closes and focus returns to "+ Добавить книгу"
- [ ] Rating dropdown appears only for «Прочитана»; setting a rating updates the shelf badge

## Errors
- [ ] Stop backend, reload page → "Не удалось загрузить библиотеку" + «Повторить» works
      after backend restart
- [ ] Import a non-UTF-8 file → clear 400 message, not a crash
