---
document_id: DOC-TESTING-TEST-INVENTORY-001
status: CURRENT
canonical: true
owner: quality
updated_at: 2026-09-18
source_commit: ab89bfb
---

# Master Test Inventory

Файловая инвентаризация всех реально существующих автоматизированных тестов в репозитории —
`tests/**`, `supplier_discovery_v2/tests/**`, `frontend/tests/**` (legacy, для справки),
`frontend-v2/tests/e2e/**` и `frontend-v2/src/**/*.test.*`. Построена сканированием реальных
файлов 2026-09-18, не выдумана заранее. Один файл — не один тест-кейс: колонка «Тестов»
считает отдельные `def test_...`/`test(...)`/`it(...)` внутри файла, не файлы.

Продуктовые сценарии, которые эти тесты покрывают, — см. [TEST_CASES.md](TEST_CASES.md)
(раздел «Расширенный каталог»). Здесь — обратная проекция: от кода к области, не от требования
к коду.

## Backend (`tests/**`, Python `unittest`)

62 файла, 607 отдельных тестов (без diagnostics). Не пересчитано построчно на предмет
requirement-привязки для каждого теста — см. TEST_CASES.md для сценариев, которые точно
проверены.

| Файл | Тестов | Область | Prod/Legacy |
|---|---|---|---|
| test_mail_deliverability.py | 90 | Mail — предпроверка/подавление/дозирование/gate провайдера | prod |
| test_mail_pacing.py | 65 | Mail — дозирование отправки | prod |
| test_mail_integration.py | 53 | Mail — сквозная интеграция отправки | prod |
| test_mail_integrity.py | 49 | Mail — идемпотентность/авторизация/атомарность | prod |
| test_logistics_quote.py | 28 | Logistics — расчёт доставки (Dellin) | prod |
| test_supplier_identity.py | 27 | Suppliers — идентичность (домен/ИНН/email) | prod |
| test_mail_status_semantics.py | 18 | Mail — оси доставки, безопасность повторов | prod |
| test_enrichment_pipeline.py | 14 | Discovery — обогащение | prod |
| test_contact_resolution_send_path.py | 14 | Suppliers — приоритет контакта при отправке | prod |
| test_contact_intelligence.py | 14 | Suppliers — contact intelligence | prod |
| test_sent_mail_sync.py | 13 | Mail — синхронизация отправленного | prod |
| test_dashboard.py | 13 | Dashboard — KPI/данные | prod |
| test_task_reminder_delivery.py | 12 | Tasks — доставка напоминаний | prod |
| test_mailru_mvp.py | 12 | Mail — Mail.ru провайдер | prod |
| test_outgoing_safety.py | 11 | Mail — safety gate исходящей почты | prod |
| test_mail_smtp_evidence.py | 11 | Mail — SMTP evidence/аудит | prod |
| test_mail_content.py | 10 | Mail — рендеринг HTML/plain/ссылки | prod |
| test_cross_provider_retry.py | 10 | Mail — retry между провайдерами | prod |
| test_canonical_runtime.py | 9 | Data — канонический runtime lock | prod |
| test_task_details.py | 6 | Tasks — CRUD | prod |
| test_supplier_import_preview.py | 6 | Suppliers — импорт (preview) | prod |
| test_secret_redaction.py | 6 | Security — редактирование секретов | prod |
| test_mail_topic_import.py | 6 | Mail — импорт по теме | prod |
| test_dashboard_bulk_sender_filter.py | 6 | Dashboard — фильтр bulk-рассыльщиков | prod |
| test_thread_metadata.py | 5 | Messages — метаданные thread | prod |
| test_support_conversations.py | 5 | Support — обращения в поддержку | prod |
| test_supplier_name_resolution.py | 5 | Suppliers — нормализация имени | prod |
| test_request_email_references.py | 5 | Requests — email references | prod |
| test_messages_visibility.py | 5 | Messages — видимость/фильтры | prod |
| test_thread_notes_visibility.py | 4 | Messages — заметки | prod |
| test_migration_replay_stability.py | 4 | Data — миграции | prod |
| test_messages_interaction_contract.py | 4 | Messages — контракт статусов | prod |
| test_db_compat_postgres_sql_adapter.py | 4 | Data — SQLite/Postgres совместимость | prod |
| test_dashboard_calendar.py | 4 | Dashboard — календарь/задачи | prod |
| test_workspace_supplier_contacts.py | 3 | Suppliers — контакты workspace | prod |
| test_workspace_supplier_classifications.py | 3 | Suppliers — классификации | prod |
| test_test_data_cleanup.py | 3 | Data — очистка тестовых данных | prod |
| test_task_reminder_ui.py | 3 | Tasks — UI-контракт напоминаний | prod |
| test_task_creation_feedback.py | 3 | Tasks — обратная связь при создании | prod |
| test_supplier_import_apply.py | 3 | Suppliers — импорт (apply) | prod |
| test_supplier_directory.py | 3 | Suppliers — справочник | prod |
| test_sent_mail_sync_ui.py | 3 | Mail — UI отправленного | prod |
| test_list_page_header_pluralization.py | 3 | UI — плюрализация заголовков | prod |
| test_followup_task_dedup.py | 3 | Tasks — дедуп напоминаний | prod |
| test_canonical_companies.py | 3 | Discovery — canonical company | prod |
| test_ai_panel_context_copy.py | 3 | AI — копия контекста в панели | prod |
| test_ai_context_scoping.py | 3 | AI — серверная граница контекста (историческая регрессия) | prod |
| test_supplier_card_panel_website_link.py | 2 | Suppliers — ссылка на сайт | prod |
| test_request_email_reference_ui.py | 2 | Requests — UI email reference | prod |
| test_page_header_consistency.py | 2 | UI — согласованность заголовков | prod |
| test_calendar_route_removed.py | 2 | Frontend — регресс на удалённый /calendar | prod |
| test_ai_chat_usage.py | 2 | AI — дневной лимит трат | prod |
| test_activity_timeline.py | 2 | Dashboard — лента активности | prod |
| test_supplier_workspace_isolation.py | 1 | Security — изоляция workspace | prod |
| test_supplier_dedup_p0_regression.py | 1 | Suppliers — **P0 GAP-003, красный тест** (новый, 2026-09-18) | prod |
| test_message_header_action_density.py | 1 | UI — плотность действий в шапке | prod |
| test_mail_topic_import_ui.py | 1 | Mail — UI импорта по теме | prod |
| test_login_provider_ring.py | 1 | Auth — кольцо провайдеров входа | prod |
| test_help_screen.py | 1 | UI — экран справки | prod |
| test_email_renderer_frame_observer.py | 1 | Mail — рендерер письма (iframe) | prod |
| test_canonical_companies_cache_reuse.py | ~2 | Discovery — переиспользование Checko-кэша между workspace | prod |

