# TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831

## Статус

`COMPLETE` — реализован полноценный outbound HTML-режим с отдельными
`body_text` и `body_html`. Изменения зафиксированы локальным коммитом
`d90bfd46f6ee421d442f2702c04cb9d280e634d9` в ветке
`codex/TASK-STATE-CONTROL-20260830`. Push не выполнялся.

## Что я делал

Исправил ранее подтверждённый разрыв между rich-text редактором и почтовым
backend-контрактом. Все три пользовательских пути теперь передают явную пару:

- bulk/new campaign: `body_text` + `body_html`;
- single/request-thread composer: `body_text` + `body_html`;
- unmatched inbox reply: `body_text` + `body_html`.

Старое поле `body` сохранено на backend как compatibility alias для старых
клиентов и внутренних вызовов.

## Серверный контракт и безопасность

- HTML нормализуется в `mail/service.py`.
- HTML очищается существующим allowlist-sanitizer на базе `nh3` до попадания в
  durable target snapshot и повторно перед MIME rendering.
- `script`, event-handler attributes, `javascript:` links и небезопасные CSS
  конструкции удаляются.
- Remote images по умолчанию не загружаются: URL хранится как
  `data-remote-src` для существующей UI-политики блокировки трекинговых пикселей.
- Значения personalization экранируются до вставки в HTML.
- `text/plain` всегда получается из очищенного HTML, если HTML содержит видимый
  текст; переданный `body_text` используется только как fallback для HTML без
  видимого текста.
- MIME остаётся `multipart/alternative`: plain part + HTML part.
- Idempotency fingerprint учитывает HTML, а legacy body-only fingerprints
  остаются совместимыми.
- Resend и campaign continuation переносят обе части контракта и не теряют
  форматирование.

Миграции не нужны: существующие `body_text`/`body_html` storage columns уже
были достаточны.

## Regression coverage

Добавлены проверки:

- одна выбранная компания с четырьмя email создаёт ровно одно outbound
  сообщение;
- rich HTML проходит через queue и доходит до fake-provider MIME как HTML;
- unsafe HTML sanitizes;
- plain text остаётся literal в HTML alternative;
- rich HTML учитывается в idempotency и конфликтует при изменении;
- unmatched inbox reply сохраняет HTML;
- campaign continuation сохраняет frozen rich pair;
- delivery-unknown resend сохраняет rich pair;
- HTTP `/api/mail/send-bulk` принимает явный HTML-контракт.

## Проверено

Фактические проверки в локальной среде:

- `python -m unittest tests.test_mail_smtp_evidence tests.test_mailru_mvp tests.test_mail_integration tests.test_mail_deliverability tests.test_mail_integrity tests.test_mail_status_semantics tests.test_mail_pacing` — `286` tests, `OK`, `1` штатный skip;
- целевой rich/MIME/HTTP/resend набор — `7` tests, `OK`;
- rich continuation + существующий bounded continuation — `2` tests, `OK`;
- `python -m compileall -q mail supplier_app.py` — `PASS`;
- `npm run typecheck` в `frontend` — `PASS`;
- `npm run lint` в `frontend` — `PASS`, `0` ошибок и `8` существующих предупреждений вне этой задачи;
- `npm run build` в `frontend` — `PASS`; сохранено существующее предупреждение о
  chunk > 500 kB;
- local smoke: `/` — HTTP `200`, `/requests/1059` — HTTP `200`,
  `/api/auth/me` — HTTP `200`, неизвестный `/api/does-not-exist` — HTTP `404`;
- real local browser без route mocks: bulk composer открыт из `/requests/1059`,
  reply composer открыт из `/messages`; проверены toolbar, rich editor,
  desktop viewport `1280x720` и mobile viewport `390x844`; mobile document
  width `380`, modal scroll width `354`, горизонтального overflow нет.

Письмо из UI не отправлялось: проверка ограничилась открытием редакторов и
рендером. Backend tests используют временные SQLite и fake providers.

## Что не изменено

- существующая база и supplier identity data;
- `supplier_identity_audit.py --apply`;
- миграции;
- SMTP/IMAP и реальные почтовые аккаунты;
- provider transport protocol;
- status/resend business policy кроме сохранения HTML при resend;
- unrelated tracked/untracked worktree changes.

## Не проверено

- реальная доставка через Yandex/Mail.ru;
- PostgreSQL acceptance;
- production deployment;
- фактическая отображаемость HTML во всех внешних почтовых клиентах;
- отсутствующие repository helper scripts `tests/run-tests.ps1` и
  `scripts/doctor.ps1`.

## Риски и следующий шаг

Remote images остаются заблокированными по умолчанию, что является текущей
security policy, а не дефектом HTML-контракта. Перед production rollout нужна
отдельная проверка на реальном test mailbox и ручной review provider-specific
rendering. Локальный сервер на `127.0.0.1:8000` оставлен запущенным.

## Рекомендация

`SAFE FOR CODE REVIEW / NOT A PRODUCTION MAIL ACCEPTANCE`. Код готов для review
и отдельного controlled mailbox acceptance; реальные отправки в этой задаче не
разрешались и не выполнялись.
