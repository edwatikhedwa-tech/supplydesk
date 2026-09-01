# SupplyDesk — исторический паспорт проекта (срез 2026-08-28)

> **HISTORICAL — NOT CURRENT.** Срез соответствует кодовой базе на **28 августа
> 2026 года** и сохранён для истории. Единственный источник текущего состояния
> продукта — [`../../ai/CURRENT_STATE.md`](../../ai/CURRENT_STATE.md); правила
> актуализации — [`../../docs/DOCUMENTATION_POLICY.md`](../../docs/DOCUMENTATION_POLICY.md).
> Подробные датированные аудиты и история решений остаются в
> `PROJECT_DOCUMENTATION.md` и профильных файлах этого каталога.

## 1. Назначение

SupplyDesk — локальное рабочее пространство снабжения. Пользователь создаёт
заявку, задаёт позиции и глубину поиска, получает список поставщиков,
обогащает карточки контактами и данными реестра, рассылает запросы и ведёт
переписку с ответами поставщиков.

Продукт не является просто поисковым скриптом: интерфейс, заявки, поставщики,
почта и история их связей используют одну рабочую базу данных.

## 2. Что реализовано

### Заявки и поиск

- создание, редактирование и удаление заявок;
- позиции, дедлайн и свободная глубина поиска от 1 до 100;
- возобновляемый поиск: положение конвейера хранится в БД, а не только в
  памяти вкладки;
- поиск поставщиков, повторное обогащение и состояния `черновик`, `в поиске`,
  `обновляется`, `завершена`, `ошибка`;
- адаптивное представление: таблица на широком экране и карточки на меньших
  ширинах.

### Поставщики и обогащение

- извлечение email, ИНН и реквизитов с сайта и из поисковой выдачи;
- parser quorum, fallback web-search, ограниченная обработка релевантных PDF;
- Checko-обогащение по ИНН: юридическое лицо, статус, ОГРН/ОГРНИП,
  финансы и риски;
- граф доказательств: значение, источник, URL, сила и решение;
- ручной ИНН с отдельной пометкой `manual`; автоматическое обогащение не
  должно затереть его;
- глобальная карточка компании, чёрный список и исключение поставщика только
  из одной заявки.

### Почта и переписка

- вход и подключение Яндекс.Почты через OAuth 2.0 с PKCE;
- access/refresh token хранятся зашифрованными AES-256-GCM;
- исходящие запросы создают отдельные сообщения и jobs на каждого получателя;
- лимит одной кампании — от 1 до 300 получателей, без CC/BCC;
- шаблон запроса: тема, текст, переменные персонализации и вложения;
- чтение входящих через IMAP XOAUTH2 с UID-курсором и дедупликацией;
- автоматическая привязка ответа к заявке по заголовкам письма, затем по
  паре `тема + email`; ручная привязка для остальных писем;
- отдельный inbox для непривязанных писем, ответ без искусственного создания
  заявки и поставщика;
- исходящая массовая операция требует idempotency key; fingerprint описывает
  пользовательский payload и не зависит от изменяемого enrichment, а targets
  хранят фактический snapshot персонализации; повтор того же ключа продолжает
  сборку или возвращает уже созданные сообщения, а изменённое содержимое даёт
  конфликт;
- безопасная state machine исходящей отправки различает `queued`, `sending`,
  `sent`, `failed` и `delivery_unknown`; `sent` означает только положительный
  ответ провайдера, а не доказанную доставку получателю;
- atomic claim с lease/token и durable irreversible gate не разрешают повторять
  неопределённую передачу; проверка по неизменяемому RFC Message-ID имеет исходы
  `found`, `not_found`, `unavailable`;
- копия в «Отправленных» выполняется после фиксации результата, включая
  синхронный ответ на письмо без привязки; сбой локальной записи после SMTP
  success не запускает обычный retry;
- `delivery_unknown` виден в строке поставщика и в переписке, поддерживает
  повторную проверку, явный ручной resend с новым Message-ID и ручное закрытие
  вопроса без изменения факта доставки;
