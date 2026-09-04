# Claude Code project instructions

This file is the Claude Code adapter. The shared project contract is in
[`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md); the lifecycle is in
[`ai/WORKFLOW.md`](ai/WORKFLOW.md); current evidence is in
[`ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) and
[`ai/LAST_HANDOFF.md`](ai/LAST_HANDOFF.md).

At the start of a new session, read those files plus
[`ai/DECISIONS.md`](ai/DECISIONS.md),
[`ai/DEFERRED_FINDINGS.md`](ai/DEFERRED_FINDINGS.md) and
[`ai/ACTIVE_TASK.md`](ai/ACTIVE_TASK.md). Use AUDIT, DESIGN DECISION,
IMPLEMENT, ACCEPTANCE and CLOSE. Do not start implementation before the root
cause and the allowed scope are understood. Do not trust a self-report from a
previous agent without checking evidence. Do not expand scope or repair
unrelated findings.

At the start of a new agent session, perform the full bootstrap once. For a
new independent task in the same healthy session, use the short Task Preflight:
workspace guard, branch, HEAD, working-tree status, active-task/conflict,
classification and verification profile. A continuation of the current task
uses only the next action-specific check and does not repeat the full
bootstrap. Revalidate only when the workspace, Git root, environment,
relevant instructions or agent context changed. The canonical details are in
`ai/VIBECODING_RULES.md`.

Update only the state files whose factual content changed; a milestone,
architecture or control change may update the relevant global state and
decision records. Append chronology for substantial work, not every
continuation message. Create a Task-ID commit after a completed iteration when
possible. Always disclose NOT VERIFIED, FAIL and BLOCKED, and report commit,
branch and push status. Do
not claim that ChatGPT Project or Claude Project has repository access unless
the relevant files were actually connected or read.

## Workspace guard

Before project-specific analysis or execution, including read-only work, enforce
the canonical `SESSION_WORKSPACE_HARD_GATE` from
[`ai/VIBECODING_RULES.md`](ai/VIBECODING_RULES.md). Only after it passes may the
agent read project state, classify the task or select project-analysis tools.
Before any file change, state/report update, backend start, frontend build,
database write, migration, artifact-producing test, commit or push, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
```

The default local root is `C:\Users\edwat\SupplyDesk`. A deliberate Git
worktree or CI checkout must pass its exact absolute root explicitly with
`-ExpectedRoot <absolute path>`. The guard only compares the real Git root; it
never changes directory, branch or files. If it prints
`BLOCKED_WRONG_WORKSPACE`, stop immediately, even when local state files appear
valid.

Before starting a backend runtime specifically, classify `RUNTIME_MODE`
(`LOCAL_CANONICAL` / `SAFE_TEST` / `CI` / `OTHER`) against
`PROJECT_MANIFEST.yaml`'s `runtime_modes` block, then
[`docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md`](docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md),
before choosing a start command or port — see
[`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md) rule 14. `SAFE_TEST` (default port
`18000`) never has real provider credentials by design and must not be used
for the owner's normal work session; do not substitute it for
`LOCAL_CANONICAL` (port `8000`) just because it is the mode already proven
working earlier in the session.

The legacy root `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS` is
recovery-only. Do not run ordinary coding tasks, the backend, frontend builds
or migrations there, and do not use it to change canonical project state.
Recovery or read-only audit of that root requires an explicit task instruction.

## VibeCoding bootstrap (mandatory)

At the start of a new session, read `PROJECT_MANIFEST.yaml`,
`ai/CURRENT_STATE.md`, `ai/VIBECODING_RULES.md` and
`ai/VIBECODING_TOOL_REGISTRY.yaml`; read `last_corrected` from the canonical
policy. Reuse them for later tasks in the same healthy session unless a
revalidation exception applies. For each new task, classify it and select only
the required checks. Emit the
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
  `mail/db_compat.py` — the SQLite/Postgres DB-API compatibility shim
  (`ManagedConnection`, `CompatRow`, `PostgresCursor`, `PostgresConnection`, SQL dialect
  adapters) extracted out of `mail/repository.py` (first step of splitting that
  8800+-line file by responsibility); `mail/repository.py` imports it back, no consumer
  outside the mail package ever referenced these names directly.
  `mail/time_utils.py` — `UTC`/`utc_now`/`iso_now`/`iso_after`/`DEFAULT_SESSION_LIFETIME_SECONDS`,
  split out so both `mail/repository.py` and `mail/auth_accounts.py` can depend on them
  without a circular import; `mail/repository.py` re-exports them for `mail/queue.py`,
  `backend/app_config.py` and tests, which still import from `mail.repository` unchanged.
  `mail/auth_accounts.py` — `AuthAccountsMixin`: users/sessions/OAuth-state/mail-account CRUD
  (`seed_user`, `authenticate`, `create_session`, `save_mail_account`, etc.) extracted out of
  `MailRepository` — the one cluster confirmed to have zero private-helper coupling with any
  other cluster in the file.
  `mail/mail_templates.py` — `MailTemplatesMixin`: `get_mail_template`/`save_mail_template`,
  another zero-coupling cluster (only touches the universal `_audit_connection`).
  `class MailRepository(AuthAccountsMixin, MailTemplatesMixin)` composes both in.
