# TASK-PYTHON-ROOT-DIAGNOSTIC-20260902

`DELIVERY_MODE: PUBLISH_REPORT_ONLY`

## Итог

`ROOT_DIAGNOSTIC: COMPLETE` — [CONFIRMED] проведён один read-only аудит
Python-кода и структуры root в текущем checkout `C:\Users\edwat\SupplyDesk`.
Создана decision-ready карта для следующего bounded refactor. Product-код,
imports, dependencies, runtime data, database, deployment и root structure не
изменялись.

Главное решение: root сейчас содержит не только backend entrypoint, но и
исторически сложившийся flat-пакет supplier-discovery. Его можно разделить по
семантическим границам, однако это не cleanup и не безопасная массовая
перестановка: runtime-модули связаны с `supplier_app.py`, `mail/repository.py`,
тестами и subprocess-путём discovery v2.

## Цель, контекст и границы

- **Цель:** определить, что является root entrypoint, backend core,
  integrations, operator tooling, tests, legacy/review surface и кандидатом на
  следующий bounded refactor.
- **Контекст:** текущая ветка `audit/frontend-knip-20260902`, HEAD
  `a6916769ea4b55eefc725a59bfc0e25474368737` на момент preflight.
- **Ограничения:** только чтение; не выполнялись product tests, backend,
  frontend, browser, provider calls, real mail, migrations и database writes.
- **Готово когда:** каждый root `*.py` и каждый meaningful tracked top-level
  directory получил решение, entrypoint chain проверена, analyzer findings
  сведены с ручными доказательствами, а Pass 2 описан без его выполнения.

## Preflight и текущий checkout

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS`; реальный Git root — `C:\Users\edwat\SupplyDesk` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` / `a6916769ea4b55eefc725a59bfc0e25474368737` |
| Рабочее дерево до Task lock | [CONFIRMED] чистое; после старта изменён только `ai/ACTIVE_TASK.md` как lock |
| Tracked files | [CONFIRMED] `419` |
| Tracked root objects | [CONFIRMED] `30` файлов и `16` директорий, всего `46` объектов |
| Untracked files | [CONFIRMED] `0` |
| Ignored files | [CONFIRMED] `52,881`; это кэши, `.venv-test`, `node_modules`, dist и runtime/local data, не кандидаты на удаление |
| `git clean -n` | [CONFIRMED] ничего не предлагает |
| Python processes | [CONFIRMED] после остановки внешнего scanner-а Python-процессов нет |
| Relevant listeners | [CONFIRMED] портов `8000`, `5173`, `18000`, `6006` в Listen не обнаружено |
| Protected local paths | [CONFIRMED] `runtime/`, `runtime/test-data/`, `frontend/node_modules/`, `frontend/dist/`, `__pycache__/`, `.ruff_cache/`, `.venv-test/` присутствуют; `.env`, `mail-data/`, `Temp/`, `artifacts/` отсутствуют |
| Legacy checkout | [CONFIRMED] не открывался и не использовался |

Старый `FINAL_CANONICAL_INVENTORY.md` сообщал `45` root objects на другом
срезе. Для этого отчёта использован свежий `git ls-tree HEAD`, поэтому текущим
считается `46`.

## Protected entrypoint review

### `BACKEND_ENTRYPOINT`

`supplier_app.py` — [CONFIRMED] локальный backend entrypoint:

- `supplier_app.py:2517-2533` загружает `.env`, создаёт `Config`, создаёт
  `SupplierApp` и вызывает `run()`;
- `supplier_app.py:2500-2514` поднимает `ThreadingHTTPServer` и обслуживает
  application handler;
- `supplier_app.py:30-52` импортирует текущий search/enrichment pipeline и
  mail package;
- `CLAUDE.md` и `PROJECT_MANIFEST.yaml` называют его backend source of truth.

### `SERVERLESS_ENTRYPOINT`

`api/index.py` — [CONFIRMED] Vercel adapter:

- `vercel.json:7-14` маршрутизирует весь HTTP-трафик в `/api/index.py`;
- `api/index.py:15-24` добавляет project root в `sys.path` и импортирует
  `supplier_app.Config`, `SupplierApp`, `SupplierHandler` и `load_dotenv`;
- `api/index.py:44-54` создаёт `_APP` и экспортирует `handler`, унаследованный
  от `SupplierHandler`.

### `ROOT_MOVE_SAFE`

