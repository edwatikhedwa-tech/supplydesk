---
document_id: HANDOFF-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: d4d2b2ab2457e3aa103f80120642bff4bc72920f
---

# Last Handoff

## Цель

Выполнить первую физическую очистку legacy SupplyDesk с отдельной canonical
копией, retained quarantine и без потери уникальных рабочих изменений.

## Что изменено

- Создан fresh canonical checkout вне legacy OneDrive и локальная ветка
  `control/safe-cleanup-batch1-20260901` от проверенного remote HEAD.
- До действий создан before-manifest; после действий — after-manifest.
- Удалены только 308 regeneratable/cache файлов; 1,481 review/backup/export/
  historical-local файл перемещён во внешний retained quarantine.
- `.env*`, canonical DB, `mail-data`, runtime, credentials, mail evidence,
  product source и unknown-review items оставлены.
- Legacy marker объявляет старую папку `DO_NOT_USE_FOR_DEVELOPMENT`.

## Что проверено

- `git ls-remote` confirmed controlled HEAD `d4d2b2ab2457e3aa103f80120642bff4bc72920f`;
  audit branch was confirmed at `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`.
- Backend full: `411` tests, `0` failures, `0` errors, `1` skipped; diagnostics
  `25/25`; frontend install/typecheck/lint/build passed, lint has 8 warnings.
- Safe HTTP smoke returned `200/200/401/401/404`; real-route Playwright `8/8`;
  Doctor OFFLINE_TEST Full `PASS`, exit `0`.
- All validators and `git diff --check` passed. Test runtime used disposable
  SQLite and was stopped by its marker-aware stop script.
- Physical delete/move targets and quarantine destinations were verified;
  no application source, database, migration, env or mail data was changed.
- Initial cleanup evidence commit `26e779c` and final closeout commit
  `e369429` were pushed normally to
  `origin/control/safe-cleanup-batch1-20260901` after one transient DNS failure;
  the final remote ref was verified.

## Что не прошло

No required offline acceptance item is blocked. `.gitignore` corrections and
the three unknown legacy items remain review-required; live external providers,
real SMTP/IMAP, real email and production migrations remain intentionally
unverified.

## Что не проверено

Canonical database rows, mailbox/provider state, live external acceptance,
production migration behavior, `knip`, `.gitignore` safe correction and the
ownership of the three source-checkout unknowns remain `NOT VERIFIED`.

## Текущее состояние runtime

The app was started only through `OFFLINE_TEST`, checked on real routes, and
stopped after acceptance. External provider actions were not performed. The
runtime marker and Doctor profile checks make the safety boundary explicit.
The legacy checkout is not a development source; the canonical checkout and
verified remote control branch are the source of truth.

## Следующий рациональный шаг

Review retained quarantine and the three unknown items in a separate task;
permanent purge is not part of Batch 1 and no merge/default-branch change is
performed automatically.

## Не повторять

Не использовать legacy OneDrive checkout для разработки; не читать секреты;
не удалять quarantine навсегда; не запускать real mail actions.
