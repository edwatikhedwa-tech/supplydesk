# TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`PASS_3_COMPLETE` — [CONFIRMED] 16 auth/session/OAuth-методов
(`_login`, `_auth_me`, `_pkce_pair`, `_auth_yandex_start`, `_oauth_start`,
`_oauth_callback`, `_finish_mail_connect_callback`, `_finish_login_callback`,
`_require_session`, `_keep_session_alive`, `_session_cookie_header`,
`_require_csrf`, `_cookie`, `_session_token`, `_csrf_token_for_session`,
`_public_user`) вынесены из `SupplierHandler` в `backend/http_auth.py` как
`AuthHandlerMixin`. `class SupplierHandler(AuthHandlerMixin,
SimpleHTTPRequestHandler)` композирует его через наследование.
`do_GET`/`do_POST`/`do_DELETE` и порядок проверки маршрутов **не
менялись** — таблица диспетчеризации НЕ вводилась (см. решение ниже).
`supplier_app.py`: 1364 → 1185 строк.

## Почему без dispatch table

Явное владельческое указание: "Не считать перевод do_GET/do_POST на route
dispatch table обязательным предварительным условием... Preferred first
batch: AUTH extraction." Auth-кластер физически НЕ шёл единым блоком — был
перемешан с `_serve_app_shell` (SPA-shell, не auth) и route-хелперами
(`_thread_messages`, `_request_route`, `_global_supplier_route` и др. —
кандидаты будущих батчей B/C). Каждый auth-метод перенесён индивидуально;
`do_GET`/`do_POST`/`do_DELETE` физически не тронуты ни одним байтом.

### DISPATCH_TABLE decision

`do_GET`/`do_POST` всё ещё длинные if/elif-цепочки (~65 маршрутов
суммарно) — но это не в scope AUTH-батча. Решение отложено до после
следующих батчей (request/global-supplier/mail route helpers), как и
предписано (`# 5. DISPATCH_TABLE DECISION` — только после безопасного
extraction всех кластеров).

`DISPATCH_TABLE: DEFERRED` (не JUSTIFIED и не NOT_NEEDED — решение
принимается после оценки оставшейся сложности `do_GET`/`do_POST` в конце
батчей A/B/C, не сейчас).

## Расположение модуля

`backend/http_auth.py` (плоский модуль, класс `AuthHandlerMixin`) — не
`backend/http/auth.py`: в дереве нет `backend/http/`-пакета, есть только
плоские модули `backend/app_config.py`, `backend/http_static.py`.
Наименование выбрано для консистентности с уже установленным паттерном
(подтверждено сверкой дерева `backend/` перед созданием файла).

## Что сделано

1. Создан `backend/http_auth.py` — 16 методов byte-for-byte + импорты
   (`base64`, `hashlib`, `HTTPStatus`, `SimpleCookie`, `new_token`,
   `token_hash`, `EncryptionConfigError`, `ProviderError`,
   `yandex_provider_factory`).
2. `supplier_app.py`: `class SupplierHandler(SimpleHTTPRequestHandler):`
   → `class SupplierHandler(AuthHandlerMixin, SimpleHTTPRequestHandler):`.
   16 методов удалены четырьмя точными диапазонами (не единым блоком, т.к.
   не шли подряд); `base64`, `hashlib`, `SimpleCookie` удалены из импортов
   (использовались только в перенесённом коде, сверено grep); `HTTPStatus`,
   `ProviderError`, `EncryptionConfigError` остались — используются вне
   auth-блока (`send_head`, обработка ошибок mail-маршрутов в `do_POST`).
3. `ai/DEFERRED_FINDINGS.md`: добавлен `FINDING-020` — отсутствие тестов
   на 404/SPA-fallback для `do_GET` (найдено попутно, не относится к этому
   переносу, код `do_GET` не менялся).

## Characterization evidence (перед переносом)

По явному требованию проверены существующие тесты на реальное покрытие
(не предположение):

| Сценарий | Существующий тест | Результат grep-проверки |
|---|---|---|
| `/api/auth/me` (authenticated) | `tests/test_mail_integrity.py::test_session_renews_on_activity_and_survives_repository_restart`, `test_expired_session_is_not_revived_by_activity` | [CONFIRMED] найдено |
| CSRF-защищённый POST | `tests/test_outgoing_safety.py::test_owner_endpoint_requires_csrf_confirmation_and_explicit_owner` | [CONFIRMED] найдено |
| Login/session | покрыто теми же двумя тестами выше + широко через весь `tests/test_mail_integrity.py`/`test_dashboard.py` (используют authenticated harness) | [CONFIRMED] |
| Unknown `/api/*` → 404, SPA fallback | — | [NOT COVERED] — записано как `FINDING-020`, не в scope (код `do_GET` не менялся) |

## Проверено

| Проверка | Результат |
|---|---|
| `ast.parse()` обоих файлов | [CONFIRMED] |
| `SupplierHandler.__mro__` | [CONFIRMED] `['SupplierHandler', 'AuthHandlerMixin', 'SimpleHTTPRequestHandler', 'BaseHTTPRequestHandler', 'StreamRequestHandler', 'BaseRequestHandler', 'object']` |
| `hasattr` на все 16 перенесённых методов | [CONFIRMED] `True` |
| Офлайн импорт `supplier_app`, `api.index.handler` | [CONFIRMED] |
| `tests.test_dashboard/test_outgoing_safety/test_mail_integrity/test_mail_integration/test_enrichment_pipeline` (129 тестов) | [CONFIRMED] `OK (skipped=1)` |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=497; failures=0; errors=9 (baseline); skipped=1` |
| Внешние ссылки на auth-методы (`grep tests/ scripts/`) | [CONFIRMED] `0` — ничего не патчит эти методы напрямую |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — 4 файла продукта
(`supplier_app.py`, новый модуль, `CLAUDE.md`, `ai/DEFERRED_FINDINGS.md`)
+ state-файлы.

## Не проверено

- NOT VERIFIED: реальный OAuth-обмен с Yandex (`_finish_login_callback`,
  `_finish_mail_connect_callback`) — требует живого provider callback,
  вне офлайн-контракта; код не изменился, только местоположение.

## Следующий шаг

Batch B (request route helpers: `_thread_messages`, `_request_route`,
`_request_action`) и Batch C (`_global_supplier_route`,
`_global_supplier_action`, mail HTTP route helpers) — каждый отдельным
коммитом, без вопроса владельцу между ними (явно разрешено). После них —
оценка `DISPATCH_TABLE` для `do_GET`/`do_POST`. Затем — `mail/repository.py`
mixin-разбиение по кластерам (auth/suppliers/messages/campaigns/queue/inbox).