- runtime kill switch проверяется на обоих исходящих путях непосредственно
  перед отправкой; входящая синхронизация продолжает работать;
- hard bounce помечает адрес как недоставляемый; внешние изображения в письме
  не загружаются по умолчанию.

### Интерфейс и качество

- дашборд с KPI заявок, ответов и непривязанных писем;
- на дашборде виден только список трёх последних непривязанных писем;
  каждое закрыто до клика и не меняет unread-состояние при просмотре;
- адаптивные routes `/`, `/requests`, `/requests/:id`, `/messages`,
  `/suppliers`, `/blacklist`, `/settings`;
- Playwright, axe-core, Storybook, Lighthouse CI и DOM-assertions подключены
  в `frontend` для регрессионной проверки интерфейса.

## 3. Как это работает

### Жизненный цикл заявки

```text
Создать заявку → поставить search job → SERP/сайты/PDF/web fallback
→ доказательства контактов и ИНН → Checko → список поставщиков
→ выбрать получателей → mail job → SMTP Яндекса → ответы через IMAP
→ связанный тред или непривязанный inbox
```

Поисковый и enrichment-конвейеры сохраняют cursor, статус и ошибку в БД. При
следующем запуске можно продолжить незавершённую ступень, а не начинать поиск
заново.

### Жизненный цикл письма

```text
Composer → POST /api/mail/send-bulk → mail_messages + mail_jobs
→ MailQueue → SMTP XOAUTH2 → status sent → IMAP-ответ
```

Входящие сопоставляются сначала по `In-Reply-To` и `References`. Если таких
заголовков нет, используется email отправителя и нормализованная тема. Когда
сопоставление небезопасно, письмо сохраняется в `mail_inbox_messages` и ждёт
решения пользователя.

## 4. Техническая карта

| Слой | Фактическая реализация |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind, React Router |
| HTTP | Python `ThreadingHTTPServer` и `SupplierHandler` |
| Данные | SQLite по умолчанию; PostgreSQL при `DATABASE_URL` |
| Миграции | SQL-файлы из `migrations/`, применяются при старте repository |
| Поиск | XMLRiver, crawler, parser quorum, web fallback, необязательный LLM |
| Реестр | Checko; ручной ИНН остаётся отдельным источником |
| Почта | Яндекс OAuth + SMTP SSL + IMAP SSL, XOAUTH2 |
| Очередь | `mail_jobs` и 1–4 фоновых Python-потока |
| Защита | HttpOnly session cookie, CSRF, PKCE, AES-GCM, HTML allowlist + iframe sandbox |

### Основные сущности

- `requests`, `request_positions`, `request_search_jobs` — заявка и поиск;
- `suppliers`, `supplier_profiles`, `supplier_evidence` — найденный поставщик
  и доказательства;
- `global_suppliers` и связанные registry/finance tables — карточка компании;
- `mail_accounts`, `mail_threads`, `mail_messages`, `mail_jobs` — почтовый
  контур;
- `mail_inbox_messages` и `mail_inbox_replies` — входящие без заявки;
- `audit_events` — аудит части пользовательских действий.

## 5. Локальный запуск

1. Скопировать `.env.example` в `.env` и заполнить только нужные интеграции.
   Секреты не добавлять в Git.
2. Установить Python-зависимости: `pip install -r requirements.txt`.
3. Собрать frontend:

   ```powershell
   cd frontend
   npm install
   npm run build
   cd ..
   ```

4. Запустить приложение:

   ```powershell
   python supplier_app.py
   ```

5. Открыть `http://127.0.0.1:8000/`.

Локальная учётная запись через `APP_USER_EMAIL` и `APP_USER_PASSWORD`
поддерживается backend API; визуальный экран входа сейчас предлагает Яндекс
OAuth как основной путь. Яндекс-почта требует `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET` и
`MAIL_TOKEN_ENCRYPTION_KEY`; исходящий поиск и реестровые данные требуют
отдельных ключей соответствующих поставщиков.

