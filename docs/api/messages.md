---
document_id: DOC-API-MESSAGES-001
status: CURRENT
canonical: false
owner: engineering
updated_at: 2026-09-04
source_commit: TASK-MESSAGES-WORKSPACE-REDESIGN-20260904
---

# API экрана «Сообщения»

Все маршруты требуют текущую сессию и CSRF-токен для `POST`. Запросы
ограничены рабочим пространством текущей сессии.

## `GET /api/correspondence`

Возвращает видимые переписки по заявкам. Каждый элемент сохраняет существующие
поля почты и дополнительно содержит:

```json
{
  "is_important": false,
  "priority": null
}
```

Метаданные принадлежат текущему пользователю. Для ручной связи без поставщика
возвращаются безопасные значения по умолчанию (`false` и `null`), потому что
такая запись не является обычным тредом поставщик↔заявка.

## `GET /api/mail/queue/messages`

Возвращает очередь исходящих писем с теми же полями метаданных. Транспортные
статусы (`queued`, `sending`, `sent`, `failed`, `delivery_unknown`) не меняются
этой функцией.

## `POST /api/correspondence/metadata`

Меняет один или оба независимых поля конкретного существующего треда:

```json
{
  "request_id": 1059,
  "supplier_id": 42,
  "important": true,
  "priority": 1
}
```

`important` принимает только `true` или `false`; `priority` — `1`, `2`, `3`
или `null` для очистки. Поле можно не передавать, если меняется только второе.
Ответ возвращает сохранённые `is_important` и `priority`. Несуществующий или
чужой тред отклоняется, поэтому drag-and-drop не может создать связь с
неверным поставщиком.

## Существующие unmatched-маршруты

`GET /api/mail/inbox/preview`, `GET /api/mail/inbox`,
`GET /api/mail/inbox/{id}/suggestions`, `POST /api/mail/inbox/manual-link` и
`POST /api/mail/inbox/manual-unlink` остаются источником истины для workflow
непривязанных писем. Drag-and-drop вызывает их, а не создаёт отдельную модель
сопоставления.
