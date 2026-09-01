# SupplyDesk — Iteration 3 UI gap

Дата проверки: 2026-08-28.

## Verdict

`NO` — обычный пользователь не может выполнить весь Iteration 3 workflow из
текущего UI.

Iteration 3 backend/API остаётся отдельным результатом:

```text
ITERATION 3 BACKEND — ACCEPTED
ITERATION 3 PRODUCT UI — PENDING
```

Frontend Iteration 3 не перестраивался в этом corrective pass. Это сознательно
не смешано с исправлением backend safety semantics.

## Что уже есть в backend/API

- `POST /api/mail/deliverability/preflight` — read-only PASS/WARNING/BLOCK;
- `POST /api/mail/deliverability/preview` — dry-run samples через тот же renderer;
- `POST /api/mail/send-bulk` — idempotent operation/campaign assembly;
- `GET /api/mail/campaigns/<id>` — campaign summary;
- `POST /api/mail/campaigns/<id>/pause`;
- `POST /api/mail/campaigns/<id>/resume`;
- `POST /api/mail/campaigns/<id>/stop`;
- `POST /api/mail/suppression` — durable manual do-not-contact;
- `GET /api/blacklist` и `POST /api/blacklist/<id>/restore` — просмотр/восстановление
  существующих blacklist entries.

## Что найдено во frontend inventory

В `frontend/src/lib/api.ts` и текущих страницах нет product flow для
preflight/dry-run, campaign summary, stage approval, pause/resume/stop или
exclusion reasons. Есть обычный composer и экран blacklist, но они не дают
пользователю пройти staged campaign workflow end-to-end.

## Минимальный будущий flow

```text
Compose campaign
↓
Preflight
↓
Warnings / exclusions
↓
Exact preview
↓
Start stage 1
↓
Campaign progress
↓
Approve next stage / Pause / Stop
```

На экране должны быть видны:

- planned/eligible/excluded;
- причина каждого exclusion (`duplicate`, `invalid_email`, `suppressed`,
  `hard_bounce`, `unresolved_safety_state` и т. п.);
- personalization distribution и similarity warning;
- provider-policy warning;
- текущий stage и status;
- accepted, failed, delivery_unknown и remaining;
- действия `Approve next stage`, `Pause`, `Stop remaining`.

## Preview contract для UI

Backend возвращает `preview_contract`: preview не является persisted intent и
не замораживает данные сам по себе. `send-bulk` замораживает operation target
snapshot при сборке операции. Если данные поставщика/заявки изменились после
preview, UI должен попросить пользователя повторить preview перед запуском.
После сборки операции повтор того же idempotent intent использует сохранённый
snapshot, а не изменившиеся enrichment data.

## Простыми словами

Защитные проверки уже доступны серверу, но в интерфейсе пока нет единого
мастера кампании. Поэтому оператор может вызвать API, однако обычный
пользователь пока не видит весь процесс «проверить → посмотреть письмо →
запустить этап → одобрить/остановить» в одном понятном экране.
