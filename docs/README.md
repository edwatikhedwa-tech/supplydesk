---
document_id: DOCS-README-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Документация SupplyDesk

Это главная точка входа в документацию продукта. SupplyDesk — приватный репозиторий: backend на
Python, serverless-обёртка API, frontend, почтовые/поставщические сценарии на SQLite/Postgres
(подробности — в manifest проекта). Живое, постоянно обновляемое состояние сессии хранится в
[`ai/CURRENT_STATE.md`](../ai/CURRENT_STATE.md) — не в этом файле.

## 1. Что такое SupplyDesk

B2B-инструмент для отдела снабжения: покупатель создаёт **заявку** с позициями (что нужно
купить), система ищет в интернете подходящих поставщиков, обогащает их данными из реестра
юрлиц и финансовой отчётности (через Checko), рассылает им письма с запросом предложения и
отслеживает ответы как переписку, привязанную к заявке. Отдельный AI-ассистент отвечает на
вопросы по этой переписке. Есть задачи/напоминания и небольшой калькулятор стоимости доставки
(Dellin). Полное описание — [`product/PRODUCT_MODEL.md`](product/PRODUCT_MODEL.md).

## 2. Как устроен продукт

- **Backend:** `supplier_app.py` (маршрутизация запросов) + `mail/` (основная бизнес-логика и
  хранение данных) + `backend/` (более новые, лучше разделённые доменные сервисы).
- **Frontend:** `frontend-v2` — это единственная реально работающая (задеплоенная) версия
  интерфейса. `frontend/` (без `-v2`) — старая версия, физически ещё лежит в репозитории, но не
  используется и не обновляется. Подробности — [`frontend/FRONTEND_ARCHITECTURE.md`](frontend/FRONTEND_ARCHITECTURE.md).
- **База данных:** на проде — Postgres, локально у разработчика — SQLite. Полная схема —
  [`technical/DATABASE_MAP.md`](technical/DATABASE_MAP.md).
- Общая карта модулей и их ответственности — [`system/SYSTEM_MAP.md`](system/SYSTEM_MAP.md).

## 3. Что сейчас работает, что частично, что сломано

Полная честная таблица по каждой функции — [`system/CURRENT_STATE.md`](system/CURRENT_STATE.md).
Кратко:

| Статус | Значение | Примеры |
|---|---|---|
| IMPLEMENTED (реализовано) | Функция работает и это подтверждено | Заявки, поставщики (базовая идентичность), переписка, AI-ассистент, задачи |
| PARTIAL (реализовано частично) | Код есть, но охватывает не все случаи | Кросс-tenant кэш поставщиков; совместимость с Postgres |
| BROKEN / нарушен инвариант (см. ниже) | Функция существует, но работает некорректно | Дедупликация поставщиков — см. `GAP-003` |
| MOCK (заглушка) | Выглядит как рабочая функция, но ничего реально не делает | Email- и телефон-напоминания задач |
| NOT_IMPLEMENTED (не реализовано) | Функции нет вообще | Push-уведомления при закрытой вкладке; управление рассылкой в новом интерфейсе |

Все найденные проблемы, с приоритетом — [`system/KNOWN_GAPS.md`](system/KNOWN_GAPS.md).

## 4. Где что искать

