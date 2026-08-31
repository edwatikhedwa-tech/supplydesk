# TASK-MESSAGES-UX-20260831

Дата закрытия UTC: `2026-08-31T06:21:32Z`
Режим: `IMPLEMENTATION → LIVE QA → CLOSE`

Commit: `a7043cc4f30f926dd792ef4aaceedee05300f3e2`
Push: `NO`

## STATUS

`COMPLETE — /messages scoped fixes implemented and verified`

## ЦЕЛЬ

Закрыть подтверждённые UX-дефекты страницы `/messages`, найденные в live
аудите: отсутствие отвязки вручную привязанного письма после reload и
искусственная пустая высота коротких plain-text писем.

## ЧТО ИЗМЕНЕНО

- `frontend/src/components/mail/EmailRenderer.tsx`
  - уменьшен искусственный минимум высоты email iframe с `80` до `24` px;
  - начальная и reset-высота используют тот же именованный минимум;
  - логика блокировки remote images, CID и текст уведомления не менялась.
- `frontend/src/components/mail/ThreadDetail.tsx`
  - для вручную привязанного треда добавлена доступная кнопка
    `Отвязать письмо`;
  - во время запроса кнопка блокируется и показывает состояние загрузки;
  - ошибка отвязки показывается как `role="alert"`.
- `frontend/src/pages/Messages.tsx`
  - добавлен callback, вызывающий существующий API manual-unlink;
  - после успешной отвязки тред закрывается, открывается вкладка
    `Без привязки`, обновляются список и счётчик.

Функциональная защита внешних изображений, отправка, очередь, статусы,
фильтры, привязка к заявкам, база, миграции, SMTP и IMAP не менялись.

## ПРОСТЫМИ СЛОВАМИ

Короткое письмо больше не получает большой пустой блок. Письмо, которое уже
привязали вручную, теперь можно отвязать и вернуть во входящие прямо из
карточки заявки, в том числе после перезагрузки страницы.

## LIVE ПРОВЕРКИ

- `node Temp/read-only-audit-20260830/audit.mjs` на
  `http://127.0.0.1:8000`, без route-mocks: `81/81 PASS`.
- Проверены desktop navigation, collapsed persistence, keyboard/tooltip,
  mobile drawer/Escape/overlay/selection, unmatched, HTML, plain text, CID
  controlled fixture, remote images, no-images, long HTML и responsive
  viewports `390`, `1024`, `1440`, `1640`.
- `node Temp/read-only-audit-20260830/remote-request-check.mjs`: remote
  image requests `0`, external image sources remaining `0`, console/page/
  failed-request errors `0`; обнаружены только ожидаемые запросы Google Fonts.
- `npx playwright test tests/live-email-regression.spec.ts
  --config=playwright.live-email.config.ts`: `1 passed` за `1.5m`, без
  route-mocks; ожидаемые sandbox warnings не являются ошибками приложения.
- Изолированный manual-link сценарий на временной SQLite-копии,
  `http://127.0.0.1:8001`: auth, поиск заявки, подтверждение, persistence,
  reload, наличие `Отвязать письмо`, отвязка и возврат во входящие — `PASS`;
  console/page/failed-request errors — `0`.
- `npm run typecheck`: `PASS`.
- `npm run lint`: `PASS`, `9` существующих warnings вне изменённых файлов.
- `npm run build`: `PASS`, сохранено существующее предупреждение о крупных
  chunks `>500 kB`.
- После проверок сервер оставлен запущенным на `127.0.0.1:8000` (PID
  `9476`).

## ВИЗУАЛЬНЫЕ АРТЕФАКТЫ

Ключевые screenshots сохранены во временных папках:

- `Temp/read-only-audit-20260830/screenshots/plain-text-1055-2097-390-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/plain-text-1055-2097-1440-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/remote-images-21-390-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/no-images-45-390-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/manual-link-after-reload-390-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/manual-link-unlinked-390-viewport.png`
- `Temp/read-only-audit-20260830/screenshots/nav-drawer-open-390-stable-viewport.png`

Визуальный self-review: текст письма читаем, remote notice находится вне
email iframe и не перекрывает его, короткий plain-text не оставляет старой
пустоты, manual unlink control не ломает карточку на mobile.

## НЕ ПРОВЕРЕНО / ОГРАНИЧЕНИЯ

- В canonical SQLite нет строк `mail_attachments` (`0`), поэтому отдельный
  live binary CID attachment не мог быть проверен как новый входящий MIME
  объект. Текущий controlled CID fixture (`message_id=167`) проверен через
  реальный `/messages` и не показывает remote notice; parser coverage уже
  существует в `tests/test_mail_integration.py`.
- Открытие существующего matched треда сохраняет текущую серверную отметку
  прочтения, а Layout сохраняет существующий enrichment side effect. Это
  не изменялось в рамках UX-фикса.
- Не запускались SMTP/IMAP, миграции, production deployment и PostgreSQL
  acceptance.

## РИСКИ И ОТКАТ

Изменения ограничены тремя frontend-файлами и обратимы revert-ом Task-ID
commit. Незакоммиченные изменения пользователя в остальных tracked-файлах
и untracked-артефакты не добавлялись и не удалялись.

## NEXT STEP

Отдельной задачей обновить/закрепить permanent live regression fixture для
реального CID attachment; outbound rich-text contract остаётся отдельным
не связанным с `/messages` направлением.

## INSTRUCTION CHECK

- Scope `/messages`: `YES`.
- Product logic outside `/messages`: `NO`.
- Remote-image protection changed: `NO`.
- SMTP/IMAP/live email: `NO`.
- Unverified items disclosed: `YES`.
