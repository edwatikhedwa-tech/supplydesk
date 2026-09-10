---
document_id: DOC-DOMAIN-SUPPLIER-MODEL-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-11
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
`mail_threads`/`mail_messages`, `thread_notes`, `tasks`, `logistics_quotes`
и т.д.) — они никогда не попадают в `canonical_companies` и не становятся
видимыми другому workspace. Изоляция проверена тестами
`test_directory_never_leaks_another_workspace` (per-workspace слой) и
`test_a_different_workspace_can_reuse_a_company_resolved_elsewhere` +
`test_write_through_carries_no_tenant_specific_data` (кросс-tenant слой —
что расшаривается, и что не расшаривается).
