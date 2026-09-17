---
document_id: CAPABILITY-CATALOG-001
status: CURRENT
canonical: false
owner: product-docs
updated_at: 2026-09-04
source_commit: 78484108ed010e152ab0e3e04d2490e8c4137d6c
---

# Каталог возможностей продукта

Это карта доказательств, а не список пожеланий к продукту. `CONFIRMED` означает, что в
репозитории есть реализация и названный тест или маршрут. `PARTIAL` означает, что код есть, но
доказательства из рантайма или сквозные доказательства неполны. `NOT VERIFIED` намеренно не
засчитывается как доставленная возможность.

| ID | Возможность | Статус | Доказательство | Диагностическое доказательство |
|---|---|---|---|---|
| CAP-AUTH-001 | Сессия, вход/выход и доступ в рамках рабочего пространства | CONFIRMED | Маршруты авторизации в `supplier_app.py`; `mail/auth.py`; `tests/test_mail_integrity.py` | DOC-004, DOC-005 |
| CAP-REQUEST-001 | Жизненный цикл заявки и позиции | CONFIRMED | Маршруты заявок в `supplier_app.py`; `mail/repository.py`; `tests/test_dashboard.py` | DOC-004, DOC-007 |
| CAP-SUPPLIER-001 | Список поставщиков, фильтры, группировка идентичности и чёрный список | CONFIRMED | Маршруты поставщиков в `supplier_app.py`; `tests/test_supplier_identity.py` | DOC-004, DOC-007 |
| CAP-DISCOVERY-001 | Офлайн/спланированный по запросам discovery и обогащение поставщиков | CONFIRMED | `supplier_discovery_v2/`; `tests/test_query_planner.py`; `tests/test_enrichment_pipeline.py` | DOC-004, DOC-007 |
| CAP-MESSAGE-001 | Переписка, исходящие и видимость сообщений | CONFIRMED | Почтовые маршруты в `supplier_app.py`; `tests/test_messages_visibility.py` | DOC-004, DOC-005 |
| CAP-INCOMING-001 | Входящая синхронизация, разбор, дедупликация и непривязанные сообщения | CONFIRMED | `mail/service.py`; `mail/content.py`; `tests/test_mail_integration.py` | DOC-004, DOC-005 |
| CAP-OUTGOING-001 | Очередь исходящих с gate провайдера и семантикой отправки | CONFIRMED | `mail/service.py`; `mail/queue.py`; `tests/test_outgoing_safety.py` | DOC-004, DOC-005 |
| CAP-RENDERING-001 | Санитизация и рендеринг содержимого HTML/plain/CID | CONFIRMED | `mail/content.py`; `frontend/tests/email-renderer-responsive.spec.ts` | DOC-004, DOC-006 |
| CAP-LINKING-001 | Привязка сообщения к заявке и поставщику | CONFIRMED | `mail/repository.py`; `supplier_app.py`; `tests/test_supplier_identity.py` | DOC-004, DOC-005 |
| CAP-THREADING-001 | Устойчивые почтовые переписки и заголовки ответа | CONFIRMED | `mail/repository.py`; `tests/test_mail_integration.py` | DOC-004, DOC-005 |
| CAP-DEDUP-001 | Защита получателя и идемпотентности | CONFIRMED | `mail/deliverability.py`; `tests/test_supplier_identity.py`; `tests/test_mail_integrity.py` | DOC-004, DOC-005 |
| CAP-PACING-001 | Дозирование, резервирование, задержки и бюджеты рассылок | CONFIRMED | `mail/pacing.py`; `tests/test_mail_pacing.py` | DOC-004, DOC-005 |
| CAP-DELIVERY-001 | Статус доставки и семантика неопределённости | CONFIRMED | `mail/deliverability.py`; `tests/test_mail_status_semantics.py` | DOC-004, DOC-005 |
| CAP-SUPPRESSION-001 | Обработка отказов доставки и подавления | CONFIRMED | `mail/bounce.py`; `tests/test_mail_status_semantics.py` | DOC-004, DOC-005 |
| CAP-CAMPAIGN-001 | Стадии рассылки, пауза/стоп и предпросмотр безопасного повтора | CONFIRMED | Маршруты рассылок в `supplier_app.py`; `tests/test_mail_deliverability.py` | DOC-004, DOC-005 |
| CAP-DATABASE-001 | Персистентность SQLite, миграции и проверки целостности | PARTIAL | `mail/repository.py`; `migrations/001..033`; в этом worktree отсутствует база данных рантайма | DOC-003 |
| CAP-LOGISTICS-001 | Ручной калькулятор стоимости доставки (одна заявка/один поставщик, Dellin) | CONFIRMED | `backend/integrations/logistics/dellin_client.py`; `backend/domain/logistics/quote_service.py`; `mail/logistics_quotes.py`; `tests/test_logistics_quote.py`; проверено вживую 04.09.2026 против `api.dellin.ru` (реальный `status: "success"`, ненулевая цена) | — |
| CAP-FRONTEND-001 | Оболочка frontend, продуктовые экраны и адаптивная приёмка | CONFIRMED | `frontend/src/`; `frontend/tests/`; унаследованное доказательство 8-проходной оболочки | DOC-006 |
| CAP-RUNTIME-001 | Блокировка канонического рантайма, происхождение и манифесты сессии | CONFIRMED | `mail/runtime.py`; `tests/test_canonical_runtime.py` | DOC-001, DOC-004 |
| CAP-DIAGNOSTIC-001 | Read-only диагностика окружения, контракта и безопасности | PARTIAL | `scripts/doctor.ps1` до этой задачи; артефакты V1 созданы здесь | DOC-001..DOC-010 |

## Границы доказательств

Каталог не заявляет о текущем здоровье провайдера, текущих строках базы данных, живой доставке
в почтовый ящик или паритете checkout'а с источником. Они остаются `NOT VERIFIED`, пока не
появится безопасное, авторизованное доказательство.
