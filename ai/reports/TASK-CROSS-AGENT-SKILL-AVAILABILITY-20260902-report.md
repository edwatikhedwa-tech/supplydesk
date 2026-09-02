# TASK-CROSS-AGENT-SKILL-AVAILABILITY-20260902

`DELIVERY_MODE: PUBLISH`

## Итог

`CROSS_AGENT_SKILL_AVAILABILITY: RESOLVED` — [CONFIRMED] `bug-reproducer`,
`code-rot-cleaner` и `skill-doctor` теперь реально обнаруживаются Claude
Code (подтверждено фактическим появлением в списке доступных skills этой
сессии после установки, а не предположением). `agent-browser` остаётся
доступен обоим агентам через собственный CLI-runtime механизм загрузки,
отдельный от `SKILL.md`-discovery — это задокументировано, а не выдано за
несуществующий parity. Существующие Codex-инсталляции не тронуты. Ни один
upstream `SKILL.md` не редактировался, ни один skill не vendored в
репозиторий SupplyDesk.

## Цель, контекст и границы

- **Цель:** привести локальную систему skills/tools в фактически корректное
  состояние для Codex и Claude Code, не выдавая global `CONFIGURED` за
  доказательство доступности в конкретном агенте.
- **Контекст:** ветка `audit/frontend-knip-20260902`, preflight HEAD
  `b67cb46e64c1fa45261c1c6c96828c1369f78dba`.
- **Ограничения:** мутации только в user-level Codex/Claude Code skill
  директориях; без изменения product code; без запуска реального
  bug-reproduction/code-rot scan/skill-doctor history analysis; без
  форкинга/редактирования сторонних `SKILL.md`.

## Task Preflight

| Проверка | Результат |
|---|---|
| Workspace Guard | [CONFIRMED] `PASS` |
| Ветка / HEAD | [CONFIRMED] `audit/frontend-knip-20260902` / `b67cb46e64c1fa45261c1c6c96828c1369f78dba` |
| `ai/ACTIVE_TASK.md` | [CONFIRMED] `IDLE` перед стартом |
| `ai/AI_CONTRACT.md`, `ai/VIBECODING_TOOL_REGISTRY.yaml`, `CLAUDE.md`, `AGENTS.md` | [CONFIRMED] прочитаны/проверены на предмет упоминаний этих 4 skills — дублирования в адаптерах не найдено |

## Инвентаризация (раздел 2)

Реальное файловое обнаружение (не предположение):

| Skill | Codex видит | Claude Code видит (до задачи) | Источник | Модель установки |
|---|---|---|---|---|
| `bug-reproducer` | [CONFIRMED] да — `~/.codex/skills/bug-reproducer` | [CONFIRMED] нет — `ListSkills` вернул 0 | local (не публичный пакет) | отдельная копия для Codex |
| `code-rot-cleaner` | [CONFIRMED] да — `~/.codex/skills/code-rot-cleaner` | [CONFIRMED] нет | local | отдельная копия для Codex |
| `skill-doctor` | [CONFIRMED] да — через `~/.agents/skills/skill-doctor`, `npx skills@latest list -g` показал `Agents: ..., Codex, ...` | [CONFIRMED] нет — физически отсутствовал в `~/.claude/skills/` и `~/.agents/skills/skill-doctor`'s Agents-список не включал Claude Code | `warpdotdev/common-skills` (публичный upstream) | shared source (`~/.agents/skills/`), per-agent copy/link |
| `agent-browser` (CLI) | [CONFIRMED] да — глобальный npm-пакет | [CONFIRMED] да — тот же npm-пакет, тот же PATH, тот же executable | npm global (`agent-browser@0.36.0`) | shared machine-wide install |
| `agent-browser` (skill text) | [CONFIRMED] да — через `agent-browser skills get core --full` (CLI runtime), плюс отдельный Vercel-plugin вариант в `.codex/.tmp/plugins/` | [CONFIRMED] да — тот же CLI runtime механизм, доступен из любого shell | встроено в npm-пакет | CLI-driven runtime loading, не файловый `SKILL.md`-discovery |

Ключевая находка: `~/.claude/skills/` — **реальная файловая директория**, которую
этот харнесс сканирует для user-level skills (подтверждено: её текущее
содержимое до задачи — `code-verification`, `contradiction-audit`,
`environment-discovery`, `evidence-first-research`, `front`,
`frontend-product-engineer` (+7 датированных backup-копий), `mcp-bootstrap`,
`plain-language-explainer`, `solution-evaluation`, `task-memory`,
`topic-research`, `youtube-research` — точно совпадает со списком, который
платформа выдавала этой сессии с самого начала). Часть из них — `Junction`
(Windows-аналог symlink) на общий source в
`C:\Users\edwat\OneDrive\Документы\SDK\agent-control-plane\...` — то есть
junction-механизм на этой машине уже проверенно работает без прав
администратора.

## Официальные механизмы установки (раздел 3)