- `backend/integrations/{registry,llm,search}/` — provider adapters moved out of the root flat
  package: `dadata_client.py`, `checko_client.py`, `llm_fallback.py`, `routerai_client.py`,
  `web_lookup.py`, `xmlriver_client.py`, `serp_parser.py` (the last with a thin root
  `serp_parser.py` compatibility wrapper — canonical invocation is
  `python -m backend.integrations.search.serp_parser ...`).
- `backend/domain/supplier_identity/` — supplier-identity product logic moved out of the
  root flat package: `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `verify.py`.
- `backend/domain/supplier_enrichment/` — supplier-enrichment logic split out of the root flat
  package: `contact_crawler.py` (moved) and `pipeline.py` (the reusable ИНН/ОГРН parsing
  extracted from `collect_inn.py`, shared by `supplier_app.py` and the CLI).
- `backend/app_config.py` / `backend/http_static.py` — `Config`, env-parsing helpers,
  `load_dotenv`, `yandex_provider_factory` and static-asset/fixture helpers extracted out of
  `supplier_app.py` (first step of turning it into a thin composition entrypoint; `SupplierApp`/
  `SupplierHandler` stay in `supplier_app.py` for now). All names remain importable from
  `supplier_app` via re-export — `api/index.py` and operator scripts are unaffected.
- `backend/http_auth.py` — `AuthHandlerMixin`: login, session, CSRF and Yandex OAuth handler
  methods (`_login`, `_auth_me`, `_require_session`, `_require_csrf`, `_oauth_start`,
  `_oauth_callback`, etc.) extracted out of `SupplierHandler`.
- `backend/http_requests.py` / `backend/http_global_suppliers.py` — `RequestRouteMixin`
  (`_thread_messages`, `_request_route`, `_request_action`) and `GlobalSupplierRouteMixin`
  (`_global_supplier_route`, `_global_supplier_action`) extracted out of `SupplierHandler`. Mail
  routes stay inline in `do_GET`/`do_POST` — unlike requests/global-suppliers, they never had a
  dedicated sub-router method to lift; carving one out would mean restructuring `do_GET`/`do_POST`
  bodies rather than a pure move, so it's deliberately not done here.
  `class SupplierHandler(AuthHandlerMixin, RequestRouteMixin, GlobalSupplierRouteMixin,
  SimpleHTTPRequestHandler)` composes all three in; `do_GET`/`do_POST`/`do_DELETE` and their route
  ordering are untouched.
- `backend/domain/supplier_enrichment/orchestrator.py` — `EnrichmentOrchestratorMixin` and
  `EnrichmentOutcome`: the ~1000-line enrichment pipeline (SERP→crawl→registry→web→finance
  retry stages, `_enrich_one`) extracted out of `SupplierApp` (Pass 2 of the same
  composition-entrypoint program). `class SupplierApp(EnrichmentOrchestratorMixin)` composes it
  in, so every method still resolves `self.repository`/`self.service`/`self.llm_*` exactly as
  before — no behavior change, no new public surface.
- `collect_inn.py` stays at root as a thinned CLI (argparse, crawl/LLM/web/DaData
  orchestration, CSV output) importing its extracted pipeline back — this is deliberate
  structure, not an oversight. Three operator CLIs already moved with thin root compatibility
  wrappers: `scripts/collect_contacts.py`, `benchmarks/benchmark_models.py`,
  `backend/integrations/search/serp_parser.py`; see `docs/architecture/REPOSITORY_LAYOUT.md`
  for the current map.

At the end of every substantive final response, include the
`[ИНСТРУМЕНТЫ И SKILLS]` block required by the `TOOL_USAGE_REPORTING` rule in
[`ai/AI_CONTRACT.md`](ai/AI_CONTRACT.md), plus the final VibeCoding
evidence/acknowledgement required by the canonical project rules.
