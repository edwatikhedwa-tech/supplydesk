# SupplyDesk — Campaign UI Iteration 4

Дата: 2026-08-28
Режим: frontend `EXTEND` поверх принятого backend Iteration 3

## Цель

Дать пользователю безопасный интерфейс для подготовки и наблюдения за
campaign из Iteration 3: read-only preflight, exact preview, явное подтверждение
перед `send-bulk`, состояние staged rollout, health, pause и Stop remaining.

Iteration 1 остаётся контрактом целостности и защиты от дублей. Iteration 2
остаётся account-level pacing, budget и provider protection. Iteration 4 не
ускоряет отправку и не меняет эти гарантии.

**Простыми словами:** перед отправкой пользователь сначала видит, что будет
исключено, какое письмо реально сформируется и почему запуск может быть
рискованным. После запуска он видит не только счётчик писем, но и состояние
кампании.

## Границы и provider policy

- Интерфейс не обещает доставку, Inbox placement или отсутствие spam
  classification.
- `accepted` отображается как «Принято почтовым сервером», а не как
  «Доставлено».
- Для ordinary Yandex показывается предупреждение: внутренние проверки и
  интервалы SupplyDesk снижают нагрузку, но не отменяют policy провайдера.
- В Iteration 4 нет live SMTP и нет обхода антиспам-политик.
- Pacing, cooldown, circuit breaker, suppression, kill switch и
  `delivery_unknown` не переписываются.

## Архитектура

```text
RequestPage / selected suppliers
  → existing Composer
  → preflight (read-only)
  → exact backend preview
  → final preflight immediately before send
  → existing send-bulk + one idempotency key
  → /mail/campaigns/:id
  → existing MailQueue / Iteration 2 limiter / Iteration 1 guards
```

Новый scheduler не создаётся. Campaign UI использует существующий bulk
Composer и общий `api` client с session/CSRF. Single send и reply flow в
`Messages` остаются отдельным workflow.

**Простыми словами:** новый экран не обходит старую очередь и не создаёт
вторую систему отправки; он добавляет безопасные контрольные шаги перед уже
существующим запуском.

## Preflight и dry-run

Bulk Composer теперь начинает с CTA `Проверить рассылку`. До успешной проверки
`send-bulk` не вызывается. Backend preflight возвращает:

- planned/eligible/excluded и уникальные domains;
- причины исключения каждого recipient;
- PASS, WARNING или BLOCK;
- personalization distribution и similarity ratio;
- размер вложений;
- provider и provider warning;
- rollout ceilings и фактический `manual_stage_approval`;
- backend-rendered preview targets.

Preflight и preview не создают jobs и не вызывают SMTP. На UI:

- `BLOCK` показывает причину и не даёт перейти к запуску;
- `WARNING` требует отдельного checkbox acknowledgement;
- provider warning показан отдельно от технических блокировок;
- exclusion reasons читаемы для человека (`suppressed`, `duplicate`,
  `invalid_email` и т. п.).

## Exact preview

Preview берётся из `/api/mail/deliverability/preview` и показывает subject/body
для конкретного supplier. Это тот же backend rendering path, который затем
используется operation target snapshot. Preview намеренно не считается
замороженным: непосредственно перед `send-bulk` UI повторяет preflight.

Если финальная проверка получила новый BLOCK или стабильные данные кампании
изменились, отправка не вызывается и пользователь возвращается к review.
Случайный preview `Message-ID` не сравнивается как содержательная часть: он
порождается заново до фактической operation assembly.

**Простыми словами:** предпросмотр показывает настоящее письмо, но не даёт
старому результату «протухнуть» и тихо отправить уже изменившиеся данные.

## Personalization и similarity

UI показывает уровень фактической персонализации из backend, а не обещает
уникальность. Случайные приветствия, пробелы, символы, invisible text,
синонимы и иные изменения ради обхода фильтров не добавляются. Similarity
warning — только объясняющий сигнал; сам по себе он не блокирует отправку.

## Подтверждение запуска

Перед `send-bulk` отображаются:

- число recipients и eligible;
- cumulative rollout `10 → 25 → 50 → все`;
- pacing `30–60 секунд` и day limit `100` как внутренние настройки SupplyDesk;
- явное предупреждение, что accepted не равно delivered;
- provider warning.

`idempotency_key` создаётся один раз на user send intent. При retry/timeout
того же HTTP намерения ключ сохраняется; новый ключ появляется только после
изменения draft fingerprint.

## Campaign detail

Маршрут: `/mail/campaigns/:id`.

Экран показывает status, stage, progress и counters: planned, eligible,
excluded, queued, waiting, attempted, accepted, failed permanent/transient,
`delivery_unknown`, suppressed, cancelled, remaining. Status mapping и
цветовые tone централизованы в `frontend/src/lib/campaign.ts`.

Доступные действия используют API Iteration 3:

- `Пауза` — остановить дальнейшее выполнение кампании;
- `Продолжить следующий этап` — resume после stage review или health pause;
- `Остановить оставшиеся` — требует confirmation и меняет только unsent
  targets; sent, `delivery_unknown` и audit history сохраняются.

Для stopped campaign Resume не показывается. `delivery_unknown` выделяется
отдельно от permanent/transient failures.

Polling выполняется только на campaign detail: чаще для active и реже для
paused, прекращается для terminal statuses. Loading, retry и error states
видимы рядом с соответствующим действием.

## manual_stage_approval — per-campaign contract