## 6. Проверка перед передачей

```powershell
python -m unittest discover -s tests -v
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test:visual
```

Для локального smoke-теста нужны HTTP 200 для `/` и `/api/auth/me`; защищённый
`/api/mail/status` без сессии обязан вернуть 401.

## 7. Обязательная следующая работа

### P0 — надёжность отправки

Iteration 1 завершила этот блок: idempotency key, сборка операции, безопасный
claim/lease, irreversible gate, `delivery_unknown`, recovery-by-Message-ID,
Sent-copy, ручной resend/resolution и runtime kill switch реализованы. SQLite
acceptance suite пройден; PostgreSQL-кейс оставлен отдельным непроверенным
интеграционным риском, потому что в текущей среде нет настроенной базы.

### P1 — почта и эксплуатация

1. Переносить jobs после дневного лимита на следующий день, а не завершать
   ошибкой после нескольких часовых retry.
2. Добавить отмену/паузу job и всей рассылки, историю send attempts и
   безопасный аудит исходящих событий.
3. Сохранять вложения входящих писем.
4. Исправить rich-text отправку: сейчас HTML из редактора экранируется как
   текст; до исправления не обещать форматирование исходящих ответов.
5. Добавить reply-to-inbox в очередь и вложения в этот сценарий.
6. Нужны backup БД, process supervisor и наблюдаемость queue/sync.

### P2 — расширение продукта

1. Google и Mail.ru: сейчас кнопки есть только в UI, backend поддерживает
   исключительно Яндекс.
2. Экран здоровья почты: лимит, размер очереди, задержка IMAP и следующая
   попытка.
3. Retention-политика для тел писем и вложений.

## 8. Сверка документации с кодом

Проверены `README.md`, `PROJECT_DOCUMENTATION.md`, профильные Markdown-файлы
этого каталога, маршруты `supplier_app.py`, mail-модули, миграции и frontend API.

| Документ | Результат сверки |
|---|---|
| `README.md` | Описывает исторический PoC parser. Вверху добавлена ссылка на этот исторический паспорт и canonical state. |
| `PROJECT_DOCUMENTATION.md` | Историческая архитектура и датированные записи; текущие URL и состояние проверяются по canonical state, коду и тестам. |
| `mail-integration.md` | Исторические решения Яндекс-почты; текущие провайдеры и live evidence проверяются по canonical state и исходникам. |
| `FRONTEND_QA.md` | Исправлено неверное утверждение о трёх письмах, открытых по умолчанию: список из трёх есть, но карточки закрыты до клика. |
| Документы с датированными аудитами | Это исторические результаты. Количество писем, тестов и данные конкретных заявок нельзя читать как актуальное состояние базы. |

## 9. Границы этого документа

- Vercel намеренно не является частью текущего рабочего контура и здесь не
  описывается как целевая инфраструктура.
- Значения `.env`, реальные письма, токены, пользовательские cookies и данные
  рабочей БД не читались и в документацию не внесены.
- Статус «реализовано» означает, что путь существует в кодовой базе и покрыт
  доступными локальными тестами. Внешняя доставка по-прежнему не обещается:
  `sent` — это принятие провайдером, а `delivery_unknown` — честно сохранённая
  неопределённость.
- Recovery истёкшего mail lease выполняется при старте очереди; периодического
  runtime-recovery в текущем процессе нет, поэтому зависшая `sending` job может
  ждать restart.

## 10. Iteration 1 — исходящая целостность

Кодовый контракт описан в `ITERATION_1_OUTGOING_MAIL_INTEGRITY.md` (в рабочей
копии имя приложенного файла нормализовано до
`ITERATION_1_OUTGOING_MAIL_INTEGRITY (1).md`). Неизменяемый исторический
`EMAIL_INTEGRITY_STEP0_REPORT.md` не редактировался.

Основные сущности реализации: `mail_send_operations`,
`mail_send_operation_targets`, `mail_job_integrity`, `mail_message_integrity`,
`mail_reply_integrity`, `mail_delivery_resolutions` и
`mail_runtime_controls`; миграция — `migrations/022_outgoing_mail_integrity.sql`.

