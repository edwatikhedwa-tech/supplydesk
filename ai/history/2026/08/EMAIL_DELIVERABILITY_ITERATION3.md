---
document_id: EMAIL-DELIVERABILITY-ITERATION3-20260829
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# SupplyDesk — Iteration 3: deliverability, content safety, preflight и staged rollout — HISTORICAL — NOT CURRENT

> Task evidence captured on 2026-08-29. It is not current delivery state.

Статус: реализовано для локального контура SQLite + provider-neutral campaign layer; live SMTP в этой итерации не выполнялся.

## Цель

Iteration 3 добавляет проверку содержимого и кампании до постановки в очередь,
точный preview того же snapshot, который будет отправлен, объяснимую оценку
похожести, staged rollout и durable health/pause/stop state поверх гарантий
Iteration 1 и account-level limiter Iteration 2.

Простыми словами: пользователь сначала видит риски и несколько реальных
примеров писем, затем система выпускает кампанию небольшими внутренними
этапами и останавливает оставшиеся письма при явном ухудшении качества.

## Provider policy

SupplyDesk не трактует технический ceiling Yandex как разрешение на массовую
рассылку. Официальная документация Yandex указывает, что лимиты могут быть
снижены раньше при подозрительной массовой, шаблонной или коммерческой
активности; обычная Яндекс.Почта предназначена для живой переписки, а для
настоящих массовых рассылок Yandex направляет к Yandex 360 для бизнеса и
специализированным mailing-возможностям:

- [Yandex: ограничения при отправке большого числа писем](https://yandex.ru/support/yandex-360/business/mail/ru/web/letter/create/send-many-letters)
- [Yandex: борьба со спамом и ограничения](https://www.yandex.com/support/yandex-360/business/mail/en/web/spam)
- [Yandex Send для специализированных рассылок](https://yandex.com/support/yandex-360/business/send/en/)

Актуальные официальные страницы показывают контекстные значения, которые нельзя
свести к единому «безопасному лимиту» приложения: русская справка указывает
лимит 300 для отправки через SMTP, а англоязычная страница антиспам-защиты —
35 получателей в одном SMTP-письме и 3000 внешних получателей за 24 часа.
SupplyDesk не выбирает между этими контекстами и не объявляет ни одно число
разрешением на массовую рассылку; лимит может быть снижен антиспам-системой.

Внутренние staged thresholds и pacing — настройки SupplyDesk. Они не являются
официальными лимитами Yandex, не обходят антиспам-политику, не гарантируют
SMTP acceptance, доставку или Inbox placement.

## Что SupplyDesk может и не может контролировать

Контролируется: синтаксис адреса, дубликаты, действующая suppression,
известные hard bounce/uncertainty, placeholder-ы, базовая структура subject/body,
размер вложений, snapshot, число этапа, account-level pacing/budget, health и
пауза оставшихся jobs.

Не контролируется: решение Yandex о политике, reputation, spam classification,
Inbox placement, фактическое чтение письма и будущие изменения provider rules.

## Архитектура

```text
supplier/request data
  → deterministic personalization
  → read-only preflight / exact preview
  → operation + immutable target snapshot
  → campaign rollout state
  → mail job
  → Iteration 2 account limiter
  → Iteration 1 suppression + kill switch + irreversible gate
  → provider adapter / SMTP
```

Campaign-слой не создаёт второго scheduler. Он только делает target eligible;
реальный slot по-прежнему резервируется непосредственно перед отправкой в
существующей очереди и общем limiter account.

Перед provider выполняется также campaign final gate. Поэтому job, захваченная
до pause/stop, освобождается без provider call и без расхода `attempts`.

## Preflight и dry-run

`MailService.preflight_bulk()` ничего не записывает, не создаёт operation/job и
не вызывает provider. Endpoint:

- `POST /api/mail/deliverability/preflight`
- `POST /api/mail/deliverability/preview`

Проверяются размер кампании, уникальные домены, rendered subject/body,
personalization coverage, invalid/missing/duplicate email, existing
suppression, hard bounce, unresolved `delivery_unknown`, attachment limits,
provider warning и ориентировочное время по pacing. Результат содержит `PASS`,
`WARNING` или `BLOCK`, список warnings/blocks и причины по каждому recipient.

Similarity warning сам по себе не блокирует кампанию. Дубликат, invalid email,
suppression, hard bounce, unresolved safety state, broken placeholder и
attachment over-limit блокируют новый bulk queue до исправления. Manual resend
после явного подтверждения Iteration 1 сохраняет отдельную семантику и не
превращается в автоматический retry.

Простыми словами: «исключено 7» не является единственным ответом — для адреса
возвращается причина вроде `duplicate`, `invalid_email`, `suppressed`,
`hard_bounce` или `unresolved_safety_state`.

## Personalization и preview

Рендеринг детерминированный. Разрешены только фактически переданные поля:
`supplier_name`, `contact_name`, `supplier_category`, `supplier_website`,
`supplier_city`, `request_name`, `request_description`, `sender_name` и
`company_name`. Случайные приветствия, пробелы, знаки, invisible text,
синонимы и искусственные фразы не добавляются.

Качество:

- level 0 — нет имени компании поставщика;
- level 1 — известна компания;
- level 2 — компания плюс известный request/category context;
- level 3 — зарезервирован для проверенного supplier-specific evidence; текущий
  renderer его сам не выдумывает.

`preview_bulk()` и queue используют один `_render_outbound_target()` path.
При создании operation target snapshot замораживается и дальше не перечитывает
изменившиеся enrichment данные. Сам read-only preview не является отдельным
durable intent/token: если supplier/request данные изменились между preview и
send-bulk, preview нужно повторить перед запуском. API явно возвращает этот
контракт; после queue отправляется именно сохранённый operation snapshot.

## Similarity и quality checks

Similarity — простой explainable fingerprint через нормализацию текста и
`SequenceMatcher`; warning по умолчанию начинается с доли 0.80 для партии от
10 писем. Он только показывает риск одинакового контента и не искажает письма.

Subject: empty — block; overly long, all-caps, excessive `!!!` — warning;
misleading `Re:`/`Fwd:` без thread — block. Subject одинаковый для большой
партии — warning только если rendered subjects действительно совпали.

Body: empty, unknown placeholder, unresolved rendered placeholder и явно
неподтверждаемое утверждение о supplier-specific research — block; много ссылок,
большой body и отсутствие ясного request context — warning.

Tracking pixel, open tracking и click tracking не добавляются.

## Validation и suppression

Email validation ограничена нормализацией, синтаксисом и duplicate detection.
SMTP probing, `VRFY`, `RCPT` enumeration и новый DNS-инфраструктурный слой не
добавлялись.

Используется существующая `blacklist_entries`/bounce модель. Ручной do-not-contact
доступен через существующий `POST /api/blacklist` и явный alias
`POST /api/mail/suppression`; reason сохраняется (`do_not_contact`, `hard_bounce`,
`manual_block`, `provider_rejection` или операторская причина). Подтверждённый
hard bounce теперь создаёт в этой же таблице email-level запись с ключом
`email:<normalized-address>`; адрес нормализуется только через trim +
lowercase (Gmail dot/plus semantics не применяются), и это блокирует новый
request даже с другим `external_key`. Soft bounce оставляет текущий state и не
создаёт permanent suppression. Перед реальным provider send сохраняется
Iteration 1 final suppression check, поэтому изменение suppression между
preflight/stages не будет проигнорировано.

## Rollout state machine

```text
active, stage 1
  ├─ stage terminal + health OK → stage 2/3/full
  ├─ manual_stage_approval      → paused_for_review
  └─ health threshold/provider  → paused_for_health

paused_for_review ── resume → active, next stage
paused_for_health  ── resume → active, same stage after operator review
active             ── stop  → stopped
all targets terminal           → completed
```

Внутренние cumulative ceilings: stage 1 = первые 10 total, stage 2 = до 25
total, stage 3 = до 50 total, stage 4 = remaining. Для 100 получателей это
10 + 15 + 25 + 50, а для 18 — 10 + 8, после чего remaining = 0. Переключение
не перепрыгивает номер stage только потому, что небольшая партия помещается в
следующий ceiling. Они configurable через
`MAIL_ROLLOUT_STAGE_1/2/3` и `MAIL_CAMPAIGN_MANUAL_STAGE_APPROVAL`; default
`manual_stage_approval=false`, а conservative mode включается значением `1`.
Это не официальная рекомендация Yandex. Stage не резервирует account budget
заранее.

API:

- `GET /api/mail/campaigns/<campaign_id>` — summary;
- `POST /api/mail/campaigns/<campaign_id>/pause`;
- `POST /api/mail/campaigns/<campaign_id>/resume`;
- `POST /api/mail/campaigns/<campaign_id>/stop`.

`Stop` меняет только ещё не начавшие отправку queued jobs. Если worker уже
успел получить claim, остановка повторно проверяется в атомарном campaign gate;
при отказе claim освобождается без расхода `attempts`, а остановленная
неотправленная job финализируется как `cancelled`. `sent`, `delivery_unknown`,
attempt audit и historical evidence не переписываются.
`Resume` не создаёт новую копию и не делает eligible уже отправленные или
неопределённые сообщения.

## Controlled operator stage hold

Для controlled acceptance можно временно ограничить автоматическое продвижение
только одной campaign process-level настройкой:

```text
MAIL_CAMPAIGN_STAGE_CAP_ID=2
MAIL_CAMPAIGN_STAGE_CAP=2
```

Это runtime safety hold, а не новая настройка campaign intent. Он действует
только для указанного `campaign_id`. Когда переход `2 → 3` превышает cap,
campaign сохраняет stage `2` и limit `25`, а получает безопасное состояние
`paused_for_review` с причиной `operator_stage_cap`. Обычный `Resume` при
активном cap не открывает Stage 3. После явного удаления обеих переменных
обычная семантика campaign снова действует; для campaign с
`manual_stage_approval=false` автоматический переход разрешён.

Эти переменные не входят в idempotency fingerprint, не меняют
`manual_stage_approval`, operation/target snapshots, Message-ID, jobs или
audit. Неполная или некорректная пара переменных безопасно означает отсутствие
cap (`NONE`). Cap не хранится в campaign intent и после restart должен быть
задан заново для controlled process. Без cap production semantics остаются
прежними; cap не является глобальным лимитом для других campaigns.

**Простыми словами:** оператор может поставить конкретную рассылку на
«стоп перед следующим этапом», не переписывая исходное решение пользователя.
Письма текущего этапа идут через обычные pacing, budget, suppression и
Iteration 1 integrity gates; следующий этап сам не откроется.

## Health metrics и pause

Summary возвращает `planned`, `eligible`, `excluded`, `queued`, `waiting`,
`attempted`, `accepted`, `failed_permanent`, `failed_transient`,
`delivery_unknown`, `suppressed`, `cancelled`, `remaining`, stage/status и
health rates. `accepted` означает принятие provider, не `delivered`.

Campaign автоматически ставится на `paused_for_health` при explicit
spam/policy rejection, authentication failure, открытом health breaker,
hard bounce, превышении configurable permanent/unknown/transient thresholds.
Текущие application defaults: hard bounce — любой подтверждённый случай;
provider rejection — 1 target; permanent failure rate > 20% при denominator
`effective_attempted` (известные terminal results/audit, lifetime кампании);
unknown rate > 10% при том же denominator. Для transient теперь используются
два сигнала: текущая последовательная серия из 3 свежих
`transient_rejected`-outcomes (accepted/permanent/uncertain обрывает серию) и
ограниченное окно последних 10 завершённых transport attempts. В окне pause
срабатывает при минимум 10 попытках, из которых минимум 5 transient и доля не
ниже 50%. Поэтому старый transient, после которого тот же job стал accepted,
остаётся в audit/lifetime analytics, но не поддерживает health pause навечно.
Единичный transient по-прежнему обрабатывается существующим cooldown/backoff.
Account breaker использует настройки
Iteration 2: 3 failures за 15 минут открывают breaker на 1 час; все значения
изменяемы через централизованный `PacingSettings`/`RolloutSettings`. Новые
внутренние параметры: `MAIL_CAMPAIGN_MAX_TRANSIENT_FAILURES=3`,
`MAIL_CAMPAIGN_TRANSIENT_WINDOW=10`,
`MAIL_CAMPAIGN_TRANSIENT_MIN_SAMPLE=10`,
`MAIL_CAMPAIGN_TRANSIENT_PAUSE_COUNT=5` и
`MAIL_CAMPAIGN_TRANSIENT_PAUSE_RATIO=0.50`.
Оставшиеся jobs сохраняются.

**Простыми словами:** три старые временные ошибки, каждая из которых позже
успешно восстановилась, не превращают кампанию в пожизненно остановленную.
Но три временные ошибки подряд сейчас или пять из последних десяти всё ещё
останавливают кампанию для проверки. Неопределённая отправка по-прежнему
остаётся `delivery_unknown` и не превращается в retry.

Yandex adapter распознаёт только явные policy/spam evidence в SMTP response;
произвольный 5xx не называется spam автоматически. Неопределённость после
DATA остаётся `delivery_unknown` по Iteration 1 и не requeue-ится campaign
механизмом.

## Interaction with Iteration 1 and 2

Iteration 1 = integrity / duplicate safety: durable Message-ID, immutable
operation snapshot, atomic claim, irreversible gate, `delivery_unknown`,
Sent-copy/recovery, kill switch и idempotency.

Iteration 2 = pacing / budgets / provider protection: единый account limiter,
persisted next-send time, jitter, rolling budgets, cooldown, breaker,
attempt audit и restart safety.

Iteration 3 только добавляет content/campaign decision layer перед этими
границами. При конфликте с ними приоритет остаётся у I1/I2.

## Operator guide

1. Оставьте `mail_runtime_controls.outgoing_enabled=0` перед review.
2. Вызовите preflight/preview и исправьте все `BLOCK` причины.
3. Проверьте samples, provider warning, personalization distribution и summary.
4. Для осторожного запуска задайте `MAIL_CAMPAIGN_MANUAL_STAGE_APPROVAL=1`.
5. При проблеме используйте campaign `pause` или `stop`; глобальную аварию
   закрывайте I1 kill switch.
6. Перед resume снова проверьте suppression и account status. Limiter, cooldown
   и budgets продолжают действовать.
7. Для controlled Stage 2 acceptance задайте cap только в запускаемом process,
   например `MAIL_CAMPAIGN_STAGE_CAP_ID=2` и
   `MAIL_CAMPAIGN_STAGE_CAP=2`, затем read-only подтвердите effective cap.
   После restart повторите настройку и проверку; не изменяйте campaign row.

## Known limitations

- PostgreSQL SQL branch не запускалась в текущей среде и остаётся
  `NOT VERIFIED`.
- Frontend campaign screen не добавлялся; backend/API и operator documentation
  готовы, UI defer за пределами узкой Iteration 3.
- Нет автоматического LLM intent analysis, open/click tracking, tracking pixel
  или DNS recipient probing.
- Supplier provenance/source snapshot не расширялся отдельной таблицей.
- Preview не имеет persistent token: он точен относительно данных на момент
  вызова, а operation snapshot создаётся при send-bulk. UI должен повторять
  preview после изменения supplier/request data.
- Ordinary Yandex mailbox может быть неподходящим транспортом для однотипной
  коммерческой массовой рассылки независимо от pacing/rollout.
- Thresholds оценивают технические результаты известных attempts, а не inbox
  placement.
