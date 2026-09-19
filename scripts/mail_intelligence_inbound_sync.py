"""Inbound-only mail sync for the shadow canary (EDW-40). A launcher, not a second implementation.

  python scripts/mail_intelligence_inbound_sync.py --workspace 1 [--interval 180] [--once]

It builds MailService exactly like SupplierApp does (same Config.from_env, same provider factory, same pacing/rollout settings) and calls the EXISTING production
method MailService.sync_all_incoming(user_id, workspace_id) - which for every connected, incoming-enabled account runs
    provider.fetch_incoming -> parse incoming -> MailRepository.import_incoming_messages (dedup, thread/request routing, attachments, cursors)
    -> analysis jobs enqueued in the same transaction when the canary gate accepts the letter (received at or after canary_started_at).
It does NOT: send mail, construct MailQueue, start any worker or thread, sync the Sent folder, touch outgoing_enabled, back-fill, or parse mail itself.
Every cycle reports the counters below and measures that no send attempt or outbound job appeared (outgoing_delta must be 0).
Logs contain counters only: no addresses, no letter content, no credentials."""

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


def outgoing_counters(repo) -> dict:
    """Read-only evidence that nothing was sent or queued for sending."""
    with repo.connect() as c:
        one = lambda sql: c.execute(sql).fetchone()[0]
        return {"send_attempts": one("SELECT COUNT(*) FROM mail_send_attempts"), "jobs": one("SELECT COUNT(*) FROM mail_jobs"),
                "outbound_messages": one("SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'"), "outgoing_enabled": int(bool(repo.outgoing_enabled()))}


def run_cycle(service, repo, workspace_id: int, user_id: int) -> dict:
    """One inbound cycle through the production method, with before/after evidence. Returns aggregate counters only."""
    before = outgoing_counters(repo)
    with repo.connect() as c:
        jobs_before = c.execute("SELECT COUNT(*) FROM mail_analysis_jobs WHERE workspace_id=?", (workspace_id,)).fetchone()[0]
    t0 = time.time()
    result = service.sync_all_incoming(user_id, workspace_id)                      # THE production inbound sync
    after = outgoing_counters(repo)
    with repo.connect() as c:
        jobs_after = c.execute("SELECT COUNT(*) FROM mail_analysis_jobs WHERE workspace_id=?", (workspace_id,)).fetchone()[0]
    accounts = result.get("accounts", [])
    return {
        "accounts_checked": len(accounts), "accounts_failed": sum(1 for a in accounts if not a.get("ok", False)),
        "scanned": sum(int(a.get("scanned", 0) or 0) for a in accounts), "imported": sum(int(a.get("imported", 0) or 0) for a in accounts),
        "unmatched": sum(int(a.get("unmatched", 0) or 0) for a in accounts), "skipped_duplicates": sum(int(a.get("skipped", 0) or 0) for a in accounts),
        "analysis_jobs_created": jobs_after - jobs_before, "seconds": round(time.time() - t0, 2),
        "outgoing_delta": {k: after[k] - before[k] for k in ("send_attempts", "jobs", "outbound_messages")}, "outgoing_enabled": after["outgoing_enabled"],
    }


def build(workspace_id: int):
    """MailService built as SupplierApp builds it (Config.from_env + provider factory), WITHOUT MailQueue, runtime session or any thread."""
    load_env()
    from backend.app_config import Config, yandex_provider_factory
    from mail.repository import MailRepository
    from mail.service import MailService
    config = Config.from_env()
    repo = MailRepository(config.db_path)
    service = MailService(repo, yandex_provider_factory, config.encryption_key, daily_limit=config.daily_limit, pacing_settings=config.pacing,
                          rollout_settings=config.rollout, campaign_max_recipients=config.campaign_max_recipients)
    accounts = [a for a in repo.list_active_mail_accounts() if int(a["workspace_id"]) == workspace_id]
    if not accounts:
        raise SystemExit("no connected mail accounts in this workspace")
    return repo, service, int(accounts[0]["user_id"]), accounts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=int, required=True)
    ap.add_argument("--interval", type=int, default=180)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    repo, service, user_id, accounts = build(args.workspace)
    if repo.outgoing_enabled():
        print(json.dumps({"refused": "durable outgoing switch is ON; this runner is inbound-only and will not run next to an enabled outgoing path"}), flush=True)
        return 3
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "start": True, "workspace": args.workspace, "accounts": len(accounts), "interval_s": args.interval,
                      "method": "MailService.sync_all_incoming"}), flush=True)
    while True:
        st = repo.canary_state(args.workspace)
        if st and st["ends_at"] and st["ends_at"] <= time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()) and st["enabled"] == 0:
            print(json.dumps({"ended": "canary window closed"}), flush=True)
            return 0
        out = run_cycle(service, repo, args.workspace, user_id)
        canary = repo.canary_state(args.workspace) or {}
        findings = [f["rule"] for f in repo.evaluate_safety(args.workspace)] if canary else []
        print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **out, "canary_stopped": bool(canary.get("stopped_at")), "stop_findings": findings}, ensure_ascii=False), flush=True)
        if any(out["outgoing_delta"].values()):
            print(json.dumps({"halt": "outgoing activity detected during an inbound-only cycle"}), flush=True)
            return 4
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
