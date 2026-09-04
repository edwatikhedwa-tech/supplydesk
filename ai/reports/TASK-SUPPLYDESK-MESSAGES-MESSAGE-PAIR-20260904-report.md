---
document_id: REPORT-TASK-SUPPLYDESK-MESSAGES-MESSAGE-PAIR-20260904
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-04
task_id: TASK-SUPPLYDESK-MESSAGES-MESSAGE-PAIR-20260904
source_commit: 4b89cc8
---

# TASK-SUPPLYDESK-MESSAGES-MESSAGE-PAIR-20260904

## Итог

Статус реализации: `PASS` по инженерным и rendered UI-проверкам. Открытая
переписка теперь визуально разделяет направления общения: письмо поставщика
слева, ответ закупщика справа. Это даёт тот же принцип, что и в ссылке
пользователя, но без подключения assistant-ui и без переноса AI-специфичных
механик в почтовый продукт.

## Дизайн-направление

Пользователь: сотрудник закупок, который быстро читает историю заявки и
решает, отвечать ли поставщику. Главная задача — отличить входящий запрос от
своего ответа за один взгляд и сохранить быстрый переход к ответу.

Визуальная идентичность SupplyDesk сохраняется как спокойный рабочий inbox:
графитовый текст, светлый фон, один синий акцент и плотная, но не шумная
иерархия. Направление `message pair` добавляет узнаваемую ось «поставщик ↔
закупщик»: inbound — слева на нейтральной поверхности, outbound — справа на
лёгком accent bubble. Email HTML остаётся визуально главным содержимым
внутри сообщения, а системные ошибки сохраняют отдельный safety-контур.

Решения следуют цепочке: две стороны переписки требуют мгновенного
различения → направление и выравнивание становятся частью иерархии → разные
стороны получают левую и правую композицию с асимметричным верхним углом →
пользователь быстрее сканирует историю без потери данных.

## Что перенесено из reference

