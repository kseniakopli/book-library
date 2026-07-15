# Manual regression checklist

Run before merging a large feature or "release". Needs both servers running and real API
keys in `backend/.env`. ~15 minutes.

## Setup
- [ ] `cd backend && pytest` — all green
- [ ] `cd frontend && npm run test` — all green
- [ ] `alembic upgrade head` on a **copy** of `library.db` — no errors, no changes on
      an up-to-date database

## Library basics
- [ ] Home page loads; shelves show correct counts
- [ ] Shelf pagination: arrows page through; position survives opening a book and returning
- [ ] Library filter narrows by title and author; clearing restores shelves
- [ ] Book page opens by click; direct URL `/books/N` works; F5 works; browser Back works

## Add & import
- [ ] Search modal: results appear after 3+ chars; candidate with cover adds instantly
      with the cover visible; description arrives within seconds without F5
- [ ] Add a book Google can't match → book stays, no error, status becomes `ready`
- [ ] Import a real CSV → report shows imported/duplicates/skipped; re-import → all duplicates
- [ ] Delete a book → confirmation → returns home; its selections are gone

## AI (spends tokens — one book is enough)
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
