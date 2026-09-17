---
document_id: DOC-SYSTEM-MAP-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Карта системы

Полный аудит репозитория проведён 2026-09-17 на ветке `experiment/frontend-v2-greenfield-20260905`
@ `dc66b0b`. Это точка входа в новое дерево документации `docs/system|product|frontend|
technical|spec|testing|validation|decisions`, созданное этим аудитом. Документ **заменяет**
`docs/architecture/COMPONENT_MAP.md` (от 2026-09-04, написан до появления `frontend-v2` —
сохранён ради истории, но не как источник текущих фактов) в роли карты того, что реально
работает сегодня.

Старые документы не отбрасываются: там, где они были проверены и подтвердились в ходе этого
аудита, на них просто даётся ссылка вместо переписывания. См.
[`KNOWN_GAPS.md`](KNOWN_GAPS.md) — там точный список того, что оказалось устаревшим.

## Что такое SupplyDesk

B2B-инструмент для отдела снабжения одного рабочего пространства (workspace): покупатель
создаёт **заявку** (request) с одной или несколькими **позициями** (position — товар, который
нужно найти), система ищет в интернете кандидатов-поставщиков, обогащает их (данные из реестра
юрлиц и финансовая отчётность через Checko), покупатель рассылает им письма с запросом
предложения, а ответы попадают в **переписку** (correspondence), привязанную к заявке и
поставщику. Отдельный AI-ассистент отвечает на вопросы, используя реальную историю переписки по
конкретной заявке. Задачи/напоминания и небольшой калькулятор стоимости доставки (Dellin)
дополняют MVP.

## Структура репозитория (верхний уровень)

| Путь | Роль |
|---|---|
| `supplier_app.py` | Главный HTTP-обработчик — маршрутизация всех запросов (GET/POST/PUT/DELETE), проверка авторизации/CSRF/лимита запросов, запуск фоновых потоков |
| `api/index.py` | Тонкая обёртка-адаптер для Vercel serverless поверх `supplier_app.py` |
| `mail/` | Слой хранения данных и бизнес-логики: `MailRepository` (составной из миксинов класс на ~9000+ строк) плюс отдельные модули (`service.py`, `content.py`, `bounce.py`, `pacing.py`, `queue.py`, `runtime.py`, `db_compat.py`, `tasks.py`, `task_reminder_delivery.py`, `contact_intelligence.py`, `canonical_companies.py`, `ai_chat_usage.py`, `ai_conversations.py`, `auth.py`, `auth_accounts.py`, `providers/`) |
| `backend/` | Более новые, лучше разделённые доменные сервисы: `http_*.py` (миксины маршрутов), `domain/{supplier_enrichment,supplier_identity,supplier_import,logistics,ai_agent}/`, `integrations/{llm,logistics,registry,search}/` |
| `migrations/` | 53 версионированных `.sql`-файла, применяются заново при каждом запуске процесса (`MailRepository.ensure_schema()`) — см. [`../technical/DATABASE_MAP.md`](../technical/DATABASE_MAP.md) |
| `frontend-v2/` | **Реально работающий (задеплоенный) интерфейс** (React 19 + Vite + Tailwind v4 + react-router-dom v7, hash-роутинг) |
| `frontend/` | **Мёртвый код, не деплоится.** Заморожен с ~2026-09-04; более богатый набор QA-инструментов (Playwright/Storybook/axe/Applitools) так и не был перенесён в v2. См. [`../frontend/FRONTEND_ARCHITECTURE.md`](../frontend/FRONTEND_ARCHITECTURE.md) |
| `supplier_discovery_v2/` | Планирование поисковых запросов / read-only HTTP-адаптеры для поиска поставщиков |
| `scripts/` | PowerShell-инструменты оператора: защита рабочей директории, запуск canonical-рантайма, диагностика |
| `tests/` | ~90 файлов на Python `unittest` (backend-регрессия) + паттерн «проверки по исходному тексту» (`test_*_ui.py` проверяет наличие строк в `.tsx`-файлах, ничего реально не рендерит) |
| `ai/` | Живой трекер состояния сессии/задач (`CURRENT_STATE.md`, `ACTIVE_TASK.md`, `DEFERRED_FINDINGS.md`, правила governance) — канонический источник «что верно прямо сейчас», отдельно от этого статического дерева `docs/` |
| `docs/` | Структурная/архитектурная/требования-документация (это дерево) — уже существовавшая, дисциплинированная система (метаданные status/owner/updated_at/source_commit), частично пересекающаяся с этим аудитом |

## Какой frontend реальный (проверено, а не предположено)

`vercel.json` собирает только `frontend-v2` (`buildCommand: cd frontend-v2 && npm run build`,
`outputDirectory: frontend-v2/dist`, и явно исключает `frontend/**` из serverless-сборки).
`frontend/` не получал коммитов ~2 недели, пока `frontend-v2/` обновляется почти ежедневно.
Подробности: [`../frontend/FRONTEND_ARCHITECTURE.md`](../frontend/FRONTEND_ARCHITECTURE.md).

## Прод vs локальная разработка

- **Прод (Vercel):** Postgres через `DATABASE_URL` (`mail/repository.py` определяет режим по
  этой переменной; `mail/db_compat.py` переводит SQL, написанный в диалекте SQLite, на диалект
  Postgres).
- **Локальная разработка:** только SQLite, файл `mail-data/supplier.sqlite3`,
  `DATABASE_URL` не задана.
- В обоих случаях выполняются одни и те же миграции и один и тот же код `MailRepository` —
  слой совместимости (`db_compat.py`) единственное место, где различия диалектов обрабатываются
  явно, и он уже приводил к двум реальным инцидентам на проде (guard миграции, работавший только
  для SQLite; несовместимость `COLLATE NOCASE`) — оба исправлены в этой сессии именно потому, что
  Postgres впервые был по-настоящему нагружен реальными данными только после того, как на проде
  настроили `CHECKO_KEY`.

