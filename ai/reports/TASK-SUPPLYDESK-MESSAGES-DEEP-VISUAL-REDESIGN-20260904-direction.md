---
document_id: TASK-SUPPLYDESK-MESSAGES-DEEP-VISUAL-REDESIGN-20260904-DIRECTION
status: HISTORICAL
owner: Codex
updated_at: 2026-09-04
---

# Design direction

## Product job

Закупщик открывает `/messages`, чтобы быстро понять, по какой заявке есть
новый ответ поставщика, прочитать контекст и выполнить следующий шаг — ответить
поставщику. Главный объект экрана — разговор, сгруппированный внутри заявки;
письмо, статус и количество являются вторичной поддержкой этого сценария.

## Visual thesis

SupplyDesk должен выглядеть как спокойный рабочий стол закупщика: заявка — это
устойчивый левый якорь, переписка — единая рабочая поверхность справа, а
следующее действие закреплено у нижнего края чтения. Узнаваемость появляется из
контраста двух ролей: слева плотный, но плоский список рабочих объектов; справа
много воздуха, последовательная лента событий и один очевидный CTA. Существующая
графитово-синяя палитра, Inter/системный sans-serif и текущие примитивы остаются;
меняется композиция и визуальный вес, а не технический стек.

## Rationale chain

| Product reason | Principle | Concrete decision | Evidence expected |
| --- | --- | --- | --- |
| Закупщик сначала выбирает заявку | Стабильный объектный якорь | Левая панель называется «Мои заявки», поиск находится в ней, группы заявок визуально главнее тредов | В списке первым считывается request name; 1280px screenshot без конкурирующих KPI-блоков |
| Нужно быстро сравнить поставщиков | Сканируемая строка | В строке остаются поставщик, тема, один статус и дата; технические счётчики и повторные действия убраны | 7+ строк сохраняют одинаковый ритм и читаются без вложенных карточек |
| После чтения нужен один следующий шаг | Действие рядом с завершением задачи | Основная кнопка перенесена в sticky footer чтения и называется «Ответить поставщику» | Открытая переписка показывает один заметный CTA внизу |
| История должна ощущаться разговором | Последовательность вместо набора карточек | Связь с заявкой становится частью заголовка, сообщения — вертикальной лентой с единым timeline rhythm | 2+ письма читаются как один поток, а не как стек равных карточек |

## Reference synthesis

| Reference category | Transferable principle | Adaptation decision | Deliberate non-copy |
| --- | --- | --- | --- |
| Intercom Inbox — conversation workflow | Inbox list and reader should share one job and keep reply action near the reader | Split-pane with request-first list and persistent reply footer | No chat bubbles, avatars are restrained and email semantics remain |
| Linear — issue/work-item hierarchy | One primary object per surface, metadata recedes | Request group is the left-side object header; status is inline semantic metadata | No dark command-center treatment or keyboard-command layer |
| Stripe Dashboard — data density | Flat rows and quiet secondary data improve scanning | Dividers, compact metadata and calm counts | No KPI-card grid or colorful analytics blocks |
| Vercel Dashboard — surface restraint | Large white working plane, low-noise shell | Remove repeated borders/radii and keep existing color tokens | No gradients, glass, new colors or decorative cards |

## Deliberate exclusions

Не добавляются новые UI primitives, новые цвета, новые карточки, анимации ради
эффекта или техническая унификация компонентов. Важность и приоритет остаются
доступны в контексте открытой переписки, но не конкурируют с выбором заявки в
каждой строке списка.

## First-render acceptance criteria

1. На desktop 1280px слева первым визуальным заголовком является «Мои заявки»,
   поиск и фильтры находятся в этой панели, а справа читается единый workspace.
2. В списке нет повторяющихся `messages_count/replies_count`, флагов и
   приоритетных контролов в каждой строке; статус представлен один раз тихой
   inline-меткой.
3. В открытой переписке связь с заявкой находится в верхней мета-строке,
   сообщения образуют одну ленту, а «Ответить поставщику» — самое заметное
   действие в нижнем footer.
4. На 390x844 и 360x800 отсутствуют горизонтальный overflow, обрезание и
   перекрытие; список и reader используют существующий mobile flow.
5. Интеракции поиска, фильтра, выбора треда, открытия заявки, ответа и
   существующих delivery-recovery действий сохраняются.