`tests/diagnostics/**` — 21 файл, 80 тестов. Это отдельная категория: read-only проверки
инструмента «Doctor» (окружение/безопасность/воспроизводимость), не продуктовые сценарии — уже
полностью описаны как `TC-DIAG-*` в TEST_CASES.md.

## `supplier_discovery_v2/tests/**` (Python `unittest`)

5 файлов, 24 теста — query planning, matching, storage, pipeline fixture, immutability.
Область: Discovery. Prod.

## Legacy `frontend/tests/**` (Playwright — НЕ трогать, только источник для чтения)

7 файлов, ~50 явных вызовов `test(...)` (некоторые размножаются на 8 viewport-проектов —
итоговое число реальных прогонов выше, см. `docs/ui-audit-20260904.md`: 88/88). Все они
проверяют legacy `frontend/`, который не задеплоен. Не расширялись и не переносились в этой
задаче (см. `docs/system/KNOWN_GAPS.md#GAP-010`).

| Файл | test() | Область |
|---|---|---|
| campaign-ui.spec.ts | 20 | Mail campaigns UI (legacy) |
| frontend-audit.spec.ts | 13 | Публичная оболочка, responsive/a11y (legacy) |
| mailru-ui.spec.ts | 9 | Mail.ru UI (legacy) |
| email-renderer-responsive.spec.ts | 3 | Рендерер письма (legacy) |
| fast-browser-smoke.spec.ts | 2 | Smoke (legacy) |
| live-email-regression.spec.ts | 2 | Реальная почта (legacy, ручной запуск) |
| storybook-visual.spec.ts | 1 (цикл по историям) | Storybook (legacy) |

## `frontend-v2` — новый QA-контур (Playwright + axe, 2026-09-17/18)

6 spec-файлов, 24 отдельных теста (после раскрытия циклов `for...of`).

| Файл | Тестов | Область | Статус на 2026-09-18 |
|---|---|---|---|
| smoke.spec.ts | 9 блоков (SMOKE-001..010) | Production routes, login, AI panel открытие | 9/9 PASS |
| a11y.spec.ts | 5 (цикл по 5 страницам) | Accessibility (axe) | 4 PASS, 1 FAIL (GAP-015) |
| visual.spec.ts | 5 (цикл по 5 экранам) | Visual regression, desktop 1440px | 5/5 PASS |
| mobile.spec.ts | 3 | Visual/interaction, 390px | 2 PASS, 1 FAIL (GAP-016) |
| regression/ai-context.spec.ts | 1 | AI context scoping (frontend-контракт поверх backend-границы) | PASS |
| regression/supplier-dedup.spec.ts | 1 (`test.fixme`) | Указатель на `tests/test_supplier_dedup_p0_regression.py` | fixme (реальный тест — в backend) |

## `frontend-v2/src/**/*.test.*` (Vitest, компонентные)

4 файла, 14 тестов: `ContactResultModal.test.tsx` (5), `CommandPalette.test.tsx` (1),
`derive.test.ts` (3), `reply-subject.test.ts` (5). Все PASS.

## Итоговые числа (файлы / отдельные тесты)

| Дерево | Файлов | Отдельных тестов |
|---|---|---|
| `tests/*.py` (продуктовые) | 62 | 607 |
| `tests/diagnostics/*.py` | 21 | 80 |
| `supplier_discovery_v2/tests/*.py` | 5 | 24 |
| `frontend/tests/*.spec.ts` (legacy, только чтение) | 7 | ~50 (до размножения по viewport) |
| `frontend-v2/tests/e2e/**/*.spec.ts` | 6 | 24 |
| `frontend-v2/src/**/*.test.*` | 4 | 14 |
| **Итого (без legacy frontend)** | **98** | **749** |
| **Итого (с legacy frontend)** | **105** | **~799** |
