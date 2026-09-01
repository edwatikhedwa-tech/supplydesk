# Yandex Mail integration — историческая документация

> **HISTORICAL — NOT CURRENT.** Текущее состояние продукта и почтового контура:
> [`../../ai/CURRENT_STATE.md`](../../ai/CURRENT_STATE.md). Этот файл описывает
> реализацию Яндекс-почты и историю её решений. Упоминания провайдеров и
> результаты live-проверок ниже действуют только на указанную дату.

## Что добавлено

Исторически репозиторий начинался как статический прототип. Реализация на дату
этого документа — backend, БД, авторизация и очередь — описана ниже. Текущие
возможности и ограничения сверяются с `../../ai/CURRENT_STATE.md`:

- `supplier_app.py` — локальный HTTP-сервер, API, сессии и OAuth callback;
- `mail/providers/base.py` — общий контракт почтового провайдера;
- `mail/providers/yandex.py` — OAuth, refresh token, SMTP и IMAP XOAUTH2 для Yandex Mail;
- `mail/crypto.py` — AES-256-GCM шифрование access/refresh token на сервере;
- `mail/repository.py` — репозиторий с SQLite для локального запуска и PostgreSQL для production;
- `mail/service.py` — шаблоны, персонализация, валидация и постановка писем в очередь;
- `mail/queue.py` — ограниченная очередь с retry и exponential backoff только
  для безопасных ошибок до необратимого этапа и явных отказов провайдера;
- `migrations/001_mail_integration.sql` — схема пользователей, workspace, заявок, поставщиков, аккаунтов, threads, messages, attachments и jobs;
- `migrations/003_mail_sync.sql` — UID-курсор синхронизации входящих сообщений.
- `migrations/004_unmatched_inbox.sql` — безопасное хранение входящих писем, которые пока не удалось сопоставить с заявкой и поставщиком.

### P0: SMTP evidence и независимая синхронизация входящих — 29 августа 2026

Новые transport attempts сохраняют безопасное техническое свидетельство в
provider-neutral таблице `mail_send_attempt_evidence`, связанной с
`mail_send_attempts`: этап SMTP, numeric code, enhanced status, ограниченный
текст ответа и класс исключения. Значения остаются `NULL`, если провайдер их
не сообщил. OAuth-токены, пароли, тела писем и секретные заголовки не
сохраняются. Исторические попытки до этой миграции не переписываются и могут
иметь пометку неполного evidence.

Адаптер Yandex различает ошибки до DATA и после DATA. Неопределённый timeout
или disconnect после необратимой границы остаётся `delivery_unknown` по
контракту Iteration 1 и не получает автоматический resend. Достоверный
terminal result закрывает pacing reservation как `consumed`, в том числе если
reservation уже была `started`; это освобождает mailbox для независимых jobs,
но не даёт права повторять неопределённое письмо.

Входящие синхронизируются отдельным IMAP-контуром даже при
`MAIL_OUTGOING_DISABLED=1`. В текущем локальном runtime применены интервалы
background sync 300 секунд, on-view sync 45 секунд и bounded wait 4 секунды;
они не включают исходящую отправку.

Контролируемая проверка 29 августа 2026 получила от Yandex явный ответ
`554 5.7.1` после DATA: сообщение отклонено по подозрению на SPAM. Это
подтверждённый provider policy rejection, поэтому проверка остановлена после
ровно одной новой SMTP-попытки. `accepted` в отчётах означает принятие
SMTP/provider, а не доставку или попадание во «Входящие». Подробный отчёт:
[`SMTP_EVIDENCE_CONTROLLED_LIVE_REPORT.md`](../../SMTP_EVIDENCE_CONTROLLED_LIVE_REPORT.md).

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
DATABASE_URL=<необязательная строка подключения PostgreSQL>
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

Redirect URI должен совпадать с зарегистрированным адресом буквально, включая
схему, порт и путь. Для другого постоянного HTTPS-контура нужен отдельный
callback URL.

## Запуск

```powershell
python -m pip install -r requirements.txt
python supplier_app.py
```

