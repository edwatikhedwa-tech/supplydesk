# TASK-MESSAGES-STATUS-FILTER-20260831

- Дата: `2026-08-31`
- Режим: `EXTEND` / implementation + browser QA
- Ветка: `codex/TASK-STATE-CONTROL-20260830`
- URL: `http://127.0.0.1:8000/messages`
- Scope: видимое состояние `Ответ получен`, перенос `Ожидает ответа` из строки в верхний фильтр.
- Non-goals: отправка писем, очередь, статусы доставки, API, база, привязки к заявкам и другие разделы SupplyDesk.

## Что изменено

1. В `frontend/src/components/mail/ThreadList.tsx` добавлен верхний фильтр
   `Все` / `Ожидает ответа` с актуальным количеством писем. Фильтр работает
   поверх уже загруженного списка и поиска, поэтому серверный контракт не
   меняется.
2. Видимая плашка `Ожидает ответа` убрана из строк списка. При выборе фильтра
   строки раскрываются, чтобы результат был сразу виден; при отсутствии
   результата показано отдельное понятное empty-state сообщение.
3. В `frontend/src/components/mail/threadStatus.ts` добавлен общий predicate
   `isAwaitingResponse`, чтобы фильтр и отображение использовали одну и ту же
   бизнес-логику.
4. Плашка `Ответ получен` переведена на более выразительную brand-blue
   поверхность `accent-100 / accent-800` с усиленным ring и лёгкой тенью.
   Доступное имя строки по-прежнему содержит статус.

## Простыми словами

Пользователь сразу видит, сколько переписок ждут ответа, и может оставить в
списке только их. Обычные строки не перегружены повторяющейся серой плашкой,
а уже полученный ответ заметнее выделен синим цветом.

## BEFORE

- [BEFORE desktop 1440](C:/Users/edwat/OneDrive/Документы/ChatGPT/SaaS/Temp/messages-before-status-filter-1440.png)

На исходном рендере `Ожидает ответа` повторялся внутри строк, верхнего
фильтра не было.

## CANDIDATE AFTER

- [Candidate desktop 1440 — строка с Ответ получен](C:/Users/edwat/OneDrive/Документы/ChatGPT/SaaS/Temp/messages-status-filter-reply-visible-1440-before-filter.png)
- [Candidate desktop 1440 — фильтр активен](C:/Users/edwat/OneDrive/Документы/ChatGPT/SaaS/Temp/messages-status-filter-desktop-1440-awaiting.png)
- [Candidate mobile 390 — обычный список](C:/Users/edwat/OneDrive/Документы/ChatGPT/SaaS/Temp/messages-status-filter-mobile-390-before.png)
- [Candidate mobile 390 — фильтр активен](C:/Users/edwat/OneDrive/Документы/ChatGPT/SaaS/Temp/messages-status-filter-mobile-390-awaiting.png)

Также сняты candidate screenshots для `1024` и `1640` пикселей.

`NO APPROVED BASELINE`: пользователь не назначал новый скриншот эталоном.

## Browser evidence

No route mocks использованы в точечной проверке. Сценарий выполнил login через
реальный API и открыл локальный runtime.

- Live API `GET /api/correspondence`: `200`; текущий срез — `78` тредов,
  `60` соответствуют `Ожидает ответа`.
- На `390x844`, `1024x768`, `1440x900`, `1640x900`:
  - верхний фильтр видим и доступен;
  - до фильтрации в видимых строках нет `Ожидает ответа`;
  - `Ответ получен` имеет фактические computed styles:
    `background rgb(219,234,254)`, `color rgb(30,64,175)`;
  - после выбора фильтра показано `60` строк, каждая имеет accessible status
    `Ожидает ответа`, другие статусы не попадают в результат;
  - `document.scrollWidth === document.clientWidth`.
- Фокус с клавиатуры на фильтре видим через `focus-visible` ring, `Enter`
  переключает `aria-pressed`.
- Runtime в точечной проверке: console errors `0`, page errors `0`, failed
  requests `0`.
- [Playwright JSON evidence](C:/Users/edwat/OneDrive/Документы/ChatGPT/SaaS/Temp/messages-status-filter-playwright.json)

## Regression checks

- `npm run typecheck` — `PASS`.
- `npm run lint` — `PASS`, `0` errors; `8` существующих warnings в других
  файлах.
- `npm run build` — `PASS`; Vite оставил только предупреждение о крупных
  chunks.
- `npx playwright test --config=playwright.live-email.config.ts` — `1/1
  PASS` без route mocks: HTML, plain text, CID, remote images; viewport
  matrix `390`, `1024`, `1440`, `1640`; существующая защита удалённых
  изображений и отсутствие overflow сохранены.
- `npm run test:visual` — `56/80 PASS`, `24 FAIL` в существующих route-mocked
  audit-сценариях. Падения локализованы в прежних областях: autofocus reply
  editor, fixture для delivery-unknown строки и request-status metrics. Они
  не затрагивают изменённые два файла; тесты и эти области намеренно не
  менялись в рамках задачи.
- Smoke: `GET /messages` — `200`; listener `127.0.0.1:8000`, PID `23584`.
  Неавторизованный `GET /api/mail/inbox` — ожидаемый `401`.

## Findings / disposition

- `P2` — повторяющийся статус `Ожидает ответа` перегружал строки и не давал
  быстро отфильтровать рабочий срез. **RESOLVED**; подтверждено screenshot +
  DOM assertions на четырёх ширинах.
- `P2` — `Ответ получен` был недостаточно выразительным. **RESOLVED**;
  подтверждено computed styles и фактическим рендером.
- P0/P1/P2 после этого узкого изменения в затронутом сценарии не выявлены.

## Не проверено / риски

- Не проверялись production, PostgreSQL, реальные SMTP/IMAP и отправка писем.
- Полный общий audit-набор не стал зелёным из-за 24 ранее существовавших
  несоответствий; их исправление не входит в эту задачу.
- Browser regression открывает реальные письма, поэтому обычное поведение
  чтения могло обновить read-state отдельных тестовых писем. Код этого UI
  фикса не меняет read-state, queue или delivery status.

## Следующий этап

Отдельной задачей обновить и затем повторно прогнать 24 failing route-mocked
audit-сценария, начиная с фикса autofocus в reply editor и согласования
delivery/status fixtures; это не нужно смешивать с текущим фильтром.