Acceptance-проверки находятся в `tests/test_mail_integrity.py`; итоговые
результаты и ограничения зафиксированы в
`EMAIL_INTEGRITY_ITERATION1_REPORT.md`.

## 11. Iteration 2 — pacing и защита account

Iteration 1 = integrity / duplicate safety. Iteration 2 = pacing / provider
protection / account budgets. Логика встроена в существующий `MailQueue`, а не
в отдельный scheduler: `mail_account_outbound_state` хранит таймеры cooldown и
breaker, `mail_send_reservations` сериализует право на следующий send-slot,
`mail_send_attempts` хранит durable audit фактических transport attempts.

Внутренние defaults — 30–60 секунд jittered interval, rolling 100 sends/hour
и 100 sends/24h на account. Это conservative application defaults, не
официальная гарантия Яндекса и не обещание Inbox placement. При 30 секундах
теоретически получается до ~120/час, при среднем интервале 45 секунд — около
~80/час, при 60 секундах — около ~60/час; 100 писем занимают примерно 50–100
минут до учёта дополнительных задержек. Transient provider
ошибки вызывают bounded backoff/cooldown, auth/repeated failures открывают
account breaker, а `delivery_unknown` по Iteration 1 никогда не requeue-ится.

Основная документация: `EMAIL_PACING_ITERATION2.md`; migration:
`migrations/023_mail_pacing.sql`; acceptance tests:
`tests/test_mail_pacing.py`. PostgreSQL branch сохранена, но в текущей среде
не запускалась (`NOT VERIFIED`).

## 12. Iteration 3 — deliverability / content safety / staged rollout

Iteration 1 = integrity / duplicate safety. Iteration 2 = pacing / budgets /
provider protection. Iteration 3 = content preflight / campaign health /
staged rollout.

Добавлены provider-neutral `mail_campaigns` и `mail_campaign_targets`, read-only
preflight/preview, deterministic personalization levels, explainable similarity
warning, validation/suppression reasons, staged eligibility, durable
pause/resume/stop и campaign summary API. Кампания использует существующий
`MailQueue` и account limiter; отдельный scheduler не создавался. Явный
spam/policy rejection и auth failure ставят campaign на health pause. `sent` не
называется delivered, `delivery_unknown` не requeue-ится.

### Health policy corrective pass — 2026-08-29

Health больше не ставит campaign на паузу только из-за lifetime-счётчика
transient targets. Audit остаётся полным, но transient-защита использует
текущую consecutive-серию (default: 3 подряд) и bounded rolling signal
(последние 10 completed attempts; минимум 5 и 50%). Accepted outcome сбрасывает
серийный счётчик. Обычная одиночная временная ошибка продолжает использовать
cooldown/backoff Iteration 2; auth/policy, breaker, permanent-failure и
`delivery_unknown`-защиты не ослаблены. Настройки централизованы в
`RolloutSettings` через `MAIL_CAMPAIGN_TRANSIENT_*`. Это внутренние safety
thresholds SupplyDesk, а не лимиты Yandex.

Документы: `EMAIL_DELIVERABILITY_ITERATION3.md`,
`EMAIL_DELIVERABILITY_ITERATION3_STEP0.md`,
`EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md` и итоговый report. Migration —
`migrations/024_deliverability.sql`; acceptance —
`tests/test_mail_deliverability.py`. Live SMTP не выполнялся; PostgreSQL
остаётся `NOT VERIFIED`; campaign UI в этой backend-focused итерации отложен.

## Iteration 3 final critical review — 2026-08-28

Iteration 3 corrective review подтверждает: cumulative rollout использует
ceilings 10/25/50/remaining; manual stage approval остаётся configurable
(default `false`, для первой ordinary-Yandex кампании рекомендуется `true`).
Подтверждённый hard bounce теперь создаёт email-level suppression в существующей
`blacklist_entries` по нормализованному `trim + lowercase` адресу; soft bounce
не создаёт permanent suppression. Pause/stop race проходит через атомарный
campaign gate, а stopped claimed-unsent job финализируется как `cancelled`.

