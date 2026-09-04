---
document_id: REPORT-TASK-MESSAGES-PRODUCT-ACCEPTANCE-CORRECTION-20260904
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-04
based_on_commit: c70e6d63a04640d8803eebc6aa878b7307f74984
---

# TASK-MESSAGES-PRODUCT-ACCEPTANCE-CORRECTION-20260904 — отчёт

## STATUS

`STATUS: BLOCKED` — source correction is complete; live acceptance is not
complete because the canonical backend is stale and the browser lacks the
required viewport control.

## Что я делал и зачем

Провёл correction-mode аудит и узко исправил отклонённые пункты `/messages`:
видимость реальной переписки, ширину деталей, B2B-иерархию, unmatched preview
и пользовательские flag/priority controls. Цель — чтобы пользователь видел
только фактическую коммуникацию и мог безопасно работать с заявкой и
поставщиком, не изменяя транспортную историю.

Простыми словами: техническая попытка отправки теперь не маскируется под
письмо. Если письмо ещё не ушло, оно остаётся в базе для аудита, но не
попадает в обычную переписку.

## Границы

Изменены только mail repository, `/messages` frontend, связанные regression
tests и контрольные документы. Не изменялись глобальная боковая панель,
AI/OCR, цены, логистика, reply-логика, manual-link source of truth,
пользовательские данные и несвязанные изменения в рабочем дереве.

## GAP ANALYSIS и первопричины

- Предыдущий `thread_messages` выбирал все сохранённые строки. Поэтому
  durable outbound `cancelled` pre-send attempt показывался как письмо.
- Список переписок считал те же технические строки в `messages_count` и
  latest-message полях.
- Детали ограничивались искусственным `max-width`, из-за чего справа
  оставалось пустое место.
- Метаданные были исправлены в исходниках, но запущенный canonical backend
  продолжал обслуживать старую версию и возвращал `404` на metadata route.
- Ранее не было доказательства настоящего pointer DnD и обязательной
  viewport matrix.

## Правило видимости письма

Обычная conversation view показывает:

- все inbound messages;
- outbound `sent`;
- outbound `delivery_unknown`, то есть письмо могло покинуть систему;
- outbound failure/bounce только если есть `sent_at` или
  `mail_job_integrity.irreversible_at`, то есть транспорт мог уже передать
  письмо.

Не показываются queued, sending, cancelled pre-send, drafts и failed
pre-send. Raw rows остаются в базе и доступны операционным audit/outbox
потокам. Это реализовано одной SQL-предикатной функцией
`_communication_message_predicate` и применено к list/count/latest и detail
queries; CSS hiding не используется.

## Исправления

- `mail/repository.py`: единый transport-aware predicate для списка,
  счётчиков, последнего сообщения и detail.
- `frontend/src/components/mail/ThreadDetail.tsx`: full remaining width,
  compact request strip, bounced status and neutral message cards.
- `frontend/src/pages/Messages.tsx`: compact header/tabs and matching detail
  gutters.
- `UnmatchedPreview.tsx`: neutral cards, amber only for semantic icon/counter,
  explicit `Компания не определена` for unknown sender.
- `ThreadList.tsx` and `ThreadMetadataControls.tsx`: visible flag/priority
  affordances; `threadStatus.ts`: bounced/attention semantics.
- Tests updated for hidden pre-send cancellation and transmitted rendering.

## Live acceptance evidence

Read-only canonical DB inspection for thread `92` showed:

- message `105`: outbound, `cancelled`, `sent_at=NULL`, `job_status=cancelled`,
  `attempts=0`, pre-send error `provider_continuation_superseded`;
- message `204`: outbound, `sent`, non-null `sent_at`, one attempt and a
  non-null irreversible timestamp;
- message `274`: inbound, `received`.

The manual link flow for unmatched inbox `79` to request `1061` was completed
through the UI, then `Отвязать` was used. The final read-only DB check found no
remaining link. This verifies the manual path and rollback, not permanent
data mutation.

