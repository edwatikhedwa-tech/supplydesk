---
document_id: DOC-CANARY-EDW-40
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-19
---

# Canary Mail Intelligence — workspace 1 (EDW-40)

**Статус: реализовано, НЕ включено.** Включение — только по явному разрешению владельца (`enable --owner-approved`).
Ни тел реальных писем, ни адресов, ни credentials в репозитории и отчётах: только счётчики, стоимость и задержки.

## 1. Конфигурация (условия, при которых анализ вообще работает)
Все пять должны выполняться одновременно, иначе AI-обработка выключена:
1. `MAIL_INTELLIGENCE_ON_SYNC=1` в окружении — **главный рубильник, но сам по себе ничего не включает**.
2. workspace входит в allowlist в коде: `ALLOWED_CANARY_WORKSPACES = {1}` (`mail/canary.py`); включить другой workspace нельзя ни командой, ни поддельной строкой в БД.
3. в таблице `mail_intelligence_canary` есть строка workspace с `enabled = 1`.
4. canary не остановлен (`stopped_at IS NULL`) и окно открыто (`started_at … ends_at`, максимум 14 дней).
5. письмо получено **не раньше** `started_at` (никакого исторического backfill).

Обработку выполняет только отдельный процесс `scripts/mail_intelligence_worker.py` (в sync и веб-процессе анализа нет). Формат: тело письма, text PDF, XLSX, DOCX. Скан PDF и изображения в canary **не читаются** (ни OCR, ни vision): сразу `manual_review` с причиной `scan_or_image_manual_review`.

Управление: `scripts/mail_intelligence_canary.py status | enable --owner-approved | disable | check | metrics | final`.

## 2. Allowlist
Только workspace 1 (`edwatik@yandex.ru` + `edwatik@mail.ru`). Все остальные workspace: выключено (тесты: попытка включить — ошибка; поддельная строка — не открывает gate; воркер не берёт их задачи).

## 3. Бюджет (жёсткий, без автоповышения)
- daily cap **1 ₽**, weekly cap **5 ₽** (скользящие 7 суток), значения хранятся в строке canary и автоматически не меняются.
- Проверка **перед каждым платным вызовом** с резервом 0,05 ₽: вызов, который мог бы достичь лимита, не делается (лимит физически не превышается). Повтор из сохранённого ответа бесплатен.
- Достижение лимита = **пауза** AI-задач (задача возвращается в очередь без списания попытки, откладывается на 30 минут, событие `budget_cap_reached`); приём и отправка почты не затрагиваются. Фактическое превышение лимита — стоп-инцидент.

## 4. Kill switch
- `disable`: `enabled = 0` — воркер не берёт задач, импорт не ставит новых; **приём/отправка почты и данные не затрагиваются**, миграций нет. Второй способ — снять `MAIL_INTELLIGENCE_ON_SYNC` или просто остановить процесс воркера.
- `enable` после паузы: окно **не сдвигается**; письма, пришедшие пока AI был выключен, ставятся в очередь одним ограниченным `since = started_at` сверщиком (без потерь, без дублей задач, без повторной оплаты — ключи идемпотентности).
- Стоп-инцидент снимается только явно: `enable --owner-approved --clear-stop`.
- Проверено тестом: `enable → process → disable → receive normally → enable again`: 2 письма = 2 платных вызова, 0 повторов, 0 дублей сообщений и фактов.

## 5. Мониторинг и немедленная остановка
Каждый цикл воркера (и `check`) вычисляет правила; любое срабатывание = **остановка canary** (`stopped_reason`, событие, дальше AI-обработки нет):
| правило | как проверяется |
|---|---|
| ложный request-scoped price fact | цена факта должна буквально присутствовать в его же источнике (цитата / строка файла) |
| факт привязан не к той заявке | заявка факта = заявка его письма (для писем без заявки — заявка анализа) |
| дубль сообщения | один Message-ID > 1 объекта (`mail_messages` + неразобранные) с начала canary |
| дубль факта | повтор (анализ, позиция); факты письма из >1 актуального анализа; повтор строки вложения |
| второй платный вызов для того же ключа | повтор в леджере со стоимостью > 0; дубль ключа запроса в кэше ответов |
| утечка secret/ciphertext | значения ключей окружения и префиксы шифртекста учётных данных ищутся в ошибках задач/вызовов/событиях и в лог-файлах; в находке секрет не повторяется |
| влияние на приём/отправку | ошибки задач про блокировку БД (`locked`, `deadlock`) за 24 ч |
| превышение budget cap | расход за день/неделю больше лимита |
| failed jobs > 5% за сутки | доля `failed` среди завершённых за 24 ч (минимальная выборка 5 задач) |
| backlog не уменьшается > 30 минут | замеры глубины очереди каждый цикл; окно ≥ 30 мин с глубиной ≥ начальной и без снижения |

Ежедневные метрики (`canary_metrics`, снимок в `mail_intelligence_metric_snapshots`, отчёт в `docs/canary/EDW-40/daily_<день>.json`): received messages; analyzed without AI; cheap AI; strong AI; manual review; failed/retried jobs; duplicate calls; queue depth; p50/p95 анализа; AI cost/day; AI cost/message; procurement-relevant messages; price facts; rejected facts; request matching; attachment processing.

## 6. Период и отчёт
Минимум 7 суток и 50 новых входящих писем, максимум 14 суток (окно закрывается само, `window_ended`). Если за 14 суток набрано меньше 50 писем, итог `final` помечается **limited sample**. Manual-review rate не является жёстким критерием, пока нет хотя бы 10 procurement-relevant писем (`manual_review_rate_is_acceptance_criterion`). S17 (EDW-39) ведётся отдельно: валидатор не ослабляется, strong-эскалация в canary не включена без измеренного результата.

## 7. Проверки перед включением
См. отчёт этапа: SQLite (все тесты), PostgreSQL 16 gate, `tests/test_canary.py` (27 тестов). Фактическое включение — отдельное решение владельца.

## 8. Как включить (для справки, НЕ выполнялось)
```
set MAIL_INTELLIGENCE_ON_SYNC=1            # только в окружении процессов приложения и воркера
python scripts/mail_intelligence_canary.py enable --workspace 1 --owner-approved
python scripts/mail_intelligence_worker.py --workspace 1 --interval 60
```
Отключить: `python scripts/mail_intelligence_canary.py disable --workspace 1`.
