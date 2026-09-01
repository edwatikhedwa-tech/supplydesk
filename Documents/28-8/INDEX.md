# Документация SupplyDesk — исторический каталог 28 августа 2026

Это единый каталог документации проекта. Все ссылки ниже относительны к этой
папке, поэтому каталог можно открыть или перенести как целое.

> **HISTORICAL — NOT CURRENT.** Этот каталог хранит архитектуру, аудиты и
> датированные snapshots. Единственный источник текущего состояния —
> [`../../ai/CURRENT_STATE.md`](../../ai/CURRENT_STATE.md). Правила обновления
> находятся в [`../../docs/DOCUMENTATION_POLICY.md`](../../docs/DOCUMENTATION_POLICY.md).

## С чего начать

1. [`../../ai/CURRENT_STATE.md`](../../ai/CURRENT_STATE.md) — актуальное
   подтверждённое состояние, runtime, база и ограничения.
2. [`../../docs/DOCUMENTATION_POLICY.md`](../../docs/DOCUMENTATION_POLICY.md) —
   обязательные правила актуализации документации.
3. [PROJECT_STATUS.md](PROJECT_STATUS.md) — исторический паспорт среза 28 августа.
4. [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md) — подробная
   архитектура, API, жизненные циклы и датированная история решений.
5. [DESIGN.md](DESIGN.md) — правила визуального языка.

## Подсистемы

- [mail-integration.md](mail-integration.md) — Yandex OAuth, SMTP, IMAP и
  почтовая очередь.
- [enrichment-and-cache.md](enrichment-and-cache.md) — поиск, извлечение
  контактов, ИНН, Checko и кэширование.
- [suppliers-screen.md](suppliers-screen.md) — поставщики, GlobalSupplier,
  ручной ИНН и чёрный список.

## Аудиты и приёмка

- [dashboard-recommendations.md](dashboard-recommendations.md)
- [requests-page-audit.md](requests-page-audit.md)
- [messages-and-mail-audit.md](messages-and-mail-audit.md)
- [FRONTEND_QA.md](FRONTEND_QA.md)

Аудиты привязаны к датам и фиксируют состояние на момент проверки. Если они
расходятся с текущими фактами, приоритет имеют код/первичный runtime и
[`../../ai/CURRENT_STATE.md`](../../ai/CURRENT_STATE.md), а не этот каталог.
