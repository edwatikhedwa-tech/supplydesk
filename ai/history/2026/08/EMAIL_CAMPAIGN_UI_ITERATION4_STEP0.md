---
document_id: EMAIL-CAMPAIGN-UI-ITERATION4-STEP0-20260829
status: HISTORICAL
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 792f441b4b6099533177e7c1d23d6252670f9309
---

# SupplyDesk — Iteration 4 UI Step 0 — HISTORICAL — NOT CURRENT

> Task evidence captured on 2026-08-29. It is not current product state.

Дата аудита: 2026-08-28

## Цель и границы

Это фактический аудит frontend перед добавлением Campaign UI. Backend
Iteration 3 и safety-контракты Iteration 1–3 не переписываются. Реальные SMTP
отправки в рамках аудита и реализации не выполняются; runtime switch должен
оставаться `outgoing_enabled=0`.

## Фактический стек и запуск

- React 18.3 + TypeScript 5.5 + Vite 5.4 + Tailwind 3.4.
- Маршрутизация — `react-router-dom` 6.30, общий shell — `Layout`.
- API-клиент централизован в `frontend/src/lib/api.ts`; он добавляет CSRF
  заголовок для non-GET запросов и использует cookie-сессию.
- Локальный backend слушает `127.0.0.1:8000`; Vite dev server —
  `127.0.0.1:5173` и проксирует `/api`/`/oauth` на backend.
- Основные проверки frontend: `npm run lint`, `npm run typecheck`,
  `npm run build`, `npm test` (Playwright).

**Простыми словами:** интерфейс — существующее React-приложение с одним
общим API-клиентом и навигацией. Новая рассылка должна стать ещё одним экраном
в этом приложении, а не отдельным инструментом.

## Аудит существующих поверхностей

| Поверхность | Факт | Решение для Iteration 4 |
| --- | --- | --- |
| Composer | `frontend/src/components/Composer.tsx` уже умеет выбирать несколько поставщиков, редактировать тему/тело, добавлять вложения и создавать idempotency key. Сейчас bulk-кнопка сразу вызывает `send-bulk` через `useRequestState.sendRequests`. | Переиспользовать его как вход в campaign flow и убрать прямой bulk bypass. Single/reply flow не расширять до wizard. |
| Request page | `frontend/src/components/RequestPage.tsx` открывает Composer из `PageHeader` и `StickyToolbar`; здесь пользователь уже выбрал поставщиков заявки. | Оставить entry point на заявке, но после подготовки открывать Campaign Composer / preflight. |
| Messages | `frontend/src/pages/Messages.tsx` показывает переписку и синхронный reply для непривязанного входящего письма. | Не смешивать reply с campaign wizard. Сохранить single-message safety и copy semantics. |
| Requests / supplier tables | `RequestsList`, `RequestPage`, `SupplierTable` — текущие места выбора заявки и поставщиков. | Использовать выбранных поставщиков как исходные targets; не дублировать таблицу поиска в кампании без необходимости. |
| Blacklist | `Blacklist.tsx` уже показывает и восстанавливает существующие blacklist entries. | Exclusion reasons показывать в campaign preflight; восстановление делать через существующий экран, не новым параллельным suppression store. |
| Layout / routing | `App.tsx` использует `BrowserRouter`; `Layout` даёт desktop rail и mobile drawer. | Добавить `/mail/campaigns/:id` и сохранить общий shell/visual language. |
| Auth / CSRF | `AuthProvider` вызывает `/api/auth/me`, сохраняет CSRF token; `api.ts` добавляет его в POST. | Все новые POST идут через `api`, raw fetch в компонентах не использовать. |
| Loading / errors | Страницы используют локальные `loading`, `error`, `role=alert/status`; кнопки обычно блокируются на время POST. | Повторить эти паттерны для preflight, preview, start, pause, resume, stop и polling. |
| Dialogs | В приложении есть локальные fixed overlays для Composer, SupplierPanel и confirmation через `window.confirm`. Нет общего Dialog primitive. | Для критичного stop/resume использовать доступный локальный dialog с Escape, focus return и явными кнопками; не добавлять dependency. |
| Responsive | Tailwind breakpoints: mobile shell до `lg`, существующие таблицы на узких ширинах переходят к stacked cards. | Campaign cards и exclusions table должны складываться без горизонтального overflow на 390px. |
| Notifications | Отдельной глобальной toast-системы не найдено; feedback локален на экране. | Показывать result/error рядом с действием и статусом campaign, без новой глобальной системы. |

**Простыми словами:** у пользователя уже есть место, где он выбирает
поставщиков и пишет письмо. Мы добавляем к этому безопасные шаги проверки и
контроля кампании, не заставляя его изучать новый раздел приложения.

## Фактический backend contract

Проверены handlers в `supplier_app.py`, `MailService` и tests
`tests/test_mail_deliverability.py` / `tests/test_mail_integrity.py`.

### Preflight и preview

- `POST /api/mail/deliverability/preflight` и
  `POST /api/mail/deliverability/preview` принимают `request_id`, `suppliers`,
  `subject`, `body`, `attachments`.