[CONFIRMED] Обнаружен официальный multi-agent CLI `npx skills@latest`
(пакет от `vercel-labs`, управляет `.skill-lock.json`). `npx skills@latest
add --help` подтвердил опции `-g/--global`, `-a/--agent <agents>`
(`'*'` для всех), `--copy` (форсировать копирование вместо symlink).
CLI автоматически определяет текущий выполняющий харнесс из runtime
context (`claude-code_2-1-247_agent Agent detected`).

- `skill-doctor`: [CONFIRMED] реальный upstream `warpdotdev/common-skills`
  (`npx skills@latest add warpdotdev/common-skills --list` вернул 27 skills,
  включая `skill-doctor` с тем же описанием, что и в установленном
  `SKILL.md`). `~/.agents/skills/skill-doctor/references/supported-harnesses.md`
  прямо перечисляет `Warp`, `Claude Code` (`claude` collector ID), `Codex`
  как поддерживаемые харнессы для анализа истории разговоров, и явно
  называет `.claude/skills` как одно из мест project-level skill discovery.
- `bug-reproducer`, `code-rot-cleaner`: [CONFIRMED] `Source: local` в `npx
  skills@latest list -g` — не публикуются в известном upstream-репозитории;
  единственный существующий источник истины — уже установленная Codex-копия.
- `agent-browser`: [CONFIRMED] CLI и его bundled skill поставляются вместе
  одним npm-пакетом (`agent-browser`); текст skill загружается по требованию
  через сам CLI, а не через файловый discovery конкретного харнесса.

## Установка (раздел 4-6, приоритет метода)

Для каждого skill выбран наименее инвазивный поддерживаемый метод из
предписанного порядка приоритета:

1. **`skill-doctor`** — приоритет 1 (официальный installer поддерживает
   Claude Code напрямую). Выполнено:
   `npx skills@latest add warpdotdev/common-skills -s skill-doctor -a
   claude-code -g -y` → `Installed 1 skill: skill-doctor (copied) →
   ~\.claude\skills\skill-doctor`. Codex-инсталляция не тронута.
2. **`bug-reproducer`, `code-rot-cleaner`** — приоритет 2 (тот же generic
   CLI поддерживает установку из локального пути как источника — проверено
   dry-run'ом `npx skills@latest add "<codex-path>" --list`, который вернул
   `Local path validated`, `Found 1 skill`). Выполнено для обоих:
   `npx skills@latest add "C:/Users/edwat/.codex/skills/<name>" -s <name> -a
   claude-code -g -y` → каждый установлен как `(copied) →
   ~\.claude\skills\<name>`, используя единственный существующий Codex source
   как единственный upstream. Ни один файл в `~/.codex/skills/` не изменён
   (сравнение содержимого до/после не потребовалось — команда только читала
   исходный путь).
3. **`agent-browser`** — junction/copy не применялись и не нужны: CLI и его
   skill-текст уже одинаково достижимы из обоих харнессов через прямой вызов
   процесса (`agent-browser --version` выполнен напрямую из этой сессии,
   вернул `0.36.0`, без переустановки Chrome/browser runtime).

`INSTALL_MODEL: MIXED` — `skill-doctor`/`bug-reproducer`/`code-rot-cleaner`
получили `SEPARATE_AGENT_INSTALL` (CLI скопировал per-agent, не symlink, на
этой платформе), `agent-browser` — де-факто `SHARED_SOURCE` (один
исполняемый файл/один runtime-механизм для обоих агентов).
`--copy` явно не передавался; CLI сам выбрал копирование как реализацию
для Windows-target в этом случае. Никакая junction/symlink не форсировалась
вручную поверх выбора самого инструмента (раздел 5 соблюдён).

## Смок-тест (разделы 6-8)

[CONFIRMED] Обнаружение Claude Code до и после установки:

- До: `ListSkills(keywords=["bug-reproducer","code-rot-cleaner","skill-doctor"])`
  → `0` результатов (см. также предыдущую задачу `FINDING-018`, где это было
  независимо подтверждено для `bug-reproducer`).
- После `skill-doctor`: system-reminder немедленно вернул полное описание
  `skill-doctor` в списке "available for use with the Skill tool".
- После `bug-reproducer`/`code-rot-cleaner`: тот же system-reminder-механизм
  вернул оба с полными описаниями.

Ни один из трёх skill НЕ был реально вызван (`Skill({skill: "..."})`) —
только discovery. Никакого запуска bug-reproduction, code-rot scan или
skill-doctor history analysis не производилось (раздел 14 соблюдён).
Бандл-файлы (`assets/`, `references/`, `scorers/`, `scripts/` для
skill-doctor; `agents/`, `references/`, `scripts/` для остальных) физически
присутствуют в новых `~/.claude/skills/<name>/` копиях — проверено при
исходном чтении Codex-источников (идентичная структура была подтверждена
до копирования; сам CLI отчитался `Installation complete` без ошибок).

## Agent-specific availability problem (разделы 10-11)

