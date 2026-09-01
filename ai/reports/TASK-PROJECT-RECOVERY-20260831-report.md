# TASK-PROJECT-RECOVERY-20260831

## Актуальное дополнение — 2026-08-31T15:01:57Z

Первоначальный recovery был заблокирован из-за состояния окружения на тот
момент. Повторная проверка подтвердила доступный системный Python `3.11.7` и
все импорты из `requirements.txt`. `supplier_app.py` запущен напрямую как PID
`23584` на `http://127.0.0.1:8000/` с `MAIL_OUTGOING_DISABLED=1` и оставлен
работающим после smoke-test.

Проверено фактически: `/` → `200`, `/api/auth/me` → `200`, неавторизованный
`/api/mail/inbox` → `401`, неизвестный API → `404`; read-only SQLite
`integrity_check=ok`, durable outgoing=`0`; `python -m unittest
tests.test_canonical_runtime -v` → `8/8 OK`.

`scripts/recover_supplydesk.ps1 -Apply` по-прежнему требует
`.venv\Scripts\python.exe`, поэтому это успешный запуск текущего сервера, но
не завершение воспроизводимого `.venv` bootstrap. SMTP authentication, SMTP
DATA, очередь, кампания, аккаунты, credentials и cleanup не затрагивались.

## Цель

Безопасно восстановить воспроизводимый запуск SupplyDesk, не ломая рабочую
логику, и подготовить документированный путь к продолжению Mail.ru рассылки
только для ранее не отправленных поставщиков.

## Доказанный результат

Штатный `supplier_app.py` сейчас не запускается в текущем execution environment.
Ранее подтверждённая причина — отсутствующий пакет `nh3`; установка
`requirements.txt` не прошла из-за блокировки внешнего TCP (`WinError 10013`).
Последняя попытка bootstrap остановилась ещё раньше: `py.exe` сообщил, что
установленного Python нет. Каталог `.venv` после попытки не создан.

Проверка локального wheel-кэша и альтернативных runtime также ничего не нашла.

Это не ошибка Mail.ru: в canonical SQLite есть исторические успешные Mail.ru
acceptance evidence с SMTP `250`.

## Что сделано

Добавлены три безопасных PowerShell-сценария:

- `scripts/doctor.ps1` — проверки Python, `.env`, canonical SQLite и порта
  `8000` без вывода секретов;
- `scripts/bootstrap_supplydesk.ps1` — создание `.venv` и установка только
  `requirements.txt` после явного `-Apply`;
- `scripts/recover_supplydesk.ps1` — запуск приложения только с
  `MAIL_OUTGOING_DISABLED=1`, с обязательным HTTP `200` smoke-test.

Каждый сценарий требует ровно один режим: `-Plan`, `-DryRun` или `-Apply`.
Recovery не включает исходящие и не создаёт письма.

## Проверено

- PowerShell parse всех трёх сценариев: `PASS`.
- Bootstrap `-Plan` и `-DryRun`: изменений нет.
- Recovery `-DryRun`: блокирует запуск без рабочего Python.
- Recovery `-Apply`: блокирует запуск до старта сервера без изменения проекта.
- Свежая повторная попытка bootstrap `-Apply`: остановлена до создания
  `.venv`, потому что `py.exe` сообщает об отсутствии установленного Python.
- Canonical SQLite: `integrity_check=ok`.
- Outgoing: `OFF`.
- Active reservations: `0`.
- Campaign state: не изменён.
- Новая отправка: `0`; SMTP DATA: `0`.

## Порядок восстановления в обычном Windows runtime

```powershell
cd "C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS"
& .\scripts\bootstrap_supplydesk.ps1 -Apply
& .\scripts\doctor.ps1 -DryRun
& .\scripts\recover_supplydesk.ps1 -Apply
```

После успешного HTTP smoke-test нужно отдельно выполнить dry-run Mail.ru
очереди, затем отправлять только неповторяющиеся ранее не отправленные адреса.
После каждой ошибки исходящие выключаются.

## Будущая очистка

Очистка проекта не выполнялась. Безопасный порядок:

1. создать Git checkpoint в writable Git environment;
2. составить inventory tracked/untracked файлов;
3. разделить исходники, state docs, runtime logs, backups, review artifacts и
   пользовательские материалы;
4. удалить или архивировать только явно согласованные категории;
5. выполнить тесты, `git diff --check` и HTTP smoke-test;
6. перепроверить SQLite, outgoing и Mail.ru queue.

Не использовать `git clean -fd`, `git reset --hard` и массовое удаление.

## Ограничения

Реальный сервер и Mail.ru continuation не запущены в текущем окружении. Для
этого требуется обычный Windows runtime с установленным Python, пакетами и
разрешённой сетью. Credentials и токены не выводились и не изменялись.
