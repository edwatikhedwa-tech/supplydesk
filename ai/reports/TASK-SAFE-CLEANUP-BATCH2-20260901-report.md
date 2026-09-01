# SupplyDesk Safe Cleanup Batch 2 — Canonical Deep Hygiene

Status: `PASS_WITH_LIMITATIONS`

Date: `2026-09-01`

This report uses `<CANONICAL_WORKSPACE>`, `<LEGACY_WORKSPACE>` and
`<QUARANTINE_ROOT>` instead of personal absolute paths. The quarantine is an
external local retention area and was not added to Git.

## Сделано

- Verified the remote Batch 1 base and worked only from the canonical checkout
  on branch `control/safe-cleanup-batch2-20260901`.
- Corrected the proven unsafe broad `.gitignore` rules in commit `0585275`.
- Moved the three resolved legacy unknown items to external quarantine after a
  fresh reference/process/hash check.
- Removed only the approved proven Python dead bindings in separate commit
  `d2ceef3`: 18 unused imports and 2 side-effect-free dead assignments.
- Re-ran the current canonical duplicate audit and kept both duplicate groups.
- Retained frontend candidates and the direct `lighthouse` dependency because
  the approved allowlist covered Python cleanup only and the remaining
  references may be manual/operator surfaces.

## Простыми словами

Рабочая копия теперь не зависит от старых файлов в OneDrive. Три старых
артефакта не уничтожены, а убраны во внешний обратимый карантин. Из Python
убраны только строки, которые не влияли на поведение. Два набора одинаковых
служебных файлов оставлены, потому что они обслуживают разные каталоги.

## Physical result

### Permanently deleted

- Canonical files: `0`.
- Product source files: `0`.
- Environment files: `0`.
- Database or mail evidence: `0`.
- Permanent quarantine purge: `NO`.

Batch 2 made no physical permanent deletion. The Python cleanup deleted only
dead source bindings, not application files.

### Moved to quarantine

- Legacy unknown files: `3` files, `43,845` bytes.
- Destination: `<QUARANTINE_ROOT>/05_UNKNOWN_REVIEW/`.
- Post-move quarantine retained total including its manifests: `1,486` files,
  `132,751,586` bytes.
- Existing Batch 1 review/backup/export quarantine was not purged or rewritten.

The three post-move hashes are recorded in
[`CLEANUP_BATCH2_MANIFEST.csv`](CLEANUP_BATCH2_MANIFEST.csv). The source paths
are absent and the quarantine copies match their pre-move SHA-256 values.

### Unknown review resolution

`UNKNOWN_REVIEW` changed from `3` to `0` in the canonical source-of-truth
classification. This means all three items received a decision; it does not
mean their contents were deleted. They remain retained under quarantine.

- `.agents/skills/neon/SKILL.md`: local stale agent artifact; no canonical or
  global owner was found. `skills-lock.json` is only a lock reference and does
  not prove that this local file is an active SupplyDesk dependency.
- `keywords.txt`: historical Test 1.1 input; only historical documentation and
  CLI examples refer to the name, with no active test/runtime invocation.
- `run_probe.py`: older root predecessor; canonical
  `supplier_source_tests/run_probe.py` is richer and separately owned. The
  different hashes were not merged.

## Duplicate audit

Current canonical tree: `387` tracked files hashed, `2` exact duplicate groups,
`4` files in those groups, `0` deletions.

- `ai/inbox/.gitkeep` and `ai/reports/.gitkeep` preserve different empty
  control-plane directories.
- `supplier_discovery_v2/tests/__init__.py` and `tests/__init__.py` preserve
  different Python test package roots.

Detailed evidence is in
[`CANONICAL_DUPLICATES_BATCH2.md`](CANONICAL_DUPLICATES_BATCH2.md).

## Python dead-code audit

Candidate tools were used only as candidate generators. Vulture produced 54
low-confidence or dynamic candidates. Ruff initially reported 18 unused
imports and 11 unused-variable candidates. Manual reference, callback, CLI,
provider and side-effect review accepted only:

- `18` unused imports;
- `2` side-effect-free dead assignments: one unused exception binding and one
  unused literal mapping assignment.

The remaining `9` Ruff `F841` candidates stay in place because their right-hand
side calls create fixtures, perform state transitions or are part of test/API
contracts. HTTP callbacks, CLI surfaces, provider adapters, migration-facing
methods and dataclass fields reported by Vulture were also retained.

