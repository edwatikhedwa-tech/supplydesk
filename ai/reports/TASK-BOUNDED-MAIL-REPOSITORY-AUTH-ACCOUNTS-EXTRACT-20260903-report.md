# TASK-BOUNDED-MAIL-REPOSITORY-AUTH-ACCOUNTS-EXTRACT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`PASS_2_COMPLETE` (mail/repository.py split) — [CONFIRMED] ~25 методов
users/sessions/OAuth-state/mail-account CRUD (`seed_user`, `authenticate`,
`create_session`, `touch_session`, `get_session`, `delete_session`,
`create_oauth_state`, `consume_oauth_state`, `create_oauth_login_state`,
`consume_oauth_login_state`, `get_or_create_oauth_user`,
`get_mail_account*`, `is_workspace_owner`, `list_*_mail_accounts`,
`save_mail_account`, `save_app_password_mail_account`,
`get_mail_account_secret`, `update_mail_tokens`, `mark_mail_error`,
`disconnect_mail_account`, плюс `_seed_default_blacklist`/`_seed_request`/
`DEFAULT_MARKETPLACE_BLACKLIST`) вынесены в `mail/auth_accounts.py` как
`AuthAccountsMixin`. `class MailRepository(AuthAccountsMixin)`.
`mail/repository.py`: `8816` → `8297` строк.

## Fresh method-cluster map — как выбирался этот кластер

Свежий аудит (Explore-агент, не полагаясь на прошлую грубую карту)
построил полную карту cross-cluster coupling для всех ~220 методов и
явно указал: этот кластер — единственный с **нулевой** приватной
связью в обе стороны с любым другим кластером (единственная точка
касания — `_audit_connection`, универсальная инфраструктура,
вызываемая из 15+ мест в 8+ кластерах, не собственность этого
кластера). Это самый безопасный кандидат после уже сделанного
DB-compat shim.

## Циклический импорт — найден и решён ДО переноса

Методы кластера используют `iso_now`/`iso_after`/`utc_now` (определены в
`mail/repository.py`) и `DEFAULT_SESSION_LIFETIME_SECONDS` (тоже там). Но
`mail/repository.py` теперь импортирует `AuthAccountsMixin` ИЗ
`mail/auth_accounts.py` — если бы `auth_accounts.py` импортировал эти
имена обратно из `.repository`, получился бы циклический импорт с
реальным риском `ImportError` в зависимости от порядка объявлений.
Решение: обе сущности вынесены в третий, независимый модуль
`mail/time_utils.py`, от которого оба файла импортируют напрямую;
`mail/repository.py` дополнительно ре-экспортирует их для существующих
внешних потребителей (`mail/queue.py`, `backend/app_config.py`,
`tests/test_mail_pacing.py`, `tests/test_outgoing_safety.py`,
`tests/test_supplier_identity.py`) — ни один из них не пришлось трогать.

## Что НЕ перенесено (сознательно, по указанию свежего аудита)

Внутри исходного диапазона строк 2450–3047 было 4 "затерянных" метода,
принадлежащих доменам Request/Supplier, не Auth: `get_request`,
`request_positions`, `request_supplier`, `set_supplier_manual_inn`
(последний реально вызывает `_get_or_create_global_supplier`/
`_link_supplier_global` — приватные хелперы другого кластера). Оставлены
на месте в `mail/repository.py`; перенос был "lift these ~25 methods,
skip that interior block", не единый диапазон.

## Проверено

| Проверка | Результат |
|---|---|
| `ast.parse()` всех трёх файлов | [CONFIRMED] |
| `MailRepository.__mro__` | [CONFIRMED] `['MailRepository', 'AuthAccountsMixin', 'object']` |
| `hasattr` на все перенесённые методы + все 4 "затерянных" | [CONFIRMED] `True` |
| Офлайн импорт `mail.repository`, `mail.queue`, `supplier_app` | [CONFIRMED] |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=497; failures=0; errors=9 (baseline); skipped=1` |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — 4 файла продукта (`mail/repository.py`,
2 новых модуля, `CLAUDE.md`) + state-файлы.

## Не проверено

- NOT VERIFIED: реальный OAuth-обмен, реальная сессия в браузере — вне
  офлайн-контракта; код не изменился, только местоположение.

## Следующий шаг

Оставшиеся кластеры по свежей карте, от простого к сложному:
mail templates (2 метода, тривиально); dashboard/reporting (у "приватных"
статиков реальный fan-out в 3 других кластера — решать ПОСЛЕ более
простых кластеров); campaign creation+lifecycle (реально один домен,
искусственно разнесённый по файлу); самое рискованное — queue/campaign/
inbox-reply, где `_job_status_transition`/`_insert_send_attempt`/
`_upsert_send_attempt_evidence` используются и очередью, и inbox-reply
одновременно — рекомендация аудита: выделить их в отдельный
`_SendAttemptInfraMixin`, от которого наследуют оба потребителя, а не
класть прямо на `MailRepository` как недифференцированную общую
инфраструктуру.
