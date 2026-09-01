"""Inspect or explicitly advance one durable request-search step locally.

The default is read-only. Pass --apply to perform the same bounded unit of
work as POST /api/requests/<id>/search/step and print its measured duration.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supplier_app import Config, SupplierApp, load_dotenv  # noqa: E402


def snapshot(db_path: str, request_id: int) -> dict[str, object]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """SELECT r.id, r.workspace_id, m.status, m.search_progress,
                      m.search_total, m.last_error, j.stage, j.position_index,
                      j.enrich_index, j.enrich_hosts_json, j.status AS job_status,
                      j.attempts, j.locked_until, j.last_error AS job_error
               FROM requests r
               LEFT JOIN request_meta m ON m.request_id=r.id
               LEFT JOIN request_search_jobs j ON j.request_id=r.id
               WHERE r.id=?""",
            (request_id,),
        ).fetchone()
        if not row:
            return {"request_id": request_id, "found": False}
        result = dict(row)
        try:
            hosts = json.loads(result.pop("enrich_hosts_json") or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            hosts = []
        result["hosts_total"] = len(hosts)
        index = int(result.get("enrich_index") or 0)
        result["next_hosts"] = hosts[index:index + 8]
        result["found"] = True
        return result
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request_id", type=int)
    parser.add_argument("--apply", action="store_true", help="advance one bounded step")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    config = Config.from_env()
    before = snapshot(config.db_path, args.request_id)
    print(json.dumps({"before": before}, ensure_ascii=True, indent=2))
    if not args.apply:
        print("Read-only inspection. Pass --apply to advance one step.")
        return 0
    if not before.get("found"):
        return 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    app = SupplierApp(config)
    started = time.monotonic()
    result = app.process_search_step(int(before["workspace_id"]), args.request_id)
    elapsed = round(time.monotonic() - started, 3)
    print(json.dumps({"result": result, "elapsed_seconds": elapsed, "after": snapshot(config.db_path, args.request_id)}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
