---
document_id: DOC-TECH-API-MAP-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Карта API

Полный перечень маршрутов `supplier_app.py` @ `dc66b0b` (ветка
`experiment/frontend-v2-greenfield-20260905`). Заменяет `docs/api/README.md`/
`docs/api/messages.md` по полноте (те документы остаются верны для своего узкого охвата —
метаданные переписки/сообщений — но никогда не были исчерпывающими).

Пути маршрутов, HTTP-методы и технические идентификаторы оставлены без перевода — они
используются программно.

## Общие правила авторизации/безопасности

Каждый маршрут требует активную сессию (`_require_session()`, иначе 401), **кроме**:
`/api/auth/login`, `/api/auth/me`, `/api/auth/yandex/start`, `/oauth/yandex/callback`,
статических файлов и заглушки SPA.

Каждый изменяющий маршрут (POST/PUT/DELETE) дополнительно требует:
- `_require_csrf()` — 403 при отсутствующем или неверном заголовке `X-CSRF-Token` (производный
  токен `sha256(session_cookie + ":csrf")`, а не случайное сохранённое значение)
- `allow_api_request()` — 429 после 30 запросов за 60 секунд на один токен сессии

Служебные (owner-only) маршруты (все под `/maintenance/*`): проверка `is_workspace_owner`, 403 с
русским текстом ошибки, если вызывающий не владелец рабочего пространства.

## GET-маршруты

| Путь | Авторизация | Назначение |
|---|---|---|
| `/maintenance/test-data-cleanup-20260909` | сессия + владелец | HTML-страница подтверждения для очистки тестовых данных |
| `/assets/*`, `/fonts/*` | нет | Статическая сборка фронтенда / шрифты |
| `/api/auth/me` | нет | Информация о текущей сессии/пользователе |
| `/api/auth/yandex/start` | нет | Начало входа через Яндекс OAuth |
| `/api/support/*` | сессия | Под-маршрутизатор чата поддержки |
| `/api/dashboard/summary` | сессия | Показатели (KPI) дашборда |
| `/api/tasks` | сессия | Список задач |
| `/api/tasks/reminders/due` | сессия | Наступившие напоминания (опрашивается с интерфейса) |
| `/api/tasks/reminders/feed` | сессия | Лента уведомлений |
| `/api/notification-settings` | сессия | Настройки уведомлений |
| `/api/workspace/members` | сессия | Список участников рабочего пространства |
| `/api/requests`, `/api/requests/*` | сессия | Список заявок + под-маршрутизатор (позиции, поиск, follow-up, заметки к переписке, оценки) |
| `/api/suppliers` | сессия | Список поставщиков с фильтрами |
| `/api/blacklist` | сессия | Чёрный список |
| `/api/global-suppliers`, `/api/global-suppliers/*` | сессия | Справочник поставщиков + детальная карточка |
| `/api/supplier-directory` | сессия | Справочник поставщиков |
| `/api/correspondence` | сессия | Список переписок (запускает синхронизацию входящих с ограничением частоты) |
| `/api/logistics/freight-types`, `/api/logistics/terminals` | сессия | Справочники логистики |
| `/api/mail/template` | сессия | Получить сохранённый шаблон письма |
| `/api/mail/status` | сессия | Статус почтового сервиса |
| `/api/mail/runtime/outgoing` | сессия | Состояние флага «исходящая почта включена» |
| `/api/mail/accounts` | сессия | Список подключённых почтовых ящиков |
| `/api/mail/inbox`, `/inbox/requests`, `/inbox/preview`, `/inbox/unmatched` | сессия | Непривязанные входящие письма (полный список / превью / кандидаты на ручную привязку) |
| `/api/mail/request-status` | сессия | Статусы почты по поставщикам одной заявки |
| `/api/mail/queue`, `/queue/messages` | сессия | Статистика очереди отправки / исходящие письма |
| `/api/mail/campaigns/<id>` | сессия | Сводка по рассылке (**в v2 интерфейс, использующий этот маршрут, отсутствует**, см. GAP-001) |
| `/api/mail/threads` | сессия | Сообщения переписки |
| `/api/mail/search` | сессия | Полнотекстовый поиск по почте |
| `/api/ai/chat/usage` | сессия | Дневной расход/лимит AI |
| `/api/ai/conversations`, `/api/ai/conversations/<id>` | сессия | Список/детали AI-диалогов |
| `/api/mail/inbox/<id>/suggestions` | сессия | Предполагаемые совпадения заявок для непривязанного письма |
| `/api/mail/inbox/conversation` | сессия | Полная переписка из папки непривязанных писем |
| `/api/mail/yandex/start` | сессия | Начало OAuth для подключения почтового ящика |
| `/oauth/yandex/callback` | нет (проверяется одноразовый токен состояния) | Callback OAuth — и для входа, и для подключения почты |
| любой другой путь под `/api/*`, `/oauth/*` | — | 404 |
| пути, похожие на исходный код (`.py`, `.env` и т.п.) | — | 404 (явная защита от сканеров) |
| любой другой путь | нет | Оболочка SPA |

## POST-маршруты

Служебные (owner-only) маршруты, все POST, все с проверкой CSRF+лимита частоты:
`/maintenance/restore-global-suppliers-20260909`, `/restore-deleted-suppliers-20260910`,
`/backfill-placeholder-supplier-names-20260911`, `/refresh-bad-global-supplier-names-20260911`.
**`/maintenance/force-enrich-all-suppliers` в этой ветке отсутствует** — см. `GAP-002` в
[`../system/KNOWN_GAPS.md`](../system/KNOWN_GAPS.md).

