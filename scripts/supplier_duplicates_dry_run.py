"""EDW-17: DRY-RUN report of historical duplicate supplier cards. Changes NOTHING.

Reuses the reviewed candidate detection of scripts/supplier_identity_audit.py (`scan_duplicates`) and
adds what the reversible merge (EDW-16) needs before anything may be applied:

  * INN verdict per pair (`merge_verdict`): different confirmed INNs are BLOCKED, never mergeable;
    an unknown INN needs an explicit manual decision;
  * the exact per-table plan of what `merge_suppliers` would re-point / set aside (`merge_plan`),
    so nothing surprising can happen (the legacy audit only knew 14 of the 25 supplier-referencing tables);
  * whether the merged card's address already has confirmed ownership evidence.

Safety: the database is opened with SQLite `mode=ro` (a write raises), the script never instantiates
MailRepository (that would run migrations = writes) and never calls any merge/apply code. The legacy
`--apply-strict-safe` of supplier_identity_audit.py is irreversible and is NOT used here.

Output: a JSON report (ids and verdicts only, no emails) under results/ (git-ignored) + a text summary.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.supplier_identity.merge_guard import merge_verdict  # noqa: E402
from mail.supplier_merge import merge_plan  # noqa: E402
from scripts.supplier_identity_audit import DEFAULT_DB, scan_duplicates  # noqa: E402


def open_readonly(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{Path(db_path).resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _inn(connection: sqlite3.Connection, supplier_id: int) -> str:
    row = connection.execute("SELECT COALESCE(inn,'') AS inn FROM supplier_profiles WHERE supplier_id=?", (supplier_id,)).fetchone()
    return row["inn"] if row else ""


def _has_confirmed_evidence(connection: sqlite3.Connection, workspace_id: int, supplier_id: int, email: str) -> bool | None:
    try:
        return connection.execute(
            """SELECT 1 FROM supplier_identity_evidence WHERE workspace_id=? AND supplier_id=? AND kind='email' AND value=?
               AND assertion='ownership' AND strength='strong' AND state='confirmed' LIMIT 1""",
            (workspace_id, supplier_id, str(email or "").strip().lower()),
        ).fetchone() is not None
    except sqlite3.OperationalError:
        return None  # database predates migration 053 (no evidence table yet)


def build_report(connection: sqlite3.Connection) -> dict[str, Any]:
    scan = scan_duplicates(connection)
    pairs: list[dict[str, Any]] = []
    for cand in scan["candidates"]:
        survivor, merged = int(cand["canonical_supplier_id"]), int(cand["duplicate_supplier_id"])
        verdict = merge_verdict(_inn(connection, survivor), _inn(connection, merged))
        plan = merge_plan(connection, survivor, merged)
        pairs.append({
            "workspace_id": int(cand["workspace_id"]),
            "survivor_supplier_id": survivor,
            "merged_supplier_id": merged,
            "host": cand.get("host") or "",
            "inn_verdict": verdict,
            "decision": {"conflict": "BLOCKED_DIFFERENT_INN", "same_company": "ELIGIBLE_SAME_INN",
                         "unknown": "NEEDS_MANUAL_CONFIRMATION"}[verdict],
            "merged_address_has_confirmed_evidence": _has_confirmed_evidence(
                connection, int(cand["workspace_id"]), merged, cand.get("email") or ""),
            "plan": plan,
            "rows_to_move": sum(t["would_move"] for t in plan.values()),
            "rows_to_set_aside": sum(t["would_set_aside"] for t in plan.values()),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run (read-only connection; no data was changed)",
        "supplier_count": scan["supplier_count"],
        "candidate_pairs": len(pairs),
        "ambiguous_not_proposed": [{"supplier_id": a["supplier_id"], "reason": a["reason"]} for a in scan["ambiguous"]],
        "decisions": dict(Counter(p["decision"] for p in pairs)),
        "pairs": pairs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run отчёт по историческим дублям поставщиков (ничего не меняет).")
    parser.add_argument("--db", type=Path, default=Path(os.getenv("MAIL_DB_PATH", str(DEFAULT_DB))))
    parser.add_argument("--out", type=Path, default=None, help="Куда записать JSON (по умолчанию results/).")
    args = parser.parse_args(argv)
    connection = open_readonly(args.db)
    try:
        report = build_report(connection)
    finally:
        connection.close()
    out = args.out or ROOT / "results" / f"supplier_duplicates_dry_run_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DRY-RUN: suppliers={report['supplier_count']} candidate_pairs={report['candidate_pairs']} "
          f"decisions={report['decisions']} ambiguous_not_proposed={len(report['ambiguous_not_proposed'])}")
    print(f"rows to move={sum(p['rows_to_move'] for p in report['pairs'])} "
          f"to set aside={sum(p['rows_to_set_aside'] for p in report['pairs'])}; report: {out}")
    print("Ничего не изменено. Применение — только отдельным решением через merge_suppliers (обратимо).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
