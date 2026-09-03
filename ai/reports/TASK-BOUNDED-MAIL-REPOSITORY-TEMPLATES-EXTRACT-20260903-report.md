# TASK-BOUNDED-MAIL-REPOSITORY-TEMPLATES-EXTRACT-20260903

`DELIVERY_MODE: PUBLISH`

## Итог

`PASS_3_COMPLETE` (mail/repository.py split) — [CONFIRMED]
`get_mail_template`/`save_mail_template` вынесены в
`mail/mail_templates.py` как `MailTemplatesMixin`. `class
MailRepository(AuthAccountsMixin, MailTemplatesMixin)`.
`mail/repository.py`: `8297` → `8234` строк. Небольшой, но безопасный шаг
(по свежей карте — второй по нулевой связности кластер после
auth/accounts).

## Проверено

| Проверка | Результат |
|---|---|
| `ast.parse()` обоих файлов | [CONFIRMED] |
| `MailRepository.__mro__` | [CONFIRMED] `['MailRepository', 'AuthAccountsMixin', 'MailTemplatesMixin', 'object']` |
| `hasattr` на оба метода | [CONFIRMED] `True` |
| Офлайн импорт `mail.repository`, `supplier_app` | [CONFIRMED] |
| `python scripts/run_test_suite.py` | [CONFIRMED] `tests=497; failures=0; errors=9 (baseline); skipped=1` |

## Change Budget

`CHANGE_BUDGET_EXCEEDED: NO` — 3 файла продукта + state-файлы.

## Следующий шаг

Campaign creation (cluster 13) + campaign lifecycle (cluster 15) —
свежий аудит установил, что это один домен, искусственно разнесённый на
~1200 строк дистанции файлом; объединение в один `CampaignMixin` —
следующий разумный шаг. Самое рискованное (queue/campaign/inbox-reply
shared send-attempt infra) — оставлено на потом, per рекомендация
аудита о выделении `_SendAttemptInfraMixin`.