`NO` — [CONFIRMED]. Перенос `supplier_app.py` сейчас не доказан безопасным:
он требует одновременно изменить Vercel import boundary, локальный
`python supplier_app.py`, абсолютный импорт из `api/index.py`, test imports,
operator scripts и включение файлов deployment bundle. В этом task перенос не
предлагается.

Code Rot Cleaner отдельно пометил `api/index.py` как orphan, потому что его
консервативный scanner не считает `api/index.py` Python convention root.
Deployment route и exported `handler` — более сильное evidence, поэтому это
`FALSE_POSITIVE`, а не кандидат на удаление.

## Root Python decision table

[CONFIRMED] AST/import inspection обработал `107` tracked Python files, без
parse errors, и построил `243` resolved local import edges. Статических
circular-import cycles не найдено. Dynamic imports, subprocesses и script-local
`sys.path` conventions проверены отдельно и не считаются покрытыми одним AST.

| Path | Current role | Evidence | Decision | Proposed target | Risk | Confidence |
|---|---|---|---|---|---|---|
| `benchmark_models.py` | Operator benchmark CLI | `argparse`, `main`, `__main__`; no inbound AST import; historical/manual CLI refs; Code Rot `CRT-632` | `MOVE_SCRIPTS` | `benchmarks/benchmark_models.py`; preserve root command only with an explicit compatibility wrapper | Medium — changes CLI path/cwd and model-cache assumptions | Medium |
| `checko_client.py` | Backend registry/finance integration | Imported by `supplier_app.py`, `scripts/verify_enrichment_live.py`, `tests/test_enrichment_pipeline.py`; HTTP client | `MOVE_INTEGRATIONS` | `backend/integrations/registry/checko_client.py` | High — runtime and test import paths | High |
| `collect_contacts.py` | Manual contact-collection CLI | `argparse`, `main`, `__main__`; no inbound AST import; Code Rot `CRT-633`; only current manifest/inventory name refs, user-facing docs are historical | `MOVE_SCRIPTS` | `scripts/collect_contacts.py` | Medium — direct invocation and root import path | High |
| `collect_inn.py` | Product enrichment pipeline plus CLI | Imported by `supplier_app.py`, `scripts/verify_enrichment_live.py`, `tests/test_enrichment_pipeline.py`; also has CLI | `MOVE_DOMAIN_PACKAGE` | Extract reusable pipeline to `backend/domain/supplier_enrichment/`; leave `scripts/collect_inn.py` as an explicit CLI wrapper | High — app/tests/scripts depend on it | High |
| `contact_crawler.py` | Supplier-site crawler and contact enrichment | Imported by app, collection modules, benchmark, live verifier and tests; requests, robots, DNS and bounded PDF fetch | `MOVE_DOMAIN_PACKAGE` | `backend/domain/supplier_enrichment/contact_crawler.py` | High — network behavior and `SiteResult` contract | High |
| `dadata_client.py` | Registry integration | Imported by `collect_inn.py`; HTTP POST/registry token boundary | `MOVE_INTEGRATIONS` | `backend/integrations/registry/dadata_client.py` | High — import chain and external provider boundary | High |
| `email_extractor.py` | Supplier identity/contact domain logic | Imported by app, crawler, resolver, LLM fallback, verifier, web lookup and root tests; fixture-tested extraction | `MOVE_DOMAIN_PACKAGE` | `backend/domain/supplier_identity/email_extractor.py` | High — many callers; contains `root_domain` bridge to search parser | High |
| `inn_extractor.py` | Supplier identity/legal-ID domain logic | `12` inbound AST importers including app, mail repository, resolver, LLM fallback and tests | `MOVE_DOMAIN_PACKAGE` | `backend/domain/supplier_identity/inn_extractor.py` | High — mail and enrichment callers | High |
| `inn_resolver.py` | Supplier identity resolution | Imported by app, live verifier and enrichment tests; resolves legal IDs, names and domains | `MOVE_DOMAIN_PACKAGE` | `backend/domain/supplier_identity/inn_resolver.py` | High — app flow and provider-backed semantics | High |
| `llm_fallback.py` | LLM-backed enrichment fallback | Imported by app, collection CLIs and benchmark; lazy-imports `RouterAiClient` | `MOVE_INTEGRATIONS` | `backend/integrations/llm/llm_fallback.py` | High — provider cost/config and output contract | High |
| `routerai_client.py` | RouterAI provider client | Imported by `llm_fallback.py` and benchmark; external HTTP/cost boundary | `MOVE_INTEGRATIONS` | `backend/integrations/llm/routerai_client.py` | High — provider config and benchmark imports | High |
| `serp_parser.py` | Search integration, backend collector and CLI | Imported by app and enrichment modules; `supplier_discovery_v2/xmlriver_subprocess.py:18` resolves its exact root path; has CLI | `DEFER` | Future `backend/integrations/search/serp_parser.py` only after subprocess and deployment path contract | High — root path is part of an explicit isolation boundary | High |
| `supplier_app.py` | Backend application, HTTP routes, auth and local server | Local `__main__`, Vercel adapter import, startup runbook, scripts and tests | `KEEP_ROOT` | None | Critical — local and serverless entrypoint | High |
| `test_extractor.py` | Standalone manual extractor check | Custom `check()`/`main()`; no `unittest.TestCase`; not in official runner; historical direct command | `DEPRECATED_REVIEW` | No move until owner chooses discovery policy; possible `tests/legacy/` later | Medium — moving may alter discovery/import behavior | High |
| `test_inn.py` | Standalone manual INN check | Custom `check()`/`main()`; no official runner membership; historical direct command | `DEPRECATED_REVIEW` | No move until explicit legacy-test contract | Medium — discovery behavior | High |
| `test_parser.py` | Standalone manual parser check | Custom checks and `FakeClient`; no official runner membership; historical direct command | `DEPRECATED_REVIEW` | No move until explicit legacy-test contract | High — parser/network boundary and discovery behavior | High |
| `test_verify.py` | Standalone manual verification check | Custom `check()`/`main()`; no official runner membership; imports `verify` | `DEPRECATED_REVIEW` | No move until explicit legacy-test contract | Medium — discovery behavior | High |
| `verify.py` | Email/INN/domain ownership domain verifier | Imported by app, `collect_contacts.py` and root test; contains optional DNS/SMTP probe | `MOVE_DOMAIN_PACKAGE` | `backend/domain/supplier_identity/verify.py` | High — external probe and supplier ownership semantics | High |
| `web_lookup.py` | Search fallback/enrichment orchestration | Imported by app, collection CLIs, resolver and root test; composes XMLRiver/LLM/extractors | `MOVE_INTEGRATIONS` | `backend/integrations/search/web_lookup.py` | High — cross-layer orchestration and provider costs | High |
| `xmlriver_client.py` | XMLRiver transport client | Imported by app, parser, collection CLIs, web lookup, source probe and tests | `MOVE_INTEGRATIONS` | `backend/integrations/search/xmlriver_client.py` | High — external transport and subprocess boundary | High |

