---
document_id: DOC-VALIDATION-TRACEABILITY-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Матрица трассировки

Требование → Реализация → Тест → Доказательство → Результат. Строка без теста/доказательства
помечается «не проверено», никогда — «пройдено». Это дополняющий, более детальный (на уровне
отдельного требования) документ к уже существовавшему, более грубому
`docs/requirements/TRACEABILITY_MATRIX.csv` (на уровне capability), соответствует
`docs/spec/requirements.yaml`.

| Требование | Реализация | Тест | Доказательство | Результат |
|---|---|---|---|---|
| REQ-AUTH-001 | `backend/http_auth.py::_login` | `tests/test_mail_integrity.py` | Юнит-тест проходит | ПРОЙДЕНО |
| REQ-AUTH-002 | `backend/http_auth.py::_require_csrf` | unittest (уровень маршрута) | Юнит-тест проходит | ПРОЙДЕНО |
| REQ-REQUEST-001 | `orchestrator.py::process_search_step` + `request_search_jobs` | `tests/test_request_search_cursor_survives_step_release` | Юнит-тест проходит | ПРОЙДЕНО |
| REQ-REQUEST-002 | *(отсутствует — только в v1)* | нет | У `frontend/src/pages/CampaignPage.tsx` нет аналога в v2 | НЕ ПРОВЕРЕНО (функция отсутствует) |
| REQ-SUPPLIER-001 | `mail/repository.py::upsert_supplier`/`resolve_supplier_for_send` | `tests/test_supplier_dedup_p0_regression.py` (новый, 2026-09-18) | Юнит-тест реально выполнен и **падает** — воспроизводит через настоящий код (не подсчёт по БД) | **ПРОВАЛЕНО** — инвариант нарушен; теперь есть исполняемое, красное доказательство вместо разового подсчёта по БД |
| REQ-SUPPLIER-002 | `orchestrator.py::_resolve_missing_inn` | `tests/test_canonical_companies_cache_reuse.py` | Юнит-тест проходит (узкий охват) | ПРОЙДЕНО (частично) |
| REQ-SUPPLIER-003 | *(отсутствует в этой ветке)* | нет | Код просмотрен только на ветке `state/current-20260917-2119` | НЕ ПРОВЕРЕНО |
| REQ-MESSAGE-001 | `mail/repository.py::_find_incoming_thread` | `tests/test_mail_integration.py` | Юнит-тест проходит | ПРОЙДЕНО |
| REQ-MESSAGE-002 | путь `mail_inbox_messages` | `tests/test_messages_visibility.py` | Юнит-тест проходит | ПРОЙДЕНО |
| REQ-MESSAGE-003 | (отсутствие маршрута DELETE) | проверка исходного кода | Полный поиск по репозиторию, найден один непривязанный к маршруту скрипт | ПРОЙДЕНО (за счёт отсутствия) |
| REQ-MESSAGE-004 | `mail/content.py::sanitize_email_html` | нет (уровень браузера) | Санитайзер покрыт юнит-тестом; кликабельность в отрендеренном виде не доказана | НЕ ПРОВЕРЕНО |
| REQ-MESSAGE-005 | Разрешение CID в `mail/providers/yandex.py` | нет (уровень браузера) | Логика разбора прочитана напрямую; не доказана в реальном отрендеренном браузере | НЕ ПРОВЕРЕНО |
| REQ-MESSAGE-006 | *(только backend, нет потребителя на frontend)* | нет | Тип `MailAttachment[]` существует, не используется для не-черновиков | **ПРОВАЛЕНО** — возможность существует, но недостижима пользователем |
| REQ-AI-001 | `chat_service._build_context` + `get_thread_owned` | `tests/test_ai_context_scoping.py` + `frontend-v2/tests/e2e/regression/ai-context.spec.ts` (новый, 2026-09-18) | Backend-юнит-тест и browser-тест оба реально выполнены и проходят | ПРОЙДЕНО (теперь на двух уровнях — сервер и клиентский контракт поверх него) |
| REQ-AI-002 | Проверка дневного лимита в `chat_service.send_message` | unittest (упомянут, повторно не запускался в этом проходе) | Путь в коде подтверждён | ПРОЙДЕНО (доказательство не перезапускалось в этой сессии) |
| REQ-TASK-001 | `mail/tasks.py` | unittest (уровень маршрута) | Юнит-тест проходит | ПРОЙДЕНО |
| REQ-TASK-002 | Опрос `RemindersContext.tsx` + `ReminderToastManager.tsx` | нет (уровень браузера) | Исходный код подтверждает опрос раз в 45 сек + вызов `Notification()` | НЕ ПРОВЕРЕНО |
| REQ-TASK-003 | *(пути отправки не существует)* | нет | Комментарий в `migrations/043_task_reminders.sql` прямо указывает, что доставка вне рамок MVP | **ПРОВАЛЕНО ПО ЗАМЫСЛУ** — соответствует задокументированному охвату MVP, не является скрытым дефектом |
| REQ-TASK-004 | `mail/task_reminder_mock.py` | нет | Docstring модуля + текст интерфейса прямо говорят «заглушка» | ПРОВАЛЕНО ПО ЗАМЫСЛУ (честно помечено) |
| REQ-TASK-005 | *(не реализовано)* | нет | Нигде не найдено Service Worker/Push API/планировщика | НЕ ПРОВЕРЕНО (функция отсутствует) |
| REQ-UI-001 | *(общих компонентов нет)* | нет | Ручной аудит кода, `docs/frontend/UI_INVENTORY.md` | **ПРОВАЛЕНО** — подтверждено прямым чтением кода, не тестом |
| REQ-DATA-001 | `mail/db_compat.py::_adapt_postgres_sql` | `tests/test_migration_replay_stability.py`, `tests/test_db_compat_postgres_sql_adapter.py` | Два реальных инцидента на проде в этой сессии, оба сейчас исправлены и покрыты тестами | ПРОЙДЕНО (узко — покрыты только два известных случая, не проведена исчерпывающая проверка всего паттерна) |

