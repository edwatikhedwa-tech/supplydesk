---
document_id: HANDOFF-013
status: CURRENT
canonical: false
owner: Claude
updated_at: 2026-09-03
based_on_commit: 6af2af1822820e996f1126b8a1b26d19be0000f0
---

# Last Handoff

This handoff records two pieces of work done under one owner instruction
("почини, а потом продолжи рефакторинг!"): (1) a root-cause fix for the
`Backend Full` `CI_INFRA` timeout, and (2) bounded root-refactor Pass 7 —
the search-integrations move (`web_lookup.py`, `xmlriver_client.py` →
`backend/integrations/search/`).

## Цель

1. «Почини»: root-cause, а не просто повторно поднять timeout, причину
   стабильного `CI_INFRA`-таймаута `Backend Full`.
2. «Продолжи рефакторинг»: перенести следующий подтверждённый
   `MOVE_INTEGRATIONS`-батч из диагностического отчёта в
   `backend/integrations/search/`, обновить всех подтверждённых
   consumers, не меняя бизнес-логику.

## Что изменено

### Часть 1 — CI_INFRA fix (отдельный коммит `6af2af1`, уже опубликован)

- Проанализированы timestamp-дельты между стартами тестов в логах трёх
  предыдущих неудачных прогонов `Backend Full` — замедление сосредоточено
  в `tests/test_mail_deliverability.py`/`tests/test_mail_integrity.py`
  (много мелких SQLite/`tempfile` операций), `7`-`60s` на CI против
  sub-second локально.
- Добавлен best-effort шаг `Add-MpPreference -ExclusionPath` (workspace +
  `RUNNER_TEMP` + `TEMP`) только в job `backend_full`, сразу после
  workspace guard. Таймаут (`35` минут) не менялся дальше.

### Часть 2 — search-integrations move (этот коммит)

- `web_lookup.py` и `xmlriver_client.py` перенесены в
  `backend/integrations/search/` (оба — 0-diff pure move).
- Обновлены 6 подтверждённых consumers: `supplier_app.py`,
  `collect_inn.py` (lazy), `scripts/collect_contacts.py` (lazy),
  `test_extractor.py`, `serp_parser.py` (только строка импорта — сам файл
  остаётся `DEFER`red), `test_parser.py`.
- `supplier_discovery_v2/immutability_check.py`: protected-path список
  мигрирован для обоих файлов.
- `supplier_discovery_v2/tests/test_immutability.py`: +2 постоянных теста.
- `docs/architecture/REPOSITORY_LAYOUT.md`, `CLAUDE.md`: обновлены.
- Добавлен
  `ai/reports/TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903-report.md`.

## Что проверено

- Workspace Guard passed до lock и до мутации.
- Fresh full-tree reference scan нашёл все 6 реальных consumers.
- `git diff --cached -M --stat` структурно доказал `0 insertions(+), 0
  deletions(-)` для обоих файлов.
- Отдельно подтверждено: `supplier_discovery_v2/xmlriver_subprocess.py` не
  затронут — вызывает нетронутый `serp_parser.py` по абсолютному пути
  через `subprocess.run(cwd=...)`.
- Offline import chain: оба новых модуля, `serp_parser`, `collect_inn`,
  `supplier_app`, `api.index` под `SUPPLYDESK_ENV=test` — все `OK`. CLI
  `--help` byte-identical до/после для `collect_contacts.py`.
- Immutability: свежий baseline на реальном дереве → `[]`; disposable
  synthetic-copy мутация каждого из 2 путей → обнаружена индивидуально.
  Закреплено `7/7 PASS` постоянными тестами.
- Поведенческие тесты: `test_extractor.py`/`test_parser.py`
  (custom-скрипты, "Все проверки пройдены", exit `0`);
  `tests.test_enrichment_pipeline` (`8/8`); полный
  `supplier_discovery_v2/tests/` (`18/18`); официальный backend suite
  (`462 tests, failures=0, errors=9 pre-existing pwsh gap, skipped=1`).
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`,
  `ai/tools/validate_vibecoding.py`: `PASS`. `git diff --cached --check`:
  `PASS`.
- Diff отсканирован на секреты: совпадений не найдено. `0`
  provider/SMTP/DNS вызовов.

## Что не прошло

Ничего из финально применённого не провалилось.

## Что не проверено

NOT VERIFIED: реальный Vercel build/deploy. NOT VERIFIED:
недокументированный внешний Python-импорт `web_lookup`/`xmlriver_client`.
Результат `workflow_dispatch profile=FULL` верификационного прогона
(`33690006924`) для CI_INFRA-фикса фиксируется отдельно из фактического
CI-вывода, не предполагается заранее.

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — `14` затронутых файлов, в пределах
ожидаемого диапазона по причинно-связанной автономной политике владельца.

## Текущее состояние runtime

Runtime для этой задачи не запускался. Ни одного provider-вызова, real
mail или записи в canonical database не произошло.

## Следующий рациональный шаг

`backend/{integrations/{registry,llm,search},domain/supplier_identity}/`
теперь содержат 10 перенесённых модулей. Оставшиеся корневые модули —
`supplier_app.py`, `api/index.py` (`KEEP_ROOT`, не переносить),
`serp_parser.py` (`DEFER`, требует явного subprocess/deployment решения),
`contact_crawler.py`/`collect_inn.py` (`MOVE_DOMAIN_PACKAGE`, High risk,
требует разделения pipeline/CLI) — каждый требует отдельной bounded задачи
с явными контрактами; ни одна не авторизована этим изменением.

## Не повторять

Не использовать legacy OneDrive checkout для разработки, не выводить и не
сохранять значения секретов, не запускать реальную почту или live
provider-вызовы, не поднимать `Backend Full` timeout повторно без нового
подтверждённого root cause, при staging большого списка файлов — стейджить
по одному пути (`git add -- <path>`), а не одним общим `git add -A --
<list>`, если хотя бы один путь мог быть уже переименован (см. инцидент из
задачи Pass 6), и не добавлять второе подтверждение VibeCoding в
промежуточное сообщение.
