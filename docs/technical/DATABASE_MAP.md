---
document_id: DOC-TECH-DATABASE-MAP-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Карта базы данных

Итоговая схема после всех 53 файлов миграций (`migrations/001_mail_integration.sql` —
`migrations/052_task_reminder_delivery.sql`), восстановлена чтением всех миграций — это не
история миграций, а результирующий набор таблиц. Заменяет `docs/data/README.md`, который
является заглушкой про назначение каталога без реального содержания схемы.

**Известная проблема нумерации миграций:** два файла претендуют на номер `026`
(`026_mail_account_profiles.sql` и `026_request_email_send_guards.sql`). Оба применяются
(порядок по алфавиту), оба идемпотентны, ничего не сломано — отмечено как `GAP-012`.

## Среда выполнения: SQLite (разработка) vs Postgres (прод)

Подтверждено: на проде задаётся `DATABASE_URL` → `mail/repository.py` подключается через
`psycopg` (Postgres); локально `DATABASE_URL` не задана → используется файл SQLite
`mail-data/supplier.sqlite3`. `mail/db_compat.py` переводит SQL, написанный в диалекте SQLite, на
диалект Postgres (фабрика строк, `BEGIN IMMEDIATE`→`BEGIN`, `last_insert_rowid()`→`LASTVAL()`,
`COLLATE NOCASE`→`LOWER()`, `INSERT OR IGNORE`→`ON CONFLICT DO NOTHING`). Этот слой уже вызвал
два реальных инцидента на проде в этой сессии (guard миграции, работавший только для SQLite, и
падение на `COLLATE NOCASE`) — оба исправлены, и оба были скрытой проблемой с самого дня
написания кода, потому что Postgres ни разу по-настоящему не нагружался реальными данными до
того, как на нём настроили `CHECKO_KEY`. `vercel.json` исключает `*.db`/`*.sqlite3` из
задеплоенной сборки — это согласуется с тем, что Postgres является единственным реальным
хранилищем на проде.

## Авторизация / рабочее пространство

| Таблица | Введена в | Назначение |
|---|---|---|
| `users`, `workspaces`, `workspace_members`, `sessions` | 001 | Базовая идентичность |
| `oauth_states` | 001 | Отслеживание CSRF-состояния OAuth |
| `oauth_login_states` | 005 | Состояние OAuth конкретно для входа |

## Заявки / дашборд

| Таблица | Введена в | Назначение |
|---|---|---|
| `requests` | 001 | Сама заявка |
| `request_meta` | 002 | Статус/прогресс/ошибка |
| `request_positions` | 002 | Позиции (товарные строки) |
| `request_details` | 012 | Дедлайн |
| `request_search_jobs` | 017 | Устойчивая очередь поиска с lease/claim |
| `request_search_options` | 018 | **Устарела, заменена, но всё ещё читается** (LEFT JOIN вместе с преемником) |
| `request_search_config` | 020 | Текущая настройка глубины поиска |
| `request_email_references` | 048 | Публичный идентификатор письма вида `SD-xxxx` |
| `request_followup_settings` | 051 | Переопределение SLA follow-up для конкретной заявки |

## Поставщики — идентичность в рамках workspace

| Таблица | Введена в | Назначение |
|---|---|---|
| `suppliers` | 001 | Идентичность по хосту/краулингу, ключ `(workspace_id, external_key)` |
| `supplier_profiles` | 002 | Профиль ИНН/обогащения |
| `request_suppliers` | 002 | Совпадение заявка↔поставщик (позиции, источник, причина) |
| `blacklist_entries` | 002 | Чёрный список в рамках workspace |
| `supplier_evidence` | 019 | Граф доказательств на уровне полей (сейчас применяется только к кандидатам ИНН) |
| `supplier_enrichment_jobs` | 019 | Устойчивая очередь повторных попыток обогащения |
| `supplier_inn_sources` | 021 | Происхождение ИНН |

## Поставщики — карточка компании (дедупликация по ИНН, всё ещё в рамках workspace)

| Таблица | Введена в | Назначение |
|---|---|---|
| `global_suppliers` | 007 | Карточка компании, уникальна по ИНН, `UNIQUE(workspace_id, inn)` |
| `global_supplier_links` | 007 | Связь 1:1 `suppliers.id` → `global_suppliers.id` |
| `global_supplier_issues`, `request_supplier_ratings` | 007 | Обратная связь пользователя |
| `global_supplier_registry` | 008 | Факты из реестра (ОГРН, статус, активность, дата регистрации) |
| `global_supplier_finances` | 009 | Финансы за последний год |
| `global_supplier_finance_history` | 014 | История финансов |
| `global_supplier_risks` | 015 | Реестровые риск-флаги |
| `global_supplier_blacklist` | 010 | Статус чёрного списка на уровне карточки компании |

## Поставщики — кросс-tenant слой (без `workspace_id`)

| Таблица | Введена в | Назначение |
|---|---|---|
| `canonical_companies` | 038 | Публичные факты, уникально по ИНН, общие для всех рабочих пространств (DECISION-022) |
| `canonical_company_finance_history`, `canonical_company_risks` | 038 | Общая история/риски |
| `canonical_company_contacts` | 051 | Справочник email компании с назначением/статусом |
| `canonical_company_contact_signals` | 051 | Накопительные сигналы доверия (`workspace_confirmed`, `inbound_reply`, `official_source`, отказы доставки) |
| `canonical_company_contact_promotions` | 051 | Накопительный журнал изменений «предпочтительного» статуса |

