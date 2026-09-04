---
document_id: REPORT-TASK-APPLITOOLS-VISUAL-QA-PILOT-20260904
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-04
task_id: TASK-APPLITOOLS-VISUAL-QA-PILOT-20260904
source_commit: 5dd23d5
---

# TASK-APPLITOOLS-VISUAL-QA-PILOT-20260904

## Итог

Статус пилота: `BLOCKED`. Это означает, что безопасная интеграция и
проверки конфигурации готовы, но реальный Eyes cloud-прогон нельзя считать
выполненным: в окружении нет `APPLITOOLS_API_KEY`, а безопасная тестовая
база не содержит переписки для настоящего сценария `/messages`.

Рекомендация: `ADOPT WITH LIMITATIONS` — предварительно использовать только
как добровольный пилот для `/messages` после подтверждения владельцем пути
данных, наличия ключа и санитизированного тестового набора. Это не решение
о включении Applitools в обязательные UI-проверки и не оценка качества
дизайна.

## Цель и границы

Целью была проверка независимого visual regression слоя — автоматического
сравнения рендера с утверждённым снимком — без редизайна продукта.

Изменения ограничены:

- официальным Playwright SDK Applitools;
- отдельным Playwright-конфигом для пилота;
- одним тестом только для `/messages`;
- обязательными state/report записями проекта.

Не менялись UI-исходники, backend, API, база данных, бизнес-логика,
существующие 88 Playwright-тестов, MCP, глобальные VibeCoding Rules и
Tool Registry.

## Совместимость и официальная интеграция

Проверено: существующий стек использует Playwright `1.62.1`. Установлен
`@applitools/eyes-playwright@1.48.4`; его заявленный peer range принимает
текущую версию Playwright.

Использована официальная fixture-based схема:

- `import { test, expect } from '@applitools/eyes-playwright/fixture'`;
- `eyes.check(...)` для визуальных checkpoint;
- отдельный `frontend/playwright.applitools.config.ts`;
- classic runner для независимых размеров viewport;
- `Dynamic` match level только для ожидаемой динамики вроде времени, а не
  для исключения большой части страницы;
- локальный Playwright screenshot сохраняется рядом с каждым Eyes checkpoint.

Официальные материалы, проверенные перед установкой:

- [Applitools Eyes + Playwright Quick Start](https://applitools.com/docs/eyes/playwright)
- [официальная интеграция с Playwright](https://applitools.com/docs/eyes/playwright/integration-with-playwright)
- [официальное advanced usage](https://applitools.com/docs/eyes/playwright/advanced-usage)
- [официальный материал об Applitools MCP](https://applitools.com/blog/add-visual-testing-to-your-ai-workflow-with-the-applitools-mcp-server/)

`eyes-setup` не запускался: он мог бы дополнительно менять проект и
запрашивать ключ. Второй E2E framework не добавлялся.

## Файлы

Изменены только файлы пилота и проектного состояния:

- `frontend/package.json` — скрипт `test:visual:eyes` и exact SDK dependency;
- `frontend/package-lock.json` — воспроизводимая фиксация зависимостей;
- `frontend/playwright.applitools.config.ts` — отдельные проекты и Eyes config;
- `frontend/tests/visual/messages.visual.spec.ts` — реальный `/messages` flow;
- `ai/ACTIVE_TASK.md`, `ai/CURRENT_STATE.md`, `ai/CHANGELOG.md`,
  `ai/INTERACTION_LOG.md`, `ai/LAST_HANDOFF.md`;
- этот отчёт.

Предсуществующие изменения в enrichment-файлах и `runtime/` не включались.

## Сценарии и viewport

Один тест проходит три состояния настоящего приложения:

1. список заявок на `/messages`;
2. открытая переписка по первой реальной паре `request_id/supplier_id`;
3. открытый ответный composer с фокусом в поле текста; отправка не выполняется.

Заложены ровно три репрезентативных размера:

- desktop: `1440×900`;
- laptop: `1280×720`;
- mobile: `390×844`.

Ключевой `/messages` API не подменяется: список переписки читается из
реального SAFE_TEST runtime. Тест останавливается с понятным `BLOCKED`, если
там нет безопасной синтетической переписки.

Динамика: checkpoint использует `Dynamic`, чтобы ожидаемые временные поля не
создавали шум. Широкие области интерфейса не игнорируются; отдельные
`ignoreRegions` не добавлялись.

## Evidence и результаты

| Проверка | Результат | Что это значит |
| --- | --- | --- |
| Workspace guard | `PASS` | Работали в каноническом корне проекта. |
| SDK/Playwright compatibility | `PASS` | SDK `1.48.4` совместим с Playwright `1.62.1`. |
| `npm ci --dry-run --ignore-scripts --no-audit --no-fund` | `PASS` | Lockfile воспроизводит установленный набор без запуска install scripts. |
| `npm run typecheck` | `PASS` | Frontend-код типизируется без ошибок. |
| `playwright ... --list` | `PASS` | Конфиг публикует 3 проекта и 3 тестовых запуска. |
| no-key `npm run test:visual:eyes -- --reporter=line` | `PASS` | `3 skipped` за `1.22s`; Eyes-запрос не отправлялся. |
| existing `npm run test:visual` | `PASS` | Все прежние `88` Playwright-тестов прошли за `4.9m`. |
| SAFE_TEST correspondence | `BLOCKED` | Endpoint ответил `200`, но вернул `0` items. |
| Eyes baseline | `NOT VERIFIED` | Нет ключа и настоящего запуска. Первый baseline не утверждён. |
| Controlled regression | `NOT VERIFIED` | Временный CSS-дефект не вносился без рабочего baseline. |
| Eyes vs Playwright comparison | `NOT VERIFIED` | Реальные результаты двух систем ещё не сопоставлялись. |
| MCP spike | `NOT INSTALLED` | SDK ещё не дал рабочего evidence; ручная авторизация не запрашивалась. |

`python ai/tools/validate_state.py`, `validate_docs.py`,
`validate_traceability.py` и `validate_vibecoding.py` завершились `PASS`.
При промежуточной проверке `validate_docs.py` видел пять отсутствующих
Playwright-артефактов в двух исторических отчётах; повторный существующий
визуальный набор заново создал эти игнорируемые локальные артефакты, после
чего финальная проверка стала зелёной. Исторические отчёты не переписывались.
`git diff --check` нарушений не нашёл.

### Почему это не PASS

Критерий `PASS` требует настоящего `/messages`, baseline на desktop/laptop/
mobile и обнаруженный контролируемый дефект. Их нет из-за внешнего ключа и
отсутствия данных, поэтому корректный статус — `BLOCKED`, а не скрытый
успешный пилот.

## Безопасность и приватность

- Значение `APPLITOOLS_API_KEY` не читалось, не печаталось и не сохранялось.
  Проверялась только наличность переменной; она отсутствует.
- Секрет не добавлялся в `.env`, репозиторий, отчёт, screenshot или лог.
  `.env*` игнорируется правилами Git; файла `.env.example` в проекте нет.
- Реальная почта SupplyDesk не отправлялась в Eyes. Использован только
  SAFE_TEST runtime `OFFLINE_TEST` на `127.0.0.1:18000`, с выключенными
  внешними провайдерами и пустой перепиской.
- В официальных материалах есть различающиеся заявления о локальном и
  облачном пути сравнения. До подтверждения конкретной конфигурации аккаунта
  Eyes следует считать данные checkpoint потенциально передаваемыми во
  внешнюю инфраструктуру. Следовательно, для продолжения нужны только
  санитизированные disposable данные.

## Сравнение с текущим Playwright подходом

Архитектурно Playwright остаётся функциональной проверкой и локальным
источником screenshot-артефактов. Eyes добавляет независимое сравнение с
baseline и внешний visual diff workflow. Фактическое преимущество, шум,
понятность diff, необходимость dashboard и время настоящего облачного
прогона ещё не измерены: пилот остановлен до отправки данных.

## Что потребуется от владельца

1. Безопасно задать `APPLITOOLS_API_KEY` в локальном процессе или CI secret
   store; ключ не присылать в чат и не записывать в файлы проекта.
2. Подготовить или одобрить санитизированную одноразовую переписку в
   SAFE_TEST. Это может потребовать отдельной владелецкой подготовки данных;
   в рамках этого пилота база намеренно не изменялась.
3. Запустить из `frontend` `npm run test:visual:eyes`.
4. Вручную проверить первый provisional baseline и только после этого
   считать его кандидатом на утверждение.
5. Выполнить временный CSS regression experiment, убедиться, что Eyes его
   обнаружил, полностью откатить дефект и повторно проверить чистое различие
   относительно этой задачи.

## Git и хронология

- До task: branch `integration/current-architecture-governance-20260903`,
  HEAD `6206c95806a8caf1dc5191e9c03762151d332ea5`.
- После подготовки: тот же branch, commit `5dd23d5`
  (`chore(qa): add Applitools messages pilot
  TASK-APPLITOOLS-VISUAL-QA-PILOT-20260904`).
- Push не выполнялся.
- Рабочие изменения, относящиеся к enrichment и `runtime/`, остаются
  нетронутыми и не должны попадать в commit этой задачи.

## Уровень уверенности

Высокая уверенность в совместимости SDK, минимальности интеграции и
безопасном поведении no-key режима. Низкая уверенность в дополнительной
ценности Applitools до получения реального baseline/diff; это сознательно
оставлено на следующий владелецкий шаг.
