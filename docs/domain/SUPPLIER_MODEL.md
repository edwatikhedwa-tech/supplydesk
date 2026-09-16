---
document_id: DOC-DOMAIN-SUPPLIER-MODEL-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-12
---

# Модель поставщика в SupplyDesk

Канонические правила о том, как SupplyDesk ищет, хранит, дедуплицирует и
отображает поставщиков. Правило: **при любой задаче, затрагивающей поиск,
обогащение, идентификацию или хранение поставщиков, сначала прочитать этот
файл.** Не дублировать его содержимое в `AGENTS.md`/`CLAUDE.md`.

Этот документ описывает **фактическое текущее состояние кода**, не план и
не желаемую архитектуру. Пункты, которые ещё не реализованы, явно помечены
как открытые, а не описаны так, будто они уже работают.

---

## 1. Текущая схема данных (уже реализовано)

Три уровня идентичности поставщика, уже существующие в БД:

1. **`suppliers`** (`migrations/001_mail_integration.sql`) — identity по
   `(workspace_id, external_key=host)`. Это единица, к которой привязан
   краулинг, обогащение и переписка (`mail_threads`, `mail_messages`
   ссылаются на `suppliers.id`, не на `global_suppliers.id`). Один и тот же
   домен в одном workspace — одна строка.
2. **`global_suppliers`** (`migrations/007_global_suppliers.sql`) —
   дедупликация по **ИНН**, `UNIQUE (workspace_id, inn)`. Комментарий в самой
   миграции описывает её назначение точно: «поставщик как единый объект во
   всех заявках, где он встретился» — **внутри одного workspace**, не между
   разными аккаунтами SupplyDesk. `global_supplier_links` связывает
   host-based `suppliers.id` с `global_suppliers.id` (максимум один global
   card на supplier).
3. **`request_suppliers`** / **`request_supplier_states`** — участие
   поставщика в конкретной заявке (позиции, статус отправки/ответа).
   Коммуникация — в `mail_threads`/`mail_messages`, тоже per-workspace.

Вокруг `global_suppliers` уже есть развитая инфраструктура источников и
уверенности (частично закрывает §5 ниже):

- **`global_supplier_registry`**, **`global_supplier_finances`**,
  **`global_supplier_finance_history`**, **`global_supplier_risks`** —
  факты из реестра/Checko, каждая со своим `updated_at`.
- **`supplier_evidence`** (`migrations/019_enrichment_reliability.sql`) —
  накопительный граф доказательств на уровне ПОЛЯ: `field_name`,
  `field_value`, `source_type`, `source_url`, `strength`, `score`,
  `decision`, `first_seen_at`, `last_seen_at`. Сейчас реально используется
  только для кандидатов ИНН (`record_supplier_evidence`, `field_name="inn"`)
  — не для `name`/`email`/других полей.
- **`supplier_enrichment_jobs`** — устойчивая очередь незавершённого
  обогащения по стадиям (crawl/registry/web/finance), с lease и retry.
  Именно она уже реализует «переиспользовать, а не искать заново» —
  **внутри** воркспейса: `supplier_enrichment_jobs` и вся очередь обогащения
  scoped по `workspace_id`.

**Важно:** несмотря на название, `global_suppliers` — это **per-workspace**
дедупликация, а не единая база поставщиков для всех клиентов SupplyDesk.

4. **`canonical_companies`** (`migrations/038_canonical_companies.sql`,
   `mail/canonical_companies.py`, DECISION-022, 2026-09-11) — настоящий
   **кросс-tenant** слой, единственная таблица в проекте без `workspace_id`.
   Ключ — ИНН (`UNIQUE`). Хранит только общие/публичные факты о юрлице:
   ИНН, ОГРН, юр./публичное название, сайт, публичный email/телефон, регион,
   статус реестра, историю финансов, риски, источник, timestamps. Владелец
   явно подтвердил (через уточняющий вопрос в сессии 2026-09-11), что имелся
   в виду именно обмен между разными аккаунтами SupplyDesk, а не только
   между заявками одного аккаунта.