- Ответ содержит `status` (`PASS`/`WARNING`/`BLOCK`), `planned`, `eligible`,
  `excluded`, `unique_domains`, `recipient_results`, `warnings`, `blocks`,
  `personalization_distribution`, `similarity_ratio`,
  `attachment_total_bytes`, `provider`, `provider_warning`,
  `estimated_duration_seconds`, `rollout`, а также `previews`.
- `recipient_results` содержит email/domain/status/reasons и
  `personalization_level`; имя поставщика можно безопасно сопоставить с уже
  загруженным request supplier по email.
- `previews` — до пяти отрендеренных targets с `to_email`, `subject`,
  `body_text`, `body_html`, `message_id_header`, `personalization_level`.
- Backend явно сообщает, что preview не frozen intent: `frozen=false`,
  `snapshot_frozen_on=send-bulk operation assembly`,
  `rerun_if_source_data_changed=true`.

**Простыми словами:** проверка и просмотр письма ничего не отправляют. Но
просмотр нельзя считать вечным обещанием: перед стартом приложение обязано
проверить письмо ещё раз.

### Start и idempotency

- `POST /api/mail/send-bulk` требует непустой `idempotency_key` и принимает тот
  же payload, что preflight, включая attachments.
- Ответ `202` содержит `queued[]`; каждый элемент включает `job_id`,
  `message_id`, `thread_id`, `operation_id` и `campaign_id`.
- Backend сам повторяет preflight при первой сборке и замораживает target
  snapshot только внутри operation assembly.
- Повтор с тем же ключом и payload возвращает прежнюю операцию; новый ключ
  допустим только для нового user intent.

**Простыми словами:** двойной клик или повтор после сетевой ошибки не должны
создать вторую кампанию. Ключ операции живёт всё время одного намерения
пользователя.

### Campaign summary и actions

- `GET /api/mail/campaigns/<id>` возвращает `campaign_id`, `operation_id`,
  `request_id`, `mail_account_id`, `provider`, `status`, `stage`, `stage_limit`,
  `manual_stage_approval`, counters (`planned`, `eligible`, `excluded`,
  `queued`, `waiting`, `attempted`, `accepted`, `failed_permanent`,
  `failed_transient`, `delivery_unknown`, `suppressed`, `cancelled`,
  `remaining`), `provider_rejection_count`, `health`, `pause_reason`,
  `provider_warning`, `updated_at`.
- Actions: `POST /api/mail/campaigns/<id>/pause`, `/resume`, `/stop`.
- Summary изначально не отдавал отдельный список excluded targets и не содержал
  request name/account email/created time. В рамках минимальной интеграции UI
  добавлено поле `excluded_targets` в существующий summary (без новой сущности),
  а имена и request title по-прежнему берутся через уже существующие
  `GET /api/requests/<request_id>` и `GET /api/mail/status`.

**Простыми словами:** после перезагрузки сервер является источником статуса,
счётчиков и сохранённых причин исключений. UI не придумывает данные локально;
имя заявки и почтовый адрес аккаунта подтягиваются из уже существующих API.

## Минимальная интеграция

Выбран режим `$front` **EXTEND**:

- наследуем graphite navigation rail, cool canvas, cobalt primary action,
  quiet borders, compact data typography и существующие card/table patterns;
- добавляем contribution кампании: staged reading order «можно ли запускать →
  что исключено → что именно увидит поставщик → что происходит сейчас»;
- сохраняем single send/reply отдельно;
- не добавляем библиотек и не создаём второй scheduler/app.

Дизайн-направление: экран кампании должен ощущаться как control room для
снабженца — спокойный, проверяемый и легко сканируемый. Сначала крупно видны
статус и следующий разрешённый шаг, затем counters и health, затем предупреждения
и диагностика. Опасные Stop и health pause имеют явный текст, но не маскируются
под обычную зелёную кнопку. На mobile counters складываются в grid, action bar
становится вертикальным, а длинные email/reason переносятся.

Acceptance criteria первого rendered slice:

1. Bulk Composer имеет первичную CTA «Проверить рассылку» и не вызывает
   `send-bulk` до успешного final preflight.
2. BLOCK лишает пользователя возможности стартовать; WARNING допускает старт
   только через явное подтверждение.
3. Preview показывает backend-rendered subject/body и предупреждает о
   non-frozen preview.
4. Campaign detail использует backend summary и отображает `accepted` как
   «Принято сервером», не «Доставлено».
5. Pause/resume/stop имеют loading/error/success states; stopped campaign не
   показывает resume; delivery_unknown выделен отдельно.
6. Нет горизонтального overflow на 390px и нет новых console/failed-request
   ошибок в основных сценариях.

## Что остаётся неизвестным до реализации

- У backend нет отдельного endpoint для списка excluded targets после reload.
  Решение: использовать сохранённый preflight context внутри UI и честно
  показывать, что это результат последней проверки; не выдавать его за новый
  authoritative query после изменения источника.
- В текущем API `manual_stage_approval` задаётся backend/env и не передаётся
  campaign-level в `send-bulk`. Значит UI не будет молча обещать переключатель
  per-campaign; фактическое значение показывается из campaign summary.
- Backend `send-bulk` в момент первой сборки сам запускает final preflight,
  поэтому frontend выполняет дополнительный final preflight непосредственно
  перед POST и обрабатывает новый BLOCK/WARNING до запуска.
