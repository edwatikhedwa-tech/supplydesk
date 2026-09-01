---
document_id: EMAIL-PACING-ITERATION2-20260829
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# SupplyDesk — Iteration 2: pacing и защита исходящей почты — HISTORICAL — NOT CURRENT

> Task evidence captured on 2026-08-29. It is not current delivery state.

## 1. Цель

Iteration 1 отвечает за целостность исходящей почты: idempotency, durable
Message-ID, atomic claim, irreversible gate и запрет опасного автоматического
resend. Iteration 2 добавляет поверх этого один общий persisted limiter на
каждый подключённый mail account. Он распределяет отправки во времени,
учитывает rolling-бюджеты и останавливает конкретный аккаунт при признаках
проблемы провайдера.

Простыми словами: письма из разных заявок, ручной resend и ответ на входящее
письмо больше не конкурируют за разные независимые «таймеры». Они используют
один безопасный бюджет конкретного ящика.

## 2. Что Iteration 2 не гарантирует

- попадание письма во «Входящие»;
- отсутствие spam classification;
- доставку адресату;
- неизменность будущих правил и лимитов провайдера;
- обход provider throttling или антиспам-политик.

`sent` по-прежнему означает положительный результат SMTP/provider acceptance,
а не подтверждённую доставку. Неопределённый результат остаётся
`delivery_unknown` по контракту Iteration 1.

## 3. Архитектура

```text
UI/API
  → MailService
  → mail_jobs
  → account reservation (atomic, persisted)
  → pacing / rolling budget
  → cooldown / circuit breaker
  → Iteration 1 suppression + kill switch + irreversible gate
  → provider SMTP
```

Второй scheduler не создавался: логика встроена в существующий `MailQueue` и
`MailRepository`. DB-транзакция закрывается до SMTP; reservation блокирует
соседние worker/process, но не удерживает транзакцию во время сети.

## 4. State machine

```text
ready + queued
  ├─ account blocked → queued / waiting (attempts unchanged)
  ├─ pacing or budget wait → queued / waiting (attempts unchanged)
  └─ atomic claim + reservation
       ├─ global switch / final guard → queued (neutral release)
       ├─ suppression → failed (no provider call, no send attempt)
       └─ irreversible gate → provider
            ├─ positive SMTP result → sent → best-effort Sent-copy
            ├─ explicit permanent refusal → failed
            ├─ transient refusal → queued at bounded backoff/cooldown time
            └─ timeout/disconnect after transfer → delivery_unknown, never auto-requeued
```

Для account защитные состояния являются persisted overlay:

- `closed` — отправка разрешена, если pacing и budgets разрешают;
- `cooldown` — конкретный account ждёт `cooldown_until`;
- `open` — circuit breaker остановил account до `breaker_until`.

Global kill switch сильнее account state и останавливает все outgoing paths.

## 5. Настройки

Настройки централизованы в `mail/pacing.py`, читаются через
`PacingSettings.from_env()` и передаются в service/queue одним объектом.

| Setting | Default | Что означает |
|---|---:|---|
| `MAIL_PACING_MIN_SECONDS` | 30 | Минимальная пауза после reservation |
| `MAIL_PACING_MAX_SECONDS` | 60 | Верхняя граница bounded jitter |
| `MAIL_MAX_PER_HOUR` | 100 | Внутренний rolling-бюджет account за 1 час |
| `MAIL_MAX_PER_DAY` | 100 | Внутренний rolling-бюджет account за 24 часа |
| `MAIL_PACING_RESERVATION_SECONDS` | 900 | Срок незавершённой reservation |
| `MAIL_COOLDOWN_BASE_SECONDS` | 300 | Первая пауза после transient/throttle |
| `MAIL_COOLDOWN_MAX_SECONDS` | 3600 | Максимальный cooldown |
| `MAIL_BREAKER_FAILURE_THRESHOLD` | 3 | Сколько проблем открывает breaker в окне |
| `MAIL_BREAKER_WINDOW_SECONDS` | 900 | Окно подсчёта проблем breaker |
| `MAIL_BREAKER_OPEN_SECONDS` | 3600 | Начальная остановка открытого breaker |
| `MAIL_RETRY_BASE_SECONDS` | 10 | Начало bounded exponential backoff job |
| `MAIL_RETRY_MAX_SECONDS` | 900 | Cap обычного backoff |

