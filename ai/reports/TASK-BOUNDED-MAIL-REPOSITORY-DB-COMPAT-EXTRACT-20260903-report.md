# TASK-BOUNDED-MAIL-REPOSITORY-DB-COMPAT-EXTRACT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`PASS_1_COMPLETE` (mail/repository.py split) — [CONFIRMED] SQLite/Postgres
DB-API compatibility shim (`ManagedConnection`, `CompatRow`,
`_postgres_row_factory`, `_adapt_postgres_sql`, `PostgresCursor`,
`PostgresConnection`, `_postgres_migration_sql`) вынесен из
`mail/repository.py` в `mail/db_compat.py`. `mail/repository.py` уменьшился
с `8928` до `8816` строк. Это первый шаг owner-направленной программы
разбиения `mail/repository.py` (8928 строк, ~220 методов в одном классе)
по обязанностям, по итогам read-only structural-аудита.

## Почему этот шаг первым

Аудит явно назвал именно эти 4 класса + 3 функции самым безопасным
кандидатом: "no business logic, single direction of dependency
(MailRepository imports it), purely mechanical move" — в отличие от
кластера queue/campaign/inbox, где приватные хелперы
(`_job_status_transition`, `_insert_send_attempt`) расшарены между
несколькими "функциональными" разделами и перенос рискованнее.

## Что сделано

1. Создан `mail/db_compat.py` — все 7 символов перенесены byte-for-byte.
2. `mail/repository.py`: определения удалены, добавлен относительный
   импорт `from .db_compat import (...)`.
3. `sqlite3`, `re` — использование вне удалённого блока подтверждено
   (42 и 15 обращений соответственно) — импорты в `repository.py`
   остаются.
4. `utc_now`/`iso_now`/`iso_after` — сознательно НЕ включены в перенос,
   хотя физически были в том же диапазоне у аудита ("165-296"): это
   generic time-хелперы, не часть DB-compat, и используются напрямую
   (`from mail.repository import utc_now`) в `mail/queue.py` и трёх
   тестовых файлах — перенос их создал бы более широкий и рискованный
   diff без явной необходимости.
5. `CLAUDE.md` обновлён.

## Проверено

| Проверка | Результат |
|---|---|
| `ast.parse()` обоих файлов | [CONFIRMED] синтаксис корректен |
| `import mail.repository`; `repo.PostgresConnection is mail.db_compat.PostgresConnection` | [CONFIRMED] |
| `import supplier_app` (транзитивный потребитель) | [CONFIRMED] OK |
| `grep` по `tests/` на прямые ссылки на перенесённые имена | [CONFIRMED] `0` совпадений — нет теста, завязанного на точное расположение |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=497; failures=0; errors=9 (baseline); skipped=1` |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — 3 файла продукта (`mail/repository.py`,
новый модуль, `CLAUDE.md`) + state-файлы. Точечный механический перенос.

## Не проверено

- NOT VERIFIED: реальное подключение к Postgres (`DATABASE_URL`) — этот
  путь не упражняется офлайн-тестами ни до, ни после переноса; сам код
  не изменился, только местоположение.

## Следующий шаг

По аудиту: mixin-разбиение `MailRepository` по обязанностям
(auth/suppliers/messages/campaigns/queue/inbox), с приватными
send-attempt/job-transition хелперами в одном общем mixin, используемом
и очередью, и inbox-реплаями — этот шаг помечен аудитом как "medium
risk" и требует более осторожной последовательной работы, чем этот чисто
механический первый шаг.
