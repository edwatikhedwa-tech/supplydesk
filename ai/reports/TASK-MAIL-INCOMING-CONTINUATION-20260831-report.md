# TASK-MAIL-INCOMING-CONTINUATION-20260831

## Цель

Проверить независимый приём почты на всех подключённых ящиках и выполнить
подтверждённое продолжение отправки заявки 1059 через Mail.ru с pacing и
аварийным выключением outgoing.

## ACCOUNTS

| Account | Provider | Email | Auth mode | Incoming | Outgoing at close |
|---:|---|---|---|---|---|
| 1 | Yandex | `edwatik@yandex.ru` | OAuth | ON | OFF |
| 23 | Mail.ru | `edwatik@mail.ru` | app password | ON | OFF |

Credential references were checked as `oauth-account:1` and
`mailru-account:23`. No token or password was logged.

## Что изменено

- `mail/service.py`: `sync_incoming` requests account credentials with
  `require_outgoing=False`; outgoing remains required for SMTP paths.
- `mail/service.py`: `_get_account_for_queue` accepts the explicit
  `require_outgoing` flag.
- `mail/repository.py`: only a ready, explicitly applied continuation plan may
  pass the campaign gate while the source campaign is paused for health.
  Ordinary campaign jobs still require an active campaign and eligible target.
- Regression tests were added for incoming-with-outgoing-off and continuation
  through a paused source campaign.

## Проверено

- Canonical runtime: production runtime, canonical SQLite database, current
  live-mail lock owned by the running process.
- Runtime HTTP smoke: `http://127.0.0.1:8000/messages` returned `200`.
- Yandex incoming sync for account 1: `200`, `ok=true`, `imported=0`.
- Mail.ru incoming sync for account 23: `200`, `ok=true`, `imported=0`.
- Both accounts reported `incoming_health=healthy`, `incoming_last_error=null`.
- Invalid account sync returned the expected safe `400` error.
- SQLite `pragma integrity_check`: `ok`.
- Targeted mail regressions: `5 OK`; Python compilation and `git diff --check`:
  `PASS`.
- Current campaign 2 remained `paused_for_health` with its existing provider
  policy pause reason. Existing Yandex queued jobs were not claimed.

## Mail.ru live continuation

The dry-run initially found `81` untouched eligible contacts. Four bounded
plans were prepared before the safety stop:

- Batch 1: jobs `155–159`, 5/5 accepted.
- Batch 2: jobs `160–164`, 5/5 accepted.
- Batch 3: jobs `165–169`, 5/5 accepted.
- Batch 4: jobs `170–174`: jobs `170–171` accepted; job `172` became
  `delivery_unknown`; job `173` was released after outgoing was disabled and
  has no SMTP attempt; job `174` remained queued.

Accepted total in this continuation: `17`, one attempt each, with SMTP
`post_data` response `250`. New jobs and RFC Message-IDs were created for each
prepared contact. The original Yandex messages/jobs were not rewritten.

### Safety stop

Job `172` targeted a Unicode-domain address. Its single attempt ended with
exception class `UnicodeEncodeError` during MIME serialization before an SMTP
DATA command could be evidenced. Because the durable irreversible gate had
already been entered, the system correctly recorded `delivery_unknown` and did
not retry it automatically. Outgoing was disabled immediately.

At close:

- `delivery_unknown`: `1` continuation job.
- Prepared but not sent: `2` jobs (`173–174`); job `173` was claimed briefly,
  then released without an attempt after the kill switch.
- Later contacts not prepared: `61`; they were not sent.
- Active pacing reservations: `0`.
- Campaign state change: `NO`.
- Other suppliers sent outside the selected continuation: `0`.
- Final durable/effective outgoing: `OFF`.

## Почему новое входящее не появилось в интерфейсе

После исправления оба IMAP-запроса завершились успешно, но вернули
`imported=0` и `skipped=1`: нового входящего сообщения в этих mailbox на
момент проверки не было. Поэтому интерфейс не мог показать новую карточку.
Это отличается от прежней ошибки Yandex, которая блокировала sync до IMAP и
затем скрывалась `maybe_sync_incoming`.

## Не завершено

Полная отправка всех 81 оставшихся контактов не завершена: после первого
доказанного `delivery_unknown` дальнейшая отправка остановлена по safety
policy. Нужна отдельная явная проверка/решение по Unicode-адресу и
`delivery_unknown`; этот отчёт не выполняет retry.

## Риски

- SMTP acceptance (`250`) подтверждает приём сообщения сервером Mail.ru, но не
  доставку в mailbox поставщика.
- Для job `172` результат внешнего транспорта неизвестен; повторная отправка
  без отдельной reconciliation может создать duplicate outreach.
- Рабочее дерево содержит чужие staged/unstaged и untracked изменения; они не
  включены в Task-ID commit.

## Следующий этап

Отдельно решить, как безопасно обработать Unicode-domain recipient и
`delivery_unknown` (reconciliation или ручное решение). До этого outgoing
остаётся OFF, автоматический retry не запускается.