Focused verification passed before the separate Python commit. The full
regression remained green afterward.

## Frontend and dependency audit

Knip was run from the clean installed frontend dependency state without
modifying repository files. It reported:

- `lighthouserc.cjs` — kept as manual Lighthouse CI configuration;
- `playwright.live-email.config.ts` — kept as manual live-mail acceptance
  configuration;
- `playwright.real-email.config.ts` — kept as manual real-mail diagnostic
  configuration;
- `src/components/suppliers/RiskFactors.tsx` — retained as `REVIEW_REQUIRED`
  because it is canonical UI source even though no current import was found;
- direct dev dependency `lighthouse` — retained because the approved cleanup
  allowlist did not authorize frontend dependency removal and `@lhci/cli`
  carries its own dependency path.

Frontend files deleted: `0`. Frontend dependencies removed: `0`. Python runtime
dependencies removed: `0`.

## `.gitignore`

Status: `PASS`.

- Before correction, `14` project-owned JSON/CSV files were hidden by broad
  extension rules outside generated/vendor/runtime trees.
- After correction, hidden project-owned JSON/CSV files: `0`.
- Environment files, database paths, runtime data and generated outputs remain
  ignored.
- Product fixtures, benchmarks, documentation CSV/JSON, manifests,
  `skills-lock.json` and `vercel.json` are no longer hidden by broad extension
  rules.
- `.env.example` remains ignored because the current publish denylist has not
  confirmed it as placeholder-only. No `.env.example` was created or exposed.

## Acceptance evidence

All checks below ran against the canonical workspace after the Python cleanup;
the safe runtime used disposable SQLite, fake/blocked providers and loopback
network only.

| Check | Result |
|---|---|
| Backend full regression | `412 tests, 0 failures, 0 errors, 1 skipped` |
| Diagnostics | `26/26 PASS` |
| `npm ci` | `PASS`, 822 packages installed |
| Typecheck | `PASS` |
| Lint | `PASS`, 0 errors and 8 existing warnings |
| Build | `PASS` |
| HTTP smoke | `/` 200, `/api/auth/me` 200, protected route 401, unknown route 404 |
| Playwright real routes | `8/8 PASS` across desktop, tablet and mobile |
| Doctor `OFFLINE_TEST -Full` | `PASS`, exit `0` |
| Documentation validator | `PASS`, GATE-001..009 |
| State validator | `PASS` |
| Traceability validator | `PASS`, TRACE-001..013 |
| `git diff --check` | `PASS` |

The backend total increased from 411 to 412 solely because the approved
`.gitignore` guardrail added one diagnostic test. There were no failures or
errors and the expected PostgreSQL skip remained one.

## Safety gates

- Active runtime/test references to quarantined legacy paths: `0`.
- Remaining references are historical, audit, publish or example references;
  none is an active runtime dependency.
- Canonical application behavior, routes, API, UI, migrations, database and
  mail settings were not changed.
- Real SMTP/IMAP connections and real email were not used.
- Canonical database was not opened, moved, modified or deleted.
- Quarantine contents were not staged and were not published.
- The legacy workspace remains marked `DO_NOT_USE_FOR_DEVELOPMENT`.

## Rollback

- Python cleanup: revert commit `d2ceef3` only.
- `.gitignore` correction: revert commit `0585275` only.
- Legacy unknowns: move the three exact SHA-verified files back from
  `<QUARANTINE_ROOT>/05_UNKNOWN_REVIEW/` only after a separate owner review.
- Do not restore or purge the entire quarantine as a rollback shortcut.

## Remaining limitations

- Live providers, real SMTP/IMAP, real email and production database behavior
  remain intentionally unverified.
- `RiskFactors.tsx`, three manual frontend configs and the direct `lighthouse`
  dev dependency remain review candidates, not deletions.
- The external quarantine remains retained and requires a separate approval for
  any permanent purge.

## Closeout

REMOTE REPORT PUSH: `YES`; the report is included in the pushed control branch
and the remote ref was independently verified at closeout.

Branch: `control/safe-cleanup-batch2-20260901`

Source of truth after closeout: the pushed control branch plus
`<CANONICAL_WORKSPACE>`. The legacy OneDrive checkout is recovery-only.