Проверенная [страница Message pair в assistant-ui](https://www.assistant-ui.com/elements/message-pair)
описывает пару пользовательского сообщения и ответа, с bubble или flat
вариантом и вторичными действиями, раскрываемыми при hover/focus. Для
SupplyDesk адаптированы только визуальные принципы:

| Принцип reference | Решение в SupplyDesk | Что сознательно не копируется |
| --- | --- | --- |
| Отправленное сообщение отделено правым bubble | Исходящие письма выровнены вправо, используют существующие accent-токены и мягкий верхний правый угол | Нет AI-терминов и отдельной runtime-модели |
| Ответ читается как спокойная левая полоса | Входящие письма выровнены влево, с sender identity и лёгкой нейтральной поверхностью | Нет имитации streaming-ответа ассистента |
| Действия не конкурируют с текстом | Collapse control остаётся компактным и раскрывается визуально через hover/focus; reply CTA остаётся главным действием | Copy/regenerate не добавляются к email |
| Пара имеет компактную мета-строку | Сохраняются отправитель, направление, адрес и дата | Не удаляются safety-статусы и delivery recovery |

## Изменения

Изменён только `frontend/src/components/mail/ThreadDetail.tsx`:

- удалена вертикальная timeline spine из основной композиции;
- удалены одинаковые full-width message cards как единственный паттерн;
- добавлена directional alignment: inbound left, outbound right;
- добавлены компактные доступные `aria-expanded` и `aria-controls` для
  сворачивания сообщения;
- сохранены `EmailRenderer`, sandboxed HTML iframe, notice внешних изображений,
  статусы отправки и recovery actions;
- сохранён sticky `Ответить поставщику` и существующий composer;
- исправлены два найденных контрастных места: `Исходящее` и ошибка отправки
  на accent surface.

Не изменялись backend, API, БД, бизнес-логика, маршруты и зависимости.

## Rendered evidence

После-снимки, просмотренные вручную:

- `frontend/test-results/frontend-audit-matched-cor-24237-ide-email-inside-the-reader-desktop-wide/desktop-wide-matched-html-reader.png`
- `frontend/test-results/frontend-audit-matched-cor-24237-ide-email-inside-the-reader-desktop-compact/desktop-compact-matched-html-reader.png`
- `frontend/test-results/frontend-audit-matched-cor-24237-ide-email-inside-the-reader-mobile-large/mobile-large-matched-html-reader.png`
- `frontend/test-results/frontend-audit-delivery-un-630d4-ectly-from-the-supplier-row-desktop-wide/desktop-wide-delivery-unknown-thread.png`
- `frontend/test-results/frontend-audit-delivery-un-630d4-ectly-from-the-supplier-row-desktop-compact/desktop-compact-delivery-unknown-thread.png`
- `frontend/test-results/frontend-audit-delivery-un-630d4-ectly-from-the-supplier-row-mobile-large/mobile-large-delivery-unknown-thread.png`

Снимки показывают real application shell с существующими route-controlled
visual fixtures: matched incoming HTML email, outbound delivery-unknown
message, sticky reply action и мобильный detail layout. Эти артефакты
игнорируются Git и не являются canonical design baseline.

BEFORE PNG для этой узкой итерации не был сохранён до изменения. Поэтому
артефактное сравнение BEFORE → AFTER и точная оценка pixel delta —
`NOT VERIFIED`; визуальное направление проверено по rendered AFTER и supplied
reference.

## Проверки

| Проверка | Результат | Примечание |
| --- | --- | --- |
| Workspace Guard | `PASS` | Канонический корень и разрешённая область подтверждены перед изменением. |
| `npm run typecheck` | `PASS` | TypeScript frontend без ошибок. |
| `npm run build` | `PASS` | Production bundle собран. |
| Targeted message states | `PASS` | `9/9`: 6 delivery/list checks + 3 matched HTML-reader checks. |
| Full Playwright visual/a11y matrix | `PASS` | `88/88` на desktop/tablet/mobile проектах за `4.9m`. |
| Accessibility | `PASS` | Axe входит в существующие message acceptance tests; после исправления контраста нарушений нет. |
| Responsive | `PASS` | `1440×900`, `1280×720`, `390×844` просмотрены; полный набор также проверил tablet и `360×800`. |
| Horizontal overflow | `PASS` | Existing geometry assertions passed; clipping/overlap не замечены на просмотренных PNG. |
| Backend/API/DB | `NOT CHANGED` | UI-only scope соблюдён. |

Первый targeted прогон выявил два контрастных нарушения, поэтому промежуточный
результат был `FAIL`; после точечной правки повторные `6/6` delivery/list и
`3/3` HTML-reader прошли. Это исправление не скрывает дефект и не меняет
бизнес-логику.

## Ограничения и риски

- Реальная SAFE_TEST переписка сейчас пуста; rendered evidence использует
  существующие контролируемые Playwright fixtures, без отправки реальных писем.
- Persisted BEFORE PNG отсутствует, поэтому нет формального pixel-level
  before/after diff.
- Вложенный HTML email сохраняет собственные стили; bubble задаёт outer
  conversation context, но не переписывает содержимое письма.
- Delivery-unknown alert намеренно остаётся более заметным, потому что это
  защитное действие, а не обычный message decoration.

## Откат

Откатить можно одним обычным Git revert commit
`TASK-SUPPLYDESK-MESSAGES-MESSAGE-PAIR-20260904`; данные и API при этом не
затрагиваются. Текущие несвязанные изменения в backend enrichment и
`runtime/` не входят в область и не должны откатываться.

## Git

- До: branch `integration/current-architecture-governance-20260903`, HEAD
  `ae557ba`.
- Изменённый UI-файл: `frontend/src/components/mail/ThreadDetail.tsx`.
- State/report-файлы обновлены согласно проектной политике.
- Commit: `4b89cc8`
  (`feat(ui): adopt message-pair reader for messages
  TASK-SUPPLYDESK-MESSAGES-MESSAGE-PAIR-20260904`).
- Push не выполняется.

## Уровень уверенности

Высокая уверенность в инженерной совместимости и responsive поведении
проверенного UI. Средняя уверенность в полном сравнении с прежним экраном,
поскольку до-скриншот этой итерации не был сохранён; это ограничение явно
оставлено в отчёте.