Основной результат разделён честно: `ITERATION 3 BACKEND — ACCEPTED /
ITERATION 3 PRODUCT UI — PENDING`. Полный campaign workflow отсутствует в UI,
но backend/API и операторские документы доступны. Generic 550 не считается
spam/policy без явного provider evidence. PostgreSQL — `NOT VERIFIED`, live SMTP
не выполнялся, `outgoing_enabled=0`.

Подробная проверка: `EMAIL_DELIVERABILITY_ITERATION3_FINAL_REVIEW.md`.

## Iteration 4 — Campaign UI поверх Iteration 3

Iteration 4 расширяет существующий bulk Composer до безопасной цепочки
preflight → exact preview → final preflight → `send-bulk`. Новый route
`/mail/campaigns/:id` показывает staged rollout, health counters, accepted как
«Принято сервером», `delivery_unknown` отдельно и действия pause/resume/stop.
Pacing, budgets, cooldown, circuit breaker, suppression, kill switch и
duplicate-safety Iteration 1 не менялись.

Для ordinary Yandex интерфейс явно показывает provider-policy warning: это не
официальный лимит Yandex и не обещание доставки или Inbox placement.
`manual_stage_approval` теперь можно выбрать для новой campaign через strict
bulk API; выбранное значение сохраняется в существующем campaign row и
используется stage transitions после restart/env changes. Документы:
`EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md`, `EMAIL_CAMPAIGN_UI_ITERATION4.md`,
`EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md`. Новая migration не нужна; migration
024 не менялась. Live SMTP не выполнялся, `outgoing_enabled=0`, PostgreSQL —
`NOT VERIFIED`.

Итоговый статус: `ITERATION 4 — ACCEPTED FOR SQLITE` после corrective pass;
frontend checkbox отражает backend default и передаёт выбор в preflight/send-bulk.

### Campaign size / duration correction — 2026-08-29

`MAIL_CAMPAIGN_MAX_RECIPIENTS` — единый provider-neutral default `300`,
используемый preflight, preview и queue validation. Значение ограничено
диапазоном `1..500`; `301+` блокируется с `campaign_size_out_of_range`, без
молчаливого усечения выбранного списка. Это не меняет account-level pacing и
budget: `MAIL_PACING_MIN_SECONDS=30`, `MAIL_PACING_MAX_SECONDS=60`,
`MAIL_MAX_PER_HOUR=100`, `MAIL_MAX_PER_DAY=100`. Duration API возвращает
объект minimum/average/maximum, а Composer показывает human-readable average и
диапазон без `NaN`. Для 120 адресов preflight дополнительно предупреждает о
необходимости ждать rolling 24-hour budget после первых 100 попыток. Live SMTP
не выполнялся; `outgoing_enabled=0`.

### P0 SMTP evidence и incoming sync — 2026-08-29

Для новых transport attempts добавлена provider-neutral таблица
`mail_send_attempt_evidence` (migration 025) с безопасными полями SMTP stage,
code, enhanced status, provider response и exception class. Ошибки после DATA
с неопределённым итогом сохраняют контракт Iteration 1:
`delivery_unknown`, без автоматического resend; известный terminal outcome
закрывает pacing reservation как `consumed`.

Входящая IMAP-синхронизация проверена отдельно при выключенной исходящей
отправке: до controlled live импортировано 7 писем, после — ошибок нет.
Контролируемая новая попытка получила явный Yandex `554 5.7.1` policy/spam
rejection после DATA; run остановлен после одной SMTP-попытки, campaign
осталась на health pause, `outgoing_enabled=0`. Job69 и его историческая
запись не изменялись. SQLite integrity — `ok`; PostgreSQL — `NOT VERIFIED`.
Полный отчёт: `SMTP_EVIDENCE_CONTROLLED_LIVE_REPORT.md`.