Откройте [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Экран входа
предлагает Яндекс OAuth как основной путь. Локальная пара `APP_USER_EMAIL` /
`APP_USER_PASSWORD` поддерживается backend API, но не является основным
видимым сценарием экрана входа. Затем откройте «Настройки → Почта» и
подключите Яндекс Почту.

## Историческая заметка: Vercel

> Этот раздел сохранён как история предыдущего временного контура. Он не
> является инструкцией для текущего локального рабочего режима.

Для очереди исходящей почты Vercel/serverless не является поддерживаемым
рабочим контуром: тёплый экземпляр не даёт постоянного worker lifecycle.
Текущая Iteration 1 проверена на обычном локальном процессе с durable DB.
Исторический адаптер и его запуск очереди не удалялись в рамках этой задачи.

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

Для пользовательского массового endpoint `/api/mail/send-bulk` обязателен
непустой idempotency key в body или `Idempotency-Key` header. Frontend создаёт
его один раз на конкретный draft-intent и повторяет с тем же ключом; отсутствие
ключа даёт HTTP 400 без создания supplier/operation/message/job. При повторе
используется snapshot персонализации из operation targets, а не заново
обогащённые данные поставщика.

Очередь имеет максимум четыре worker-потока (по умолчанию один). Для каждой
операции действует durable claim с lease/token и проверкой готовности операции;
после начала необратимого этапа timeout/disconnect не переводится в обычный
retry. Явный отказ SMTP до принятия письма сохраняет прежнюю retry-логику.
Существующий локальный предел — 250 получателей в день — не является частью
Iteration 1 и не изменялся.

Источники ограничений: [лимиты отправки Yandex Mail](https://yandex.ru/support/yandex-360/customers/mail/ru/web/letter/create/send-many-letters).

## База данных

- `users`, `workspaces`, `workspace_members`, `sessions`, `oauth_states`;
- `requests`, `suppliers`, `request_supplier_states`;
- `mail_accounts` — provider, email, encrypted tokens, expiry, status и ошибка;
- `mail_threads` — уникальная пара `workspace + request + supplier`;
- `mail_messages` — исходящие и входящие сообщения, MIME body, status, Message-ID и reply headers;
- `mail_attachments` — валидированные вложения;
- `mail_jobs` — queued/sending/sent/failed/delivery_unknown, attempts, next
  retry; companion integrity tables хранят claim, lease, gate и copy status;
- `mail_account_outbound_state` — persisted account-level next-send timer,
  cooldown, rolling breaker state и failure window;
- `mail_send_reservations` — атомарные account send-slot reservations, не
  удерживающие DB-транзакцию во время SMTP;
- `mail_send_attempts` — durable sanitized audit фактических transport attempts;
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
- `invalid_grant`/`invalid_token` переводят локальный аккаунт в `revoked`,
  после чего требуется повторное подключение. Кнопка «Отключить» очищает
  локальные токены; внешний OAuth grant у Яндекса отдельным revoke-запросом
  сейчас не отзывается.

## Добавление Gmail/Outlook

Новый провайдер реализует `MailProvider`: `exchange_code`, `refresh_token`, `get_account`, `test_connection`, `send_message`, `fetch_incoming`. Общие threads, messages, sync state и UI переиспользуются; для Gmail и Outlook нужно добавить соответствующие OAuth scopes и конкретный транспорт API/SMTP/IMAP в новый класс.

## Синхронизация входящих

Входящие сообщения Yandex читаются через IMAP XOAUTH2 в режиме `BODY.PEEK[]`, сохраняются с `direction=inbound`, находят thread по `In-Reply-To`/`References` и fallback по нормализованной теме и email поставщика. Синхронизация использует UID-курсор в `mail_sync_states`, поэтому повторный запуск не создаёт дубликаты и не помечает письма прочитанными. В интерфейсе раздел «Переписка» запускает проверку автоматически; кнопку «Обновить входящие» можно использовать повторно.

Для первой синхронизации пользователь должен заново пройти OAuth после
добавления `mail:imap_full`: один OAuth-токен не может одновременно
использоваться с другим набором прав. Отдельной кнопки «Обновить доступ для
входящих» сейчас нет: нужно отключить почту и пройти стандартное подключение
заново. В Яндекс.Почте также должны быть включены IMAP и «Пароли приложений и
OAuth-токены».

## Iteration 2: pacing и account protection

Исходящие jobs, manual resend и синхронный ответ на непривязанное входящее
письмо используют единый limiter конкретного `mail_account`. Перед provider
атомарно проверяются `next_send_not_before`, rolling 1-hour/24-hour budgets,
cooldown, circuit breaker и актуальный blacklist/suppression. Waiting оставляет
job queued и не расходует `attempts`; worker ждёт bounded wake hint и может
проснуться через `wake_event`.

Централизованные настройки: `MAIL_PACING_MIN_SECONDS` (30),
`MAIL_PACING_MAX_SECONDS` (60), `MAIL_MAX_PER_HOUR` (100),
`MAIL_MAX_PER_DAY` (100), а также cooldown/breaker/backoff settings из
`mail/pacing.py`. Это внутренние conservative defaults, не provider limit.
Ориентировочно 100 писем при таком pacing занимают 50–100 минут: 30 секунд
дают теоретически до ~120/час, 45 секунд в среднем — около ~80/час, 60
секунд — около ~60/час. Фактическое время может быть больше из-за cooldown,
retries, budgets и provider errors; это не гарантия отсутствия блокировки или
попадания во «Входящие».
Справка Yandex: [ограничения массовой отправки](https://www.yandex.ru/support/yandex-360/customers/mail/ru/web/letter/create/send-many-letters)
и [диагностика SMTP-лимита](https://www.yandex.ru/support/yandex-360/customers/mail/ru/web/letter/create/troubleshooting).

Iteration 2 не обещает доставку, Inbox placement или отсутствие spam
classification. Она не создаёт новый scheduler, новый provider или dashboard.
Подробный операторский guide и state machine находятся в
`EMAIL_PACING_ITERATION2.md`; PostgreSQL остаётся `NOT VERIFIED` без реального
экземпляра.

## Iteration 3: deliverability и staged rollout

Iteration 3 = content preflight / campaign health / staged rollout поверх
Iteration 1 integrity и Iteration 2 pacing. `POST
/api/mail/deliverability/preflight` и `/preview` не отправляют и не создают
jobs; они возвращают PASS/WARNING/BLOCK, recipient exclusion reasons,
personalization distribution, similarity warning, exact rendered samples,
attachment size и Yandex provider warning. Preview использует тот же renderer,
что и immutable operation target snapshot.

`mail_campaigns`/`mail_campaign_targets` хранят stage/status и eligibility.
Внутренние stages по умолчанию 10/25/50/remaining, configurable и не являются
официальной рекомендацией Yandex. `GET /api/mail/campaigns/<id>` отдаёт
planned/eligible/queued/waiting/attempted/accepted/failed/unknown/remaining и
health. `pause`, `resume` и `stop` не переписывают sent, delivery_unknown или
audit; suppression повторно проверяется непосредственно перед SMTP.

Явные spam/policy и auth provider failures останавливают campaign health;
uncertain после DATA остаётся I1 `delivery_unknown` без автоматического resend.
Tracking pixel, SMTP probing, fake personalization и новый provider не
добавлялись. Campaign UI отложен; backend/API и операторская документация
готовы. Полный контракт — `EMAIL_DELIVERABILITY_ITERATION3.md`, а live plan
подготовлен, но не выполнялся.

Health transient policy: lifetime audit сохраняется, но health pause считает
текущую серию из 3 последовательных `transient_rejected` либо последние 10
завершённых попыток (pause при 5 transient и доле не ниже 50%). Accepted
сбрасывает серию. Это внутренние настраиваемые параметры
`MAIL_CAMPAIGN_TRANSIENT_*`, не ограничения Yandex; одиночный transient
остаётся в cooldown/backoff, а uncertainty не получает право на resend.

### Iteration 3 final critical review

Campaign rollout имеет cumulative ceilings 10/25/50/remaining и не резервирует
account budget заранее. Manual approval configurable; hard bounce записывается
в существующий email-level `blacklist_entries`, soft bounce не создаёт
permanent suppression. Финальный campaign gate защищает от pause/stop race до
provider, а Stop сохраняет `sent`, `delivery_unknown` и audit history.

Для ordinary Yandex отображается policy warning: официальные страницы не дают
SupplyDesk «безопасного лимита», а ограничения могут быть снижены для
однотипных/шаблонных коммерческих писем. Preview frozen только при `send-bulk`
в operation snapshot; до этого он read-only и требует повторного запуска при
изменении исходных данных. Подробности в
`EMAIL_DELIVERABILITY_ITERATION3_FINAL_REVIEW.md`; UI campaign workflow —
pending, live SMTP не выполнялся.

## Campaign UI Iteration 4

Bulk Composer теперь является безопасным входом в campaign workflow:
preflight и exact preview read-only, WARNING требует acknowledgement, BLOCK
запрещает запуск, а final preflight выполняется непосредственно перед
`send-bulk`. Campaign detail доступен по `/mail/campaigns/:id` и показывает
accepted как принятие сервером, не как доставку, а `delivery_unknown` —
отдельно.

UI не создаёт второй scheduler и не обходит account limiter, cooldown, circuit
breaker, suppression, global kill switch или idempotency contract. Для ordinary
Yandex показан policy warning; internal pacing не является лимитом Yandex и не
обещает Inbox placement. В Composer можно выбрать `manual_stage_approval` для
новой campaign; backend принимает только JSON boolean, включает значение в
fingerprint и сохраняет его в существующем campaign snapshot. После создания
режим immutable, а detail только отображает его. Live SMTP не запускался;
подробности в `EMAIL_CAMPAIGN_UI_ITERATION4.md` и report.

### Campaign size and duration correction — 2026-08-29

В Iteration 4 единый setting `MAIL_CAMPAIGN_MAX_RECIPIENTS` имеет default
`300` (допустимый диапазон конфигурации `1..500`). Одно effective значение
используется в `preflight`, `preview` и `queue_bulk`; frontend получает его в
`campaign_limits.max_recipients`. Поэтому 300 — верхняя граница одной
кампании, а 301 и больше блокируются прозрачно, без silent truncation.

Это отдельный лимит размера кампании. Account budget остался
`MAIL_MAX_PER_HOUR=100` и `MAIL_MAX_PER_DAY=100`; pacing остался 30–60 секунд.
Для 120 адресов ориентир pacing — 3570/5355/7140 секунд, но UI отдельно
предупреждает, что rolling 24-hour budget 100 может удерживать оставшиеся
письма. Duration object отображается как average и диапазон, поэтому старый
`NaN` больше не возникает.

Техническое число 300 в официальной справке Yandex для SMTP не трактуется как
разрешение на массовую коммерческую рассылку или гарантия Inbox placement.
Policy warning в Composer сохранён; live SMTP в этой проверке не запускался.