5. **`workspace_supplier_classifications`**
   (`migrations/046_workspace_supplier_classifications.sql`) — рабочие
   классификации одной карточки внутри одного workspace: категория, товар,
   бренд или специализация. Каждая запись несёт собственные `value`, `source`,
   `confidence`, необязательный `source_url` и timestamps. Факты с источником
   `manual`, `registry` и `ai` хранятся раздельно: новая ручная метка не
   выдаётся за реестровую/AI и не перезаписывает их. UI текущего MVP создаёт
   только `manual`; появления источников `registry`/`ai` потребуют отдельной
   подтверждённой интеграции.

## 2. Supplier invariant (реализован на уровне ИНН-резолюции, 2026-09-11)

**Инвариант:** поставщик — каноническая сущность; одна организация не
должна заново создаваться и полностью обогащаться при каждом новом
обнаружении — ни внутри одного workspace, ни между разными workspace.

Реализовано:

- Внутри workspace — дедупликация по ИНН (`global_suppliers`), устойчивая
  очередь обогащения (`supplier_enrichment_jobs`).
- Между workspace — `canonical_companies`. `apply_supplier_enrichment`
  пишет туда каждый раз, когда реально резолвит компанию (тот же уровень
  доверия, что `trusted_name=True`). `_resolve_missing_inn`
  (`backend/domain/supplier_enrichment/orchestrator.py`) проверяет
  `canonical_companies` по ИНН **до** живого запроса `checko.lookup()`/
  `checko.finances()` — если компания уже известна (найдена любым другим
  workspace), эти два запроса не выполняются, а `apply_supplier_enrichment`
  вызывается сразу с закэшированными данными. Проверено тестом
  `tests/test_canonical_companies_cache_reuse.py` (RED-to-GREEN, second
  workspace makes zero Checko calls for an ИНН the first workspace already
  resolved).

**Не реализовано (честно, см. §4):** сама первичная догадка ИНН по домену
(`resolve_inn_by_registry`, до 6 запросов) остаётся per-host и не выигрывает
от кросс-tenant кэша (ключ там — не ИНН, а домен, для которого ИНН ещё не
известен). Основной пайплайн обогащения заявки (`_process_enrich_step`) пока
не читает `canonical_companies` — только `_resolve_missing_inn`. Между собой
`suppliers`/`global_suppliers` (per-workspace) и `canonical_companies`
(кросс-tenant) не связаны отдельной FK-таблицей — связь только по значению
ИНН.

## 3. Supplier-name invariant (реализован, 2026-09-11)

**Инвариант:** отображаемое имя поставщика (`suppliers.name` и
`global_suppliers.name`) должно происходить из нормализованных/подтверждённых
данных и не должно автоматически становиться раскавыченным `<title>`
страницы, рекламным H1, SEO description или темой письма.

Предпочтительный порядок значения `name`:

1. официальное название из реестра/Checko (`apply_supplier_enrichment`'s
   `company_name`, всегда приходит вместе с резолвленным ИНН — проверено по
   каждому месту вызова в
   `backend/domain/supplier_enrichment/orchestrator.py`);
2. то же самое, по сути — название по ИНН (Checko/DaData реестр);
3. уже сохранённое нормализованное имя (не даунгрейдить существующее);
4. домен/host как честный нейтральный фолбэк;
5. `Поставщик {id}` — крайний случай (`list_supplier_directory`, уже было).

Что было исправлено, чтобы это стало правдой (не только на новых записях, а
системно):

- **`upsert_search_result`** (`mail/repository.py`): плейсхолдер для нового
  имени — `host`, никогда не сырой `title` страницы выдачи.
- **`upsert_supplier`**: `ON CONFLICT` для `name` больше не перезаписывает
  безусловно. Пустое или равное `host` (плейсхолдер) значение побеждает
  только когда текущее имя тоже пустое; настоящее имя (не пустое, не равное
  своему host) — всегда побеждает, как и раньше. Раньше повторное появление
  уже известного поставщика в НОВОМ поисковом результате откатывало уже
  обогащённое настоящее имя обратно к плейсхолдеру.
