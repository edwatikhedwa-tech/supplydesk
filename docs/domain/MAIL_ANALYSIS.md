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
- Модели: `MAIL_ANALYSIS_CHEAP_MODEL` (по умолчанию `DEFAULT_MODEL` из `llm_fallback.py`), `MAIL_ANALYSIS_STRONG_MODEL` (не задана → эскалации нет, сразу manual review). Стоимость — фактическая из ответа шлюза (`provider_reported`, поле `usage.cost`); если его нет — оценка по каталогу цен (`catalog_estimate`).
- Downstream: `quote_received` закрывает открытые follow-up задачи «Связаться с поставщиком» этого поставщика в этой заявке; обработчик модель не вызывает.

## Изменения после benchmark на реальных вызовах (EDW-26, `docs/benchmarks/MAIL_ANALYSIS_BENCHMARK_20260919.md`)
- Схема ответа strict-совместимая (все поля обязательны, `additionalProperties: false`, валюта — enum); prompt задаёт валюту, ступени цены, SKU.
- Правила без AI: «во вложении» без цены, «цена/цену/цены», письма без thread с маркером отписки. Проверки: цена дословно в цитате, валюта видна в письме
  (если модель её опустила — берётся из цитаты, только если там ровно одна), диапазон цен и число-не-цена отклоняются, полнота (сумма рядом с валютой, которой нет
  в фактах → `price_mentioned_not_extracted` → strong, затем `incomplete_extraction` → ревью). «КП» без цены — тип `other`, не ошибка.
- Strong не вызывается, если письму не хватает информации (`letter_lacks_information` → ревью). `[SD-N]` без известного отправителя: заявка определена, поставщик — на ревью (`supplier_unconfirmed`).
- Ledger дополнительно хранит `cached_tokens`, `retries`, `endpoint`; стоимость — `provider_reported` из ответа шлюза (`usage.cost`).

## Не входит в slice 1
Подключение к live-sync (анализ запускается явно), LLM для неоднозначной привязки, обещания поставщика, вложения/OCR, логистика, история цен (Iteration 4), измерение на реальном ящике.

## Вложения (EDW-33, `mail/attachment_intelligence.py`)
Каскад: hash → парсер (xlsx/docx/pdf-слова) → локальный OCR → контрольная сумма qty×цена=сумма → vision только для недочитанных страниц (принимается при контрольной сумме и цифре, видимой в OCR) → ручное ревью. Привязка к позициям детерминированная (exact/analog/ambiguous/unmatched, при сомнении — ambiguous). Каждый факт с локатором. Результаты и границы: `docs/benchmarks/ATTACHMENT_INTELLIGENCE_BENCHMARK_20260919.md`. Не сделано: хранение в БД (EDW-35), кроссплатформенный OCR (EDW-34), реальные файлы (EDW-36).