| Тема | Документ |
|---|---|
| Общая карта системы, модулей и их ответственности | [`system/SYSTEM_MAP.md`](system/SYSTEM_MAP.md) |
| Что работает / частично / сломано (полная таблица) | [`system/CURRENT_STATE.md`](system/CURRENT_STATE.md) |
| Все найденные проблемы с приоритетом | [`system/KNOWN_GAPS.md`](system/KNOWN_GAPS.md) |
| **Почта / переписка** — как связываются письма с заявками, статусы, вложения | [`product/MESSAGES.md`](product/MESSAGES.md) |
| **Поставщики** — как устроена идентичность, обогащение, известная проблема дублирования | [`product/SUPPLIERS.md`](product/SUPPLIERS.md), [`domain/SUPPLIER_MODEL.md`](domain/SUPPLIER_MODEL.md) |
| **AI-ассистент** — как формируется контекст, что реально работает | [`product/AI_ASSISTANT.md`](product/AI_ASSISTANT.md) |
| Пользовательские сценарии (что видит и делает покупатель) | [`product/USER_FLOWS.md`](product/USER_FLOWS.md) |
| Frontend: какой реально используется, почему интерфейс выглядит несогласованным | [`frontend/FRONTEND_ARCHITECTURE.md`](frontend/FRONTEND_ARCHITECTURE.md), [`frontend/UI_INVENTORY.md`](frontend/UI_INVENTORY.md) |
| Полный список API-маршрутов | [`technical/API_MAP.md`](technical/API_MAP.md) |
| Полная схема базы данных | [`technical/DATABASE_MAP.md`](technical/DATABASE_MAP.md) |
| Внешние интеграции (Checko, RouterAI, Dellin и др.) | [`technical/INTEGRATIONS.md`](technical/INTEGRATIONS.md) |
| **Требования** к продукту (по каждой функции, с ID) | [`spec/requirements.yaml`](spec/requirements.yaml), `requirements/` (старый, более грубый каталог) |
| Бизнес-правила, которые нельзя нарушать (инварианты) | [`spec/PRODUCT_INVARIANTS.md`](spec/PRODUCT_INVARIANTS.md) |
| **Тесты** — тест-кейсы и стратегия проверки | [`testing/TEST_CASES.md`](testing/TEST_CASES.md), [`testing/TEST_STRATEGY.md`](testing/TEST_STRATEGY.md) |
| Как запустить проверку (validation) | См. раздел 5 ниже |
| Архитектурные решения (ADR) | [`decisions/`](decisions/README.md) |

## 5. Как запустить проверку системы (validation)

- **Backend-тесты** (Python, `unittest`): `python -m unittest discover -s tests -p "test_*.py"`
  из корня репозитория, либо через `tests/run-tests.ps1`.
- **Frontend-проверка** (`frontend-v2`): `npm run lint` (проверка кода) и `npm run build`
  (проверка сборки) из папки `frontend-v2`. Реального браузерного/визуального тестирования для
  `frontend-v2` пока нет — подробности и рекомендации в
  [`testing/TEST_STRATEGY.md`](testing/TEST_STRATEGY.md) (раздел про пробел в QA для
  frontend-v2).
- **Полная матрица «требование → реализация → тест → результат»**, где ничего не засчитано как
  пройденное без доказательства — [`validation/TRACEABILITY_MATRIX.md`](validation/TRACEABILITY_MATRIX.md).

## Устаревшие документы — не доверять вслепую

`architecture/COMPONENT_MAP.md` и `product/CAPABILITY_CATALOG.md` (оба помечены как `status:
CURRENT`, датированы 1–4 сентября) были написаны **до появления `frontend-v2`** и описывают
старый `frontend/` так, будто это и есть текущий интерфейс. Они не удалены (сохраняют
историческую ценность), но для вопроса «что сейчас реально работает» им доверять нельзя — см.
[`system/KNOWN_GAPS.md`](system/KNOWN_GAPS.md) (`GAP-011`).

## Дерево документации, созданное аудитом 2026-09-17

Ниже — полный список новых разделов, добавленных полным аудитом системы и продукта. Они
проверены напрямую по коду, а не переписаны из старых предположений. Начать удобнее всего с
[`system/SYSTEM_MAP.md`](system/SYSTEM_MAP.md).

- [`system/`](system/SYSTEM_MAP.md) — карта системы, таблица статусов
  ([`CURRENT_STATE.md`](system/CURRENT_STATE.md)), все найденные проблемы
  ([`KNOWN_GAPS.md`](system/KNOWN_GAPS.md)).
