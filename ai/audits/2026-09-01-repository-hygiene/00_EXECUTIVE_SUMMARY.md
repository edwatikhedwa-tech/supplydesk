# SupplyDesk safe snapshot + repository hygiene audit

**STATUS: PARTIAL**
**SNAPSHOT_STATUS: PASS**

## Сделано

Внешний физический снимок сохранён в
`<LOCAL_SNAPSHOT_ROOT>\20260901-110706`. Отсутствующий
`mail-data\\supplier.sqlite3.live-mail.lock` исследован и доказан как
`EPHEMERAL_RUNTIME`: это OS-синхронизационный маркер, а не данные базы или
конфигурация. Он намеренно исключён и создаётся заново при запуске.

Для `supplier.sqlite3` создан отдельный backup через официальный SQLite
Backup API (`sqlite3.Connection.backup()`), затем выполнены `integrity_check`,
`quick_check`, сверка схемы, метаданных и агрегированных row counts. Все
проверки дали `ok`/`MATCH`.

Создана независимая audit-копия и переключена на локальную ветку
`audit/repository-hygiene-20260901`. Выполнены backend/frontend smoke-проверки,
инвентаризация, анализ документации, дублей, зависимостей и dead-code сигналов.

## Ключевой результат

- исходник: `<LOCAL_PROJECT_ROOT>`;
- remote: `https://github.com/edwatikhedwa-tech/supplydesk.git`;
- GitHub visibility: `PRIVATE` (read-only GitHub CLI);
- исходная ветка: `codex/TASK-STATE-CONTROL-20260830`;
- исходный HEAD: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`;
- Git единицы измерения: 266 tracked FILES, 2 modified tracked FILES,
  0 staged FILES, 709 untracked FILES, 55 319 ignored FILES, 711 status PATH
  ENTRIES;
- physical inventory: 56 553 FILES, включая 259 `.git` metadata files;
- текущий размер физической директории: 956 758 252 байта (примерно 912,4 MiB);
- база: SQLite `mail-data\\supplier.sqlite3`, journal mode `delete`;
- logical SQLite backup: PASS;
- исходный сервер был наблюдаем на `127.0.0.1:8000` во время первичного
  capture, но при финальной проверке listener на 8000 уже отсутствовал;
  audit-сервер оставлен на `127.0.0.1:18000`;
- GitHub: repository private, один workflow `Dependency Graph`, CodeQL и
  Dependabot alerts недоступны через API.

## Ограничения

Functional baseline не полностью зелёный: 321 тест прошёл, 52 существующих
теста завершились FAIL, 1 SKIP; это baseline текущей копии и не повод менять
продукт в этой задаче. В безопасной среде исходящая почта отключена.
Playwright real-route smoke дал 18/18 PASS, но исторический live-email тест не
нашёл ожидаемое письмо в текущем снимке данных. Knip запустился частично из-за
несовместимости локального Vite/Rollup (`rollup/parseAst`).

Ни один файл исходного проекта не удалён, код и документация исходника не
рефакторились. Отчёты находятся только во внешнем `02_REPORTS`.

## Основные отчёты

- `LOCK_INVESTIGATION.md` — доказательство статуса lock-файла;
- `SQLITE_CONSISTENCY.md` — логическая проверка SQLite backup;
- `BASELINE_MANIFEST.csv` — файловый manifest без содержимого секретов;
- `FUNCTIONAL_BASELINE.md` — фактические test/browser результаты;
- `PROJECT_INVENTORY.csv`, `UNTRACKED_FILES_AUDIT.md` — карта файлов;
- `DEPENDENCY_AUDIT.md`, `DEAD_CODE_AUDIT.md` — analyzer evidence;
- `DOCUMENTATION_MAP.md`, `DUPLICATES_REPORT.md` — документация и дубли;
- `CLEANUP_PLAN.md` — будущие небольшие batches без выполнения очистки;
- `GITIGNORE_RECOMMENDATIONS.md`, `SECURITY_FINDINGS.md` — риски и предложения;
- `FINAL_REPORT.md` — итоговый структурированный отчёт.
