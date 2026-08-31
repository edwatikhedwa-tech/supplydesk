# TASK-MESSAGES-NAV-TOGGLE-20260831

Дата закрытия UTC: `2026-08-31T06:36:26Z`
Режим: `EXTEND → LIVE QA → CLOSE`

Commit: `2ba2547383c42ad92b246527739eb2a2a56f8e76`
Push: `NO`

## ЦЕЛЬ

Сделать синюю иконку в desktop-навигации единственной кнопкой сворачивания
и раскрытия меню: стрелка вправо в свернутом состоянии и влево в раскрытом.

## ЧТО ИЗМЕНЕНО

- Изменён только `frontend/src/components/Layout.tsx`.
- На desktop синий control теперь переключает sidebar `248 ↔ 76 px`.
- Доступное имя и `aria-expanded` отражают текущее состояние.
- Удалена отдельная маленькая кнопка справа, чтобы не было двух конкурирующих
  управляющих элементов.
- На mobile логотип внутри drawer по-прежнему ведёт на дашборд; mobile menu
  button, overlay, Escape и закрытие после выбора пункта не менялись.

## ПРОСТЫМИ СЛОВАМИ

Теперь пользователь нажимает прямо на синюю кнопку: она раскрывает меню,
показывая стрелку вправо, а в открытом меню та же кнопка показывает стрелку
влево и сворачивает его.

## ПРОВЕРЕНО

- Реальный Playwright без route-mocks на `http://127.0.0.1:8000`:
  синий control по клику переключил `248 → 76 → 248 px`, сохранил blue
  background, доступные имена и `aria-expanded`.
- Полный live audit `/messages`: `81/81 PASS`, включая keyboard toggle,
  persistence после reload, tooltip, active/unread, mobile drawer и все
  mail cases на `390`, `1024`, `1440`, `1640` px.
- Console errors, page errors и failed requests в полном аудите: `0`.
- `npm run typecheck`: `PASS`.
- `npm run lint`: `PASS`, только существующие warnings в других файлах.
- `npm run build`: `PASS`, только существующее предупреждение о chunks
  больше `500 kB`.
- Сервер оставлен запущенным на `127.0.0.1:8000`.

## SCREENSHOTS

Candidate after:

- `Temp/read-only-audit-20260830/screenshots/nav-blue-collapsed-1440-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/nav-blue-expanded-1440-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/nav-drawer-open-390-stable-viewport.png`

BEFORE evidence was retained in the earlier audit artifacts. Approved
baseline: `NO APPROVED BASELINE` — user approval of a new visual baseline was
not given.

## ОГРАНИЧЕНИЯ

- Не изменялись API, backend, mail, database, queue, statuses, filters,
  SMTP/IMAP и другие страницы.
- Другие tracked/untracked пользовательские изменения рабочего дерева не
  добавлялись и не удалялись.
- Production, PostgreSQL и real Mail.ru acceptance не проверялись.
