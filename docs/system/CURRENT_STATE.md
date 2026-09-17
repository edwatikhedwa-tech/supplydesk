---
document_id: DOC-SYSTEM-CURRENT-STATE-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Текущее состояние — таблица статусов по функциям

Статусы (системные значения оставлены на английском, с русским пояснением):

| Статус | Значение |
|---|---|
| `IMPLEMENTED` | Реализовано и подтверждено (есть тест или живое доказательство) |
| `IMPLEMENTED / NOT VERIFIED` | Код есть, но нет ни теста, ни живого доказательства |
| `PARTIAL` | Реализовано частично — не все случаи покрыты |
| `BROKEN` | Реализовано, но работает некорректно |
| `MOCK` | Заглушка — выглядит как рабочая функция, но ничего реально не делает |
| `NOT_IMPLEMENTED` | Функции нет вообще |
| `UNKNOWN` | Недостаточно данных, чтобы дать оценку |

`IMPLEMENTED` никогда не означает «без единого бага» — это значит, что описанное поведение
существует и у него есть подтверждение.

Это **новый документ**, созданный этим аудитом, отдельно от `ai/CURRENT_STATE.md` (живой трекер
состояния сессии, обновляется непрерывно) и `docs/CURRENT_STATE.md` (в корне `docs/`, помечен
как `HISTORICAL`, заморожен 30.08.2026). При расхождениях доверять этому файлу для состояния на
17.09.2026, а `ai/` — для всего, что произошло позже.

## Авторизация

| Функция | Статус | Доказательство |
|---|---|---|
| Вход по email+паролю | IMPLEMENTED | Один заранее заведённый пользователь (`APP_USER_EMAIL`/`APP_USER_PASSWORD`), PBKDF2-SHA256, 240 тыс. итераций — `mail/auth.py`, `backend/http_auth.py:32` |
| Вход через Яндекс OAuth | IMPLEMENTED | PKCE-схема, `backend/http_auth.py:142` |
| Вход через Google / Mail.ru OAuth | NOT_IMPLEMENTED | `frontend-v2/src/pages/Login.tsx:49-53` — кнопки честно помечены `enabled: false` и подписаны «Скоро» прямо в интерфейсе, а не скрытая заглушка |
| Управление сессией | IMPLEMENTED | Скользящее продление, cookie `HttpOnly`/`SameSite=Lax` |
| Защита CSRF | IMPLEMENTED | Проверяется на каждом изменяющем маршруте |
| Изоляция рабочих пространств (workspace) | IMPLEMENTED | `tests/test_supplier_workspace_isolation.py`; `global_supplier_detail` проверяет пару `(workspace_id, id)` |
| Регистрация нескольких организаций (multi-tenant) | NOT_IMPLEMENTED | Модель с одним заранее заведённым пользователем, не общая регистрация |

## Заявки

| Функция | Статус | Доказательство |
|---|---|---|
| CRUD заявок/позиций | IMPLEMENTED | `backend/http_requests.py`, `tests/test_dashboard.py` |
| Устойчивый, возобновляемый поиск (SERP → обогащение) | IMPLEMENTED | Очередь `request_search_jobs` с lease/claim, `tests/test_request_search_cursor_survives_step_release` |
| Дедлайн / SLA на follow-up по заявке | IMPLEMENTED | `request_followup_settings`, `docs/domain/SUPPLIER_MODEL.md` §7.1 (проверено, актуально) |
| Импорт поставщиков из CSV (предпросмотр/применение) | IMPLEMENTED | `backend/domain/supplier_import/`, `/api/supplier-import/{preview,apply}` |
| Расчёт стоимости доставки (Dellin, одна заявка/один поставщик) | IMPLEMENTED | `docs/product/CAPABILITY_CATALOG.md` CAP-LOGISTICS-001, проверено вживую 04.09.2026 на реальном API Dellin |
| Мониторинг/управление массовой рассылкой (пауза/возобновление/стоп) в новом интерфейсе | **NOT_IMPLEMENTED в frontend-v2** | Полноценная страница есть в `frontend/src/pages/CampaignPage.tsx` (старая версия), в v2 нет ни маршрута, ни аналога — реальная потеря функциональности, см. `GAP-001` |

## Поставщики

