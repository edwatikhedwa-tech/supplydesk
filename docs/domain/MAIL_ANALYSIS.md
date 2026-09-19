---
document_id: DOC-DOMAIN-MAIL-ANALYSIS-001
status: CURRENT
canonical: true
owner: project-control
updated_at: 2026-09-19
---

# Анализ входящей почты (Mail Intelligence Core, Iteration 2)

Спецификация: `docs/Solutions/SupplyDesk_AI_Mail_Intelligence_Documentation_Pack_v1` (Architecture §3–8, QA MAIL-*, Cost COST-*).
Код: `mail/message_analysis.py` (`MessageAnalysisMixin`), миграция `057_mail_analysis_core.sql`, тесты `tests/test_mail_analysis_core.py`.

## Конвейер одного письма

```
письмо → idempotency (workspace, письмо, content_hash, analysis_version) → есть: 0 вызовов модели
       → точные правила: bounce / bulk-отправитель / нет сигнала для извлечения / привязка треда / [SD-N] + известный отправитель / кандидаты
       → бюджет → cheap-модель → проверка → (невалидно) один strong → иначе manual review
       → факты с provenance + ledger каждого шага + событие → обработчик события без модели
```

| Что | Где |
|---|---|
| Результат анализа письма (тип, привязка, статус, причина ревью, версия, hash) | `mail_analyses` (уникальный ключ = ключ идемпотентности) |
| Каждый шаг решения (в т.ч. «правила», стоимость 0): причина, модель/провайдер, токены, стоимость, источник стоимости, задержка, версия, hash | `mail_ai_runs` |
| Факты: позиция/цена/валюта/НДС/срок + дословная цитата и смещения в тексте | `mail_facts` (`proposed` → `superseded`; сам факт заявку не меняет) |
| Downstream-события (`quote_received`) | `mail_analysis_events` (одно на анализ и тип) |

## Правила
- Точные правила раньше ИИ; модель не привязывает письмо к заявке (в slice 1 ИИ только извлекает факты).
- Факт сохраняется, только если его цитата дословно есть в письме; SKU, которого нет в тексте, отбрасывается; цена > 0; валюта из списка.
- Повторный анализ неизменного письма той же версии = 0 вызовов. Изменился текст (без цитируемой истории) → новый анализ. Иная версия → используется прежний результат, пока не запрошен `reprocess=True` (новый versioned анализ, старый сохраняется, его факты `superseded`).
- Ошибка провайдера: письмо не блокируется, анализ `pending_retry`, до 3 попыток, затем manual review. Дневной бюджет `MAIL_ANALYSIS_DAILY_BUDGET_RUB` (по умолчанию 20 ₽ на workspace) проверяется до вызова.
- Модели: `MAIL_ANALYSIS_CHEAP_MODEL` (по умолчанию `DEFAULT_MODEL` из `llm_fallback.py`), `MAIL_ANALYSIS_STRONG_MODEL` (не задана → эскалации нет, сразу manual review). Стоимость — по ценам каталога RouterAI (`catalog_estimate`); фактическая цена провайдера пока недоступна.
- Downstream: `quote_received` закрывает открытые follow-up задачи «Связаться с поставщиком» этого поставщика в этой заявке; обработчик модель не вызывает.

## Не входит в slice 1
Подключение к live-sync (анализ запускается явно), LLM для неоднозначной привязки, обещания поставщика, вложения/OCR, логистика, история цен (Iteration 4), измерение на реальном ящике.
