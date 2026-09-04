---
document_id: REPORT-TASK-ROOT-CAUSE-RUNTIME-FIX-20260903
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-03
---

# TASK-ROOT-CAUSE-RUNTIME-FIX-20260903 — отчёт

## Цель

1. Read-only root-cause анализ, почему предыдущая сессия перепутала
   `LOCAL_CANONICAL`-рантайм (порт 8000) и `SAFE_TEST`-рантайм (порт 18000).
2. Минимальная причинно-связанная поправка в governance, чтобы это не
   повторялось.
3. Полное автоматическое восстановление `.env` из legacy checkout по явному
   разрешению владельца, без ручного выбора секретов и без их вывода куда-либо.
4. Проверка Yandex OAuth на реальном `LOCAL_CANONICAL`-рантайме.

## ROOT-CAUSE ANALYSIS (read-only)

См. финальный ответ пользователю в чате этой сессии — блоки `ROOT_CAUSE`,
`PROCESS_FAILURE`, `INSTRUCTION_GAP`, `AGENT_ERROR`, `WHAT_SHOULD_HAVE_HAPPENED`.
Кратко: `PROJECT_MANIFEST.yaml` уже содержал оба порта (`backend_default_port:
8000` и `browser_acceptance.audit_live_route_url: http://127.0.0.1:18000`) в
одном файле, но без явной связки «это два разных, взаимоисключающих режима
работы» — агент не перечитал этот файл в момент выбора порта для ярлыка и
взял порт из уже проверенного в сессии `start_test_runtime.ps1`, не
проверив, совпадает ли это с фактическим намерением владельца («обычная
работа» vs «безопасный тест»). Отдельно был найден повторный дефект
кодировки: `.env`-патч через `Get-Content -Raw`/`Set-Content -Encoding
UTF8` в Windows PowerShell 5.1 побил кириллические комментарии в файле
(та же категория бага, что вчера в `start_server_and_open.ps1`) —
обнаружено системным уведомлением об изменении файла на диске, исправлено
немедленно через явную `UTF8Encoding` без BOM и повторное чтение из
исходного файла.

## DESIGN DECISION (governance fix)

Минимальные, причинно-связанные правки — ничего не переписано целиком:

- `PROJECT_MANIFEST.yaml`: добавлен блок `runtime_modes` (после `runtime:`,
  перед `browser_acceptance:`) с двумя явно названными режимами —
  `LOCAL_CANONICAL` (порт 8000, `python supplier_app.py`, `.env` в корне,
  канонический `mail-data/supplier.sqlite3`) и `SAFE_TEST` (порт 18000,
  `scripts/start_test_runtime.ps1 -Apply`, одноразовая БД, ключи провайдеров
  всегда пустые). Это первый источник истины по этому вопросу.
- `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md`: было расплывчатое
  «use the repository's documented startup path» без единой команды.
  Заменено на явный раздел «Runtime mode classification» с двумя
  однозначными командами и явным требованием классифицировать режим
  раньше выбора команды/порта.
- `ai/AI_CONTRACT.md` (правило 14): добавлено предложение — перед стартом
  backend-рантайма классифицировать `RUNTIME_MODE` по
  `PROJECT_MANIFEST.yaml`, затем по раннбуку, и не выводить режим из «что
  уже работало раньше в этой сессии».
- `ai/VIBECODING_RULES.md`: у существующей строки про профили
  `scripts/doctor.ps1` (тоже содержит имя `LOCAL_CANONICAL`, но в другом
  смысле — read-only диагностика БД) добавлена одна строка-разграничение,
  чтобы два одноимённых, но разных понятия не путались снова.
- `CLAUDE.md`: одна короткая сноска в разделе «Workspace guard» с прямой
  ссылкой на раннбук и явным предупреждением не подменять `SAFE_TEST`
  вместо `LOCAL_CANONICAL` только потому, что первый уже был проверен в
  сессии.

Новый тяжёлый governance-механизм не создавался; `PROJECT_MANIFEST.yaml`
остаётся единственным источником истины, раннбук и `AI_CONTRACT.md` —
пойнтеры на него.

## IMPLEMENT (env recovery)

- Workspace Guard: `PASS` для `C:\Users\edwat\SupplyDesk` перед стартом и
  перед стартом рантайма.
- Legacy checkout использован только как read-only источник: файл
  `.env` прочитан на диске, ничего в legacy-папке не изменено и не
  запускалось.
- Существовавший `C:\Users\edwat\SupplyDesk\.env` (частичный, из прошлой
  сессии) сохранён как `.env.backup-20260903-232311` — вне git, с
  timestamp, по паттерну `.env.backup-*`, уже присутствующему в
  `.gitignore`.