`POST /api/mail/send-bulk` теперь принимает необязательное поле
`manual_stage_approval`, строгое JSON-boolean `true` или `false`. Если поле
отсутствует, используется текущий backend default
`MAIL_CAMPAIGN_MANUAL_STAGE_APPROVAL`. Эффективное значение определяется один
раз при сборке новой операции, попадает в fingerprint и сохраняется в
`mail_campaigns.manual_stage_approval`.

После создания campaign это значение неизменно: изменение env/default или
перезапуск процесса не меняет уже созданную кампанию. Повтор с тем же ключом и
тем же режимом возвращает ту же operation/campaign; смена `true` на `false`
или обратно с тем же ключом считается конфликтом намерения. Существующие
fingerprint v2 поддерживаются безопасно: они не переписываются и используют
сохранённый campaign snapshot, если он есть.

Composer получает default из preflight и показывает реальный checkbox
`Подтверждать каждый этап вручную` до запуска. Campaign detail только
отображает сохранённое состояние и не предоставляет переключатель после
создания:

- `Этапы подтверждаются вручную.`
- `Этапы продолжаются автоматически при нормальном состоянии кампании.`

**Простыми словами:** пользователь выбирает для каждой новой кампании, нужно
ли вручную подтверждать следующий этап. Выбор записывается вместе с кампанией
и не «переезжает» из-за изменения настроек сервера.

## API types

Добавлены типизированные методы в `frontend/src/lib/api.ts`:

- `preflightBulk`;
- `previewBulk`;
- `getCampaign`;
- `pauseCampaign`;
- `resumeCampaign`;
- `stopCampaign`;
- typed `sendMailBulk` result.

В `CampaignSummary` добавлено поле `excluded_targets` через минимальное
расширение существующего repository summary. Новая таблица для UI не создана.

## Responsive и accessibility

Используется существующий shell и дизайн-язык SupplyDesk: graphite rail, cool
canvas, cobalt action, quiet borders, white cards. Campaign cards складываются
на tablet/mobile, длинные email/reason переносятся, horizontal overflow
проверяется тестом. Composer и confirmation dialog имеют `role=dialog`,
`aria-modal`, label, Escape, focus return и базовый Tab focus trap. Цвет
статуса сопровождается текстом.

## Что не входит в Iteration 4

- отдельный большой dashboard кампаний;
- новый provider, scheduler или transport;
- tracking pixels/open/click tracking;
- SMTP probing;
- fake personalization;
- изменение уже созданной campaign после её создания;
- live SMTP acceptance.

## Операторский сценарий

1. На заявке выбрать поставщиков и нажать `Подготовить запрос`.
2. Нажать `Проверить рассылку`.
3. Разобрать BLOCK/WARNING, exclusions, provider warning и exact preview.
4. Явно подтвердить WARNING, если он есть.
5. Просмотреть финальное резюме и запустить кампанию.
6. На campaign detail наблюдать accepted/failed/unknown и stage.
7. При необходимости поставить Pause или безопасно остановить оставшиеся.

После изменения источника данных повторная проверка обязательна. Для
`delivery_unknown` UI не предлагает автоматический resend.

## Известные ограничения

- Campaign list отдельно не добавлялся; доступ к detail появляется после
  успешного `send-bulk`.
- После reload exclusions доступны из persisted `excluded_targets`; если
  старый backend не отдаёт это поле, frontend не должен придумывать список.
- default режима берётся из env только при отсутствии выбора в новом запросе;
- после создания campaign режим не редактируется отдельным PATCH/UI toggle.
- PostgreSQL не проверялся в текущей инфраструктуре.
- Live SMTP не выполнялся; deliverability и Inbox placement не проверялись.

## Исправление лимита кампании и отображения времени — 2026-08-29

Единый provider-neutral setting `MAIL_CAMPAIGN_MAX_RECIPIENTS` имеет default
`300` и безопасно ограничивается диапазоном `1..500`. Это одно effective
значение используется backend `preflight`, `preview` и `queue_bulk`, а также
возвращается UI в `campaign_limits.max_recipients`; frontend не дублирует число
в нескольких местах. Поэтому `1..300` проходят size check, а `301+` получают
`campaign_size_out_of_range` без тихого обрезания списка.

Этот лимит кампании не равен account budget: текущие `MAIL_MAX_PER_HOUR=100` и
`MAIL_MAX_PER_DAY=100` не изменены. Кампания из 120 получателей может пройти
preflight, но оставшиеся письма будут ждать освобождения rolling 24-hour
budget после исчерпания 100.

Backend duration contract — объект с `minimum`, `average`, `maximum`, а не
одно число. При pacing 30–60 секунд для 120 получателей это 3570 / 5355 /
7140 секунд (ориентир около 1 ч 29 мин; диапазон примерно 1 ч – 1 ч 59 мин).
UI показывает average и диапазон; `NaN`, `undefined` и `[object Object]` не
используются.

Официальная справка Yandex указывает техническое ограничение 300 писем в
сутки для отправки через SMTP, но это не является разрешением на массовую
однотипную коммерческую рассылку: защитные ограничения могут сработать раньше.
SupplyDesk сохраняет соответствующее предупреждение и не обещает доставку или
Inbox placement. См. [справку Yandex о массовой отправке](https://www.yandex.ru/support/yandex-360/customers/mail/ru/web/letter/create/send-many-letters).

**Простыми словами:** одна кампания теперь может содержать до 300 выбранных
получателей, но ящик всё равно отправляет по своим внутренним лимитам 100 в
сутки. Если выбрано больше допустимого, список не урезается сам — пользователь
видит точное превышение и должен исключить адреса вручную. Время отображается
нормально и остаётся только оценкой pacing, а не обещанием доставки.
