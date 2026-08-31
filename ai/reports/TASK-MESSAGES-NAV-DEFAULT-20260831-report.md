# TASK-MESSAGES-NAV-DEFAULT-20260831

Дата закрытия UTC: `2026-08-31T06:42:12Z`
Режим: `EXTEND → LIVE QA → CLOSE`

Commit: `9c15c6f6dc9cadb989196fb23ebcfd696c3b0e3e`
Push: `NO`

## ЦЕЛЬ

Сделать desktop-навигацию свернутой по умолчанию при первом запуске.

## ЧТО ИЗМЕНЕНО

В `frontend/src/components/Layout.tsx` функция чтения настройки теперь
возвращает `true`, если ключ состояния отсутствует или localStorage недоступен.
Сохранённое пользователем состояние не перезаписывается: при наличии ключа
`true` или `false` используется именно оно.

## ПРОСТЫМИ СЛОВАМИ

Новый пользователь сразу видит компактную панель с синей кнопкой и стрелкой
вправо. После нажатия меню раскрывается, стрелка смотрит влево, а выбор
запоминается для следующих открытий.

## ПРОВЕРЕНО

- Реальный Playwright без route-mocks на `http://127.0.0.1:8000`:
  - без ключа состояния начальная ширина `76 px`, label `Развернуть меню`,
    `aria-expanded=false` — `PASS`;
  - click синей кнопки даёт `248 px`, label `Свернуть меню`,
    `aria-expanded=true`, storage `false` — `PASS`;
  - reload сохраняет раскрытое состояние — `PASS`.
- Полный `/messages` no-mock audit после изменения: `81/81 PASS`, включая
  navigation, keyboard, tooltip, persistence, mobile drawer и mail cases.
- Viewports: `390`, `1024`, `1440`, `1640` px.
- Runtime в полном audit: console errors `0`, page errors `0`, failed
  requests `0`.
- `npm run typecheck`: `PASS`.
- `npm run lint`: `PASS`, только существующие warnings вне изменённого файла.
- `npm run build`: `PASS`, только существующее предупреждение о chunks
  больше `500 kB`.
- Local server оставлен запущенным на `127.0.0.1:8000`.

## ВИЗУАЛЬНЫЕ АРТЕФАКТЫ

Candidate after:

- `Temp/read-only-audit-20260830/screenshots/nav-default-collapsed-1440-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/nav-blue-collapsed-1440-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/nav-blue-expanded-1440-viewport.png`

Approved baseline: `NO APPROVED BASELINE` — отдельное письменное approval
для обновления визуального baseline не предоставлялось.

## НЕ ИЗМЕНЕНО

Mobile menu, dashboard route, API, backend, mail, database, queue, statuses,
filters, SMTP/IMAP и пользовательские изменения в других файлах не менялись.

## ОГРАНИЧЕНИЯ

Production, PostgreSQL и real Mail.ru acceptance не запускались. Рабочее
дерево остаётся dirty из-за ранее существующих tracked/untracked файлов;
они не добавлялись и не удалялись.
