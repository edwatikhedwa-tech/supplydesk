"""Separate analysis worker for the Mail Intelligence canary (EDW-40). Run as its own process; stop it (or the kill switch) at any time.

  python scripts/mail_intelligence_worker.py --workspace 1 [--interval 60] [--once]

Never touches receive/send. Logs JSON lines with aggregate counters only (no letter content, no addresses, no credentials).
Requires MAIL_INTELLIGENCE_ON_SYNC=1 AND an enabled canary row for the workspace (scripts/mail_intelligence_canary.py enable).
Reads .env into ITS OWN process environment (never printed). Writes the aggregated daily report to docs/canary/EDW-40/daily_<day>.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_env() -> None:
    for name in (".env", ".env.local"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#"):
                    os.environ.setdefault(m.group(1), m.group(2).strip("\"'"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=int, required=True)
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    load_env()
    from mail.repository import MailRepository
    repo = MailRepository(Path(os.getenv("MAIL_DB_PATH", str(ROOT / "mail-data" / "supplier.sqlite3"))))
    worker_id = f"canary-worker-{os.getpid()}"
    logs = list((ROOT / "runtime").glob("**/*.log"))[:20] if (ROOT / "runtime").exists() else []
    report_dir = ROOT / "docs" / "canary" / "EDW-40"
    report_dir.mkdir(parents=True, exist_ok=True)
    while True:
        out = repo.canary_tick(args.workspace, worker_id, log_paths=logs)
        m = out.get("metrics") or {}
        if m:
            (report_dir / f"daily_{m['day']}.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "active": out.get("active"), "stopped_reason": out.get("stopped_reason", ""), "findings": [f["rule"] for f in out.get("findings", [])],
                          "reconciled": out.get("reconciled_jobs"), "jobs": out.get("jobs", {}), "queue_depth": m.get("queue_depth"), "ai_cost_rub_today": m.get("ai_cost_rub")}, ensure_ascii=False), flush=True)
        if args.once or not out.get("active"):
            return 0 if not out.get("findings") else 2
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