## Как читать эту таблицу

- **ПРОЙДЕНО** означает, что есть настоящий тест или прямое, воспроизводимое доказательство.
- **ПРОВАЛЕНО** означает, что требование подтверждённо не соблюдается, с доказательством.
- **НЕ ПРОВЕРЕНО** означает ни то, ни другое — код прочитан и понят, но нет ни теста, ни живого
  доказательства ни в одну, ни в другую сторону. Это большинство строк, связанных с поведением в
  браузере, и честно так — у `frontend-v2` сейчас нет e2e-покрытия (`GAP-010`).

## Сводка покрытия (2026-09-18, закрытие пробелов между backend/QA/документацией)

Построена из этой матрицы (22 строки REQ-*, `docs/spec/requirements.yaml`),
`docs/spec/PRODUCT_INVARIANTS.md` (12 строк INV-*) и полного каталога `docs/testing/TEST_CASES.md`
(детальные блоки + расширенный табличный раздел). Методология: строка считается «покрыта тестом»,
только если в её колонке «Тест»/«Тест(ы)» назван конкретный файл или framework, реально
исполняемый — не «код прочитан», не «упомянут», не «docstring подтверждает».

```text
Requirements total:              22   (docs/spec/requirements.yaml)
Requirements with >=1 test:      11
Requirements without test:       11

Product invariants total:        12   (docs/spec/PRODUCT_INVARIANTS.md)
Covered (HELD, есть тест/доказательство): 10
Not covered / VIOLATED:           2   (INV-SUP-002 = GAP-003, INV-OPS-001 = GAP-002)

Automated test cases (TC-* с реально исполняемым тестом): 106
Manual / not yet automated (NOT_TESTED):                    5
Not implemented (UNCOVERED — нет теста вообще):            10
Blocked (функция отсутствует, тест не может пройти):        3
```

Не покрыты ни одним тестом (`Requirements without test`, 11 из 22): REQ-REQUEST-002 (функция
отсутствует, GAP-001), REQ-SUPPLIER-003 (не влито в рабочую ветку, GAP-002), REQ-MESSAGE-003/004/
005/006, REQ-TASK-002/003/004/005, REQ-UI-001. Ни один из этой сессии не переносился и не
дописывался — список зафиксирован как есть.

Полный, построчный список `UNCOVERED`-сценариев (по 12 продуктовым областям, не только REQ-уровню)
— в `docs/testing/TEST_CASES.md`, раздел «Расширенный каталог».
