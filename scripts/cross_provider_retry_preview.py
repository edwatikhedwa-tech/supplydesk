"""Read-only preview for one safe cross-provider retry candidate.

The script opens SQLite with ``mode=ro`` and deliberately bypasses
``MailRepository.__init__`` so production validation cannot run migrations or
write runtime state.  It never loads credential values and never calls a
provider.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Running a script by path puts ``scripts`` (not the repository root) on
# sys.path.  Add the root explicitly before importing application modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail.repository import MailRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only cross-provider retry preview")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--request-id", required=True, type=int)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--message-id", required=True, type=int)
    parser.add_argument("--target-account-id", required=True, type=int)
    parser.add_argument("--attempt-id", type=int)
    args = parser.parse_args()

    db_path = args.db.expanduser().resolve()
    if not db_path.is_file():
        raise SystemExit(f"Database not found: {db_path}")
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        account = connection.execute(
            "SELECT user_id FROM mail_accounts WHERE id=?",
            (args.target_account_id,),
        ).fetchone()
        if not account:
            raise SystemExit("Target account not found")
        # The evaluator only uses repository statics and the passed connection;
        # __init__ is intentionally skipped because it runs migrations.
        repository = object.__new__(MailRepository)
        result = repository._evaluate_cross_provider_retry_connection(
            connection,
            workspace_id=int(connection.execute(
                "SELECT workspace_id FROM mail_accounts WHERE id=?",
                (args.target_account_id,),
            ).fetchone()[0]),
            user_id=int(account["user_id"]),
            request_id=args.request_id,
            original_job_id=args.job_id,
            original_message_id=args.message_id,
            target_account_id=args.target_account_id,
            original_attempt_id=args.attempt_id,
        )
        result.pop("_normalized_recipient", None)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