A real pointer drag was attempted with CUA accessibility coordinates
`[104,304] -> [270,535]`. No link confirmation, URL transition or DB link
followed; therefore DnD is `NOT VERIFIED`, not a pass.

The canonical backend process is PID `16228`, started before the current
source correction. Smoke checks returned Vite `200`, backend root `200`,
`/api/auth/me` `200`, protected `/api/correspondence` and `/api/mail/threads`
`401` without request headers, and `/api/correspondence/metadata` `404`.
The `404` is the live blocker for flag/priority set/reload acceptance.

## Browser evidence and viewport matrix

Actual authenticated canonical-session render inspected: `1287×912`.
The list, selected detail and unmatched detail were viewed; detail width,
compact header, neutral preview and long inbound message content were checked.
Accessibility labels and the priority menu were inspected through the browser
accessibility tree.

| Required viewport | Result | Reason |
|---|---|---|
| 1440×900 | `NOT VERIFIED` | CUA has no viewport capability |
| 1920×1080 | `NOT VERIFIED` | CUA has no viewport capability |
| 1024×768 | `NOT VERIFIED` | CUA has no viewport capability |
| 390×844 | `NOT VERIFIED` | CUA has no viewport capability |

The requested screenshot evidence set A–H was not saved as local files. Inline
browser screenshots were inspected at 1287×912, but are not reported as the
mandatory viewport matrix.

## frontend-product-engineer audit

- Engineering: source correction, typecheck, production build and focused
  tests pass.
- UX: request → supplier → conversation hierarchy and the compact header were
  corrected; no third panel or global sidebar was added.
- Visual: actual 1287×912 render inspected; no obvious overlap or clipped
  content remained after the correction. No approved `/messages` reference
  image exists in the repository, so reference comparison is limited to the
  supplied textual direction.
- Accessibility: semantic labels and keyboard-visible controls were checked
  in the accessibility tree; full keyboard and screen-reader audit was not
  run.
- Responsive: mandatory desktop/tablet/mobile widths are not verified.
- Content stress: long company names, unknown sender labels and a rich inbound
  body were inspected at 1287×912; broader content-stress widths are not
  verified.

`REFERENCE MATCH: PARTIAL` — the corrected 1287×912 render follows the
textual product direction, but no approved image and no mandatory-width
evidence were available.

## Проверено

- `python -m unittest discover -s tests -p 'test_messages_visibility.py'` —
  `5/5` passed.
- `python -m unittest discover -s tests -p 'test_mail_status_semantics.py'` —
  `18/18` passed.
- `python -m unittest discover -s tests -p 'test_thread_metadata.py'` —
  `2/2` passed.
- The corrected HTML/text rendering test — `1/1` passed.
- Full `python -m unittest discover -s tests -p 'test_mail*.py'` — exit code
  `0`.
- `npm run typecheck` and `npm run build` — passed; `npm run lint` — zero
  errors and five pre-existing warnings outside this task.
- `git diff --check` — passed.
- Workspace Guard — `PASS` before changes, build and validation.

## Не проверено

Не проверены live flag/priority set → reload → switch → remove → reload из-за
stale backend `404`; не доказан успешный real DnD; не получены обязательные
скриншоты 1440×900, 1920×1080, 1024×768 и 390×844; не выполнен полный
keyboard/screen-reader аудит; не запускались CI, performance и отсутствующие
`scripts/audit_toolchain.py`/browser-geometry runner.

## Риски и откат

Изменение predicate может уменьшить видимое число писем именно там, где ранее
ошибочно показывались pre-send технические записи; raw data и outbox не
удаляются. Откат исходников — возвратом нового commit. Схема метаданных не
менялась в этой correction-задаче; уже существующие пользовательские и
почтовые данные не трогались. Несвязанные изменения
`backend/domain/supplier_enrichment/orchestrator.py`,
`tests/test_enrichment_pipeline.py` и untracked `runtime/` сохранены вне
коммита.

## Итог

Кодовая correction-часть выполнена и проверена. Итоговая приёмка:
`BLOCKED` — нужен запуск свежего canonical backend, затем live metadata
sequence, доказанный pointer DnD и реальные screenshots обязательных ширин.