| Функция | Статус | Доказательство |
|---|---|---|
| Трёхуровневая идентичность (suppliers/global_suppliers/canonical_companies) | IMPLEMENTED | `docs/domain/SUPPLIER_MODEL.md` (проверено, актуально) |
| Дедупликация по ИНН внутри workspace | IMPLEMENTED | `global_suppliers UNIQUE(workspace_id, inn)` |
| Кросс-tenant кэш компаний | IMPLEMENTED | `canonical_companies`, `tests/test_canonical_companies_cache_reuse.py` |
| Идентичность поставщика по хосту (один сайт — одна запись) | **PARTIAL — подтверждён живой пробел** | Незаметно откатывается на использование email-адреса как ключа, если хост неизвестен на момент записи (`resolve_supplier_for_send`, `mail/repository.py:3551`) — 28 из 243 строк поставщиков в локальной базе несут этот признак (11.5%). См. `GAP-003`, `INV-SUP-002` |
| Обогащение через Checko (реестр + финансы) | IMPLEMENTED | `backend/integrations/registry/checko_client.py`; требует `CHECKO_KEY` (на момент аудита на проде не настроен) |
| Служебный маршрут `force_enrich_all_suppliers` (принудительное обогащение всех поставщиков) | **ОТСУТСТВУЕТ В ЭТОЙ ВЕТКЕ** | Существует только на ветке `state/current-20260917-2119` (снапшот этой сессии), не влит в `experiment/frontend-v2-greenfield-20260905`. См. `GAP-002` |
| Ручной ввод ИНН + защита от автоматической перезаписи | IMPLEMENTED | `tests/test_manual_inn_is_visible_and_wins_over_later_auto_candidate` |

## Сообщения / Почта

| Функция | Статус | Доказательство |
|---|---|---|
| Привязка входящего письма к переписке (по заголовкам, затем по теме+email) | IMPLEMENTED | `mail/repository.py:2638-2660` |
| Папка непривязанных писем (никогда не теряются молча) | IMPLEMENTED | `mail_inbox_messages`, подтверждено: нигде нет пользовательского удаления писем/переписок |
| Вложения — исходящие (при составлении письма) | IMPLEMENTED | Ограничения по размеру соблюдаются, хранится как BLOB |
| Вложения — входящие, отображаются в переписке | **PARTIAL** | Разбираются и сохраняются (`mail_attachments`), но `frontend-v2/src/pages/Messages.tsx` никогда не отображает и не даёт скачать их для уже отправленных или полученных писем — реальная возможность backend без интерфейса, нигде ранее не задокументированная как ограничение. `GAP-004` |
| Санитизация HTML (allowlist через nh3/Ammonia) | IMPLEMENTED | `mail/content.py::sanitize_email_html`, соответствует `docs/ui/MESSAGES_SCREEN_SPEC.md` §9 |
| Ссылки в письме кликабельны при отображении | **IMPLEMENTED / NOT VERIFIED** | Санитайзер принудительно ставит `target="_blank"` и безопасный `rel`, но нет ни одного браузерного/Playwright-теста, доказывающего, что результат реально кликабелен — предположение, не доказательство |
| Inline-картинки (CID) | IMPLEMENTED | Преобразуются в `data:`-ссылки при разборе письма; любой оставшийся `cid:`-адрес дополнительно вырезается при отображении |
| Учёт прочитанных/непрочитанных | IMPLEMENTED | Прочтение — побочный эффект открытия переписки (добавляется строка в `mail_message_reads`); пути «пометить непрочитанным» нет |
| Производный признак `needs_followup` («требует follow-up») | IMPLEMENTED | Подтверждено: полностью соответствует `docs/domain/SUPPLIER_MODEL.md` §7.1 |
| Физическое удаление письма/переписки | NOT_IMPLEMENTED (так и задумано) | Во всём репозитории есть только один DELETE-запрос к этим таблицам (офлайн-скрипт `scripts/supplier_identity_audit.py`, без HTTP-маршрута) — соответствует заявленному правилу «меняется статус, а не удаляются данные» |
| Приоритизация контакта при отправке (workspace-override → кросс-tenant консенсус → запасной вариант) | IMPLEMENTED | `mail/contact_intelligence.py::resolve_contact_priority`, 14 тестов в `tests/test_contact_resolution_send_path.py` |

