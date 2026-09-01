# SupplyDesk safe snapshot — blocker resolved

## Первоначальная причина остановки

Физический copy не смог прочитать файл, удерживаемый другим процессом:

`mail-data\\supplier.sqlite3.live-mail.lock`

- исходник существует, 289 байт;
- SHA-256 исходника: `NOT_READABLE` из-за OS lock;
- frozen physical copy отсутствует;
- обычное чтение и `robocopy` получили sharing violation;
- `robocopy /B` не был доступен из-за отсутствия Backup and Restore privilege.

## Разрешение

Исследование `mail/runtime.py` показало, что lock создаётся
`LiveMailLock.acquire`, удерживается только на время процесса и освобождается
`LiveMailLock.release`; файл не удаляется, но следующий запуск снова открывает
и захватывает его. Изолированный тест подтвердил: после release файл остаётся,
а новый процесс может снова получить lock. Runtime manifest связал текущего
owner с Python PID 16704, а source `RuntimeSession` создаёт путь при старте.

Классификация: **EPHEMERAL_RUNTIME**.
`snapshot_status=INTENTIONALLY_EXCLUDED`; `reason=ephemeral runtime lock`;
`restoration_required=NO`.

Поэтому отсутствие lock не делает snapshot невосстановимым и не требовало
останавливать работающий SupplyDesk.

## SQLite verification

`mail-data\\supplier.sqlite3` имеет journal mode `delete`; WAL, SHM и journal
sidecar не обнаружены. Создана отдельная копия через
`sqlite3.Connection.backup()` в `00_FROZEN_BASELINE/mail-data/`.

- source `integrity_check`: `ok`;
- backup `integrity_check`: `ok`;
- source/backup `quick_check`: `ok`;
- schema objects, metadata and aggregate row counts: `MATCH`;
- source mtime and `data_version` remained stable;
- source DB writes: none.

## Snapshot gate

| Проверка | Результат |
|---|---|
| source modified tracked files and untracked project state preserved | PASS |
| only missing path | ephemeral lock |
| critical hashes | 14/15 equal; 15th is intentionally unreadable lock |
| SQLite logical backup | PASS |
| unexplained critical failures | none |
| final snapshot status | **PASS** |

`BASELINE_MANIFEST.csv` contains `INTENTIONALLY_EXCLUDED` for the lock and
`BACKED_UP_LOGICALLY` for the SQLite backup. The baseline includes 56 543
physical copied files from the 56 544 source capture entries; the one difference
is the proven ephemeral lock, not application data.

Audit workspace was created only after this gate and uses a separate runtime
database. No source file, database, Git index, branch or history was changed.
