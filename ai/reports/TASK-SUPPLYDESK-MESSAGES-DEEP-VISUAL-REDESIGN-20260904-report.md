---
document_id: REPORT-TASK-SUPPLYDESK-MESSAGES-DEEP-VISUAL-REDESIGN-20260904
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-04
task_id: TASK-SUPPLYDESK-MESSAGES-DEEP-VISUAL-REDESIGN-20260904
source_commit: d7b0e39
---

# SupplyDesk `/messages` — deep visual redesign

## Статус

`PASS` — изменённый экран визуально проверен в браузере и в полном
responsive/a11y прогоне.

`PARTIAL` — before PNG не сохранён отдельным локальным файлом: исходный экран
зафиксирован в том же авторизованном CUA-сеансе inline при `1280×720`. Также не
было предоставлено утверждённого reference screenshot для pixel/reference
сравнения.

`DOC_IMPACT=YES` — обновлены каноническое состояние, журнал, handoff,
decision register и этот отчёт; product/API contract не менялся.

## Сделано

Изменён только visual layer `/messages`:

- `frontend/src/pages/Messages.tsx` — поиск стал локальным для рабочего списка;
- `frontend/src/components/mail/ThreadList.tsx` — request-first navigator,
  плоские activity rows, спокойные статусы, компактная иерархия;
- `frontend/src/components/mail/UnmatchedPreview.tsx` — нейтральный компактный
  preview без вложенных карточек;
- `frontend/src/components/mail/OutboxList.tsx` — тот же спокойный язык для
  очереди отправки;
- `frontend/src/components/mail/ThreadDetail.tsx` — conversation workspace:
  supplier/context header, timeline сообщений и sticky next-step footer.

Новые UI primitives не создавались. Техническая унификация компонентов,
архитектура приложения, backend, база данных, API, бизнес-логика и mail
semantics не изменялись.

## Простыми словами

Раньше экран выглядел как список писем, где одновременно спорили статусы,
счётчики, флаги и кнопки. Теперь сначала видна заявка, затем переписка по ней,
а внизу всегда понятен следующий шаг — ответить поставщику. Функции не
удалены: вторичные действия остались в контексте выбранной переписки или в
соответствующих вторичных разделах.

## Before / after evidence

Один и тот же авторизованный сценарий: `/messages`, список и выбранная
переписка `ООО "ШАЛЕ"`, desktop `1280×720`.

| Состояние | Evidence | Статус |
|---|---|---|
| Before — список | Снимок показан inline в CUA до изменений: `Переписки`, большая секция `БЕЗ ПРИВЯЗКИ`, карточки, counters и повторяющиеся row controls. Отдельного PNG-пути нет. | `PARTIAL` |
| Before — detail | Снимок показан inline в CUA до изменений: header reply button, отдельная большая карточка связи с заявкой, полноразмерные message cards. Отдельного PNG-пути нет. | `PARTIAL` |
| After — live list/detail | Снимки показаны inline в CUA после изменений при том же размере: `Мои заявки`, local search, flat rows, compact context, timeline, sticky CTA. | `PASS` |
| After — desktop fixture | [`desktop-user matched reader`](../../frontend/test-results/frontend-audit-matched-cor-24237-ide-email-inside-the-reader-desktop-user/desktop-user-matched-html-reader.png) | `PASS` |
| After — mobile fixture | [`mobile-small matched reader`](../../frontend/test-results/frontend-audit-matched-cor-24237-ide-email-inside-the-reader-mobile-small/mobile-small-matched-html-reader.png) | `PASS` |

## UX решения

1. Главный объект — не письмо и не статус, а заявка с её разговором.
2. Поиск находится рядом со списком заявок, поэтому пользователь фильтрует
   именно рабочий контекст, а не абстрактный глобальный mailbox.
3. В строке заявки оставлены только название, поставщик, последний статус,
   тема и дата активности.
4. В центре поставщик, состояние ответа и связанная заявка собраны в одну
   лёгкую строку контекста.
5. Лента использует временную ось и аватары, чтобы входящие и исходящие
   сообщения читались как разговор, а не как набор CRM-карточек.
6. Sticky footer делает главный следующий шаг стабильным и очевидным.
7. Цветовая система не расширялась: сохранены существующие нейтральные и
   акцентные токены; статусы остаются маленькими семантическими элементами.

## Удалено из основной композиции

- глобальное поле поиска из верхнего header (поиск перемещён в левый список);
- повторяющиеся flag/priority controls из строк списка;
- counters сообщений и ответов в каждой строке;
- повторяющиеся status badges в строках и unmatched preview;
- отдельная большая карточка `СВЯЗАНО С ЗАЯВКОЙ`;
- вложенные bordered cards у каждого unmatched preview item;
- повторяющийся технический текст `Компания не определена`;
- отдельная header-кнопка ответа, дублировавшая главный CTA внизу detail.

