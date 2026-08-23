# Yandex Mail integration

## Что добавлено

Текущий репозиторий был статическим прототипом: в нём не было backend, БД, авторизации, ORM или очереди. Интеграция добавлена рядом с существующим `supplier_finder.html`:

- `supplier_app.py` — локальный HTTP-сервер, API, сессии и OAuth callback;
- `mail/providers/base.py` — общий контракт почтового провайдера;
- `mail/providers/yandex.py` — OAuth, refresh token, SMTP и IMAP XOAUTH2 для Yandex Mail;
- `mail/crypto.py` — AES-256-GCM шифрование access/refresh token на сервере;
- `mail/repository.py` — репозиторий с SQLite для локального запуска и PostgreSQL для production;
- `mail/service.py` — шаблоны, персонализация, валидация и постановка писем в очередь;
- `mail/queue.py` — ограниченная очередь с retry и exponential backoff;
- `migrations/001_mail_integration.sql` — схема пользователей, workspace, заявок, поставщиков, аккаунтов, threads, messages, attachments и jobs;
- `migrations/003_mail_sync.sql` — UID-курсор синхронизации входящих сообщений.
- `migrations/004_unmatched_inbox.sql` — безопасное хранение входящих писем, которые пока не удалось сопоставить с заявкой и поставщиком.

Входящие письма синхронизируются вручную или при открытии раздела «Переписка». Сообщения с безопасным сопоставлением сохраняются в thread заявки и поставщика. Письма без сопоставления сохраняются отдельно в `mail_inbox_messages` и показываются в разделе «Переписка» как «Неразобранное входящее» — они не прикрепляются к чужой заявке.

## OAuth flow

1. Авторизованный пользователь вызывает `GET /api/mail/yandex/start`.
2. Сервер создаёт одноразовые `state` и PKCE `code_verifier`, связывает их с session/user/workspace и отправляет пользователя на Yandex OAuth.
3. В callback сервер проверяет state, session и срок жизни, один раз обменивает code на токены.
4. Email определяется через `GET https://login.yandex.ru/info?format=json` с заголовком `Authorization: OAuth ...`.
5. Access token и refresh token шифруются AES-256-GCM и сохраняются только в серверной БД. Frontend их не получает.
6. Для отправки используется `smtp.yandex.com:465` и SMTP AUTH XOAUTH2. Пароль пользователя приложение не видит.

Запрошенные scopes:

- `mail:smtp` — SMTP отправка;
- `mail:imap_full` — доступ к чтению почты по IMAP; приложение не выполняет удаление писем;
- `login:email` — получение email подключённого аккаунта.