- **`_get_or_create_global_supplier`**: параметр `trusted_name`. `True`
  только у `apply_supplier_enrichment` (значение всегда авторитетное,
  всегда побеждает). `False` (как раньше — только если пусто) у остальных
  трёх вызывающих (ручной ввод ИНН, `backfill_global_suppliers`,
  `restore_global_supplier_directory`) — их значение не авторитетное,
  первая запись не должна навсегда блокировать более позднее настоящее имя.
- **`backfill_placeholder_supplier_names`** (owner-only maintenance route
  `/maintenance/backfill-placeholder-supplier-names-20260911`) — системный
  бэкафилл: сбрасывает `suppliers.name` на `host` только для строк без
  подтверждённого ИНН (`supplier_profiles.inn` пусто) — не трогает вручную
  ни одну запись, решение основано на состоянии данных. Прогнано один раз
  на продакшене 2026-09-11: 213 строк.
- **`refresh_bad_global_supplier_names`** (owner-only maintenance route
  `/maintenance/refresh-bad-global-supplier-names-20260911`) — для
  `global_suppliers.name`, уже застрявших на плохом значении (та же причина,
  что и `upsert_supplier`, но для global-карточки): находит кандидатов по
  паттерну «похоже на рекламный текст», делает **реальный** Checko-запрос по
  их ИНН и переписывает имя только если Checko подтвердил компанию —
  паттерн используется только чтобы выбрать, кого перепроверить, никогда для
  того, чтобы выдумать имя. **Не выполнено на продакшене**: `CHECKO_KEY` не
  сконфигурирован в production-окружении Vercel (`checko_unavailable: true`
  при вызове 2026-09-11) — см. §6.

## 4. Что НЕ реализовано (честно, не для будущей задачи, а для текущего статуса)

- **Полная интеграция кэша во весь pipeline** — только `_resolve_missing_inn`
  читает `canonical_companies`; основной путь резолюции реестра
  (`_process_enrich_step` и связанные `_resume_*`-методы) — нет.
- **Дедупликация по домену между workspace** — только по ИНН; если два
  workspace находят один и тот же домен, но ИНН ещё не резолвлен ни у кого,
  кросс-tenant кэш не помогает (нечем ключеваться).
- **`refresh_bad_global_supplier_names`** не может исправить уже застрявшие
  `global_suppliers.name` на production, пока не появится `CHECKO_KEY` в
  Vercel env — код готов и покрыт тестами, но не выполнялся на реальных
  данных.
- **TTL/принудительная актуализация** — ни `canonical_companies`, ни
  `supplier_evidence` не читаются для решения "устарело — актуализировать";
  каждая строка `canonical_companies` считается вечно актуальной с момента
  записи. Не реализовано.
- **Условия использования Checko/DaData на хранение их данных — НЕ
  проверены.** Перед тем, как этот кросс-tenant кэш обслуживает заметный
  объём, нужна реальная проверка их оферты/API-документации на ограничения
  повторного хранения/кэширования ответов — в сессии 2026-09-11 это не
  удалось сделать (инструменты WebSearch/WebFetch были недоступны из-за
  сбоя инфраструктуры), решение о запуске в текущем виде принято владельцем
  как приемлемый риск для внутреннего кэша одного продукта (не публикация
  и не перепродажа данных третьим лицам), а не как подтверждённый факт
  соответствия условиям.

## 5. Tenant isolation invariant

Глобальная карточка поставщика (`global_suppliers`, per-workspace) и
`canonical_companies` (кросс-tenant) содержат только допустимые общие
сведения об организации — см. точный список разрешённых полей в
`migrations/038_canonical_companies.sql` и тест
`tests/test_canonical_companies.py::test_write_through_carries_no_tenant_specific_data`.
Переписка, заявки, заметки, цены, отношения, задачи, приватные контакты и
любые другие пользовательские данные остаются исключительно в
`workspace_id`-scoped таблицах (`suppliers`, `request_suppliers`,
`mail_threads`/`mail_messages`, `thread_notes`, `tasks`, `logistics_quotes`,
`workspace_supplier_contacts`, `workspace_supplier_classifications`).