`MOVE_CANDIDATES` здесь означает предложение для Pass 2, а не разрешение на
перемещение. `DELETE_CANDIDATE: 0`: ни один файл не прошёл multi-signal
threshold. В частности, отсутствие inbound import не отменяет CLI,
subprocess, framework, documentation или external-consumer role.

## Root directory classification

[CONFIRMED] Reviewed all `16` tracked top-level directories. Local ignored
directories are listed separately as protected local data and are not semantic
repository areas.

| Directory | PURPOSE | CURRENT_ROLE | Decision | WHY / EVIDENCE | RISK_OF_MOVE | TARGET_LOCATION |
|---|---|---|---|---|---|---|
| `.github/` | CI workflow | Control/build automation | `KEEP` | Workflow maps source paths to verification profiles | High | None |
| `Documents/` | Historical product/operator documentation | `HISTORICAL — NOT CURRENT` support archive; excluded from Vercel | `DEFER` | Existing files preserve chronology and are explicitly not current-state source | Medium | None in this task |
| `ai/` | Agent control, state, reports and validators | Operational control plane | `KEEP` | Referenced by adapters, validators and task workflow | High | None |
| `api/` | Serverless adapter | Vercel entrypoint | `KEEP` | `vercel.json` routes all requests to `api/index.py` | Critical | None |
| `benchmarks/` | Reproducible benchmark inputs | Runtime-independent benchmark data | `KEEP` | `enrichment_cases.json` is the current fixture source | Low | None |
| `docs/` | Product/architecture/operations documentation | Current supporting documentation | `KEEP` | Owns product docs; links to canonical `ai/CURRENT_STATE.md` | Medium | None |
| `fixtures/` | Seed and enrichment fixtures | Backend/runtime test input | `KEEP` | `supplier_app.load_fixture_data` and benchmark references | High | None |
| `fonts/` | Required UI assets | Deployment asset | `KEEP` | Explicitly included by `vercel.json` | High | None |
| `frontend/` | React/Vite client and browser tests | Product frontend | `KEEP` | Current SPA/build boundary; frontend out of this audit | High | None |
| `mail/` | Mail domain, repository, queue and providers | Backend core package | `KEEP` | Imported by app; schema/persistence and safety contracts depend on it | Critical | None |
| `migrations/` | Versioned SQL schema | Runtime schema source | `KEEP` | `mail/repository.py` loads sorted `migrations/*.sql` | Critical | None |
| `scripts/` | Operator, diagnostic and test-runtime tools | Canonical tooling area | `KEEP` | Manifest and runner explicitly own this directory | High | None |
| `supplier_discovery_v2/` | Isolated supplier discovery pilot | Active importable package with own CLI/tests | `KEEP` | `python -m supplier_discovery_v2.run`; its boundary intentionally subprocesses root parser | Critical | None; do not merge with legacy pipeline here |
| `supplier_source_tests/` | Read-only source/provider probe | Manual test/operator surface | `KEEP` | Own README, source matrix and direct `run_probe.py` entrypoint; local `sources` import | High | None |
| `tests/` | Official Python test suites | Standard unittest runner scope | `KEEP` | `scripts/run_test_suite.py` explicitly discovers `tests/` and v2 tests | Critical | None |
| `work/` | Retained task artifact | Legacy layout/supporting work record | `DEFER` | Current tracked file is a completed documentation task; no product import role | Medium | None |

