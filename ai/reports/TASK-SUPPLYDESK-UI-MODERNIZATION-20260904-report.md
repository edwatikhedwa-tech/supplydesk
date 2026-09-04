---
document_id: REPORT-TASK-SUPPLYDESK-UI-MODERNIZATION-20260904
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-04
task_id: TASK-SUPPLYDESK-UI-MODERNIZATION-20260904
---

# SupplyDesk UI modernization — итоговый отчёт

## Статус

`PASS` — инженерная и rendered UI-проверка финального frontend-кода.
`PARTIAL` — owner-facing before/after comparison: before screenshot доступен
inline в рабочем сеансе, но отдельного локального PNG до-версии нет; approved
reference image владельцем не предоставлена.

## Сделано

### Этап 0 — аудит

- Подтвержден стек: React 18 + TypeScript + Vite, Tailwind CSS 3,
  `lucide-react`; отдельные shadcn/Radix зависимости отсутствуют.
- Подтверждены реальные маршруты: `/`, `/requests`, `/requests/new`,
  `/requests/:id`, `/messages`, `/mail/campaigns/:id`, `/suppliers`,
  `/blacklist`, `/settings`, `/login` и fallback.
- Найдены inline-дубли кнопок, status badges, counters, search inputs,
  empty/error states и различия page shells.
- Подробный исходный аудит: [`docs/ui-audit-20260904.md`](../../docs/ui-audit-20260904.md).

### Этап 2 — базовая дизайн-система

Добавлены локальные primitives без установки новой библиотеки:

- `frontend/src/components/ui/Button.tsx` — primary/secondary/ghost/danger/link;
- `frontend/src/components/ui/StatusBadge.tsx` — semantic state + quiet `Count`;
- `frontend/src/components/ui/TextField.tsx` — единое поле поиска/ввода;
- CSS product tokens в `frontend/src/index.css`.

Правило: статус отвечает «что происходит?», количество не притворяется
статусом, действие не оформляется текстовой ссылкой.

### Этап 3 — `/messages`

- Светлая рабочая поверхность с графитовой навигацией и одним синим action
  цветом.
- Заголовок, контекст `заявка → поставщик → переписка` и поиск собраны в одну
  понятную шапку.
- Разделы «По заявкам», «Без привязки», «Очередь» стали лёгкой навигацией;
  фильтр основного списка сохранён как «Отправленные и ответы» /
  «Ожидает ответа».
- Список сгруппирован по заявке; unmatched preview и counters сделаны тише;
  статусные элементы унифицированы.
- Detail: поставщик, статус, связь с заявкой, история, одно основное действие
  «Ответить»; preserved reply, manual link, metadata и recovery actions.
- Очередь/ошибки/неподтверждённая доставка не смешиваются с основной
  перепиской, но остаются доступны в своих сценариях.

Не изменялись backend, API-контракты, база, миграции, маршрутизация,
бизнес-логика отправки и исходные почтовые данные.

## Screenshot comparison

`До`: authenticated `/messages` — inline screenshot в рабочем сеансе до
изменений; были видны segmented tabs, плотные filter pills, разноцветные
preview cards и пустая detail-area.

`После`: inline CUA screenshots проверили list/empty state и selected thread;
автоматические rendered artifacts сохранены существующим Playwright runner:

- [after — queue/list responsive artifact](../../frontend/test-results/frontend-audit-messages-de-00dad-il-separate-from-the-outbox-desktop-user/desktop-user-messages-primary-and-outbox.png)
- [after — opened thread](../../frontend/test-results/frontend-audit-matched-cor-24237-ide-email-inside-the-reader-desktop-user/desktop-user-matched-html-reader.png)
- [after — mobile queue artifact](../../frontend/test-results/frontend-audit-messages-de-00dad-il-separate-from-the-outbox-mobile-small/mobile-small-messages-primary-and-outbox.png)

Смысловое сравнение: одна синяя кнопка и ясная иерархия вместо равноправных
цветных сигналов; спокойные counters вместо badge-шума; request context
перенесён непосредственно над message history.

## UX-проблемы, найденные и исправленные

| Приоритет | Проблема | Исправление | Влияние |
|---|---|---|---|
| P1 | Не было стабильной иерархии действий | Shared `Button` variants | Пользователь быстрее понимает основной шаг |
| P1 | Смешивались статус и количество | `StatusBadge` + `Count` | Меньше неверных визуальных сигналов |
| P1 | `/messages` перегружал список, unmatched и очередь | Группировка и разделы без удаления функций | Быстрее сканировать заявки и ответы |
| P2 | Много рамок, карточек и теней | Тонкие разделители, белые surfaces, меньше shadow | Меньше визуального шума |
| P2 | Неравномерные inputs/focus states | `TextField` и общие focus rules | Предсказуемее клавиатура и поиск |
| P2 | Ошибка превью конкурировала с важным workflow alert | Preview error переведён в polite status | Ошибка не перекрывает критическое действие |
| P3 | Разная типографическая плотность | Product tokens и единые роли текста | Чище иерархия |

## Проверено

- Workspace guard: `PASS` перед изменениями и проверками.
- `npm run typecheck`: `PASS`, ошибок TypeScript нет.
- `npm run lint`: `PASS`, 0 ошибок; 5 предупреждений в pre-existing файлах
  `SupplierPanel.tsx`, supplier status helpers и `auth.tsx`.
- `npm run build`: `PASS`.
- `AUDIT_BASE_URL=http://127.0.0.1:5173 npm run test:visual`: `PASS`, 88/88;
  профили: 1920×1080, 1640×900, 1440×900, 1280×800, 1024×768, 768×1024,
  390×844, 360×800.
- Автоматические axe checks в наборе: `PASS`.
- CUA live smoke на `http://127.0.0.1:5173/messages`: `PASS`, list → detail →
  back, tabs, search, filter, unmatched load; 1280×720,
  `scrollWidth=1280`, `clientWidth=1280`.
- HTTP smoke: frontend Vite работает на `127.0.0.1:5173`; backend canonical
  процесс оставлен запущенным на `127.0.0.1:8000`.

## Не проверено / ограничения

- Before screenshot нет отдельным локальным PNG; он сохранён только inline в
  истории рабочего сеанса.
- Точная визуальная сверка с Linear/Vercel/Stripe/Notion невозможна без
  approved reference image; выполнена только принципиальная reference
  synthesis, поэтому `REFERENCE MATCH: PARTIAL`.
- Canonical backend на `:8000` остаётся stale относительно текущего frontend
  source и ранее возвращал `404` для metadata route; backend не менялся в этой
  задаче, поэтому persistence metadata не является acceptance этой итерации.
- `scripts/audit_toolchain.py` и отдельный repository geometry runner не
  найдены; геометрия подтверждена существующим Playwright набором и live CUA.

## Риски и откат

Риск ограничен frontend visual regression и совместимостью существующих mail
states. Откат — revert коммита этой задачи; backend, база и почтовая история
от этого не изменятся. Тестовые screenshot artifacts находятся в
`frontend/test-results/` и не входят в коммит.

## Следующий этап

После подтверждения владельца перенести primitives на `/requests`,
`/suppliers`, `/blacklist`, `/settings` и dashboard через отдельные узкие
итерации с собственными before/after screenshots. Не расширять этот коммит до
полного frontend rewrite.

## Уровень уверенности

Высокий для финального `/messages` source и автоматизированной viewport matrix;
средний для owner-facing pixel comparison из-за отсутствия отдельного before
PNG и approved reference image.
