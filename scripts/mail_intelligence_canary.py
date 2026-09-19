"""Owner control of the Mail Intelligence canary (EDW-40). Nothing here runs by itself and nothing raises a budget.

  status --workspace 1                 config, spend, caps, stop state
  enable --workspace 1 --owner-approved [--clear-stop]   opens the window (first time: started_at = now), reconciles letters that arrived while disabled
  disable --workspace 1                kill switch: AI processing stops at once; receive/send untouched; no data migration
  check --workspace 1                  evaluates the stop rules now (stops the canary if one fires)
  metrics --workspace 1 [--day YYYY-MM-DD] [--write]   aggregate metrics; --write stores docs/canary/EDW-40/daily_<day>.json
  final --workspace 1 [--write]        summary of the period (marks a limited sample)
Reports contain counts, costs and latencies only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["status", "enable", "disable", "check", "metrics", "final"])
    ap.add_argument("--workspace", type=int, required=True)
    ap.add_argument("--owner-approved", action="store_true")
    ap.add_argument("--clear-stop", action="store_true")
    ap.add_argument("--day")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    from mail.repository import MailRepository
    repo = MailRepository(Path(os.getenv("MAIL_DB_PATH", str(ROOT / "mail-data" / "supplier.sqlite3"))))
    ws = a.workspace
    if a.command == "status":
        out = {"state": repo.canary_state(ws), "spend": repo.canary_spend(ws), "env_flag_on": os.getenv("MAIL_INTELLIGENCE_ON_SYNC") == "1", "active": repo.canary_active(ws)}
    elif a.command == "enable":
        if not a.owner_approved:
            raise SystemExit("REFUSED: enabling the canary needs --owner-approved (an explicit owner decision).")
        out = repo.canary_enable(ws, clear_stop=a.clear_stop)
    elif a.command == "disable":
        repo.canary_disable(ws)
        out = {"disabled": True, "state": repo.canary_state(ws)}
    elif a.command == "check":
        out = {"findings": repo.enforce_canary_safety(ws), "state": repo.canary_state(ws)}
    elif a.command == "metrics":
        from datetime import UTC, datetime
        day = a.day or datetime.now(UTC).strftime("%Y-%m-%d")
        out = repo.canary_snapshot_day(ws, day)
        if a.write:
            path = ROOT / "docs" / "canary" / "EDW-40" / f"daily_{day}.json"
            path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        out = repo.canary_final_summary(ws)
        if a.write:
            (ROOT / "docs" / "canary" / "EDW-40" / "final_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