Root non-Python files remain `KEEP_ROOT`: agent entrypoints, manifests,
requirements, deployment config, `.gitignore`, `skills-lock.json` and
`stop_domains.txt`. No new `REPOSITORY_LAYOUT.md` is created because this task
does not execute a root refactor.

## Practical import/reference map

### Backend runtime group

[CONFIRMED] `supplier_app.py` is the composition root for the current legacy
enrichment path. It imports `checko_client`, `collect_inn`, `contact_crawler`,
`email_extractor`, `inn_extractor`, `inn_resolver`, `llm_fallback`,
`serp_parser`, `verify`, `web_lookup` and `xmlriver_client`, plus `mail/*`.
`api/index.py` imports only the app entrypoint directly.

### Domain group

[CONFIRMED] `email_extractor`, `inn_extractor`, `inn_resolver` and `verify`
form the identity/ownership logic used by the app, enrichment tests and some
operator tools. `contact_crawler` and the reusable part of `collect_inn` form
the supplier-enrichment pipeline. `mail/repository.py` also imports
`inn_extractor.validate_inn_checksum`, so this group is not isolated from mail.

### Integration group

[CONFIRMED] `checko_client` and `dadata_client` are registry adapters;
`routerai_client` and `llm_fallback` are LLM/provider adapters;
`xmlriver_client`, `serp_parser` and `web_lookup` are search/fallback adapters.
They are not unused just because some calls are lazy or conditional.

### Operator/test group

[CONFIRMED] `benchmark_models.py` and `collect_contacts.py` are standalone
operator CLIs with no resolved inbound imports. `scripts/verify_enrichment_live.py`
is an explicit live verification tool. `scripts/run_test_suite.py` owns the
official unittest suite and includes only `tests/` plus
`supplier_discovery_v2/tests/`; it does not include root `test_*.py`.

### Explicit non-import boundary

[CONFIRMED] `supplier_discovery_v2/xmlriver_subprocess.py:18-38` launches the
root `serp_parser.py` by path, with output files in the v2 output directory.
`supplier_discovery_v2/README.md` explicitly says the existing parser is not
imported or modified. This is a deliberate boundary, not an orphan reference.

### Suspicious directions

1. [CONFIRMED] `supplier_app.py` imports the CLI-named `collect_inn.py` and
   `serp_parser.py`; this is mixed responsibility, not proof of a bug. Pass 2
   should extract library modules while preserving CLI wrappers.
2. [CONFIRMED] `email_extractor.root_domain()` lazily imports
   `serp_parser.root_domain_of()`, so domain extraction depends on a search
   parser. This is a strong candidate for a small domain-boundary change inside
   the larger refactor, not a deletion signal.
3. [CONFIRMED] Several scripts add the repository root to `sys.path` before
   importing flat root modules. Moving modules requires a package/import
   contract, not a filesystem-only move.
4. [CONFIRMED] `supplier_source_tests/run_probe.py` imports local `sources` as a
   script sibling. The AST resolver did not resolve that edge because it is
   path-sensitive; manual inspection retained both files.

### Circularity result