## AI-ассистент

| Функция | Статус | Доказательство |
|---|---|---|
| Реальный вызов LLM (не заглушка) | IMPLEMENTED | RouterAI, `backend/integrations/llm/routerai_client.py` |
| Контекст ограничен только поставщиками с реальной коммуникацией | IMPLEMENTED | Исправлено 10.09.2026 (`0d16945`), проверяется на сервере (`get_thread_owned`), подтверждено этим аудитом как всё ещё верное |
| Дневной лимит расходов | IMPLEMENTED | Таблица `ai_chat_usage`, по умолчанию 10₽/день, проверяется до вызова модели |
| Лимит по частоте запросов (в минуту/пакетами) | NOT_IMPLEMENTED | Есть только суммарный дневной лимит |
| Учёт размера/токенов контекста | **PARTIAL** | Только обрезка по числу символов (лимит 40 000 символов, грубая обрезка с конца); реального подсчёта токенов нет |

## Задачи / Календарь

| Функция | Статус | Доказательство |
|---|---|---|
| CRUD задач + завершение | IMPLEMENTED | Полный набор маршрутов, реальные таблицы |
| Напоминания о задачах — в интерфейсе (тост, вкладка открыта) | IMPLEMENTED | Опрос раз в 45 сек, `RemindersContext.tsx` |
| Напоминания о задачах — push-уведомление браузера (вкладка закрыта) | NOT_IMPLEMENTED | Нет Service Worker/Push API/серверного планировщика |
| Напоминания о задачах — email | **MOCK** (записывается, но никогда не отправляется) | Нет пути отправки нигде для канала `channel='email'`, хотя форма принимает и валидирует такой выбор |
| Напоминания о задачах — телефон | MOCK (прямо помечено в интерфейсе) | «Телефонный канал работает только как local mock: звонка не будет.» |
| Отображение календаря | IMPLEMENTED | `DashboardCalendar.tsx`, реальные данные задач, не тестовые |
| Полноэкранный `/calendar` | УДАЛЁН 17.09.2026 | Был мёртвым/недостижимым кодом после удаления пункта меню; удалён в этой сессии |

## Frontend

| Функция | Статус | Доказательство |
|---|---|---|
| `frontend-v2` — реально задеплоенный интерфейс | IMPLEMENTED (подтверждено) | `vercel.json` собирает только `frontend-v2` |
| `frontend` (старая версия) где-либо задеплоен | NOT_IMPLEMENTED | Ноль коммитов ~2 недели, явно исключён из сборки Vercel |
| Общие UI-примитивы: Button, Modal, Toast, состояния загрузки/пусто/ошибка | IMPLEMENTED, используются последовательно | См. `../frontend/UI_INVENTORY.md` |
| Общие UI-примитивы: Input, Checkbox, Card, Table, Tabs | **NOT_IMPLEMENTED как общие компоненты** — каждая страница делает свою версию | Основная причина эффекта «франкенштейна», см. `../frontend/UI_INVENTORY.md` |
| Браузерное/e2e/визуальное тестирование frontend-v2 | NOT_IMPLEMENTED | В старой версии есть Playwright+axe+Storybook+Applitools; ничего не перенесено в v2. CI-джоб `frontend_v2` запускает только lint+build, без реальных проверок в браузере |

## QA-инфраструктура

| Инструмент | frontend-v2 | frontend (старая версия) |
|---|---|---|
| TypeScript | ✅ | ✅ |
| Линтер | oxlint (не ESLint) | ESLint |
| Юнит-тесты | Vitest + Testing Library (всего 4 файла) | — |
| E2E/браузерные тесты | ❌ нет | ✅ Playwright |
| Проверка доступности (accessibility) | ❌ нет | ✅ axe-core |
| Визуальное регрессионное тестирование | ❌ нет | ✅ Applitools Eyes |
| Каталог компонентов | ❌ нет | ✅ Storybook |
| Backend-тесты | unittest, ~90 файлов, `tests/run-tests.ps1` | (общее) |
| CI | `.github/workflows/ci.yml` — джоб `frontend_v2` только lint+build | джобы `frontend`/`browser_smoke`/`browser_full` реально гоняют Playwright |
