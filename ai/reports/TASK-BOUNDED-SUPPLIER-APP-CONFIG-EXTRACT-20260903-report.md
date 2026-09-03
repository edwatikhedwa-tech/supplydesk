# TASK-BOUNDED-SUPPLIER-APP-CONFIG-EXTRACT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`PASS_1_COMPLETE` — [CONFIRMED] `Config`, env-парсинг (`_bounded_int_env`,
`_bounded_float_env`, `_flag_env`), `load_dotenv`, `yandex_provider_factory`
вынесены в `backend/app_config.py`; `FRONTEND_DIST`, `_looks_like_source_path`
и `load_fixture_data` — в `backend/http_static.py`. `supplier_app.py`
уменьшился на ~215 строк за счёт удаления дублирующегося кода; все
перенесённые имена остаются импортируемыми из `supplier_app` (ре-экспорт),
поведение не изменилось.

## Контекст

Первый шаг owner-направленной программы: превратить `supplier_app.py`
(2542 строки) в тонкую composition-точку и разбить `mail/repository.py`
(8928 строк) по обязанностям — по итогам двух read-only structural-аудитов
(агенты Explore), запущенных ранее в этой сессии. `supplier_discovery_v2`
владелец явно оставил изолированным пилотом надолго — не трогается.
`FINDING-009` явно исключён из scope (нужен отдельный owner-approved
security task).

## Что сделано

1. Создан `backend/app_config.py`: `Config` (dataclass + `from_env`),
   `_bounded_int_env`, `_bounded_float_env`, `_flag_env`, `load_dotenv`,
   `SESSION_LIFETIME_MIN_SECONDS`/`MAX_SECONDS`, `yandex_provider_factory`.
   `ROOT` пересчитан относительно нового расположения файла
   (`Path(__file__).resolve().parents[1]`).
2. Создан `backend/http_static.py`: `FRONTEND_DIST`, `_SOURCE_SUFFIXES`,
   `_looks_like_source_path`, `load_fixture_data`. Аналогично, `ROOT`
   пересчитан локально.
3. `supplier_app.py`: старые определения удалены, добавлены импорты из
   двух новых модулей. `ROOT`, `_strict_optional_bool`, `EnrichmentOutcome`
   оставлены на месте — используются в коде, который остаётся в файле на
   этом шаге (route-хендлеры, enrichment pipeline).
4. Импорт `ProviderError` (`mail.types`) возвращён явно — он используется
   в 8 местах `SupplierHandler`, не только в перенесённом
   `yandex_provider_factory`; при первой правке импорта это едва не было
   упущено, поймано сверкой grep по каждому удаляемому имени перед
   удалением определений.
5. `CLAUDE.md`: добавлен пункт про новые модули в Project layout.

## Побочная находка и исправление (не в scope продукта)

При проверке `import nh3` (транзитивная зависимость `mail.content`) упал с
`DLL load failed` — воспроизведено независимо от любых правок этой задачи
(`python -c "import nh3"` в чистом виде тоже падал). Диагностика:
файл `nh3.pyd` физически на месте и не менялся; ни один процесс Python не
держал его открытым; `MsMpEng` (Windows Defender) активен в системе —
тот же паттерн, что уже официально задокументирован в проекте для
`Backend Full` CI (`ci: exclude workspace/temp from Windows Defender
scanning`). Подождал минуту с повторными попытками — не самоисправилось.
С явного разрешения владельца ("полный карт-бланш") выполнено
`python -m pip install --force-reinstall --no-deps nh3` — переустановлена
локальная копия (0.3.6 → 0.3.7, оба варианта укладываются в
`requirements.txt: nh3>=0.3,<0.4`, правка зависимостей не потребовалась).
Импорт восстановлен, полный набор тестов подтверждён зелёным. Системные
настройки/антивирус не менялись — только переустановлен один Python-пакет
через штатный `pip`.

## Проверено

| Проверка | Результат |
|---|---|
| `ast.parse()` всех изменённых файлов | [CONFIRMED] синтаксис корректен |
| Офлайн импорт: `supplier_app`, `api.index.handler`, `backend.app_config`, `backend.http_static` изолированно | [CONFIRMED] все имена (`Config`, `load_dotenv`, `load_fixture_data`, `yandex_provider_factory`, `FRONTEND_DIST`) резолвятся из `supplier_app` |
| `python -m unittest tests.test_dashboard tests.test_outgoing_safety tests.test_mail_integrity tests.test_mail_integration` | [CONFIRMED] `OK (skipped=1)` — эти 4 файла явно обращаются к `supplier_app.Config`/`load_fixture_data`/`yandex_provider_factory` |
| `python scripts/run_test_suite.py` (полный набор) | [CONFIRMED] `tests=497; failures=0; errors=9 (те же pre-existing pwsh-gap); skipped=1` |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — 4 файла продукта
(`supplier_app.py`, 2 новых модуля, `CLAUDE.md`) + state-файлы. Точечный,
механический перенос без изменения поведения.

## Не проверено

- NOT VERIFIED: реальный запуск сервера (`supplier_app.py` как процесс) —
  не требовался для этого шага, офлайн-импорт и regression-тесты
  покрывают контракт.
- NOT VERIFIED: Vercel build/deploy.

## Следующий шаг

Pass 2 (по тому же owner-направлению): извлечь enrichment pipeline
(~1500 строк, `SupplierApp._enrich_one` и связанные методы) в
`backend/domain/supplier_enrichment/` — аудит оценил это как
low-medium risk, самый большой прирост. Затем — routes/auth mixins
(medium risk, требует сначала перевода `do_GET`/`do_POST` с
линейной if/elif-цепочки на таблицу маршрутов). Затем —
`mail/repository.py` по тому же принципу (сначала DB-compat shim,
затем mixins по обязанностям).
