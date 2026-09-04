---
document_id: REPORT-TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-03
---

# TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903 — отчёт

## Цель

MVP-калькулятор стоимости доставки для одной заявки и одного поставщика:
ручной ввод маршрута и параметров груза, расчёт через публичный калькулятор
Деловых Линий, сохранение результата. Без автооформления перевозки, без
сравнения нескольких перевозчиков, без оптимизатора закупки.

## AUDIT

Task Preflight: workspace guard — `PASS`; ветка
`integration/current-architecture-governance-20260903`; рабочее дерево на
входе чистое; `ai/ACTIVE_TASK.md` — `IDLE`, конфликтов нет. Изучены:
`backend/integrations/registry/dadata_client.py` и
`backend/integrations/registry/checko_client.py` (стиль клиента, on-demand
конструктор, чтение ключа из окружения), `mail/mail_templates.py`
(zero-coupling mixin-паттерн для расширения `MailRepository`),
`backend/http_requests.py` (`_request_route`/`_request_action`, точный
паттерн веток `.../inn`, `.../rating`, `.../irrelevant`), `supplier_app.py`
(`update_supplier_inn` — как HTTP-слой на лету создаёт внешнего клиента и
переживает отсутствие ключа), `frontend/src/components/SupplierPanel.tsx`
(визуальный стиль блока «ИНН компании»), `migrations/*.sql` (миграции —
идемпотентные `CREATE TABLE IF NOT EXISTS`, подхватываются автоматически по
`migrations/*.sql` glob, отдельной регистрации не требуют).

## Проверка официальной документации Деловых Линий

`https://dev.dellin.ru/api/calculation/calculator/` и
`.../api/terminals/search/` отдают HTTP 401 / блокировку
«Доступ к ресурсу ограничен» на прямой запрос (бот-защита сайта; обход
технических мер защиты запрещён политикой и не предпринимался). Официальная
документация была открыта через публичный архив Wayback Machine
(`web.archive.org`, снимок `20240221125337`, страница отмечена как
«Обновлено 10.01.2024») — то есть тот же самый официальный контент
dev.dellin.ru, полученный через легальный публичный архив, а не в обход
защиты самого сайта. Из документации подтверждены и использованы дословно:
адрес метода (`https://api.dellin.ru/v2/calculator.json`), обязательность
`appkey`, полная структура `request.delivery`/`request.cargo` (`DeliveryType`,
`DerivalArrival`, `Cargo`), структура ответа (`data.price`, `data.derival`,
`data.arrival`, `data.<type>`, `data.packages`, `data.insurance`,
`data.orderDates`). Поля не придуманы по памяти. Страница «Ошибки методов
API» отдельно не открывалась — код ошибок из тела ответа извлекается
best-effort (см. `_extract_error_message` в `dellin_client.py`), без
претензии на точное соответствие недокументированной здесь схеме ошибок.

## DESIGN DECISION

- **Только `calculator.json`, без `request_terminals.json`.** MVP вводит
  маршрут вручную одной строкой на сторону («город/терминал»). Калькулятор
  поддерживает это напрямую через `variant: "address"` +
  `address.search: "<свободный текст>"` (документировано: система сама
  разбирает текст города/адреса и возвращает разбор в `foundAddresses`).
  Поиск терминалов потребовал бы отдельного вызова и предварительного
  KLADR-кода города — лишняя интеграция для этой MVP-версии, сознательно не
  реализована.
- **Тип перевозки — `"auto"` фиксированно.** Форма MVP не даёт пользователю
  выбрать вид перевозки; интерцити-грузоперевозка — обычный кейс B2B-закупки.
- **`cargo.weight` (вес самого тяжёлого места) при `places > 1`** —
  документация требует это поле, но форма MVP не собирает вес по местам
  отдельно. Используется общий вес как консервативная (не занижающая
  стоимость) оценка; это явно закомментировано в
  `backend/domain/logistics/quote_service.py`.
- **`term_days`** считается как разница дней между `orderDates.pickup` и
  `orderDates.giveoutFromOspReceiver` (единственная пара дат в ответе,
  покрывающая весь путь от передачи груза до готовности на терминале
  получателя); при отсутствии любой из дат — `None`, а не выдуманное число.
- **`vat_included`** — в изученной части документации явного поля НДС нет;
  хранится и возвращается как `None` (не проверено), а не угадывается.