- Полный `.env` скопирован из legacy checkout автоматически, без ручного
  выбора отдельных секретов (20 переменных перенесено как есть).
- После копирования — только анализ ИМЁН переменных (список см. в финальном
  ответе чата), без вывода значений.
- Две переменные (`SUPPLYDESK_CANONICAL_DB_PATH`, `MAIL_DB_PATH`) указывали
  на путь внутри legacy-папки — удалены из скопированного `.env`, чтобы
  backend/app_config.py упал на собственный дефолт: канонический
  `mail-data/supplier.sqlite3` под текущим checkout'ом, а не legacy DB.
  `DATABASE_URL` в исходном файле отсутствовал (не Postgres, риска
  перенаправления на чужую БД нет).
- Несекретные runtime-настройки приведены к canonical-контракту явно:
  `APP_HOST=127.0.0.1`, `PORT=8000`, `APP_BASE_URL=http://127.0.0.1:8000`,
  `SUPPLYDESK_ENV` — `production` → `development` (это реальная локальная
  разработка, не боевой деплой).
  `MAIL_OUTGOING_DISABLED=1` был уже в исходном файле — оставлен как есть.
- В процессе патча обнаружена и исправлена собственная ошибка кодировки
  (см. root-cause) — итоговый файл перечитан из оригинала с явной UTF-8 без
  BOM, кириллица восстановлена, проверено отсутствием символа-заменителя
  `U+FFFD` в файле.

## ACCEPTANCE

- `PROJECT_MANIFEST.yaml` остаётся валидным YAML после правки (проверено
  `yaml.safe_load`), `runtime_modes.LOCAL_CANONICAL.base_url` и
  `runtime_modes.SAFE_TEST.default_port` читаются корректно.
- `ai/tools/validate_docs.py`, `ai/tools/validate_state.py`,
  `ai/tools/validate_vibecoding.py` — все `PASS`.
- `git diff --check` — чисто (только предупреждение о конвертации
  LF→CRLF, не ошибка).
- Реальный запуск `python supplier_app.py` (не `start_test_runtime.ps1`):
  `GET /` → `200`, `GET /api/auth/me` → `200`,
  `GET /api/auth/yandex/start` → `302` на `oauth.yandex.ru` с
  `redirect_uri=http://127.0.0.1:8000/oauth/yandex/callback` — байт-в-байт
  тем же значением, что было в исходном `YANDEX_REDIRECT_URI` legacy-файла.
- Порт 18000 не слушается ни одним процессом на момент проверки; активен
  только порт 8000 (`LOCAL_CANONICAL`).
- Секретные значения (`YANDEX_CLIENT_SECRET`, `MAIL_TOKEN_ENCRYPTION_KEY`,
  `APP_USER_PASSWORD`, `ROUTERAI_KEY`, `XMLRIVER_KEY`, `CHECKO_KEY*`) в чат,
  логи или этот отчёт не выводились — только `VARIABLE_PRESENT: YES/NO` и
  безопасные несекретные значения (порт/URL/environment).

## Что НЕ проверено

- Факт реального завершения OAuth (обмен кода на токен) — для этого нужен
  вход владельца в свой аккаунт Яндекса, я его не выполнял и не буду.
- Действительно ли `redirect_uri` всё ещё зарегистрирован в консоли
  `oauth.yandex.ru` именно сейчас — я не открывал консоль Яндекса (нет
  доступа и не должен запрашивать пароль в чате). Совпадение подтверждено
  только между значением из legacy `.env` и значением, которое сейчас
  реально формирует приложение — не с самой консолью Яндекса.
- Найден один посторонний, неактуальный артефакт:
  `runtime/test-runtime.json` содержит `status: ready, port: 18000` от
  более раннего запуска сегодняшней сессии, хотя тот процесс был
  корректно остановлен `stop_test_runtime.ps1` — сам скрипт по своему
  дизайну не удаляет файл-метку после остановки (не баг этой задачи, не
  трогал). Подтверждено отдельной проверкой: на порту 18000 сейчас никто
  не слушает.

## Изменения вне продуктового кода

`PROJECT_MANIFEST.yaml`, `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md`,
`ai/AI_CONTRACT.md`, `ai/VIBECODING_RULES.md`, `CLAUDE.md`,
`ai/CURRENT_STATE.md`, `ai/DECISIONS.md`, `ai/LAST_HANDOFF.md`,
`ai/CHANGELOG.md`, `ai/INTERACTION_LOG.md`, `ai/ACTIVE_TASK.md`. `.env` и
`.env.backup-*` — локальные, гитигнорены, не коммитятся.