## Поставщики — приватный слой контактов/классификаций workspace

| Таблица | Введена в | Назначение |
|---|---|---|
| `workspace_supplier_contacts` | 045 | Вручную добавленные контактные лица, видимость приватная/для команды |
| `workspace_supplier_classifications` | 046 | Метки категорий вручную/из реестра/от AI, происхождение хранится отдельно |
| `workspace_supplier_contact_events` | 051 | История результатов действия «Связаться» |
| `workspace_supplier_contact_overrides` | 051 | Предпочтительный email на уровне workspace, накопительная запись (не удаляется, заменяется) |

## Почта — транспорт

`mail_accounts`(001) · `mail_threads`(001, уникальность `(workspace_id, request_id,
supplier_id)`) · `mail_messages`(001) · `mail_attachments`(001) · `mail_jobs`(001) ·
`request_supplier_states`(001, **статус доставки** по паре заявка/поставщик, отдельно от
метаданных совпадения в `request_suppliers`) · `mail_sync_states`(003) ·
`mail_inbox_messages`(004, непривязанные входящие, без связи с заявкой/поставщиком) ·
`mail_inbox_threads`/`mail_inbox_replies`(006) · `mail_message_reads`/
`mail_inbox_message_reads`(011/032) · `mail_inbox_request_links`(031, результат ручной
привязки) · `mail_account_profiles`(026, `+sent_sync_enabled` добавлено в 050) ·
`mail_folder_sync_states`(049) · `mail_sent_messages`(049).

## Почта — целостность отправки / пейсинг / рассылки

`mail_send_operations`/`_targets`(022) · `mail_job_integrity`/`mail_message_integrity`/
`mail_reply_integrity`(022) · `mail_delivery_resolutions`(022) · `mail_runtime_controls`(022) ·
`mail_request_email_guards`(026) · `mail_account_outbound_state`/`mail_send_reservations`/
`mail_send_attempts`(023) · `mail_send_attempt_evidence`(025) · `mail_campaigns`/
`mail_campaign_targets`(024, **обслуживают страницу мониторинга рассылок, у которой нет
интерфейса в v2 — GAP-001**) · `mail_database_identity`/`mail_runtime_sessions`/
`mail_send_attempt_runtime`(027) · `mail_reconciled_outbound_events`(028) ·
`mail_continuation_plans`(029) · `mail_cross_provider_retries`(030).

## Почта — метаданные интерфейса

`mail_thread_user_metadata`(034) · `mail_thread_notes`(035, персональные) ·
`mail_thread_workspace_notes`(041, общие для команды) · `mail_thread_status`(039, метка
`conversation_status`) · `workspace_mail_templates`/`_attachments`(020).

## Задачи

`tasks`(037) · `task_details`(042) · `task_reminders`(043, пересобрана миграциями 044/052) ·
`user_notification_settings`(052). **Внешний ключ `tasks.supplier_id` указывает на
`global_suppliers(id)`, а не на `suppliers(id)`** — легко ошибиться при чтении кода, стоит
запомнить отдельно.

## AI / Логистика / Прочее

`ai_chat_usage`(036) · `ai_conversations`/`ai_messages`(040) · `logistics_quotes`(033) ·
`audit_events`(002) · `search_result_sources`(013) · `support_conversations`/
`support_messages`(047).

## DDL только для Postgres

`016_finance_bigint.sql` расширяет финансовые колонки до BIGINT — пропускается на SQLite по
явной метке `-- postgres-only`, которую проверяет `ensure_schema()`.

## Ключевые связи, которые важно помнить

- `suppliers` →(1:1 через `global_supplier_links`)→ `global_suppliers`. Одна запись `suppliers`
  принадлежит максимум одной карточке компании.
- `global_suppliers` ↔ `canonical_companies`: **внешнего ключа нет** — связь только по
  совпадению значения `inn`.
- `request_suppliers` (метаданные совпадения: позиции, источник, причина) vs
  `request_supplier_states` (статус доставки, `last_message_id`) — два разных смысла на одном и
  том же составном ключе, специально разделены ещё с миграций 001/002.
- У `mail_inbox_messages` по определению нет внешнего ключа на заявку/поставщика (это и значит
  «непривязанное») — связывается позже через `mail_inbox_request_links`.
- `workspace_supplier_contacts`/`_classifications`/`_contact_overrides` используют
  `global_supplier_id` (приватный слой workspace); `canonical_company_contacts` использует
  `canonical_company_id` (кросс-tenant слой) — эти два слоя существуют параллельно, без внешнего
  ключа между собой. Полное обоснование границы — `docs/domain/SUPPLIER_MODEL.md` §6-7.

## Проверка на «осиротевшие» таблицы

Проверены выборочно менее очевидные таблицы (`audit_events`, `request_supplier_ratings`,
`mail_thread_workspace_notes`, `global_supplier_issues`, `search_result_sources`,
`mail_reconciled_outbound_events`, `workspace_supplier_contact_overrides`,
`canonical_company_contact_promotions/signals`, `support_conversations/messages`,
`logistics_quotes`, `mail_database_identity`, `mail_runtime_sessions`) — **подтверждённых
осиротевших таблиц не найдено**, у всех есть реальные обращения в коде. Единственная «заменённая,
но не удалённая» таблица — `request_search_options` (018): её данные были перенесены в
`request_search_config` (020) в той же миграции; `mail/repository.py` до сих пор читает обе.