[CONFIRMED] No cycles were found in the resolved AST graph. [NOT VERIFIED]
Reflection, runtime `importlib`, environment-selected modules and all external
consumer imports were not exhaustively proven absent.

## Code Rot Cleaner

`CODE_ROT_CLEANER: USED_REPORT_ONLY`.

[CONFIRMED] The installed `code-rot-cleaner` skill and bundled analyzer were
used without `prove` or `apply-approved`. Outputs were written outside the
repository to:

`C:\Users\edwat\AppData\Local\Temp\SupplyDesk-code-rot-20260902\`

The analyzer scanned `3,249` source files (`839,922` LOC / `35,564,692` bytes)
because its source walk includes `.venv-test` unless the directory is named
exactly `.venv`; it excludes `node_modules`, dist, caches and other configured
directories. It reported `767` candidates: `699` orphan files, `63` duplicate
files, `4` unused exports, `0` unused dependencies and `1` commented-code
block. `76` were marked proof-eligible by the scanner, but no proof ran.

The tracked/relevant subset was manually reviewed:

| Candidate | Initial analyzer result | Manual result |
|---|---|---|
| `CRT-632` `benchmark_models.py` | Orphan, medium confidence, medium risk | `REVIEW`; operator CLI and historical/manual usage; move candidate, not delete |
| `CRT-633` `collect_contacts.py` | Orphan, medium confidence, medium risk | `REVIEW`; operator CLI; move candidate, not delete |
| `CRT-631` `api/index.py` | Orphan, medium confidence, medium risk | `KEEP`; Vercel route/exported handler false positive |
| `CRT-697` `supplier_discovery_v2/run.py` | Orphan, high confidence, low risk | `KEEP`; `python -m` package entrypoint false positive |
| `CRT-698`/`CRT-699` source-test files | Orphan candidates | `KEEP`; direct manual entrypoint and script-local import |

The scanner output is candidate evidence only. It did not execute product code,
project commands or dependency installation. No candidate is `SAFE TO REMOVE`.

## Ruff and Vulture

- `RUFF: NOT_AVAILABLE_FOR_THIS_AUDIT` — `python -m ruff --version` returned
  `No module named ruff`; no install and no project dependency/config change
  was attempted.
- `VULTURE: NOT_AVAILABLE_FOR_THIS_AUDIT` — `python -m vulture --version`
  returned `No module named vulture`; no install was attempted.

Existing Ruff cache presence was not treated as proof that Ruff is installed or
that its result is current. Native AST, reference search, existing project
reports and Code Rot Cleaner were sufficient to continue the report-only pass.

## Multi-signal dead-code decision

`DELETE_CANDIDATES: 0` — [CONFIRMED]. No item has all required signals:

- no inbound import;
- no string/config/route reference;
- no entrypoint, operational or test-discovery role;
- no dynamic/framework convention;
- independent analyzer agreement;
- history compatible with removal.

`benchmark_models.py` and `collect_contacts.py` fail the deletion threshold
because they are executable operator surfaces with documented/manual intent.
Root `test_*.py` fail it because they are standalone checks whose discovery
contract is not the official runner and whose historical use is not disproven.
`api/index.py`, v2 `run.py` and source-test files fail it by explicit entrypoint
evidence.

## Test file classification

| Path/group | CURRENT_DISCOVERY_STATUS | Role | RECOMMENDATION |
|---|---|---|---|
| `tests/` | [CONFIRMED] Discovered by `scripts/run_test_suite.py` | Active automated unittest suite | `KEEP` |
| `supplier_discovery_v2/tests/` | [CONFIRMED] Discovered by official full suite and v2 wrapper | Active automated discovery-package tests | `KEEP` |
| `test_extractor.py` | [CONFIRMED] Not in official runner; manual `__main__` check | Legacy/manual diagnostic test | `DEFER` |
| `test_inn.py` | [CONFIRMED] Not in official runner; manual `__main__` check | Legacy/manual diagnostic test | `DEFER` |
| `test_parser.py` | [CONFIRMED] Not in official runner; manual `__main__` check | Legacy/manual diagnostic test | `DEFER` |
| `test_verify.py` | [CONFIRMED] Not in official runner; manual `__main__` check | Legacy/manual diagnostic test | `DEFER` |
| `supplier_source_tests/run_probe.py` | [CONFIRMED] Not unittest-discovered; direct CLI | Manual read-only source/provider test tool | `KEEP` |

Do not simply move root `test_*.py` into `tests/`: the move would alter import
and discovery topology. First choose whether these checks should remain manual,
be converted into explicit unittest cases, or be retired under an approved
allowlist.

## Operator and one-off script classification

| Path | Classification | Current status | Canonical destination |
|---|---|---|---|
| `benchmark_models.py` | `OPERATOR_SCRIPT` | Manual benchmark with cache and optional provider calls | `benchmarks/` after CLI compatibility review |
| `collect_contacts.py` | `OPERATOR_SCRIPT` | Manual contact collection CLI | `scripts/` after import-path review |
| `collect_inn.py` | `PRODUCT_RUNTIME + OPERATOR_SCRIPT` | Reusable backend pipeline and CLI in one file | Split reusable code into backend domain; explicit `scripts/` wrapper |
| `serp_parser.py` | `PRODUCT_RUNTIME + OPERATOR_SCRIPT` | Backend collector, CLI and v2 subprocess target | Keep root until path/deployment contract is migrated |
| `supplier_source_tests/run_probe.py` | `TEST_TOOL + OPERATOR_SCRIPT` | Read-only provider/source probe, direct invocation | Keep current isolated directory |
| `scripts/diagnostics/diagnostic_runner.py` | `OPERATOR_TOOL` | Canonical static/read-only diagnostic runner | Keep `scripts/diagnostics/` |
| `scripts/run_test_suite.py` | `TEST_TOOL` | Official offline unittest runner | Keep `scripts/` |
| `scripts/test_runtime_entry.py` | `TEST_TOOL + RUNTIME_ADAPTER` | Safe offline runtime entrypoint | Keep `scripts/` |
| `scripts/runtime_status.py` | `OPERATOR_TOOL` | Read-only runtime status | Keep `scripts/` |
| `scripts/process_request_step.py` | `OPERATOR_SCRIPT` | Manual app request processing adapter | Keep `scripts/` |
| `scripts/supplier_identity_audit.py` | `OPERATOR_TOOL` | Database-backed identity audit; protected default DB path | Keep `scripts/`; do not run here |
| `scripts/reconcile_request_1059_historical_queue.py` | `LEGACY OPERATOR_SCRIPT` | Historical reconciliation surface with canonical-data risk | `DEFER`; no execution or deletion |
| `scripts/cross_provider_retry_preview.py` | `OPERATOR_SCRIPT` | Read-only retry preview | Keep `scripts/` |
| `scripts/verify_enrichment_live.py` | `TEST_TOOL + OPERATOR_SCRIPT` | Explicit live-provider verifier | Keep `scripts/`; live execution not in this task |
| `supplier_discovery_v2/run.py` | `PRODUCT PILOT CLI` | Active package `python -m` entrypoint | Keep `supplier_discovery_v2/` |

## Duplicate responsibility review

These are conceptual overlaps, not deletion decisions.

| Group | RESPONSIBILITY_OVERLAP | BEHAVIORAL_DIFFERENCE | CAN_CONSOLIDATE | EVIDENCE |
|---|---|---|---|---|
| `email_extractor.py` vs `supplier_discovery_v2/contacts.py` | Both extract public contact candidates | Legacy extractor handles obfuscation, JSON-LD, Cloudflare and `EmailHit` scoring; v2 handles simple email/phone extraction, platform-owned filtering and `ContactCandidate` | `REVIEW`, not now | Source inspection of both modules and separate tests/models |
| `contact_crawler.py` vs `supplier_discovery_v2/direct_site.py` | Both inspect supplier websites and contact pages | Legacy crawler has bounded retries, robots, DNS/MX, PDF and `SiteResult`; v2 has limited read-only pages, role classification and v2 evidence | `NO` under current boundaries | `supplier_discovery_v2` README explicitly isolates the pilot |
| `serp_parser.py` vs `supplier_discovery_v2/pipeline.py` / connectors | Both participate in supplier discovery/search | Legacy parser is current app collector and XMLRiver CLI; v2 adds query planning, catalog connectors, qualification and subprocess isolation | `REVIEW`; only after v2 replacement proof | `xmlriver_subprocess.py` hardcodes the existing parser path |
| `verify.py` vs `supplier_discovery_v2/matching.py` | Both affect candidate acceptance | `verify.py` verifies email/INN/domain ownership; v2 classifies buyer/seller, product match and public contacts | `NO` without a shared contract | Different output types and different acceptance semantics |
| `serp_parser.root_domain_of` vs `email_extractor.root_domain` | Same domain-normalization responsibility | Extractor delegates lazily to parser to avoid copying; this creates a direction smell rather than byte duplicate | `REVIEW` | `email_extractor.py:269-273` |

No byte-identical duplicate implementation relevant to this root review was
found. Existing duplicate groups from prior hygiene evidence remain intentionally
kept by package role; this task did not reclassify or delete them.

## Component lifecycle review

[CONFIRMED] The maintained lifecycle registry currently has one explicit
non-active record: `frontend/playwright.real-email.config.ts` is `DEFERRED`.
No Python root component has an unambiguous formal `DEPRECATED`, `DISABLED` or
`SUPERSEDED` record in `docs/architecture/COMPONENT_LIFECYCLE.md`.

[HYPOTHESIS] `benchmark_models.py`, `collect_contacts.py` and root `test_*.py`
look like retained PoC/manual surfaces and receive `DEPRECATED_REVIEW` in this
diagnostic table. That is not a formal lifecycle status: they still have
possible operator/documentation value and no replacement has been proven.
`supplier_discovery_v2/` is an active canonical package despite the `v2` suffix;
the suffix alone is not versioned garbage. The lifecycle registry was not
changed because the evidence does not establish replacement/removal conditions
for the root Python files.

## Target architecture proposal

This is a [HYPOTHESIS] derived from current responsibilities, not an executed
filesystem plan:

```text
root/
  supplier_app.py                         protected local backend entrypoint
  api/index.py                            protected serverless adapter
  backend/
    domain/
      supplier_identity/
        email_extractor.py
        inn_extractor.py
        inn_resolver.py
        verify.py
      supplier_enrichment/
        contact_crawler.py
        pipeline.py                        extracted from collect_inn.py
    integrations/
      registry/
        checko_client.py
        dadata_client.py
      search/
        xmlriver_client.py
        web_lookup.py
        serp_parser.py                      only after path migration
      llm/
        routerai_client.py
        llm_fallback.py
  mail/                                    existing backend core boundary
  migrations/                              existing schema boundary
  supplier_discovery_v2/                   isolated pilot boundary, unchanged
  scripts/
    collect_contacts.py
    collect_inn.py                         thin explicit CLI wrappers
    ...                                     existing operator/control tools
  benchmarks/
    benchmark_models.py
  tests/                                    official suites only
    legacy/                                 possible future home, not automatic
