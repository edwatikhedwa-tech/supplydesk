# SQLite consistency report

Status: PASS — `supplier.sqlite3` has a logically consistent frozen backup.

## Source and related runtime files

| Item | Result |
|---|---|
| Live source | `<LOCAL_PROJECT_ROOT>\mail-data\supplier.sqlite3` |
| Source size | 8,310,784 bytes at capture |
| Journal mode | `delete` |
| `supplier.sqlite3-wal` | not present |
| `supplier.sqlite3-shm` | not present |
| `supplier.sqlite3-journal` | not present |
| Source integrity check | `ok` |
| Source quick check | `ok` |
| Writes during backup | no evidence of a change; mtime and `data_version` stayed stable |
| Backup | `00_FROZEN_BASELINE\mail-data\supplier.sqlite3.consistent-backup` |

## Method

The backup was produced outside the source project with Python’s standard `sqlite3.Connection.backup()` API, opening the source in read-only mode. The source database was not updated, vacuumed, migrated, or otherwise modified.

## Verification

Both source and backup returned `ok` for `PRAGMA integrity_check` and `PRAGMA quick_check`. The report `SQLITE_BACKUP_REPORT.json` records matching schema objects, table/index/trigger/view metadata, `user_version`, schema version, page size, journal metadata, and aggregate row counts. No row contents or credentials were written to the report.

The logical backup is byte-identical to the copy placed into the frozen baseline (`SHA-256 108041647C6B754E288750FCE9EF25BFEFF6F3D350C5D528A920808950CF8CCD`). A byte-for-byte comparison with a live database file is not used as the correctness criterion for an online SQLite backup.

## Restore conclusion

`LOGICALLY_CONSISTENT_BACKUP = PASS`. The backup contains the verified schema and aggregate data state needed for restoration. The separate `.live-mail.lock` is not a SQLite database component and is handled by `LOCK_INVESTIGATION.md`.

## Limits

The check proves SQLite structural consistency and matching aggregate state at capture time. It does not prove that external mail providers, OAuth sessions, or live network services can be restored from local files.