- [`product/PRODUCT_MODEL.md`](product/PRODUCT_MODEL.md),
  [`USER_FLOWS.md`](product/USER_FLOWS.md), [`MESSAGES.md`](product/MESSAGES.md),
  [`SUPPLIERS.md`](product/SUPPLIERS.md), [`AI_ASSISTANT.md`](product/AI_ASSISTANT.md) —
  поведение продукта, проверенное по коду, а не по внешнему виду интерфейса.
- [`frontend/FRONTEND_ARCHITECTURE.md`](frontend/FRONTEND_ARCHITECTURE.md),
  [`UI_INVENTORY.md`](frontend/UI_INVENTORY.md),
  [`FRONTEND_V1_V2_COMPARISON.md`](frontend/FRONTEND_V1_V2_COMPARISON.md) — какой frontend
  реально работает, и обоснованная (не абстрактная) причина визуальной несогласованности.
- [`technical/API_MAP.md`](technical/API_MAP.md), [`DATABASE_MAP.md`](technical/DATABASE_MAP.md),
  [`DATA_FLOW.md`](technical/DATA_FLOW.md), [`INTEGRATIONS.md`](technical/INTEGRATIONS.md).
- [`spec/PRODUCT_INVARIANTS.md`](spec/PRODUCT_INVARIANTS.md),
  [`spec/requirements.yaml`](spec/requirements.yaml) — устойчивые правила и статус по каждому
  требованию отдельно от более грубого старого каталога `requirements/requirements.yaml`.
- [`testing/TEST_CASES.md`](testing/TEST_CASES.md) (продуктовые тест-кейсы добавлены к уже
  существовавшим диагностическим), [`testing/TEST_STRATEGY.md`](testing/TEST_STRATEGY.md)
  (дополнена разделом о пробеле в QA для `frontend-v2`).
- [`validation/TRACEABILITY_MATRIX.md`](validation/TRACEABILITY_MATRIX.md) — цепочка
  «требование → реализация → тест → доказательство → результат»; без доказательства статус
  всегда «не проверено», никогда не «пройдено».
- [`decisions/`](decisions/README.md) — пока пусто намеренно: этот аудит только фиксировал
  находки, решений по ним ещё не принималось.

## Прочие разделы (существовали до этого аудита)

- [`product/`](product/README.md) — точка входа продуктовой документации.
- [`requirements/`](requirements/README.md) — бизнес- и функциональные требования (более старый,
  грубый формат).
- [`architecture/`](architecture/README.md) — архитектурная документация. **См. предупреждение
  об устаревании выше, прежде чем доверять строке `COMP-FRONTEND`.**
- [`data/`](data/README.md) — заглушка про модель данных (без реального содержания схемы; см.
  [`technical/DATABASE_MAP.md`](technical/DATABASE_MAP.md)).
- [`api/`](api/README.md) — контракты API (узкий охват; полный список — в
  [`technical/API_MAP.md`](technical/API_MAP.md)).
- [`testing/`](testing/README.md) — стратегия тестирования.
- [`operations/`](operations/README.md) — runbook'и и эксплуатационные процедуры.
- [`domain/`](domain/SUPPLIER_MODEL.md) — модель идентичности/обогащения поставщиков (актуальна,
  читать перед любой задачей, связанной с поставщиками).
- [`ui/`](ui/MESSAGES_SCREEN_SPEC.md) — спецификация экрана «Сообщения» (актуальна).
- [`DOCUMENTATION_POLICY.md`](DOCUMENTATION_POLICY.md) — жизненный цикл документов, владение,
  критерии готовности.

## Текущий контроль

Перед принятием решений по реализации читать [`../AGENTS.md`](../AGENTS.md),
[`../PROJECT_MANIFEST.yaml`](../PROJECT_MANIFEST.yaml) и
[`../ai/CURRENT_STATE.md`](../ai/CURRENT_STATE.md).