```

The point is semantic ownership, not an arbitrary root object count. The
`backend/` name is justified only if the next task creates the package together
with import and deployment contracts; do not create empty buckets or a generic
`utils/`/`services/` dumping ground. `supplier_app.py` may remain a root
composition entrypoint even after support modules move.

## One bounded Pass 2 proposal

Do not execute this Pass 2 in the current task.

### SAFE BATCH

High-confidence manual surfaces, with compatibility preserved:

1. Move the implementation of `benchmark_models.py` to `benchmarks/` and keep
   a tiny root compatibility wrapper only if the documented `python
   benchmark_models.py ...` command is retained or deliberately versioned.
2. Move the implementation of `collect_contacts.py` to `scripts/` and preserve
   its import bootstrap and output-path behavior, or leave it root if the
   owner wants the historical CLI contract unchanged.

Estimate: `2` implementation files plus up to `2` compatibility wrappers;
approximately `2–6` direct import/path edits; offline CLI/help and fixture
checks only; deployment risk low if wrappers remain. This still needs an
explicit implementation task and focused acceptance.

### REVIEW BATCH

One coordinated package move for the runtime support modules:

- six domain/enrichment files: `collect_inn.py` (split), `contact_crawler.py`,
  `email_extractor.py`, `inn_extractor.py`, `inn_resolver.py`, `verify.py`;
- six integration files: `checko_client.py`, `dadata_client.py`,
  `llm_fallback.py`, `routerai_client.py`, `web_lookup.py`,
  `xmlriver_client.py`;
- `serp_parser.py` only after its root subprocess path is replaced with an
  explicit configured/package entrypoint.

Estimate: `12–13` implementation files, `supplier_app.py`,
`mail/repository.py`, live-verifier scripts and enrichment tests affected;
dozens of import statements/call sites require re-baselining from a fresh AST;
backend full regression, discovery tests, offline runtime smoke and deployment
bundle inspection required. Deployment risk high because `api/index.py` loads
the root app and Vercel include/exclude behavior must be proven.

### DO NOT TOUCH

- `supplier_app.py` root location and `api/index.py` handler boundary;
- `mail/`, `migrations/`, canonical/runtime data and `.env*` paths;
- `supplier_discovery_v2/` isolation and its `serp_parser.py` subprocess until
  a replacement contract is accepted;
- root `test_*.py` until discovery semantics are explicitly chosen;
- `supplier_source_tests/`, `Documents/` and `work/` merely for visual root
  cleanup;
- frontend, browser acceptance and the unrelated Browser Full failure.

## Time and tool boundaries

- [CONFIRMED] One broad PASS 1 and one manual PASS 2 were used; no third broad
  audit or micro-audit chain was started.
- `TIME_BUDGET_EXCEEDED: NO` — the diagnostic completed within the requested
  target window.
- Browser: `NOT_NEEDED` by task scope.
- Bug Reproducer: `NOT_NEEDED` by task scope; incidental issues are not fixed.
- Frontend/Knip: `NOT_NEEDED`; prior frontend audit evidence was not reopened.

## Final status fields

```text
ROOT_DIAGNOSTIC: COMPLETE
ROOT_PYTHON_FILES: 20
ROOT_DIRECTORIES_REVIEWED: 16
KEEP_ROOT: 1
MOVE_CANDIDATES: 14
DELETE_CANDIDATES: 0
DEPRECATED_REVIEW: 4
DEFER: 1
CODE_ROT_CLEANER: USED_REPORT_ONLY
RUFF: NOT_AVAILABLE
VULTURE: NOT_AVAILABLE
PRODUCT_CODE_CHANGED: NO
FILES_MOVED: 0
FILES_DELETED: 0
DEPENDENCIES_CHANGED: NO
BROWSER: NOT_NEEDED
BUG_REPRODUCER: NOT_NEEDED
PASS2_READY: YES — bounded plan exists; execution requires a separate approved task
HIGHEST_RISK_AREA: supplier_app.py/api/index.py/serp_parser.py import and deployment boundary
RECOMMENDED_NEXT_TASK: Bounded root-module refactor review, starting with CLI compatibility and a fresh import/deployment contract; do not move protected entrypoints
ACTIVE_TASK: IDLE at closeout
COMMIT: PUBLISHED — final closeout commit is recorded in Git history and control-plane state
PUSH: PASS — remote SHA matches `301934fb0daa1f49cad8c793c9a5acbd30b10152`
FAST_CI: PASS — workflow run `33645377974`; report-only fast control path passed
FINAL_STATUS: PASS_WITH_LIMITATIONS
```

## What changed / what did not change

- [CONFIRMED] New tracked artifact: this report only, plus required updates to
  existing control-plane state/handoff/log files at closeout.
- [CONFIRMED] No `supplier_app.py`, `api/**`, `mail/**`, `migrations/**`,
  `frontend/**`, `supplier_discovery_v2/**`, tests or dependencies changed.
- [CONFIRMED] No files moved or deleted; no runtime/database/mail/provider
  action occurred.

## Limitations, rollback and confidence

- [NOT VERIFIED] Ruff/Vulture findings; neither tool is installed and no ad-hoc
  installation was attempted.
- [NOT VERIFIED] Runtime reachability for rare operator commands, external
  consumers, reflection and environment-selected imports.
- [NOT VERIFIED] Vercel remote build/deployment after a hypothetical move.
- [NOT VERIFIED] Product regression; intentionally not required for a report-only
  control change.
- [CONFIRMED] Rollback for this audit is a normal Git revert of the report/state
  commit. No source, data or deployment rollback is needed because none was
  changed.

Confidence is `HIGH` for the protected entrypoint decisions, direct inbound
imports, directory roles and current official test discovery; `MEDIUM` for
future move targets; and `LOW` only for claims about absence of external or
dynamic consumers.

## Инструменты и skills

| TYPE | Name | Use |
|---|---|---|
| SKILL | `environment-discovery` | Read-only OS/tool/workspace preflight |
| SKILL | `code-rot-cleaner` | Bundled static candidate scan in `report-only` mode; outputs external to repo |
| TOOL | Workspace Guard | Confirmed canonical Git root before task lock and report mutation |
| TOOL | Git / `git ls-files` / `git ls-tree` / `git grep` / `git log` | Branch, HEAD, worktree, tracked inventory, references and history |
| TOOL | Python `ast` | Tracked Python import graph, entrypoint and cycle inspection |
| TOOL | `rg` | String/config/entrypoint/reference search |
| TOOL | PowerShell process/listener checks | Active process, port and protected-path inventory |
| WORKFLOW | `PASS 1 → PASS 2 → report-only closeout` | Bounded diagnostic workflow; no refactor pass executed |