- **Таблица `logistics_quotes` без `workspace_id`.** Изоляция по
  workspace обеспечивается через JOIN c `requests.workspace_id` — тот же
  паттерн, что уже применён у `request_supplier_states`
  (per-request/per-supplier таблица без собственного `workspace_id`).
- **Кэш — `dict` в памяти процесса**, ключ — sha256 нормализованных входных
  данных; клиент Деловых Линий и кэш живут в одном
  `LogisticsQuoteService`-инстансе на `SupplierApp` (переживает отдельные
  HTTP-запросы, но не перезапуск процесса) — соответствует ограничению
  задачи «без Redis/очередей».
- Коммерческое разрешение на использование API Деловых Линий в платном
  SaaS — **NOT VERIFIED**, нигде в коде и комментариях не утверждается
  обратное.

## IMPLEMENT

Изменённые/новые файлы:
- `backend/integrations/logistics/dellin_client.py` — транспортный клиент:
  сборка запроса `appkey`+`delivery`+`cargo`, простой in-memory
  rate-limiter (45/мин, 1600/час, скользящее окно `collections.deque`),
  повтор только на 429/5xx (максимум 2 повтора с растущей паузой), 4xx —
  без повтора, типизированные исключения
  (`DellinRateLimitedError`/`DellinInvalidInputError`/`DellinProviderError`).
- `backend/domain/logistics/quote_service.py` — жёсткий гейт
  (`MissingRequiredFieldsError`, подкласс `ValueError` — подхватывается уже
  существующим generic-обработчиком в `do_POST`), хэш входных данных, кэш,
  сборка payload'ов, разбор ответа в `QuoteResult`
  (`carrier/price/currency/term_days/cost_breakdown/status/input_hash/
  calculated_at` + `message` для явного пользовательского текста).
- `mail/logistics_quotes.py` — `LogisticsQuotesMixin`
  (`save_logistics_quote`/`get_latest_logistics_quote`/
  `list_logistics_quotes_for_request`), по образцу `mail/mail_templates.py`.
  `mail/repository.py`: `class MailRepository(AuthAccountsMixin,
  MailTemplatesMixin, LogisticsQuotesMixin)`.
- `migrations/033_logistics_quotes.sql` — таблица `logistics_quotes` и
  индекс `(request_id, supplier_id)`, точно по списку полей из задачи.
  Миграция выполнена в рамках этой задачи по явному разрешению владельца.
- `backend/http_requests.py` — `GET`/`POST`
  `/api/requests/{id}/suppliers/{supplier_id}/logistics` внутри уже
  существующих `_request_route`/`_request_action`.
- `supplier_app.py` — `self.logistics_quote_service = LogisticsQuoteService()`
  в `SupplierApp.__init__` (один экземпляр на процесс).
- `frontend/src/lib/types.ts` — `LogisticsQuote`/`LogisticsQuoteStatus`/
  `LogisticsQuoteCostBreakdown` (поля в `snake_case`, как отдаёт API — этот
  же стиль уже используют все остальные типы в файле, а не camelCase).
- `frontend/src/lib/api.ts` — `calculateLogistics`/`getLogisticsQuote`.
- `frontend/src/components/SupplierPanel.tsx` — секция «Логистика» сразу
  после блока «ИНН компании», тот же визуальный паттерн (label/input/button
  стили скопированы из ИНН-блока). Кнопка «Рассчитать доставку» неактивна,
  пока не заполнены все обязательные поля (дублирует бэкендовый жёсткий
  гейт на клиенте).
- `tests/test_logistics_quote.py` — 11 тестов: жёсткий гейт, кэш по хэшу,
  unavailable ≠ 0 (contract-price/provider-error/rate-limited/invalid-input),
  4xx не повторяется, 429/5xx повторяется ограниченно и в итоге завершается
  типизированной ошибкой, успех после одного повтора, round-trip
  сохранения/чтения в реальной SQLite. Клиент Деловых Линий везде замокан —
  реальная сеть в тестах не используется.

## ACCEPTANCE

- Backend-тесты: `powershell -ExecutionPolicy Bypass -File .\tests\run-tests.ps1`
  → `tests=515, failures=0, errors=9, skipped=1`. `515 = 504` (зафиксированный
  ранее в `ai/CURRENT_STATE.md` baseline) `+ 11` новых тестов. `errors=9` —
  тот же самый ранее задокументированный `pwsh`-gap, не увеличился.
