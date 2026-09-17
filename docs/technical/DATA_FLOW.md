---
document_id: DOC-TECH-DATA-FLOW-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Поток данных

Техническое (на уровне функций/маршрутов) описание сценариев, изложенных по-человечески в
[`../product/USER_FLOWS.md`](../product/USER_FLOWS.md). Этот файл отвечает на вопрос «как это
работает изнутри», тот — «что видит пользователь».

## Авторизация → сессия → API

`Login.tsx` → `POST /api/auth/login` (или полный цикл Яндекс OAuth) → `backend/http_auth.py` →
`repository.authenticate()`/`_finish_login_callback` → создаётся сессия, ставится cookie →
каждый следующий запрос несёт cookie + заголовок `X-CSRF-Token` (производный, не хранится
отдельно) → `_require_session()`/`_require_csrf()` проверяют каждый маршрут.

## Заявка → позиции → поставщики → коммуникация

`POST /api/requests` (создание) → действие «начать поиск» на `POST /api/requests/<id>` →
создаётся запись в `request_search_jobs` → клиент опрашивает шаг поиска → `process_search_step`
(`orchestrator.py`) выполняет одну позицию SERP или одну пачку обогащения за вызов, сохраняя
курсор → по завершении `request.status = 'completed'`, поставщики уже существуют в
`suppliers`/`request_suppliers` → при составлении/отправке письма реальный получатель
определяется через `resolve_supplier_for_send` (совпадение по хосту → совпадение по email →
**запасной вариант — создание новой записи**, см. `GAP-003`) → создаются `mail_threads`/
`mail_messages` → `request_supplier_states` обновляется при ответе/отказе доставки.

## Поставщики: поиск → обогащение → контакты → привязка к заявке

Найдено в SERP → `upsert_search_result` (имя по умолчанию — хост, никогда сырой заголовок из
выдачи) → ставится в очередь `supplier_enrichment_jobs` (краулинг → предположение ИНН по реестру
→ запасной веб-поиск → финансы) → `apply_supplier_enrichment` — единая точка записи: обновляет
`suppliers`, `global_suppliers` (через `_get_or_create_global_supplier`),
`global_supplier_registry`/`_finances` и `canonical_companies` (кросс-tenant кэш) за один вызов →
`_resolve_missing_inn` проверяет `canonical_companies` по ИНН **до** реального запроса к Checko,
поэтому второе рабочее пространство, резолвящее ту же компанию, не делает ни одного запроса к
Checko.

## Сообщения: почтовый ящик → синхронизация → сообщение → переписка → заявка/поставщик

Фоновая или по просмотру синхронизация (`maybe_sync_incoming`, с ограничением частоты) либо
ручной `POST /api/mail/sync` → забор по IMAP (`mail/providers/*.py`) → `import_incoming_messages`
→ `_find_incoming_thread` (совпадение по заголовкам → совпадение по теме+email) → совпало:
добавляется в `mail_messages`, у переписки обновляется `last_message_at`; не совпало: попадает в
`mail_inbox_messages` (`status='unmatched'`, никогда не удаляется) → человек разрешает через
`attach_inbox_message`/`manually_link_inbox_message` → `GET /api/correspondence` отображает
переписки, `thread_messages()` помечает как прочитанное побочным эффектом открытия.

## AI-ассистент: выбор → сборка контекста → вызов LLM

Пользователь открывает «ИИ-помощника» в переписке → интерфейс предлагает в качестве
дополнительного контекста только те переписки, где `threadResponseStatus === 'answered'`
(это фильтр только для удобства интерфейса) → `POST /api/ai/chat` с `thread_ids` →
`chat_service._build_context` **заново проверяет каждый id на сервере**
(`get_thread_owned`, молча отбрасывает всё, что не принадлежит этому рабочему пространству и
заявке — это и есть настоящая граница безопасности, а не клиентский фильтр) → для каждой
подтверждённой переписки — до 10 последних сообщений реальной коммуникации, каждое обрезано до
4500 символов → весь контекст ограничен 40 000 символами → проверка дневного лимита расходов
(`ai_chat_usage`) → вызов RouterAI → ответ и расход записываются.

## Задачи / напоминания

`POST /api/tasks` → запись в `task_reminders` (канал `in_app`/`email`/`phone`) → **реально
доставляется только `in_app`**: `RemindersContext.tsx` опрашивает
`GET /api/tasks/reminders/due` каждые 45 секунд, пока открыта вкладка, показывает тост и
вызывает системное уведомление браузера. Напоминания `email`/`phone` записываются и проходят
валидацию, но никогда не отправляются — см. `docs/system/CURRENT_STATE.md`.
