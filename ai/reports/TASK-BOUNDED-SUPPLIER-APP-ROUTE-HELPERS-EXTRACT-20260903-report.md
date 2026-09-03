# TASK-BOUNDED-SUPPLIER-APP-ROUTE-HELPERS-EXTRACT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`BATCHES_A_B_COMPLETE` — [CONFIRMED] request-маршрутные хелперы
(`_thread_messages`, `_request_route`, `_request_action`) вынесены в
`backend/http_requests.py` (`RequestRouteMixin`); global-supplier хелперы
(`_global_supplier_route`, `_global_supplier_action`) — в
`backend/http_global_suppliers.py` (`GlobalSupplierRouteMixin`).
`class SupplierHandler(AuthHandlerMixin, RequestRouteMixin,
GlobalSupplierRouteMixin, SimpleHTTPRequestHandler)`. `do_GET`/`do_POST`/
`do_DELETE` не тронуты ни одним байтом. `supplier_app.py`: 1185 → 1038
строк.

## Батч C (mail HTTP route helpers) — НЕ выполнен, обоснование

В отличие от request/global-supplier, у mail-маршрутов **никогда не было
отдельного sub-router метода** — все ~35 GET-веток и ~30 POST-веток
`/api/mail/*` обрабатываются инлайн прямо внутри `do_GET`/`do_POST`
(проверено grep: `_mail_route`/`_mail_action` не существуют). Извлечь их
"как есть" технически невозможно — извлекать нечего. Единственный способ
получить для них mixin — сначала СОЗДАТЬ новую границу метода внутри
`do_GET`/`do_POST` (заменить инлайн-блок на вызов нового метода), что уже
не чистый перенос, а изменение тела `do_GET`/`do_POST`. Явное указание
владельца: "do_GET/do_POST стей в SupplierHandler; их route condition
ordering не менять... После extraction они просто вызывают inherited
methods" — это описывает лифтинг УЖЕ существующих методов, не создание
новых границ. Батч C оставлен нетронутым до отдельного решения.

## DISPATCH_TABLE decision

| Метод | Строк | Комментарий |
|---|---|---|
| `do_GET` | ~204 | Не сократился батчами A/B — bulk даёт inline mail-логика |
| `do_POST` | ~326 | Аналогично |
| `do_DELETE` | ~52 | Короткий, не проблема |

`DISPATCH_TABLE: NOT_NEEDED` — таблица диспетчеризации сама по себе не
уменьшит объём кода: реальный объём создают тела mail-маршрутов, которые
таблица не сжимает, только меняет способ поиска ветки. Per явное указание
("Не переписывать рабочую маршрутизацию ради архитектурной эстетики"),
переписывать `do_GET`/`do_POST` на таблицу без содержательной причины не
стал.

## Проверено

| Проверка | Результат |
|---|---|
| `ast.parse()` всех изменённых/новых файлов | [CONFIRMED] |
| `SupplierHandler.__mro__` | [CONFIRMED] `[SupplierHandler, AuthHandlerMixin, RequestRouteMixin, GlobalSupplierRouteMixin, SimpleHTTPRequestHandler, ...]` |
| `hasattr` на все 5 методов | [CONFIRMED] `True` |
| Офлайн импорт `supplier_app`, `api.index` | [CONFIRMED] |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=497; failures=0; errors=9 (baseline); skipped=1` |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — 4 файла продукта (`supplier_app.py`, 2
новых модуля, `CLAUDE.md`) + state-файлы.

## Не проверено

- NOT VERIFIED: живые request-маршруты (`/api/requests/*`,
  `/api/global-suppliers/*`) под реальным браузером — покрыты офлайн
  HTTP-тестами, не ручным browser QA (не требовалось — UI не менялся).

## Следующий шаг

Батч C (mail route helpers) требует отдельного решения владельца: либо
(а) оставить mail-маршруты инлайн в `do_GET`/`do_POST` навсегда (они уже
работают, не изменение поведения не требуется), либо (б) выполнить более
инвазивный рефакторинг — вынести каждый inline-блок в новый метод
(меняя тело `do_GET`/`do_POST`), что выходит за рамки "чистого переноса"
и ближе к архитектурному решению, чем к mechanical extraction. Не начат
без вашего подтверждения.

После решения по батчу C — переход к `mail/repository.py` mixin-разбиению
(auth/suppliers/messages/campaigns/queue/inbox).