## Объединено или перемещено

- global search → local search inside `Мои заявки` / `Рабочий список`;
- supplier + reply status + related request → compact conversation context;
- message header and body → timeline node with one readable content surface;
- reply action → sticky `Следующий шаг` footer;
- request activity and supplier identity → one quiet request row;
- unmatched / outbox presentation → same low-noise list language, при этом
  существующие workflow links and actions preserved.

## Матрица визуальной трансформации

| Dimension | Before | After | Acceptance |
|---|---|---|---|
| Product job / entry | Mailbox and technical triage compete | Request → conversation → reply | `PASS` |
| Hierarchy | Similar weight for cards, badges, counters, actions | Request navigator, conversation, one CTA | `PASS` |
| Composition | Nested cards and separate request card | Flat navigator + compact context + timeline | `PASS` |
| Language | Technical labels and repeated statuses | `Мои заявки`, `Переписка`, `Следующий шаг` | `PASS` |
| Typography | Many competing small labels | Clear eyebrow, supplier title, muted context | `PASS` |
| Density | High-density rows with controls/counts | Calm rows with activity essentials | `PASS` |
| Interaction | Reply action duplicated in header/detail | One obvious footer CTA; existing secondary actions retained | `PASS` |
| Responsive | Same dense composition stressed at small widths | List/detail behavior and compact feed remain usable | `PASS` |
| A11y / state | Repeated visual signals | Semantic status, visible focus/interaction states, axe-clean matched flow | `PASS` |
| Personality | Legacy CRM/mailbox impression | Procurement desk / conversation workspace | `PASS` (qualitative CUA review) |

## Проверено

Фактически выполнено:

- `& .\scripts\assert_workspace.ps1` → `WORKSPACE_GUARD: PASS`;
- `npm run typecheck` → `PASS`, 0 ошибок;
- `npm run lint` → `PASS`, 0 ошибок; 5 существующих предупреждений в
  `SupplierPanel.tsx`, `RegistryFinanceRow.tsx`, `StatusBits.tsx` и `auth.tsx`;
- `npm run build` → `PASS`, Vite production build завершён;
- `$env:AUDIT_BASE_URL='http://127.0.0.1:5173'; npm run test:visual` →
  `88 passed` за `5.0m`;
- matched correspondence target → `8 passed` на всех configured viewport
  profiles;
- `browser_geometry_audit.mjs` для `/messages` → `7` viewport checked,
  `0` failed;
- live CUA at `1280×720`: list/detail, search `ШАЛЕ`, filter
  `Ожидает ответа`, selection, reply dialog open/close; live geometry
  `scrollWidth=clientWidth=1280`, horizontal overflow отсутствует;
- HTTP smoke: frontend `/` → `200`, backend `/` → `200`, `/api/auth/me` →
  `200`, protected `/api/correspondence` without auth → `401`;
- backend `python supplier_app.py` remains on `127.0.0.1:8000`, frontend Vite
  remains on `127.0.0.1:5173`.

## Не проверено

- before screenshot как отдельный локальный PNG — `NOT VERIFIED`, CUA показал
  его inline, но текущий CUA API не дал пути сохранения;
- approved reference image / pixel-diff baseline — `NOT VERIFIED`, исходник не
  предоставлен;
- Lighthouse performance report — `NOT VERIFIED`, отдельный Lighthouse
  command в доступном локальном toolchain не запущен;
- live authenticated CUA mobile screenshot — `NOT VERIFIED`; mobile
  responsive state покрыт fixture Playwright screenshots и `88/88`, но CUA
  live viewport был desktop `1280×720`.

## Риски и откат

Риск низкий: изменён только frontend presentation layer; backend, данные,
API-контракт, маршруты и бизнес-логика не менялись. Сохранены существующие
reply, manual link, metadata и delivery recovery actions.

Откат: вернуть этот коммит целиком через обычный обратный commit либо применить
обратный patch к пяти frontend-файлам; перед откатом проверить, что сторонние
изменения в `backend/**`, `tests/**` и `runtime/` не входят в allowlist.

## Следующий этап

После подтверждения владельцем можно применить тот же visual language к
следующему согласованному экрану. Для `/messages` полезный отдельный follow-up
— сохранить BEFORE PNG в versioned visual-baseline storage и при необходимости
добавить Lighthouse run; это не блокирует текущую UI-проверку.

## Уровень уверенности

`HIGH` для frontend-кода и проверенных desktop/tablet/mobile fixture states;
`MEDIUM` для субъективного вывода «это новый продукт», поскольку он требует
оценки владельца или пользователя, а не только automated checks.