Источники: [Yandex OAuth authorization code, state и PKCE](https://yandex.com/dev/id/doc/en/codes/code-url), [refresh token](https://www.yandex.com/dev/id/doc/en/tokens/refresh-client), [OAuth-авторизация в Яндекс Почте](https://yandex.ru/support/yandex-360/business/mail/ru/web/security/oauth).

## ENV

Скопируйте `.env.example` в `.env` и заполните:

```text
APP_USER_EMAIL=your-login@example.com
APP_USER_PASSWORD=use-a-local-password-at-least-8-chars
MAIL_TOKEN_ENCRYPTION_KEY=<32-byte-url-safe-base64>
DATABASE_URL=<PostgreSQL connection string; production/Vercel>
YANDEX_CLIENT_ID=<client-id>
YANDEX_CLIENT_SECRET=<client-secret>
YANDEX_REDIRECT_URI=http://127.0.0.1:8000/oauth/yandex/callback
YANDEX_OAUTH_SCOPE=mail:smtp mail:imap_full login:email
```

Важно: угловые скобки в примерах (`<client-id>`, `<client-secret>`) — только обозначение места для значения. В реальном `.env` их указывать нельзя.

Ключ шифрования можно сгенерировать без сохранения его в репозиторий:

```powershell
python -c "from mail.crypto import generate_key; print(generate_key())"
```

`APP_USER_*` — временная локальная учётная запись, потому что в исходном проекте не было системы авторизации. В production её нужно заменить существующим identity provider и оставить те же проверки user/workspace ownership.

## Создание Yandex OAuth приложения

1. Откройте [oauth.yandex.ru](https://oauth.yandex.ru/).
2. Создайте приложение для web-приложения.
3. Укажите redirect URI ровно:
   `http://127.0.0.1:8000/oauth/yandex/callback`
4. Включите доступ к почте для SMTP и IMAP (`mail:imap_full`), а также доступ к email пользователя.
5. Скопируйте Client ID и Client Secret в `.env`.

Redirect URI должен совпадать с зарегистрированным адресом буквально, включая схему, порт и путь. Для production используйте HTTPS и отдельный callback URL.

## Запуск

```powershell
python -m pip install -r requirements.txt
python supplier_app.py
```

Откройте [http://127.0.0.1:8000/supplier_finder.html](http://127.0.0.1:8000/supplier_finder.html), войдите через `APP_USER_EMAIL`/`APP_USER_PASSWORD`, откройте «Настройки → Почта» и подключите Яндекс Почту.

## Деплой на Vercel

Для Vercel добавлен тонкий адаптер `api/index.py` и конфигурация `vercel.json`: существующие HTML, API-маршруты и OAuth callback обслуживаются тем же `SupplierHandler`, без переписывания приложения.

В production ENV нужно добавить серверные переменные из `.env.example`: `APP_USER_EMAIL`, `APP_USER_PASSWORD`, `MAIL_TOKEN_ENCRYPTION_KEY`, `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`, `YANDEX_OAUTH_SCOPE`, `XMLRIVER_USER`, `XMLRIVER_KEY`, а также задать:

```text
APP_BASE_URL=https://<production-domain>
YANDEX_REDIRECT_URI=https://<production-domain>/oauth/yandex/callback
```

Этот callback URI нужно буквально добавить в настройках Yandex OAuth-приложения. На Vercel переменная `DATABASE_URL` указывает на подключённую Neon PostgreSQL, поэтому сессии, OAuth state, подключённая почта и переписка не зависят от конкретного serverless-экземпляра. Если `DATABASE_URL` отсутствует, локальный адаптер использует SQLite в `MAIL_DB_PATH`; `/tmp` на Vercel остаётся только аварийным fallback и не предназначен для постоянных данных.

Neon добавляется через Vercel Marketplace. При первом запуске production схема миграций создаётся автоматически. Старые данные из эфемерной SQLite-базы Vercel не переносятся: после первого деплоя нужно войти заново и ещё раз подключить Яндекс Почту.

## Отправка

Кнопка «Написать» создаёт одно письмо одному supplier email. «Отправить запрос выбранным» создаёт отдельную job и отдельный thread для каждого поставщика; CC/BCC не используется. Переменные `{{supplier_name}}`, `{{request_name}}`, `{{request_description}}`, `{{sender_name}}`, `{{company_name}}` заменяются до постановки в очередь. Если имени поставщика нет, приветствие становится «Здравствуйте!».

Очередь имеет максимум четыре worker-потока (по умолчанию один), ограниченный retry и exponential backoff. При SMTP 4xx/rate limit очередь замедляется, а в интерфейсе сохраняется понятная ошибка. По умолчанию локальный безопасный предел — 250 получателей в день, ниже документированного ограничения Yandex Mail для SMTP/почтовых программ.

Источники ограничений: [лимиты отправки Yandex Mail](https://yandex.ru/support/yandex-360/customers/mail/ru/web/letter/create/send-many-letters).

## База данных

- `users`, `workspaces`, `workspace_members`, `sessions`, `oauth_states`;
- `requests`, `suppliers`, `request_supplier_states`;
- `mail_accounts` — provider, email, encrypted tokens, expiry, status и ошибка;
- `mail_threads` — уникальная пара `workspace + request + supplier`;
- `mail_messages` — исходящие и входящие сообщения, MIME body, status, Message-ID и reply headers;
- `mail_attachments` — валидированные вложения;
- `mail_jobs` — queued/sending/sent/failed, attempts, next retry;
- `mail_sync_states` — папка INBOX, UIDVALIDITY, последний UID, результаты и ошибка синхронизации;
- `mail_inbox_messages` — входящие письма без безопасной привязки к заявке/поставщику.

## Безопасность

- пароль почты не запрашивается и не хранится;
- OAuth state одноразовый, короткоживущий и привязан к session/user/workspace;
- PKCE используется с `S256`;
- токены не выдаются API/frontend и не пишутся в логи;
- access/refresh token шифруются AES-256-GCM ключом из ENV;
- все mail API требуют авторизацию и CSRF header;
- email, тема и вложения валидируются на backend;
- HTML письма строится из экранированного plain text, поэтому пользовательский текст не вставляется как произвольный HTML;
- IMAP читает сообщения через `BODY.PEEK[]` и не меняет флаги прочитанности;
- права проверяются через текущую session и workspace;
- OAuth revoke/invalid grant переводит аккаунт в `revoked`, после чего требуется повторное подключение.

## Добавление Gmail/Outlook

Новый провайдер реализует `MailProvider`: `exchange_code`, `refresh_token`, `get_account`, `test_connection`, `send_message`, `fetch_incoming`. Общие threads, messages, sync state и UI переиспользуются; для Gmail и Outlook нужно добавить соответствующие OAuth scopes и конкретный транспорт API/SMTP/IMAP в новый класс.

## Синхронизация входящих

Входящие сообщения Yandex читаются через IMAP XOAUTH2 в режиме `BODY.PEEK[]`, сохраняются с `direction=inbound`, находят thread по `In-Reply-To`/`References` и fallback по нормализованной теме и email поставщика. Синхронизация использует UID-курсор в `mail_sync_states`, поэтому повторный запуск не создаёт дубликаты и не помечает письма прочитанными. В интерфейсе раздел «Переписка» запускает проверку автоматически; кнопку «Обновить входящие» можно использовать повторно.

Для первой синхронизации пользователь должен заново пройти OAuth после добавления `mail:imap_full`: один OAuth-токен не может одновременно использоваться с другим набором прав. В настройках почты кнопка «Обновить доступ для входящих» запускает повторную авторизацию. В Яндекс.Почте также должны быть включены IMAP и «Пароли приложений и OAuth-токены».
