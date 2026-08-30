# Publish denylist — TASK-REMOTE-SETUP-SIMPLIFIED

Status: `ACTIVE — EXCLUSION BOUNDARY FOR NON-MANIFEST PATHS`

This denylist is a safety boundary for the current publish. It does not delete,
move, untrack or modify any path. Explicit manifest paths may be staged after
the final security scan; everything else remains excluded.

## I — secrets and credential-like files

Always exclude:

- `.env`
- `.env.local`
- `.env.p0-backup-20260830`
- `.env.production.local`
- `.vercel/.env.preview.local`
- any other `.env*` file, including `.env.example` until it is separately
  confirmed to contain placeholders only
- files containing passwords, SMTP credentials, OAuth/JWT secrets, API keys,
  access tokens, cookies, sessions, private keys or database URLs with
  credentials

Action: `EXCLUDE`; for real exposed credentials, `ROTATE_AND_REVIEW`.

## F — temporary/runtime files

Exclude:

- `Temp/`
- `runtime/`
- `tmp/`
- `*.log`
- local runtime state and generated test output
- `mail-data/`, `*.sqlite3`, `*.db`

Reason: local data, logs, generated state and possible operational information.

## G — screenshots, archives and backups

Exclude:

- `*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.webp`
- `*.zip`, `*.rar`, `*.7z`, `*.tar`, `*.gz`
- `REVIEW_EXPORT/`, `REVIEW_EXPORT_VERIFY/`, `REVIEW_PACKAGE*/`
- `P0_REVIEW_EXPORT/`, `P0_REVIEW_VERIFY/`
- `mailru-mvp-backup-20260829/`
- `_archive/source-uploads/FrontSAAS.rar`
- `_archive/source-uploads/Inbox.zip`
- any directory or file named as a backup, snapshot or export

Reason: generated/review copies are not a canonical source and may include
secrets, personal data or duplicated code.

## H — personal or unknown material

Exclude until owner review:

- `Documents/`
- one-off root artifacts and files whose provenance is not verified
- any untracked file not explicitly admitted by the owner-approved allowlist

The current uncommitted paths are not called `pre-existing` as a fact. Their
provenance is `UNKNOWN` / `NOT VERIFIED`.

## A/B/C/E — paths outside the explicit manifest

The following current changed path classes remain denied unless they are named
by the current explicit manifest, even if their extensions look like source or
documentation:

- application source under `api/`, `mail/`, `frontend/src/`, root Python files,
  `migrations/`, `fixtures/` and `supplier_discovery_v2/`;
- tests under `tests/` and `frontend/tests/`;
- configuration such as `.gitignore`, `.vercelignore`, `vercel.json`,
  `requirements.txt` and frontend configs;
- ordinary root/docs Markdown reports and deleted tracked documents.

Action: `EXCLUDE` / `UNKNOWN`, not automatic inclusion.

## Current blocked inventory

At the inventory snapshot before this task's four new safety documents:

- `66` modified tracked paths;
- `6` deleted tracked paths;
- `599` untracked paths;
- `0` staged paths;
- `677` unique paths.

After creating the safety documents, the new files themselves are AI
documentation pending the same final scan; no file was staged.

## Release gate

Nothing on this denylist may be staged or pushed. The current task may stage
only the separately maintained explicit manifest after its final scan. A secret
in that manifest or Git history remains a hard blocker.