`workspace_supplier_contacts` (migration `045`) хранит ручные контактные
лица карточки поставщика. Запись принадлежит одному workspace; вариант
`private` видит только создавший её пользователь, `workspace` — участники
этого workspace. Ни имя, ни телефон, ни email из этой таблицы не становятся
canonical/public-данными компании и не используются для автоматической
рассылки. Эти и другие workspace-данные никогда не попадают в
`canonical_companies` и не становятся видимыми другому workspace. Изоляция
проверена тестами
`test_directory_never_leaks_another_workspace` (per-workspace слой) и
`test_a_different_workspace_can_reuse_a_company_resolved_elsewhere` +
`test_write_through_carries_no_tenant_specific_data` (кросс-tenant слой —
что расшаривается, и что не расшаривается).

`workspace_supplier_classifications` (migration `046`) следует той же
границе: метка принадлежит workspace и её автору; изменить или удалить её
может только автор. Поля происхождения не являются косметической подписью —
они входят в саму запись, поэтому ручной ввод, реестр и AI остаются
различимыми в API и карточке. Ни одна такая метка не повышает статус
`canonical_companies` и не используется для автоматической рассылки.

Контракт адресации карточки также tenant-scoped: `global_supplier_detail`
сначала ищет `global_suppliers` по паре `(workspace_id, id)` и возвращает
отсутствие карточки для чужого идентификатора. Создание workspace-контакта или
классификации повторяет ту же проверку до INSERT. Это покрыто
`tests/test_supplier_workspace_isolation.py`: данные и попытки мутации из
второго workspace не пересекают границу, даже при одинаковом ИНН организации.

## 7. needs_followup и самообновляемые email-контакты (2026-09-15, DECISION-024)

`mail/contact_intelligence.py` (`ContactIntelligenceMixin`, `migrations/
051_contact_intelligence.sql`). Две независимые части.

### 7.1 needs_followup

Производное (никогда не хранимое) состояние переписки: есть хотя бы одно
реально ушедшее (`last_outbound_status == 'sent'`) исходящее сообщение, ответа
нет, и с момента отправки прошло не меньше `sla_business_days` рабочих дней
(понедельник-пятница, без календаря праздников — открытая граница) для этой
заявки. По умолчанию — 2 рабочих дня; настраивается per-заявка через
`request_followup_settings` (`GET/POST /api/requests/{id}/followup-settings`).
Вычисляется в `MailRepository.annotate_needs_followup`, вызывается из
`list_threads` — та же логика места, что и клиентский `threadResponseStatus`
(`frontend-v2/src/lib/derive.ts`), только на backend, чтобы не дублировать
расчёт бизнес-дней на фронте. **`needs_followup` не заменяет и не трогает**
`threadResponseStatus`/`waiting` (транспортный статус) и `conversation_status`
(`mail_thread_status`, §13 `docs/ui/MESSAGES_SCREEN_SPEC.md`) — это третий,
независимый, чисто производный признак.

Для переписки с `needs_followup=true` в Messages доступны действия
«Связаться» (открывает форму результата контакта: не дозвонился / контакт
подтверждён / уточнён новый email / связаться позже / поставщик не работает
с запросом — `POST /api/requests/{id}/suppliers/{supplier_id}/contact-result`,
`workspace_supplier_contact_events`, историчная запись с датой/пользователем/
результатом/комментарием) и «Напомнить» (создаёт обычную задачу через уже
существующий `MailRepository.create_task`, не отдельную сущность —
`POST /api/requests/{id}/suppliers/{supplier_id}/remind`).

### 7.2 Email-контакты: workspace-override + кросс-tenant consensus

Два независимых слоя, никогда не путать:

1. **Workspace-override** (`workspace_supplier_contact_overrides`) — если
   после звонка пользователь указывает новый email через результат
   «Связаться» (`new_email_provided`), новый адрес становится preferred
   **только для текущего workspace** и немедленно используется для этого
   workspace вперёд (AC-02). Append-only: предыдущее значение получает
   `superseded_at`, а не удаляется (AC-07 на уровне workspace). **Не
   перезаписывает** ничего в `global_suppliers`/`canonical_companies`.
2. **Кросс-tenant consensus** (`canonical_company_contacts` +
   `canonical_company_contact_signals` + `canonical_company_contact_promotions`,
   расширение слоя `canonical_companies` из §1.4/DECISION-022, ключ —
   `canonical_company_id` по ИНН, **не** `global_suppliers.id`, который
   per-workspace и не может агрегировать между разными аккаунтами
   SupplyDesk — см. DECISION-024). Каждый email компании хранится с
   назначением (`rfq`/`sales`/`tender`/`general`/`personal`/`unknown`) и
   статусом (`preferred`/`secondary`/`deprecated`/`candidate`). Сигналы:
   - `workspace_confirmed` (слабый) — любое подтверждение через «Связаться»
     (`contact_confirmed` или `new_email_provided`);
   - `inbound_reply` (сильный) — реальный входящий ответ с этого адреса;
   - `official_source` (сильный) — зарезервировано для будущего
     подтверждения из официального источника компании (сейчас не
     заполняется автоматически ни одним пайплайном);
   - `hard_bounce`/`soft_bounce` — из `mail/bounce.py::classify_bounce`,
     синхронизируются pull-based (см. ниже), никогда не удаляют контакт.

   Кандидат становится `preferred`, только если один и тот же нормализованный
   email подтверждён **минимум 3 независимыми workspace**
   (`COUNT(DISTINCT workspace_id)` по позитивным сигналам — несколько
   пользователей одного workspace всегда считаются одним подтверждением,
   AC-04) **и** есть хотя бы один сильный сигнал (AC-05/AC-06). Предыдущий
   `preferred`-контакт при этом переводится в `secondary`, но не удаляется
   (AC-07). Hard bounce снижает доверие: если у него нет более свежего
   позитивного сигнала, он блокирует новое продвижение в `preferred`, а уже
   `preferred`-контакт с необработанным hard bounce переводится в
   `secondary` — но **никогда не удаляется** одним bounce (AC-08). Soft
   bounce только логируется и не меняет статус контакта.

   Ни один API-ответ не содержит `workspace_id` контрибьютора — только
   `confirming_workspace_count` (число) и `has_strong_signal` (булево),
   доказано `tests/test_contact_intelligence.py::
   test_ac09_explanation_never_exposes_which_workspaces_confirmed` (AC-09).

**Синхронизация сигналов — pull-based, не встроена в живой inbound-pipeline.**
`_sync_workspace_contact_signals` пересчитывает сигналы этого workspace из
его собственных `mail_messages` при чтении карточки поставщика
(`list_email_contacts_for_global_supplier`, вызывается из
`global_supplier_detail`) или при записи результата контакта. Осознанная
граница: реальный inbound-приём остаётся нетронутым (высокий риск,
`MAIL_CHANGE`), а не push-хуком в критический путь. Значит, консенсус
обновляется не мгновенно при получении письма, а при следующем обращении к
карточке этого поставщика любым пользователем затронутого workspace —
задокументированный компромисс, не скрытый баг.

### 7.3 Единый resolver адресата: preview и реальная отправка (2026-09-16)

`mail/contact_intelligence.py::resolve_contact_priority` — единственная,
side-effect-free (никаких записей, включая аудит-лог) реализация приоритета
выбора адреса. Вызывается из **двух** мест на одной и той же относительной
точке пайплайна (сразу после того, как `_select_contact_for_request` выбрал
конкретный уже известный контакт карточки компании):