`/api/auth/login` (до авторизации, без CSRF по определению) и `/api/auth/logout` (сессия+CSRF,
без ограничения частоты) — два исключения из общих правил авторизации. Все остальные ниже — с
сессией, CSRF и ограничением частоты:

`/api/enrichment/step` (пульс для очереди обогащения на Vercel), `/api/mail/runtime/outgoing`,
`/api/mail/test`, `/api/mail/accounts/mailru/connect`, `/api/mail/accounts/<id>/
{sent-sync,test}`, `/api/mail/sync`, `/api/mail/sent/{preview,sync}`, `/api/mail/topic/
{preview,import}`, `/api/mail/diagnose*` (5 вариантов диагностики), `/api/mail/resync`, `/api/
mail/disconnect`, `/api/mail/template`, `/api/mail/deliverability/{preflight,preview}`,
`/api/mail/send`, `/api/mail/send-bulk`, `/api/mail/cross-provider-retry/{preview,apply}`,
`/api/mail/campaigns/<id>/{continuation-dry-run,continuation-apply,pause,resume,stop}`,
`/api/mail/messages/<id>/{verify,resend,resolve}`, `/api/mail/inbox/{manual-link,manual-unlink,
ignore,attach,reply}`, `/api/correspondence/metadata`, `/api/ai/chat`, `/api/support/*` (POST),
`/api/tasks` (создание), `/api/supplier-import/{preview,apply}`, `/api/tasks/<id>/done`,
`/api/tasks/reminders/{read-all,<id>/dismiss,<id>/snooze,<id>/read}`, `/api/notification-settings`
(сохранение), `/api/requests` (создание), `/api/blacklist` (добавление), `/api/mail/suppression`,
`/api/irrelevant`, `/api/blacklist/<id>/restore`, `/api/global-suppliers/*` (под-маршрутизатор
действий), `/api/requests/*` (под-маршрутизатор действий — старт/шаг поиска, обновление ИНН,
оценки, настройки follow-up, заметки к переписке, результат контакта).

## PUT / DELETE

| Путь | Метод | Назначение |
|---|---|---|
| `/api/tasks/<id>` | PUT | Обновить задачу |
| `/api/mail/accounts/<id>` | DELETE | Отключить почтовый ящик |
| `/api/tasks/<id>` | DELETE | Удалить задачу |
| `/api/requests/<id>` | DELETE | Удалить заявку (409, если требуется разрешение по доставке — `BR-DATA-001`) |

## Обработка ошибок

`do_POST` оборачивает весь каскад маршрутов в один `try/except` в следующем порядке приоритета:
`DeliverabilityPreflightError` → 409 (с деталями в поле `preflight`) · `PermissionError` → 403 ·
`(ValueError, TypeError, ProviderError, EncryptionConfigError)` → 400, либо 503 конкретно для
`ProviderError`, помеченной как временная (transient) · любое другое `Exception` →
`log.exception(...)`, затем 500 с общим текстом на русском (этот перехватчик был добавлен после
реального случая, когда `/api/ai/chat` падал молча, без следа в логах). `do_PUT`/`do_DELETE`
используют те же коды ответов, но с отдельным `try/except` на каждый маршрут вместо одного общего
каскада. Все JSON-ответы с ошибкой имеют вид `{"error": "<текст на русском>"}`.

## Фоновые задачи (не маршруты, но часть поведения системы в рантайме)

| Задача | Когда запускается | Назначение |
|---|---|---|
| `request_search_jobs` | По требованию (действие «шаг поиска» на `POST /api/requests/<id>`), опрашивается, пока открыта карточка заявки | Поиск в SERP → обогащение хостов по позициям, один шаг за один вызов |
| `supplier_enrichment_jobs` | Локально: фоновый поток каждые 15 сек. На Vercel: пульс `POST /api/enrichment/step` (фоновый поток отключён при заданной переменной `VERCEL`) | Очередь повторных попыток обогащения (краулинг/реестр/веб/финансы), задержка между попытками растёт до 6 часов |
| Синхронизация почты | Фоновый поток каждые 300 сек (локально) + ограничение по просмотру раз в 45 сек (`maybe_sync_incoming`, срабатывает при открытии экрана «Сообщения»/«Входящие») | Забор писем по IMAP для всех активных почтовых ящиков |

## Доменные сервисы (`backend/`)

| Модуль | Ответственность |
|---|---|
| `http_auth.py` | Вход, начало/callback OAuth, вспомогательные функции сессии/CSRF |
| `http_global_suppliers.py` | Детальная карточка поставщика, заметки, контакты, классификации |
| `http_requests.py` | Жизненный цикл заявки/позиций/поиска, расчёты логистики, follow-up, заметки к переписке |
| `http_static.py` | Отдача статики, загрузка фикстур |
| `http_support.py` | Внутренний чат поддержки |
| `domain/ai_agent/chat_service.py` | Оркестрация AI-чата + дневной лимит расходов |
| `domain/logistics/quote_service.py` | Поиск маршрутов/терминалов + расчёт стоимости (Dellin) |
| `domain/supplier_enrichment/` | Полный пайплайн SERP→краулинг→реестр→веб→финансы, оба драйвера очередей |
| `domain/supplier_identity/` | Извлечение email/ИНН, проверка контрольной суммы ИНН и резолюция по реестру, проверка владения доменом |
| `domain/supplier_import/` | Предпросмотр/применение массового импорта из CSV |
| `integrations/llm/` | LLM-фолбэк с ограничением бюджета + клиент RouterAI |
| `integrations/logistics/` | Клиент API Dellin |
| `integrations/registry/` | Клиенты Checko и DaData |
| `integrations/search/` | Клиент SERP-поиска XMLRiver, резервный веб-поиск |
| `integrations/secret_redaction.py` | Маскирование секретов в логах/ошибках |