**Простыми словами:** при дефолтном окне 30–60 секунд теоретический темп
составляет до примерно 120 писем/час при минимальном интервале, примерно 80
писем/час при среднем интервале 45 секунд и примерно 60 писем/час при
максимальном интервале. Партия из 100 писем по одному pacing занимает
ориентировочно 50–100 минут, а не уходит одним всплеском. Фактическое время
может быть больше из-за cooldown, retry, budget wait и provider errors. Это
пример поведения приложения, а не гарантия deliverability.

Это наши `conservative application defaults`, а не обещанные лимиты Яндекса.
В официальной справке Yandex для SMTP указано 300 получателей/писем в сутки в
соответствующем сценарии, при этом лимит может быть снижен антиспам-системой;
Yandex также рекомендует специализированный сервис для массовых рассылок:
[официальные ограничения Yandex](https://www.yandex.ru/support/yandex-360/customers/mail/ru/web/letter/create/send-many-letters),
[официальная диагностика SMTP-лимита](https://www.yandex.ru/support/yandex-360/customers/mail/ru/web/letter/create/troubleshooting).
Официальный provider limit не используется как безопасный application budget.

## 6. Ошибки и реакции

| Событие | Что делает система | Можно повторять автоматически? |
|---|---|---|
| Pacing/budget wait | Оставляет job queued, вычисляет wake time | Да, после времени; attempts не растёт |
| Global switch | Не вызывает provider; освобождает claim нейтрально | Да после включения switch |
| Suppression/blacklist | Повторно проверяет непосредственно перед gate и блокирует job | Нет без осознанного изменения suppression |
| 421/450/451/452 или другой transient refusal | Пишет audit, bounded backoff и account cooldown | Да только до `max_retries`, без uncertainty |
| Повторные provider/auth/throttle failures | Увеличивает cooldown или открывает account breaker | Нет до recovery/operator action |
| 5xx permanent refusal | `permanent_rejected`, job failed | Нет |
| Auth/account failure | `open`, account помечается revoked/error существующим механизмом | Нет до reconnect/recovery |
| Timeout/disconnect после DATA | `delivery_unknown`, audit `uncertain` | Нет; только verify/manual resend I1 |
| SMTP success + DB failure | I1 сохраняет `delivery_unknown`/Sent-copy path | Нет |

После positive SMTP result pacing не создаёт второй send. Sent-copy остаётся
best-effort следом за durable result, как в Iteration 1.

## 7. Account scheduling и concurrency

`mail_account_outbound_state` хранит `next_send_not_before`, cooldown и
breaker. `mail_send_reservations` хранит владельца, token, срок reservation и
её terminal status. Worker резервирует slot в короткой атомарной транзакции,
после чего только победитель получает право продолжить claim.

SQLite использует `BEGIN IMMEDIATE`; PostgreSQL-ветка использует обычную
транзакцию и `SELECT ... FOR UPDATE` для строки account state. В обоих случаях
transaction не удерживается во время SMTP. Наличие active reservation также
блокирует второй claim, даже если jitter равен нулю.

Выбор job сохраняет старый порядок `next_attempt_at/created_at`; jobs другого
аккаунта могут продолжать работу, пока один account на cooldown. Это простая
fairness-модель без второго scheduler.

## 8. Hourly/daily budget

Источником факта реального transport attempt является `mail_send_attempts` с
`started_at`. Бюджеты rolling: 3600 секунд и 86400 секунд от текущего UTC.
Reservation до gate не расходует budget; actual attempt фиксируется на gate и
завершается одним audit-row.

При исчерпании budget job остаётся queued, `attempts` не увеличивается, SMTP не
вызывается. Worker получает bounded wake hint, а не claim/release loop.

## 9. Cooldown и circuit breaker

Throttling/transient refusal увеличивает bounded cooldown: base → 2× → cap.
Повторные проблемы в окне увеличивают failure counter; после threshold account
переходит в `open` до persisted `breaker_until`. Auth failure сразу открывает
account safety state. Успешная отправка сбрасывает failure counter и закрывает
breaker, но не отменяет уже рассчитованный `next_send_not_before`.

Global switch и account cooldown не смешиваются:

```text
GLOBAL SWITCH OFF → запрещены все исходящие пути
ACCOUNT COOLDOWN   → остановлен только конкретный mailbox
```

## 10. Attempt audit

`mail_send_attempts` содержит job/message/reply, account, attempt number,
reservation token, start/end UTC, ограниченную outcome taxonomy, provider
classification, `irreversible_reached`, cooldown flag, next retry и sanitized
error. В таблицу не попадают OAuth tokens, пароль, SMTP AUTH или тело письма.

Возможные outcomes: `in_progress`, `accepted`, `permanent_rejected`,
`transient_rejected`, `uncertain`, `blocked_global`. Ожидание не создаёт строку
каждую секунду; `paced` и `budget_wait` являются scheduling state, а не audit
spam.

## 11. Suppression и attachment safety

Используется существующая `blacklist_entries` и существующий bounce/hard-bounce
механизм. Новая blacklist/suppression таблица не создавалась. Перед provider
выполняется актуальная проверка по external key/email, поэтому blacklist,
добавленный после queue creation, всё равно блокирует send.

Существующие backend guardrails вложений сохраняются: максимум одного файла
10 MiB и суммарно 20 MiB, с отказом до assembly/SMTP. Storage deduplication не
переделывалась и остаётся отдельным technical debt.

## 12. Restart behavior

Migration/startup recovery не меняет исторические `sent` или
`delivery_unknown` jobs и не requeue-ит их. Persisted state сохраняет pacing,
cooldown, breaker, rolling audit history и retry timestamp. Terminal job
reservation закрывается при recovery; in-progress audit для
`delivery_unknown` получает `restart-recovery` classification. Restart не
сбрасывает таймер в ноль и не выпускает накопленный burst.

## 13. Kill switch interaction

Проверка Iteration 1 остаётся общей авторитетной точкой перед provider. Даже
после reservation и после gate финальная проверка перед DATA может запретить
SMTP. В этом случае provider DATA не вызывается; обычный retry не создаётся.

## 14. Sync reply, manual resend и idempotency

Manual resend создаёт новый message/job и проходит тот же account limiter;
исторический `delivery_unknown` не переписывается. Повтор bulk с тем же
idempotency key не создаёт новую reservation — reservation появляется только
при фактическом claim.

Синхронный ответ на непривязанное входящее письмо также создаёт reservation
того же account. Если slot недоступен, provider не вызывается и пользователю
возвращается deterministic wait error; этот sync path не превращается в
скрытую вторую очередь. После gate он сохраняет прежний Sent-copy контракт.

## 15. Operator guide

- Чтобы остановить всё: установить `mail_runtime_controls.outgoing_enabled=0`.
- Чтобы посмотреть состояние: вызвать `MailRepository.pacing_status(account_id)`
  или прочитать `mail_account_outbound_state` вместе с rolling counts.
- Чтобы понять ожидание: проверить `next_send_not_before`, `cooldown_until`,
  `breaker_until`, budget counts и job `next_attempt_at`.
- Чтобы снять cooldown: сначала подтвердить причину и отсутствие provider
  проблемы; затем операторским действием очистить account state. Это не
  должно переписывать audit и не даёт права requeue `delivery_unknown`.
- Чтобы изменить лимиты: задать централизованные `MAIL_*` defaults при запуске
  или использовать будущий operator/config механизм; dashboard для этого не
  добавлялся.
- После аварии сначала оставить global switch off, проверить DB integrity и
  состояния, затем включать отправку отдельно после review.

## 16. Known limitations

- PostgreSQL SQL-ветка сохранена, но в текущей среде PostgreSQL не запускался и
  остаётся `NOT VERIFIED`.
- Нет UI для редактирования pacing/budget settings.
- Runtime recovery для произвольно зависшего живого worker остаётся частью
  существующего I1 startup recovery; lease expiry не является разрешением на
  resend после irreversible stage.
- Application pacing не доказывает Inbox placement и не заменяет provider
  policy/compliance.

## 17. P0 corrective: started reservation lifecycle

Lease expiry сама по себе не закрывает reservation со статусом `started`:
после irreversible boundary это не доказывает, что провайдер не принял письмо.
Известный terminal outcome закрывает reservation в обоих состояниях
`reserved` и `started`:

```text
known transient/permanent outcome → reservation consumed
cooldown/backoff                → сохраняется
uncertain/in_progress           → не освобождается автоматически
```

Startup recovery дополнительно выполняет bounded reconciliation stale
`started` rows. Она закрывает только доказанные terminal cases с согласованными
job/message/reply status. Для `uncertain` это означает: сначала должен быть
durable owner-state `delivery_unknown`, затем reservation закрывается как
`consumed`; это не создаёт права на automatic resend. `in_progress`, отсутствие
attempt или противоречивые данные остаются на консервативном recovery path
Iteration 1 и не освобождаются по одному только lease timeout.

**Простыми словами:** система может убрать зависший слот только когда база уже
знает, чем закончилась попытка. Если результат неизвестен, слот не
«освобождается наугад». После того как база честно зафиксировала
`delivery_unknown`, слот закрывается, но именно это письмо всё равно нельзя
отправить автоматически повторно; остальные письма ящика могут продолжить
работу.