1. `mail/service.py::preflight_bulk` — предпросмотр кампании до отправки;
   результат сразу перезаписывает `item["email"]` перед рендером письма и
   проверкой признаков доставляемости, поэтому `recipient_results`/
   `previews` в предпросмотре показывают именно тот адрес, который получит
   реальная отправка.
2. `mail/repository.py::resolve_supplier_for_send` — окончательное
   определение адреса перед вставкой в `mail_messages` (используется и для
   новой заявки/кампании, и для ручного/повторного письма).

Ни preview, ни сам resolver никогда не хранят и не кэшируют результат
между вызовами — при каждом обращении оба места читают текущее состояние
БД заново, поэтому если данные изменились между показом предпросмотра и
фактической отправкой (например, appeared новый hard bounce), отправка
разрешает адрес заново, а не использует то, что видел предпросмотр раньше.
Само протоколирование понижения приоритета (`audit_events`,
`action='mail.contact_resolution.demoted'`) вынесено из resolver-а наружу —
им управляет **только** `resolve_supplier_for_send`, в момент реального
коммита к отправке; предпросмотр никогда не пишет в журнал аудита, сколько
бы раз его ни дёрнули (доказано
`tests/test_contact_resolution_send_path.py::
test_hard_bounced_preferred_is_not_shown_as_final_in_preview_when_a_safer_alternative_exists`).

Приоритет, применяемый в обоих местах:

1. workspace-preferred override (`workspace_supplier_contact_overrides`),
   если он не имеет необработанного hard bounce;
2. иначе кросс-tenant `preferred`-контакт (§7.2), если и он не имеет
   необработанного hard bounce;
3. иначе — прежнее поведение без изменений: адрес, уже сохранённый в
   `suppliers.email` (тот, что передал вызывающий код).

Если и предпочтительный workspace-контакт, и глобальный preferred имеют
hard bounce, отправка не блокируется и не падает — используется прежний
fallback-адрес (пункт 3). Существующая защита от опечатки/чужого адреса
(`stored_email != email → ValueError` в `resolve_supplier_for_send`) не
ослаблена: адрес, который не совпадает ни с уже сохранённым в
`suppliers.email`, ни с результатом `resolve_contact_priority`, по-прежнему
отклоняется.

`_select_contact_for_request` (выбор между несколькими уже известными
контактами карточки компании, ротация неиспользованных адресов, проверка
«уже ответил»/«уже писали в этой заявке») не изменена — апгрейд происходит
только в момент финального связывания уже выбранного контакта с
`suppliers.id`-строкой — один раз в preview, один раз в реальной отправке,
оба раза через один и тот же вызов `resolve_contact_priority`. Доказано
`tests/test_contact_resolution_send_path.py` (14 тестов): workspace
preferred побеждает и в preview, и при отправке; глобальный preferred
используется при отсутствии override, тоже в обоих местах; workspace
preferred побеждает глобальный; hard bounce не выбирается слепо ни в
preview, ни при отправке при наличии безопасной альтернативы (и preview
при этом не пишет в аудит-лог — только реальная отправка); при отсутствии
альтернативы используется прежний fallback, а не блокировка; новый
получатель без сохранённого `supplier_id` не затронут; другой workspace
той же компании не видит чужой override — ни в preview, ни при отправке;
прямой вызов resolver-а, preview и реальная отправка при неизменном
состоянии данных возвращают один и тот же адрес; два разных исходных
supplier-контакта, которые после resolution сходятся в один final email,
корректно блокируются как дубликат (§7.4). Плюс полный существующий
`test_mail_pacing.py`/`test_mail_deliverability.py`/
`test_mail_status_semantics.py` без регрессий.

### 7.4 duplicate_recipient и unique_domains считаются по final recipient (2026-09-16)

До этого исправления `preflight_bulk` считал `duplicate_recipient` и
`unique_domains`/`many_recipients_same_domain` **до** выбора контакта
(`_select_contact_for_request`) и до `resolve_contact_priority` — то есть по
исходным, ещё не разрешённым адресам. Если два разных поставщика заявки
после применения приоритета (workspace preferred/global preferred)
сходились в один и тот же реальный email, старая проверка дублей это не
ловила: система могла бы молча поставить в очередь два отдельных письма
на один и тот же почтовый ящик.

