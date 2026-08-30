# Supplier Discovery v2 — изолированный пилот

## Цель

По позиции или ключу пользователя найти товарные предложения, отделить продавцов/производителей от buyer-заявок и вернуть только релевантные публичные контакты с URL-доказательствами.

## Жёсткая граница

Этот каталог не изменяет и не импортирует production-код парсера. В live-режиме существующий `serp_parser.py` запускается только как отдельный read-only subprocess, а все JSON/CSV/SQLite-файлы создаются внутри `supplier_discovery_v2/`. Production-БД, миграции, `.env`, `stop_domains.txt` и текущие extractors не используются для записи.

## Запуск

Из корня репозитория:

```powershell
python -m supplier_discovery_v2.run --plan --key "кабель ВВГнг 3х2.5"
python -m supplier_discovery_v2.run --dry-run --key "кабель ВВГнг 3х2.5"
python -m supplier_discovery_v2.run --live --key "кабель ВВГнг 3х2.5" --max-serp-queries 3 --max-direct-sites 8
```

`--live` явно разрешает ограниченный read-only сетевой прогон. Используются публичные GET-запросы и существующий XMLRiver-парсер. Логины, формы заказа, отправка сообщений, CAPTCHA/rate-limit обход и раскрытие закрытых контактов не выполняются.

Результаты: `out/latest_report.json`, `out/qualified_contacts.csv`, `out/latest_summary.md`, `data/discovery.sqlite3`. В репозитории секреты не сохраняются.

## Проверки

```powershell
python -m unittest discover -s .\supplier_discovery_v2\tests -p "test*.py" -v
python .\supplier_discovery_v2\immutability_check.py --write-baseline
python .\supplier_discovery_v2\immutability_check.py
```

Baseline содержит только SHA-256 защищённых файлов, не содержимое секретов. После live-прогона повторить проверку неизменности.

## Текущее покрытие источников

- XMLRiver через неизменённый subprocess текущего parser-а — discovery и SERP landing URLs.
- Flagma — поиск и публичные карточки товаров.
- ProductCenter, PromPortal, OptomTovar, All.biz, Postavshikov.net — только ограниченные GET-адаптеры; детали считаются кандидатами только при наличии реальной карточки и публичного seller-контакта.
- Прямой сайт продавца — landing page и ограниченный обход страниц contacts/контакты/реквизиты.

Источники, где нужен POST или закрытая авторизация, сознательно отложены до отдельной проверки официального API и условий использования.
