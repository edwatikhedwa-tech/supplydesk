# Repository architecture rules

## Root hygiene

The repo root holds only real, load-bearing source and config — nothing generated, scratch,
or temporary. Before adding anything to root, ask whether it belongs in one of these instead:

- **`tmp/`** — the one designated place for scratch/working files (gitignored). Downloaded
  archives you're extracting, one-off debug scripts, intermediate output — all go here, never
  loose at root.
- **`results/`**, **`artifacts/`** — already-gitignored output folders for extraction results
  and QA screenshots respectively. Use these for their existing purpose, don't recreate siblings.
- **`_archive/`** — reversible archive for retired code that might still be worth referencing
  (e.g. `_archive/frontend-legacy/` for the pre-migration single-file frontend,
  `_archive/source-uploads/` for raw archives once their contents have been extracted into the
  tree). Move things here instead of deleting when "retire but keep" is the intent.
- **`fixtures/`** — static seed/demo data the backend reads at runtime (e.g.
  `fixtures/demo_catalog.json`, seeded into a fresh workspace by `supplier_app.load_fixture_data`).

Never dump uploaded `.rar`/`.zip`/`.tar` archives, ad-hoc `check.js`/`test.py` scripts, or
downloaded reference material directly at root — they land in `tmp/` while being worked on, and
in `_archive/` or a proper subfolder once their useful content has been extracted.

## Project layout

- `frontend/` — the React/Vite SPA (TypeScript, Tailwind). Talks to the backend exclusively via
  same-origin `/api/*` fetch calls (see `frontend/src/lib/api.ts`); no separate database or
  auth provider of its own.
- `supplier_app.py` / `api/index.py` — the Python backend (`BaseHTTPRequestHandler`-based, no
  framework). Serves `frontend/dist/` as the SPA shell and exposes the JSON API under `/api/*`
  and OAuth callbacks under `/oauth/*`. This is the single source of truth for data — the
  frontend has no independent backend of its own (any future prototype/scaffold that ships with
  its own Supabase/Firebase project must be rewired to this API before it's kept).
- `mail/` — the real Yandex IMAP/SMTP integration and SQLite-backed mail repository.
- Root-level `*.py` files besides `supplier_app.py`/`api/` (e.g. `serp_parser.py`,
  `checko_client.py`, `email_extractor.py`) are a flat package of supplier-discovery/extraction
  modules genuinely imported by the backend — this is deliberate structure, not clutter; don't
  move them without checking what imports them first.

## Before archiving or replacing a frontend/module

Move it, don't delete it — put it under `_archive/` with a clear name. Update whatever served it
(routing, `vercel.json` `includeFiles`/`excludeFiles`, build scripts) so there's no dangling
reference to the moved path, and re-run the test suite before considering the change done.