Исправлено разделением `preflight_bulk` на два прохода без дублирования
логики выбора адреса:

1. **Проход 1** — для каждого элемента вызывается уже существующий
   `_select_contact_for_request`, и если он выбрал конкретный контакт —
   тот же самый `resolve_contact_priority`, что и раньше (никакой отдельной
   копии). Результат (выбранный контакт + его final email) сохраняется, но
   пока не используется ни для каких проверок.
2. Только после того как final email известен **для каждого** элемента,
   считаются `duplicate_recipient` и `unique_domains`/
   `many_recipients_same_domain` — по final email, а не по исходному.
3. **Проход 2** — та же самая логика построения `recipient_results`,
   `reasons`, `flags`, рендера письма, что была раньше, просто читает уже
   готовые результаты прохода 1 вместо повторного вызова
   `_select_contact_for_request`/`resolve_contact_priority` (каждый
   вызывается ровно один раз на элемент, как и до этого исправления).

Элемент, для которого `_select_contact_for_request` вообще не выбрал
контакт (неоднозначная идентичность, уже отвечено и т.п.), никогда не
становится письмом — для него, как и раньше, используется исходный
запрошенный адрес; resolution для таких элементов не выполнялся ни до, ни
после этого исправления.

Реальная отправка (`queue_bulk`) защищена автоматически, без отдельного
исправления: для новой (не повторной) операции она всегда вызывает
`preflight_bulk` внутри себя и поднимает `DeliverabilityPreflightError` при
`status="BLOCK"` — раз `preflight_bulk` теперь корректно ловит
post-resolution дубликат, `queue_bulk` никогда до него не доходит. Отдельная
ранняя проверка в `queue_bulk` (`keys = {supplier["email"] ...}`) осталась
как есть — это самостоятельная, более узкая проверка «не прислал ли вызывающий
код буквально одинаковую строку дважды», не претендующая на семантику
final recipient, и её сохранение не ослабляет защиту.

Проверены и намеренно **не изменены** остальные recipient-зависимые места
(они либо не зависят от email/домена получателя, либо уже были корректно
рассчитаны после выбора контакта, либо являются самостоятельной более узкой
проверкой):

- `deliverability_flags` (suppressed/hard_bounce/unresolved_delivery_unknown) —
  уже вызывался после выбора и (со второго раунда) после resolution;
- `is_blacklisted`/`is_suppressed` — про идентичность поставщика/адреса
  блокировки, не про то, какой из нескольких контактов выбран для отправки;
- `subject_quality`/`body_quality`/`provider_policy_warning` — не зависят
  от конкретного email/домена получателя;
- `queue_bulk`'s ранняя `keys = {...}` проверка — самостоятельная и более
  узкая, описана выше.

Доказано `tests/test_contact_resolution_send_path.py::
test_two_suppliers_converging_to_the_same_final_email_are_blocked_as_duplicates`
(preview блокирует, реальная отправка поднимает
`DeliverabilityPreflightError`, ни одно сообщение не создаётся) и
`test_unique_domains_counted_by_final_recipient_not_original` (два разных
исходных домена, один final-домен → `unique_domains == 1`).

**Что не реализовано (честно):** `official_source`-подтверждения не
заполняются никаким пайплайном автоматически. Домен-статистика и проверка
дублей в `preflight_bulk` (`unique_domains`, `duplicate_recipient`)
по-прежнему считаются по исходным/сохранённым адресам, а не по
апгрейженным — если бы два разных поставщика этой заявки после апгрейда
совпали на один и тот же итоговый адрес, существующая проверка дублей это
не поймает (узкий, не встречавшийся на практике край; отдельная задача,
не расширяю эту без явного запроса). См. `ai/DEFERRED_FINDINGS.md`.
