# Publish allowlist — TASK-REMOTE-SETUP-SIMPLIFIED

Status: `ACTIVE FOR THIS TASK — EXPLICIT STAGING AFTER FINAL SCAN`

The previous `TASK-PUBLISH-SAFETY-001` review was intentionally conservative
and is retained in its report. This task uses exclusion-first rules: confirmed
source, tests, documentation and build configuration are admitted explicitly;
unknown, local, generated and operational paths stay excluded. Every admitted
path still requires the final staged-tree scan.

## AI state

The following state files are the only files currently admitted as
`SAFE CANDIDATE` for future publication, subject to the final scan:

- `AGENTS.md`
- `CLAUDE.md`
- `ai/AI_CONTRACT.md`
- `ai/WORKFLOW.md`
- `ai/CURRENT_STATE.md`
- `ai/LAST_HANDOFF.md`
- `ai/CHANGELOG.md`
- `ai/INTERACTION_LOG.md`
- `ai/DECISIONS.md`
- `ai/DEFERRED_FINDINGS.md`
- `ai/ACTIVE_TASK.md`
- `ai/PUBLISH_ALLOWLIST.md`
- `ai/PUBLISH_DENYLIST.md`
- `ai/PUBLISH_SECURITY_REPORT.md`
- `ai/reports/` — Markdown reports only, after the same scan
- `ai/inbox/` — task files only, after the same scan
- `ai/adapters/`
- `ai/templates/`
- `ai/tools/` — validator source only; generated `__pycache__` is excluded

Why needed: these files carry the shared agent contract, current state,
handoff, chronology and validation rules. Risk: they may disclose local paths,
operational metadata or future report content, but the scan performed for this
task found no secret values in the AI state. Status: `SAFE CANDIDATE`, not
`SAFE TO PUSH`.

## Application candidate files

The current working-tree source is admitted only through the explicit path
specification in `ai/PUBLISH_MANIFEST.md`. This does not admit every untracked
file or claim that every changed file is project source.

### A — application source selected by the manifest

Confirmed source path groups and concrete examples:

- `api/index.py`
- `checko_client.py`, `collect_inn.py`, `contact_crawler.py`,
  `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`,
  `supplier_app.py`, `web_lookup.py`, `run_probe.py`
- `mail/` — for example `mail/service.py`, `mail/repository.py`,
  `mail/providers/yandex.py`, `mail/providers/mailru.py`
- `frontend/src/` — React/TypeScript/CSS source
- `migrations/` — schema changes, requiring a separate migration review
- `fixtures/` and `supplier_discovery_v2/` — data/implementation fixtures

Why needed: application runtime and feature behavior. Risk: unreviewed product
changes, migrations, local data assumptions and duplicated worktree copies.

### B — tests selected by the manifest

Concrete path groups/examples:

- `tests/` — for example `tests/test_mail_integration.py`,
  `tests/test_mailru_mvp.py`, `tests/test_supplier_identity.py`
- `frontend/tests/` — Playwright specs and fixtures
- `frontend/src/components/mail/EmailRenderer.stories.tsx`

Why needed: reproducible verification. Risk: live-email fixtures, screenshots,
environment assumptions and possible operational data. No test path is approved
until its DB/provider safety is reviewed.

### C — project configuration selected by the manifest

Concrete examples: `.gitignore`, `.vercelignore`, `vercel.json`,
`requirements.txt`, `frontend/.gitignore`, `frontend/eslint.config.js`,
`frontend/tailwind.config.js`, `frontend/playwright.config.ts`,
`frontend/lighthouserc.cjs`.

Why needed: reproducible setup and build configuration. Risk: deployment
settings, ignore-rule gaps and accidental inclusion of local files.

## Excluded files

The following are not allowlisted:

- every `.env*` file, including `.env.example`;
- `.env`, `.env.local`, `.env.p0-backup-20260830`, `.env.production.local`,
  `.vercel/.env.preview.local`;
- `Temp/`, `runtime/`, `tmp/`, local databases and `mail-data/`;
- screenshots and visual snapshots (`*.png`, `*.jpg`, `*.jpeg`, `*.gif`,
  `*.webp`);
- archives (`*.zip`, `*.rar`, `*.7z`, `*.tar`, `*.gz`);
- backups, review exports, `P0_REVIEW*`, `REVIEW_*` and
  `mailru-mvp-backup-20260829/`;
- runtime logs;
- `Documents/` and other personal/unknown documents until owner review;
- deleted tracked files, which are not an instruction to delete or publish;
- any file with credential-like content, cookies, session data or private keys.

## Gate

Only paths in `ai/PUBLISH_MANIFEST.md` may be staged, and only after a fresh
staged-tree scan returns `PASS`. Excluded local env files do not block this
task by themselves. A secret in the publish set or Git history, inability to
create a safe commit, or missing GitHub authentication remains a hard blocker.
