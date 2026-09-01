# Claude Code project instructions

This file is the Claude Code adapter. The shared project contract is in
[`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md); the lifecycle is in
[`ai/WORKFLOW.md`](ai/WORKFLOW.md); current evidence is in
[`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) and
[`ai/LAST_HANDOFF.md`](ai/LAST_HANDOFF.md).

Before implementation, read those files plus
[`ai/DECISIONS.md`](ai/DECISIONS.md),
[`ai/DEFERRED_FINDINGS.md`](ai/DEFERRED_FINDINGS.md) and
[`ai/ACTIVE_TASK.md`](ai/ACTIVE_TASK.md). Use AUDIT, DESIGN DECISION,
IMPLEMENT, ACCEPTANCE and CLOSE. Do not start implementation before the root
cause and the allowed scope are understood. Do not trust a self-report from a
previous agent without checking evidence. Do not expand scope or repair
unrelated findings.

Update the state files and append-only chronology during the iteration. Create
a Task-ID commit after a completed iteration when possible. Always disclose
NOT VERIFIED, FAIL and BLOCKED, and report commit, branch and push status. Do
not claim that ChatGPT Project or Claude Project has repository access unless
the relevant files were actually connected or read.

## VibeCoding bootstrap (mandatory)

Before any project task, read `PROJECT_MANIFEST.yaml`,
`ai/CURRENT_STATE.md`, `ai/VIBECODING_RULES.md` and
`ai/VIBECODING_TOOL_REGISTRY.yaml`; read `last_corrected` from the canonical
policy, classify the task and select only the required checks. Emit the
VibeCoding acknowledgement exactly once in the final response after the task
is completed or stopped; never emit it in intermediate updates. If the policy
is missing, ambiguous or its date is unreadable, use
`VIBECODING POLICY: NOT VERIFIED` exactly once in the final response and do
not modify the project. Detailed rules live only in
[`ai/VIBECODING_RULES.md`](ai/VIBECODING_RULES.md).

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
in `_archive/` or a proper subfolder once their useful content is extracted.

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

At the end of every response, include the instruction-check block required by
[`ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md`](ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md).
