---
document_id: DOC-FRONTEND-V1-V2-COMPARISON-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# Сравнение Frontend v1 и v2

См. [`FRONTEND_ARCHITECTURE.md`](FRONTEND_ARCHITECTURE.md) о том, какая версия реально работает
и почему их сочетание создаёт визуальную несогласованность. Этот файл — детальное сравнение
страниц и библиотек.

## Страницы/маршруты

| Маршрут в v1 | Файл в v1 | Маршрут в v2 | Файл в v2 | Статус |
|---|---|---|---|---|
| `/` | `Dashboard.tsx` | `/` | `Dashboard.tsx` | Есть в обеих |
| `/requests` | `RequestsList.tsx` | `requests` | `Requests.tsx` | Есть в обеих (переименован) |
| `/requests/new` | `NewRequest.tsx` (отдельная страница) | — | `NewRequestModal` (модальное окно внутри `Requests.tsx`) | Изменение UX-паттерна, не реальная потеря функциональности |
| `/requests/:id` | `RequestPage` | `requests/:id` | `RequestDetail.tsx` | Есть в обеих |
| `/messages` | `Messages.tsx` | `messages` | `Messages.tsx` | Есть в обеих |
| `/mail/campaigns/:id` | `CampaignPage.tsx` | — | — | **Только в v1 — реальная потеря функциональности, `GAP-001`** |
| `/suppliers` | `Suppliers.tsx` | `suppliers` | `Suppliers.tsx` | Есть в обеих |
| — | — | `suppliers/:id` | `SupplierDetail.tsx` | Только в v2 (в v1 вместо этого — всплывающая панель) |
| `/blacklist` | `Blacklist.tsx` | `blacklist` | `Blacklist.tsx` | Есть в обеих |
| `/settings` | `Settings.tsx` | `settings` | `Settings.tsx` | Есть в обеих |
| `/login` | `Login.tsx` | (закрыт для неавторизованных) | `Login.tsx` | Есть в обеих |
| `*` | `NotFound.tsx` | `*` | `NotFound.tsx` | Есть в обеих |
| — | — | `help` | `Help.tsx` | Только в v2 |

Других страниц, существующих только в v1, кроме мониторинга рассылок, не найдено.

## Различия в библиотеках/инструментах

| Параметр | v1 (`frontend/`) | v2 (`frontend-v2/`) |
|---|---|---|
| React | 18.3.1 | 19.2.8 |
| Роутер | react-router-dom ^6, `BrowserRouter` | react-router-dom ^7, `HashRouter` |
| Иконки | lucide-react ^0.446 | lucide-react ^1.41 (переход через мажорную версию) |
| Стили | Tailwind ^3.4 + PostCSS | Tailwind ^4.3 через плагин Vite |
| Компонентные примитивы | написаны вручную | Radix UI (headless) |
| Таблицы | вручную | `@tanstack/react-table` (только в 1 из 6 таблиц) |
| Тосты (всплывающие уведомления) | нет | `react-toastify` |
| Линтер | ESLint 9 | oxlint |
| E2E/визуальное/accessibility-тестирование | Playwright + Storybook + Applitools Eyes + axe-core + Lighthouse CI | ничего из этого нет |

## `RequestDetailExperiment.tsx` — вопрос уже решён, действий не требуется

Существовал только временно в рабочей директории (никогда не попадал в историю ветки
`experiment/frontend-v2-greenfield-20260905` — зафиксирован только на отдельной ветке-снапшоте
`state/current-20260917-2119`, коммит `dcb0576`). Структурное сравнение с рабочей страницей
`RequestDetail.tsx`:

- **Экспериментальная версия (577 строк):** одна монолитная функция, вся логика внутри (задачи,
  позиции, строки таблицы) — нет отдельных вложенных компонентов, кроме нескольких чистых
  вспомогательных функций.
- **Рабочая `RequestDetail.tsx` (~840 строк):** более развитая версия — логика разделена на
  компоненты `PositionsRow`, `CommunicationCell`, `PrimaryAction`, `OverflowMenu`, `CompanyCell`,
  `AgeCell`/`RevenueCell`/`ProfitCell`/`RegistryCell`, `SupplierTableRow`/`SupplierMobileRow`,
  `TasksOnRequest`. Также есть интеграция с `RemindersContext`, общий компонент `PageHeader`,
  стрелки-индикаторы тренда на финансовых ячейках и отдельный рендер строки для мобильных
  экранов — ничего этого нет в экспериментальном файле.

**Ни одна идея из экспериментального файла не отсутствует на рабочей странице.** Он читается как
более ранний, менее отрефакторенный черновик того же экрана — уже корректно определён как
избыточный и удалён, согласно записи в `ai/ACTIVE_TASK.md`: «его реальная функциональность уже
корректно жила в `RequestDetail.tsx`». Переноса или спасения каких-либо идей не требуется.
