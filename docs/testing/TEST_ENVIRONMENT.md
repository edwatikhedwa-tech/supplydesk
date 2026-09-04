# SupplyDesk Test Environment

## Что это

`OFFLINE_TEST` — воспроизводимый профиль для чистого checkout. Он запускает
настоящий backend и настоящие HTTP-маршруты, но использует только отдельный
локальный test-venv, disposable SQLite и синтетические данные. Disposable DB
означает временную базу, создаваемую миграциями в test-пути и не содержащую
данные владельца.

Цель профиля — дать разработчику, CI или Repair Agent один безопасный путь к
регрессии backend, frontend-gates и Playwright без приватного `.env`, личной
почты, production credentials и внешней сети.

## Workspace boundary

Before setup, tests, frontend build, safe runtime start or Doctor, the
workspace guard must pass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
```

Without an override it accepts only `C:\Users\edwat\SupplyDesk` and rejects
the legacy recovery-only root `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS`.
For an intentional Git worktree or CI checkout, pass its exact absolute path:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1 -ExpectedRoot 'C:\path\to\worktree'
```

The guard never changes directory, branch or files. CI supplies its checkout
root explicitly through `-ExpectedRoot $env:GITHUB_WORKSPACE`.

## Чистый checkout: последовательность

Команды выполняются из корня репозитория в PowerShell 7. Python 3.11.7
проверен в текущей среде; политика поддерживает Python 3.11.x.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_test_env.ps1 -Plan
powershell -ExecutionPolicy Bypass -File .\scripts\setup_test_env.ps1 -Apply
powershell -ExecutionPolicy Bypass -File .\tests\run-tests.ps1
Push-Location .\frontend
npm ci --no-audit --fund=false
npm run typecheck
npm run lint
npm run build
if (-not (Test-Path "$env:USERPROFILE\AppData\Local\ms-playwright\chromium-*")) { npx playwright install chromium }
Pop-Location
powershell -ExecutionPolicy Bypass -File .\scripts\start_test_runtime.ps1 -Apply -Purpose SAFE_TEST
powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1 -DryRun -Profile OFFLINE_TEST -Full
```

`setup_test_env.ps1 -Plan` только показывает план. Только `-Apply` создаёт
`.venv-test` и устанавливает зависимости из `requirements-test.txt`; глобальный
Python, Git, база и env-файлы не изменяются. Обычный `tests/run-tests.ps1`
ничего не устанавливает.

## Зависимости

`requirements.txt` — зависимости приложения. `requirements-test.txt` ссылается
на него, потому что текущие тесты импортируют реальные модули приложения. При
аудите 33 Python-файлов тестов обнаружены только стандартная библиотека и эти
runtime-модули.

| Класс | Состав | Решение |
|---|---|---|
| `RUNTIME_DEPENDENCY` | requests, beautifulsoup4/lxml, cryptography, psycopg, nh3, quotequail, openai, dnspython, pypdf | остаются в `requirements.txt` |
| `TEST_ONLY_DEPENDENCY` | нет доказанных внешних пакетов | не добавлялись |
| `OPTIONAL_TOOL` | Playwright browser binary | ставится отдельно только для browser acceptance |
| `NOT_REQUIRED` | pytest, pytest-cov | runner использует стандартный `unittest` |

Официальная backend-команда:

```powershell
.\tests\run-tests.ps1
```

Режимы `-Diagnostics` и `-Quick` доступны для короткой проверки; полный режим
является значением по умолчанию. Python runner —
`scripts/run_test_suite.py`. Он очищает унаследованные production/provider
переменные и блокирует DNS/соединения вне loopback. Runner не задаёт
`SUPPLYDESK_ENV` намеренно: существующие provider-neutral unit-тесты создают
`MailService` напрямую и должны проверять fake-provider state machine без
application runtime. Для запуска настоящего приложения safe runtime задаёт
`SUPPLYDESK_ENV=test`. Внутри unit-тестов разрешены только уже существующие fake-provider
double; реальный внешний SMTP/IMAP socket технически недоступен. Ошибка
внешнего обращения становится ошибкой теста, а не тихим сетевым побочным
эффектом. Продуктовый safe runtime дополнительно включает
`MAIL_OUTGOING_DISABLED=1`.

## Классификация переменных

| Класс | Переменные и смысл |
|---|---|
| `REQUIRED_FOR_RUNTIME` | `SUPPLYDESK_ENV=test`, `APP_HOST=127.0.0.1`, `PORT`, `APP_BASE_URL`, `MAIL_DB_PATH`, `SUPPLYDESK_RUNTIME_MARKER` |
| `REQUIRED_FOR_TEST` | `.venv-test`, `requirements-test.txt`, `tests/run-tests.ps1`; отдельные тесты создают свои временные DB |
| `OPTIONAL` | `APP_USER_EMAIL` и `APP_USER_PASSWORD` — синтетическая login-фикстура safe runtime; `ENRICHMENT_RETRY_INTERVAL_SECONDS=0`, `MAIL_SYNC_* = 0` выключают фоновые live-пути |
| `SECRET` | provider OAuth/app-password, encryption key, `DATABASE_URL`; в OFFLINE_TEST не задаются реальными значениями и не читаются из `.env` |
| `EXTERNAL_SERVICE` | `YANDEX_*`, `MAILRU_*`, `SMTP_*`, `IMAP_*`, `CHECKO_*`, `XMLRIVER_*`, `OPENAI_API_KEY`; пусты или запрещены |
| `DANGEROUS` | `DATABASE_URL`, `SUPPLYDESK_CANONICAL_DB_PATH`, real provider credentials, `MAIL_OUTGOING_DISABLED=0`; runtime-entrypoint отказывает при небезопасной комбинации |

В репозитории нет `.env.test.example`: для этой стадии безопаснее задавать
значения программно в `start_test_runtime.ps1` и не создавать шаблон, который
можно ошибочно заполнить личными данными.

## Disposable SQLite

Safe runtime использует `runtime/test-data/supplier.sqlite3`, который игнорируется
Git и не является канонической базой. При создании `SupplierApp` существующий
`MailRepository` применяет миграции только к этому test-пути, затем добавляет
синтетического пользователя и fixture `fixtures/demo_catalog.json`. Скопированные
`mail-data`, customer records, mailbox messages и private `.env` не используются.

`OFFLINE_TEST` отказывает для `mail-data/supplier.sqlite3`, а Doctor проверяет
SQLite read-only (`quick_check`, `integrity_check`) и наличие миграционной схемы.
Вызов start runtime может писать только disposable DB и runtime logs/marker.

## Почта и сеть

Реальная исходящая почта в этом профиле технически запрещена сразу несколькими
слоями: `SUPPLYDESK_ENV=test`, `MAIL_OUTGOING_DISABLED=1`, отсутствие provider
credentials/accounts и loopback-only socket guard. SMTP и IMAP connection paths
не получают внешний socket; provider acceptance остаётся отдельным ручным
профилем `LIVE_EXTERNAL` и не входит в canonical regression.

По умолчанию внешняя сеть запрещена. Supplier discovery network tests, если
будут добавлены позднее, должны быть отдельной явно названной группой и не
входить в `tests/run-tests.ps1`.

## Safe runtime и HTTP acceptance

Запуск:

```powershell
.\scripts\start_test_runtime.ps1 -Plan
.\scripts\start_test_runtime.ps1 -Apply -Purpose SAFE_TEST
```

Порт по умолчанию — `18000`; если он занят, запуск останавливается и другой
порт не выбирается. Приложение настоящее, frontend берётся из собранного `frontend/dist`.
Marker `runtime/test-runtime.json` содержит только machine/process evidence:
`profile=OFFLINE_TEST`, `environment=test`, `database.kind=disposable_sqlite`,
`outgoing_mail=disabled`, `external_providers=fake/blocked`,
`network.external_connections=blocked`.

Минимальный ручной smoke-проверочный набор:

```powershell
Invoke-WebRequest http://127.0.0.1:18000/
Invoke-WebRequest http://127.0.0.1:18000/api/auth/me
Invoke-WebRequest http://127.0.0.1:18000/api/requests
Invoke-WebRequest http://127.0.0.1:18000/api/mail/status
Invoke-WebRequest http://127.0.0.1:18000/api/diagnostic-unknown
```

Ожидается: `/` и `/api/auth/me` — `200`, защищённые `/api/requests` и
`/api/mail/status` без cookie — `401`, неизвестный API — `404`. После сборки
существующий Playwright public-shell тест выполняется по реальным маршрутам:

```powershell
Push-Location .\frontend
$env:RUNTIME_PURPOSE = 'AUTOMATED_TEST'
$env:RUNTIME_MODE = 'SAFE_TEST'
$env:RUNTIME_BACKEND_URL = 'http://127.0.0.1:18000'
$env:AUDIT_BASE_URL = 'http://127.0.0.1:18000'
npm test -- tests/frontend-audit.spec.ts -g 'public shell' --workers=1
Pop-Location
```

`npm test` проходит через `scripts/run_playwright.mjs` и обязательный guard.
Этот тест проверяет все восемь существующих viewport-проектов. Тесты с route
mock остаются unit/UI fixtures и не выдаются за live-route acceptance.

Для визуальной приёмки рабочего интерфейса используется только canonical:

```powershell
Push-Location .\frontend
$env:RUNTIME_PURPOSE = 'VISUAL_ACCEPTANCE'
$env:RUNTIME_MODE = 'LOCAL_CANONICAL'
$env:RUNTIME_BACKEND_URL = 'http://127.0.0.1:8000'
$env:AUDIT_BASE_URL = 'http://127.0.0.1:8000'
npm run test:visual -- -g 'public shell' --workers=1
Pop-Location
```

SAFE_TEST предназначен для автоматических проверок и имеет заметный badge
`SAFE TEST · DISPOSABLE DATA · PORT 18000`; этот badge не является доказательством
визуальной приёмки canonical runtime.

Остановка только помеченного test-процесса:

```powershell
.\scripts\stop_test_runtime.ps1 -Plan
.\scripts\stop_test_runtime.ps1 -Apply
```

## Doctor profiles

```powershell
.\scripts\doctor.ps1 -Plan
.\scripts\doctor.ps1 -DryRun -Profile OFFLINE_TEST
.\scripts\doctor.ps1 -DryRun -Profile OFFLINE_TEST -Full
```

`-Plan` только описывает проверки. `-DryRun` диагностирует; он не устанавливает
venv, не создаёт DB, не запускает сервер и не чинит данные. `-Full` — явный
расширенный read-only режим, который запускает полный backend runner,
frontend gates и public-shell Playwright, если среда уже подготовлена.
`-Apply` остаётся `SAFETY_BLOCK`.

| Профиль | Требуется | Не требуется или запрещено |
|---|---|---|
| `OFFLINE_TEST` | test dependencies, disposable DB, safe runtime, backend regression, frontend gates, Playwright real routes | canonical DB, private `.env`, SMTP/IMAP, real email и external network — запрещены |
| `LOCAL_CANONICAL` | read-only structural/runtime evidence по запросу | test runtime не обязателен; real email всё равно не запускается |
| `LIVE_EXTERNAL` | нет автоматического acceptance | provider/network/email — manual-only, Doctor блокирует автоматический путь |

Doctor различает `NOT_REQUIRED_FOR_OFFLINE_ACCEPTANCE` и
`NOT_VERIFIED_REQUIRED`: отсутствие live mailbox не снижает статус offline-профиля,
но отсутствие test DB, venv, runner, runtime или browser evidence остаётся
`ENVIRONMENT_GAP`.

## Behavioral coverage and limits

Историческая цифра `373 passed, 1 skipped` сохранена только как baseline для
сравнения. Runner не подгоняет количество: итоговый `tests`, failures, errors и
skipped берутся из фактического unittest результата. В Doctor полная регрессия
запускается только с `-Full`; обычная диагностика остаётся быстрой.

До этого этапа offline tooling было лишь теоретически eligible и backend suite
не запускался из-за отсутствия pytest. После этого этапа backend requirements и
runner стали воспроизводимыми, но это не превращает все 21 requirement в
поведенчески доказанные. Validator отдельно выводит
`offline_eligible_requirements` и `offline_behaviorally_diagnosable`; второй
показатель учитывает только реально поведенческий или runtime-level Doctor
контроль. Live provider
семантика и полноценные authenticated flows с реальной перепиской остаются
ограничением; synthetic login и read-only routes проверяются отдельно, когда
это возможно.

## CI readiness

Будущий CI может выполнить ту же последовательность без GitHub Actions-файла:

1. setup Python 3.11.x и `requirements-test.txt`;
2. `tests/run-tests.ps1`;
3. `npm ci --no-audit --fund=false`;
4. `npm run typecheck`, `npm run lint`, `npm run build`;
5. validators, diagnostic tests и safe runtime/browser acceptance.

Ни один шаг не копирует `.env`, database, cookies или provider token.