- Frontend: `npm run typecheck` — чисто; `npm run build` — успешно; `npm run
  lint` — `0 errors, 5 warnings` (без новых ошибок; предупреждение о
  зависимостях `useEffect` в `SupplierPanel.tsx` унаследовано от уже
  существовавшего в файле паттерна `[supplier?.id, onClose]`, подтверждено
  сравнением с `git show HEAD:...`, не внесено этой задачей).
- Ручная приёмка в реальном приложении (не только юнит-тесты): поднят
  безопасный `OFFLINE_TEST`-рантайм (`scripts/start_test_runtime.ps1`,
  порт `18042`, одноразовая SQLite, исходящая почта выключена, реальные
  провайдеры не настроены), собран актуальный `frontend/dist`. В браузере
  открыта заявка `#1043`, карточка поставщика — секция «Логистика»
  отрендерилась сразу после блока ИНН, кнопка «Рассчитать доставку»
  корректно неактивна до заполнения всех полей и активируется после. После
  заполнения (Москва → Ростов-на-Дону, 2 места, 120 кг, 1.5 м³,
  100×80×60 см) и нажатия кнопки: `POST .../logistics` → `200`, интерфейс
  показал явный текст «DELLIN API KEY не настроен — расчёт стоимости
  доставки недоступен.» — **не цену 0 ₽**. Строка сохранилась в
  одноразовой SQLite (`logistics_quotes`, `status='unavailable'`,
  `price=NULL`, `cargo_max_dims_cm='100x80x60'`). Повторное открытие той же
  карточки поставщика вызвало `GET .../logistics` → `200` и автоматически
  показало тот же сохранённый результат («Не удалось получить тариф у
  перевозчика.») без повторного расчёта.

## Что проверено

- Схема запроса/ответа калькулятора Деловых Линий — по официальной
  документации (через публичный архив, см. выше).
- Жёсткий гейт, кэш, retry-политика (429/5xx повторяются ограниченно, 4xx —
  нет), unavailable≠0 — юнит-тестами с замоканным клиентом.
- Полный HTTP-путь `POST`/`GET` `/api/requests/{id}/suppliers/{id}/logistics`
  через реальный `SupplierApp`/`MailRepository`/SQLite и реальный браузер
  (без реального ключа Деловых Линий — см. ниже).
- Персистентность (`save_logistics_quote`/`get_latest_logistics_quote`)
  реальной SQLite-БД (юнит-тест и ручная проверка).
- Официальный backend-suite и frontend typecheck/build/lint.

## Что НЕ проверено

- **Реальный вызов `api.dellin.ru` с настоящим `DELLIN_API_KEY`** —
  `NOT VERIFIED`. Ключа нет, сетевой доступ к `dev.dellin.ru`/`api.dellin.ru`
  из этой среды не подтверждён (сайт документации блокирует автоматические
  обращения; `api.dellin.ru` отдельно не проверялся и не должен вызываться
  без явного ключа и разрешения — задача прямо запрещает выполнение реальных
  внешних вызовов без такой проверки).
- **Коммерческое разрешение на использование API Деловых Линий в платном
  SaaS** — `NOT VERIFIED`, явно зафиксировано как таковое и не должно
  трактоваться иначе до отдельного подтверждения владельцем продукта.
- Точный формат ошибок метода (`Ошибки методов API`) — страница отдельно не
  открывалась; извлечение сообщения из тела ответа — best-effort, не
  гарантированно точное для всех кодов ошибок.

## Риски и ограничения

- Кэш и rate-limiter живут только в памяти процесса — перезапуск backend
  сбрасывает оба; при нескольких процессах (не текущая архитектура) лимит
  считался бы независимо в каждом.
- `address.search` как способ передачи маршрута зависит от качества
  распознавания текста самим Деловыми Линиями — при неоднозначном вводе
  результат может быть с расхождением (та же логика уже видна в
  `foundAddresses` документации).

## Изменения вне продуктового кода

`ai/CURRENT_STATE.md`, `ai/LAST_HANDOFF.md`, `ai/DECISIONS.md`,
`ai/CHANGELOG.md`, `ai/INTERACTION_LOG.md`, `ai/ACTIVE_TASK.md` — обновлены
по обычному протоколу CLOSE.

## VIBECODING POLICY

VibeCoding-квитанция — см. финальное сообщение сессии (эмитируется один раз
в финальном ответе, не в этом отчёте).