## Модель фоновых процессов

Cron не используется. Две устойчивые очереди задач с механизмом lease/claim
(`request_search_jobs`, `supplier_enrichment_jobs`), спроектированные так, чтобы переживать
«заморозку» serverless-функции посреди выполнения:
- Локально: фоновый поток опрашивает очередь каждые 15 секунд (`orchestrator.py`).
- На Vercel (задана переменная `VERCEL`): фоновый поток отключён; вместо этого frontend вызывает
  `POST /api/enrichment/step` как «пульс» — за один вызов продвигается ровно один шаг очереди.

Отдельный поток синхронизации почты опрашивает IMAP каждые 300 секунд локально, плюс
синхронизация при открытии экрана (`maybe_sync_incoming`, не чаще раза в 45 секунд на
пользователя).

## Трёхуровневая модель идентичности поставщика (проверено по `docs/domain/SUPPLIER_MODEL.md`)

1. `suppliers` — в рамках одного workspace, ключ `(workspace_id, external_key=host)`. Хранит
   идентичность для краулинга и почты.
2. `global_suppliers` — в рамках одного workspace, дедупликация по ИНН («карточка компании»).
3. `canonical_companies` — кросс-tenant (без `workspace_id`), ключ по ИНН, только публичные
   факты о компании.

Модель реальная и в целом соблюдается — но есть один подтверждённый, **живой** (а не
исторический) пробел: см. [`INV-SUP-002` в `../spec/PRODUCT_INVARIANTS.md`](../spec/PRODUCT_INVARIANTS.md)
и [`GAP-003` в `KNOWN_GAPS.md`](KNOWN_GAPS.md).

## AI-ассистент (подтверждено: реальный, не заглушка)

Обращается к настоящей LLM через RouterAI (переменная окружения `ROUTERAI_CHAT_KEY`, модель по
умолчанию — `meta-llama/llama-3.3-70b-instruct`). Сборка контекста проверяется на сервере
(`get_thread_owned` заново сверяет каждый переданный клиентом id переписки с рабочим
пространством и заявкой) и явно ограничена поставщиками с реальной коммуникацией — историческая
проблема «в AI-контекст попадали все поставщики заявки» была найдена и исправлена 10.09.2026
(коммит `0d16945`) и подтверждённо остаётся исправленной. Подробности:
[`../product/AI_ASSISTANT.md`](../product/AI_ASSISTANT.md).

## Задачи/Календарь (проверено: сами задачи реальны, доставка напоминаний — по большей части нет)

CRUD задач и их завершение — реальные, хранятся в БД, привязаны к маршрутам API. Полноэкранный
роут `/calendar` удалён 17.09.2026 как мёртвый код (пункт меню на него уже был убран ранее) —
единственный интерфейс календаря теперь — виджет `DashboardCalendar` на дашборде, и он
отображает реальные данные задач. Про доставку напоминаний документация честна: только
in-app-канал (тост в интерфейсе + системное уведомление браузера, пока вкладка открыта, опрос
раз в 45 секунд) реально что-то делает; напоминания по email записываются, но никогда не
отправляются (нет пути отправки вообще); напоминания по телефону прямо в интерфейсе помечены
как локальная заглушка. Подробности: [`../product/PRODUCT_MODEL.md`](../product/PRODUCT_MODEL.md).

## Авторизация

Два способа входа: email+пароль (единственный заранее заведённый пользователь через переменные
`APP_USER_EMAIL`/`APP_USER_PASSWORD` — не общая регистрация) и вход через Яндекс OAuth (PKCE).
Сессии — непрозрачные токены на стороне сервера в cookie с флагами `HttpOnly`/`SameSite=Lax`.
Защита CSRF — производный токен (`sha256(session+":csrf")`), а не случайное сохранённое
значение. Авторизация доступа — неявно по workspace (доверяет `session["workspace_id"]`) плюс
одна роль «владелец» для служебных (maintenance) маршрутов. Подробности:
[`../technical/API_MAP.md`](../technical/API_MAP.md).

## Указатель по темам

| Тема | Документ |
|---|---|
| Статус по каждой функции (реализовано/частично/сломано/заглушка/не реализовано) | [`CURRENT_STATE.md`](CURRENT_STATE.md) |
| Всё найденное, что не так, но не исправлено | [`KNOWN_GAPS.md`](KNOWN_GAPS.md) |
| Инварианты продукта (устойчивые правила, у каждого свой ID) | [`../spec/PRODUCT_INVARIANTS.md`](../spec/PRODUCT_INVARIANTS.md) |
| Полный список маршрутов API | [`../technical/API_MAP.md`](../technical/API_MAP.md) |
| Полная схема базы данных | [`../technical/DATABASE_MAP.md`](../technical/DATABASE_MAP.md) |
| Frontend v1 vs v2, инвентарь UI-компонентов | [`../frontend/`](../frontend/FRONTEND_ARCHITECTURE.md) |
| Бизнес-правила почты/переписки | [`../product/MESSAGES.md`](../product/MESSAGES.md) |
| Модель идентичности поставщиков + проблема дублирования | [`../product/SUPPLIERS.md`](../product/SUPPLIERS.md) |
| Правила формирования AI-контекста | [`../product/AI_ASSISTANT.md`](../product/AI_ASSISTANT.md) |
| requirements.yaml, тест-кейсы, трассировка | [`../spec/`](../spec/requirements.yaml), [`../testing/`](../testing/TEST_CASES.md), [`../validation/TRACEABILITY_MATRIX.md`](../validation/TRACEABILITY_MATRIX.md) |
