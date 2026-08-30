# TASK-PUBLISH-SAFETY-001 — отчёт подготовки безопасной публикации

Дата: `2026-08-30T17:38:06Z` UTC

Статус: `BLOCKED`

## Цель и результат

Подготовлен будущий publish set для приватного GitHub, но внешнее действие
остановлено до очистки credentials и ручного утверждения состава. Созданы:

- `ai/PUBLISH_ALLOWLIST.md`;
- `ai/PUBLISH_DENYLIST.md`;
- `ai/PUBLISH_SECURITY_REPORT.md`;
- этот отчёт.

Изменялись только документы `ai/**`. Не выполнялись `git add`, commit,
создание репозитория, настройка `origin` или push.

## 1. Проверенная среда

- Project root/Git root: `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS`.
- Branch: `codex/TASK-STATE-CONTROL-20260830`.
- HEAD: `34b064bddeec5b2598f7f9f251d5ec374deadbab`.
- GitHub CLI установлен и авторизован как `edwatikhedwa-tech`.
- `origin` отсутствует.
- `edwatikhedwa-tech/supplydesk` read-only lookup: `NOT FOUND`.
- `git ls-files` содержит `149` tracked files в HEAD.
- В staging до и после работы: `0` файлов.

`gh` auth не является разрешением на создание remote. Точное имя приватного
репозитория и общая ветка не подтверждены владельцем.

## 2. Working tree inventory

Снимок до создания четырёх новых safety documents:

- `66` tracked modified;
- `6` tracked deleted;
- `599` untracked;
- `0` staged;
- `677` unique paths;
- tracked diff: `17125 insertions(+), 3588 deletions(-)`.

Историческое число `170` не воспроизведено. Его provenance:
`REPORTED, NOT VERIFIED`. Uncommitted paths не удалялись, не перемещались и не
считались автоматически принадлежащими текущему агенту.

### Классификация

| Class | Meaning | Count | Current bytes | Include? |
|---|---|---:|---:|---|
| A | application source | 190 | 5,311,176 | `REVIEW REQUIRED` |
| B | tests | 51 | 1,367,469 | `REVIEW REQUIRED` |
| C | project configuration | 15 | 14,891 | `REVIEW REQUIRED` |
| D | AI documentation | 7 | 45,652 | conditional `SAFE CANDIDATE` |
| E | ordinary documentation | 89 | 1,649,887 | `REVIEW REQUIRED` |
| F | temporary/runtime | 58 | 1,361,861 | `EXCLUDE` |
| G | screenshots/archives/backups | 253 | 19,374,458 | `EXCLUDE` |
| H | personal or unknown | 14 | 475,699 | `EXCLUDE` until owner review |
| I | secrets in status paths | 0 | — | ignored env overlay blocks |

Сумма: `677`. Размеры — текущие размеры существующих файлов, не patch size.

Примеры A: `api/index.py`, `mail/service.py`, `mail/repository.py`,
`frontend/src/`, `migrations/`, `supplier_app.py`.
Примеры B: `tests/`, `frontend/tests/`, `test_mailru_mvp.py`.
Примеры C: `.gitignore`, `.env.example`, `vercel.json`, frontend configs.
Примеры F/G: `Temp/`, `runtime/`, screenshots, `*.zip`, review exports,
`mailru-mvp-backup-20260829/`.
Примеры H: `Documents/` и provenance-неподтверждённые one-off materials.

Классификация по пути не доказывает происхождение файла. Все uncommitted
пути остаются `UNKNOWN` / `NOT VERIFIED` для публикации.

## 3. Security scan

Проверены потенциальные candidates и текстовые файлы без вывода значений.
Результаты:

| Path | Risk | Pattern/status | Action |
|---|---|---|---|
| `.env` | credentials/config | file present | `EXCLUDE`; `ROTATE_AND_REVIEW` if exposed |
| `.env.local` | credentials/config | file present | `EXCLUDE`; `ROTATE_AND_REVIEW` if exposed |
| `.env.p0-backup-20260830` | credentials backup | file present | `EXCLUDE`; `ROTATE_AND_REVIEW` |
| `.env.production.local` | production credentials/DB URL | high-confidence pattern found | `EXCLUDE` and `ROTATE_AND_REVIEW` |
| `.vercel/.env.preview.local` | preview credentials/config | file present | `EXCLUDE`; `ROTATE_AND_REVIEW` |
| `mail-data/` | local mail/account database | present and ignored | `EXCLUDE` |
| `runtime/` | runtime logs/state | present | `EXCLUDE` |

Не найдено high-confidence private-key, GitHub-token, AWS-key или Bearer-token
pattern в committed HEAD и status-listed text paths. Это не является гарантией
безопасности archives/screenshots и не отменяет блокировку по env-файлам.

Значения секретов, строки credentials и содержимое env-файлов не выводились и
не сохранялись в отчётах.

## 4. AI state integrity

Проверены `AGENTS.md`, `CLAUDE.md`, обязательные `ai/*.md`, `ai/reports/`,
`ai/inbox/`, `ai/adapters/`, `ai/templates/` и `ai/tools/validate_state.py`.
`ai/inbox/` содержит только `.gitkeep`; product task не создавалась.

AI state files are included as conditional candidates in the allowlist. The
new allowlist/denylist/security report are themselves documentation only. The
validator and scoped formatting check must pass before any future staging.

## 5. `.gitignore`

Подтверждены правила для `.env*`, `mail-data/`, `*.sqlite3`, `*.db`, `tmp/`,
`artifacts/`, `cache/`, Python cache, virtualenvs и runtime JSON. Generic
`secrets/`, `credentials/`, browser profiles и logs покрыты не полностью.

`.gitignore` не изменялся: он уже uncommitted, его provenance неизвестна, а
данный этап заблокирован. Ignored status не считался доказательством
безопасности.

## 6. Allowlist decision

### Safe candidates

Только AI state paths из `ai/PUBLISH_ALLOWLIST.md`, и то условно: после
quarantine/rotation env-файлов, финального scan staged tree и owner approval.

### Review required

Все application source, tests, project config и ordinary documentation paths.
Нужны ручные решения по происхождению, актуальности, секретам, личным данным,
live-provider fixtures и миграциям.

### Excluded

Env/credentials, Temp/runtime, mail-data/local databases, screenshots, archives,
backups, logs, review exports, `Documents/` personal/unknown materials и
удалённые tracked paths.

## 7. Почему push запрещён

Push запрещён одновременно по четырём причинам:

1. local env/backup files могут содержать credentials;
2. `.env.production.local` дал high-confidence credential/database-URL match;
3. `677` путей не имеют утверждённого publish set;
4. repository и shared branch не подтверждены, `origin` отсутствует.

Создание private repository также не выполнялось, потому что это внешнее
изменение до завершения security gate.

## 8. Следующее действие

Владелец должен безопасно кварантировать/очистить env-файлы и при необходимости
ротировать credentials, не присылая их значения в чат; утвердить repository
owner/name, shared branch и allowlist; затем повторить scan staged tree. Только
после `PASS` можно отдельно разрешить создание private repository, настройку
`origin`, commit выбранных файлов и push.