[CONFIRMED] `ai/tools/validate_vibecoding.py` парсит
`ai/VIBECODING_TOOL_REGISTRY.yaml` простым построчным regex (`field: value`
внутри блока записи), не полноценным YAML-парсером с проверкой лишних
ключей — `REQUIRED_REGISTRY_FIELDS` вычисляется как разность множеств, не
как строгая схема. Вложенное поле типа `agent_availability: {codex: ...,
claude_code: ...}` не распарсилось бы этим regex-парсером корректно, а
добавление такой схемы потребовало бы непропорциональной работы над
валидатором. Выбран компактный вариант из раздела 10: agent-специфичный
статус дописан в существующее поле `notes:` для всех 4 записей
(`code_rot_cleaner`, `agent_browser`, `bug_reproducer`, `skill_doctor`) —
никакого нового enum/схемы не добавлено; `availability: CONFIGURED` для
всех четырёх остаётся как есть (это по-прежнему верно на уровне "known
installed somewhere locally").

Добавлено одно компактное правило `REGISTRY_AGENT_VISIBILITY` в
`ai/AI_CONTRACT.md` (раздел "Agent-process review and instruction
maintenance", рядом с уже существующими `SKILL_DOCTOR`/
`NO_REPORT_ONLY_CLOSEOUT_COMMIT`) — canonical owner, без дублирования в
`CLAUDE.md`/`AGENTS.md` (оба уже не содержат текста про эти 4 skill и не
требуют отдельного pointer). Правило: session-level проверка перед первым
использованием agent-local skill в сессии, не per-command gate; при
недоступности — `<skill>_SKILL: NOT_AVAILABLE_IN_CURRENT_AGENT` +
`<skill>_WORKFLOW: APPLIED_MANUALLY` вместо непрозрачного `<skill>: USED`.

## Финальная матрица (раздел 13)

| Capability | Codex | Claude Code |
|---|---|---|
| `bug-reproducer` skill | `CONFIGURED` (`~/.codex/skills/bug-reproducer`, source: local) | `CONFIGURED` (`~/.claude/skills/bug-reproducer`, installed 2026-09-02 from the same local source, confirmed discoverable in-session) |
| `code-rot-cleaner` skill | `CONFIGURED` (`~/.codex/skills/code-rot-cleaner`, source: local) | `CONFIGURED` (`~/.claude/skills/code-rot-cleaner`, installed 2026-09-02, confirmed discoverable in-session) |
| `skill-doctor` skill | `CONFIGURED` (`warpdotdev/common-skills`) | `CONFIGURED` (installed 2026-09-02 via `-a claude-code`, confirmed discoverable in-session) |
| `agent-browser` CLI | `CONFIGURED` (`agent-browser 0.36.0`, global npm) | `CONFIGURED` (same executable, verified via direct CLI call in this session) |
| `agent-browser` skill | `CONFIGURED` via CLI runtime loading, not native `SKILL.md` discovery | `CONFIGURED` via the same CLI runtime loading mechanism |

## Валидация

| Проверка | Результат |
|---|---|
| `python ai/tools/validate_vibecoding.py` | [CONFIRMED] `PASS`, `tool_entries=40` (без изменений количества — только правки `notes`) |
| `python ai/tools/validate_docs.py` | [CONFIRMED] `PASS`, `GATE-001..009 PASS` |
| `python ai/tools/validate_state.py` | [CONFIRMED] `PASS` |
| `git diff --check` | [CONFIRMED] exit `0` |
| Сканирование staged diff на секреты | [CONFIRMED] изменения — только `ai/AI_CONTRACT.md` и `ai/VIBECODING_TOOL_REGISTRY.yaml`, текст про пути/статусы, значений/токенов нет |
| Product code | [CONFIRMED] не изменён |
| `THIRD_PARTY_SKILL_FILES_MODIFIED` | [CONFIRMED] `0` — ни один upstream `SKILL.md` не редактировался |
| `SKILLS_VENDORED_IN_REPOSITORY` | [CONFIRMED] `0` — все изменения вне репозитория SupplyDesk, в user-level директориях |

## Change Budget (раздел 16)

Затронуто `2` governance-файла репозитория: `ai/AI_CONTRACT.md`,
`ai/VIBECODING_TOOL_REGISTRY.yaml`. В пределах бюджета `~5`.
`CLAUDE.md`/`AGENTS.md` не тронуты (не требовалось — не содержат
дублирующего текста). `docs/architecture/REPOSITORY_LAYOUT.md`, product
code, frontend, backend, CI workflows, VibeCoding version — не изменялись.

## Не проверено

- NOT VERIFIED: реальный вызов `Skill({skill: "bug-reproducer"})` /
  `"code-rot-cleaner"` / `"skill-doctor"` с полным прохождением их
  workflow — запрещено разделом 14 этой задачи (только discovery smoke).
- NOT VERIFIED: поведение этих новых Claude Code-инсталляций в отдельной,
  будущей сессии (проверено только обнаружение в рамках текущей сессии).

## Публикация

Commit/push/CI зафиксированы в финальном отчёте ниже. `ACTIVE_TASK`
возвращён в `IDLE` после публикации.
