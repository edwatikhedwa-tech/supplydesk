# Pilot benchmark — 2026-08-28

Это не статистическая оценка конверсии: выполнен один bounded live smoke на позиции `кабель ВВГнг 3х2.5`, количество `100`, регион `Москва`.

| Этап | Результат |
| --- | ---: |
| SERP queries | 3 |
| Уникальные SERP results | 22 |
| Offer candidates | 11 |
| Exact qualified seller offers | 3 |
| Unique qualified public contacts | 8 |
| Writes to current system | 0 |

## Что реально сработало

- XMLRiver + direct-site landing pages дали exact-кандидатов и публичные seller-контакты.
- Flagma отдала карточки, но найденные страницы с `Купим...` были buyer requests и корректно исключены.
- ProductCenter/PromPortal в этом bounded-прогоне отдали страницы каталога без подтверждённого exact seller-contact; в qualification не попали.

## Итоговые exact offers

- `Электрика 24` — https://www.electrika24.ru/shop/kabel_kabelkanal/kabel_osvetitel/vvg-3-2-5/
- `Lampoved` — https://www.lampoved.ru/kabeli/vvgng/vvgngls325
- `мос-кабель.рф` — https://xn----8sbdqwjbq1a0j.xn--p1ai/vvgng_3x2,5.html

Контакты и evidence URL хранятся в `out/latest_report.json` и `out/qualified_contacts.csv`. Контакт считается пригодным только вместе с карточкой товара; актуальность цены, наличия, MOQ и условий поставки этим smoke-тестом не подтверждалась.

## Ограничения benchmark-а

- SERP-выдача динамическая; повторный запуск может дать другой набор URL.
- Выбраны только 3 SERP queries, 4 direct landing pages и 2 каталоговых адаптера.
- Юрлицо/ИНН, финансы и ownership intentionally не добавлялись в новый pilot, чтобы не затрагивать production enrichment и не выдавать неподтверждённую идентификацию.
