# TASK-MAILRU-FINAL-CONTINUATION-20260831 — final report

## Цель

Завершить отправку по заявке `1059` через подключённый Mail.ru account `23`
только для адресов, которые свежая проверка подтверждает как строго не
затронутые предыдущими попытками, и доказать отсутствие повторной отправки на
один адрес.

## Ограничения

- Не отправлять через Yandex.
- Не повторять принятые, отклонённые или неопределённые доставки.
- Не создавать jobs прямой записью в SQLite.
- Не обходить pacing, provider rejection, cooldown или breaker.
- После завершения вернуть исходящую отправку в OFF.

## Выполнение

- Fresh dry-run: `safe=true`, `eligible_untouched=61`.
- Создано `13` bounded continuation plans: двенадцать по пять targets и один
  target; новые jobs `175`–`235`.
- Transport выполнялся штатной очередью по одному job.
- Итог: `60 sent`, `1 failed`, `0 delivery_unknown`.
- Все `60` принятых попыток имеют SMTP evidence `post_data / 250`.
- Job `182` получил постоянный `rcpt_to / 550` invalid-recipient rejection до
  irreversible stage; автоматического повтора не было.
- Job `176` сначала получил transient connection failure до DATA и был
  безопасно повторён. Вторая попытка завершилась `post_data / 250`.

## Проверка снимка интерфейса

Снимок с бейджами `Ждём ответа`, `Ожидает отправки`, `Отправлено · 3`
соответствует карточке компании «Печи ТУТ». Репозиторий объединяет в неё четыре
разных supplier rows, четыре сайта и четыре уникальных email.

Хронология состояния:

- один контакт был ранее принят Yandex;
- два Mail.ru contacts были приняты jobs `177` и `178`;
- job `176` после transient connection failure оставался queued;
- поэтому карточка честно показывала три accepted contacts и один queued
  contact, а `Ждём ответа` означал отсутствие ответа хотя бы на одно принятое
  письмо;
- позже job `176` получил `post_data / 250`, и текущая карточка показывает
  `Отправлено · 4` без queued badge.

Это не три отправки на один email. Read-only проверка request `1059` показала
`125` sent rows и `125` distinct sent recipients; duplicate sent recipients
`0`. Recipient groups with more than one accepted attempt: `0`.

## Остаточная очередь

В локальной базе остаются три historical Yandex jobs со status `queued`:

- jobs `49` и `54` имеют disputed transient attempts с
  `irreversible_reached=1` и не могут безопасно повторяться;
- job `71` имеет zero attempts, но его exact recipient уже подтверждён как
  Mail.ru accepted через durable reconciled event; повтор запрещён.

Свежий continuation dry-run поэтому корректно возвращает `safe=true`,
`eligible_untouched=0`, `would_create=0`. Эти строки требуют отдельного
локального status reconciliation для чистого UI, но не новой отправки.

## Проверено

- SQLite `PRAGMA integrity_check`: `ok`.
- Active send reservations: `0`.
- Durable outgoing: `0`; server process uses `MAIL_OUTGOING_DISABLED=1`.
- HTTP root: `200`; protected API without session: `401`; unknown API: `404`.
- Authenticated browser render at `1600x900`: current company card has
  `4 email · 4 сайта`, `Ждём ответа`, `Отправлено · 4`, no queued badge.
- Final continuation dry-run: no eligible untouched targets.
- Consistent pre-send backup integrity: `ok` at
  `mail-data/backups/supplier.sqlite3.pre-mailru-final-20260831-215700.bak`.

## Не проверено

- Фактическое попадание каждого письма во входящие поставщика: SMTP `250`
  доказывает принятие почтовым сервером, но не чтение и не отсутствие spam
  filtering.
- Provider-side inbox state всех получателей.
- PostgreSQL и production deployment.

## Риски и следующий этап

Смешанные бейджи корректны на уровне данных, но без слова «контакт» выглядят
как повтор одного письма. Отдельная UI-итерация может показывать
`3 контакта отправлено` и `1 контакт в очереди`. Отдельная data-only
reconciliation-итерация должна перевести три historical Yandex jobs в честные
terminal statuses по существующим доказательствам без запуска SMTP.

## Откат

Отправленные письма нельзя отозвать. Для локальной базы до этапа отправки
сохранён проверенный backup, указанный выше. Текущий closeout меняет только
документацию проекта и не меняет mail data.
