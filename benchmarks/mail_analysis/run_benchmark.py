"""EDW-26: controlled benchmark of the Mail Intelligence Core on REAL RouterAI calls.

    python benchmarks/mail_analysis/run_benchmark.py [--cheap M] [--strong M] [--judge M] [--budget RUB] [--tag T]

* ~60 synthetic letters (benchmarks/mail_analysis/dataset.py) with hand-written expected results, in a THROWAWAY
  SQLite database - never the project database. No mailbox is read; no real correspondence leaves the machine.
* The key is read from the environment / .env (never printed, logged or written to the report).
* A hard spend cap (--budget, rub) stops the run before the next call.
* A second model acts only as a JUDGE of mismatches; its opinion never replaces the hand-written truth.
* The report keeps ids, categories, tokens, cost, latency and verdicts - not letter bodies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.mail_analysis.dataset import CATEGORY_ORDER, DATASET, REQUESTS, SUPPLIERS  # noqa: E402
from mail import message_analysis as core  # noqa: E402
from mail.message_analysis import ModelReply, RouterAiAnalysisModels  # noqa: E402
from mail.repository import MailRepository  # noqa: E402

DEFAULT_CHEAP, DEFAULT_STRONG, DEFAULT_JUDGE = "mistralai/mistral-nemo", "openai/gpt-4.1-mini", "deepseek/deepseek-v4-flash"


def load_env_key() -> None:
    """Make ROUTERAI_KEY available from .env without printing it."""
    if os.getenv("ROUTERAI_KEY"):
        return
    for name in (".env", ".env.local"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.match(r"^\s*ROUTERAI_KEY\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#") and m.group(1).strip("\"'"):
                    os.environ["ROUTERAI_KEY"] = m.group(1).strip("\"'")
                    return
    raise SystemExit("ROUTERAI_KEY is not configured")


class BudgetStop(Exception):
    pass


class RecordingModels:
    """Wraps the production adapter: records every reply (raw answer included) per letter and enforces the cap."""

    def __init__(self, inner: RouterAiAnalysisModels, cap_rub: float) -> None:
        self.inner, self.cap = inner, cap_rub
        self.spent = 0.0
        self.calls = 0
        self.current = ""
        self.log: list[dict[str, Any]] = []

    def model_for(self, stage: str) -> str | None:
        return self.inner.model_for(stage)

    def call(self, stage: str, system: str, user: str, schema: dict) -> ModelReply:
        if self.spent >= self.cap:
            raise BudgetStop(f"spend cap {self.cap} rub reached")
        reply = self.inner.call(stage, system, user, schema)
        self.calls += 1
        self.spent += float(reply.cost_rub or 0.0)
        self.log.append({"letter": self.current, "stage": stage, "raw": reply.data, "reply": reply})
        return reply


# --------------------------------------------------------------------------------------------- fixture
def build_fixture(repo: MailRepository, letters: list[dict[str, Any]]) -> dict[str, Any]:
    user = repo.seed_user("benchmark@example.invalid", "correct-horse-battery")
    ws, uid = int(user["workspace_id"]), int(user["id"])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with repo.connect() as c:
        c.execute("INSERT INTO mail_accounts(user_id, workspace_id, provider, email, status, created_at, updated_at) "
                  "VALUES (?, ?, 'fake', 'buyer@example.invalid', 'connected', ?, ?)", (uid, ws, now, now))
        account = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
    reqs = {k: repo.create_request(ws, name=v, description="", positions=[{"name": v, "quantity": "1"}], sender_name="Buyer",
                                   company_name="ООО Бенчмарк", user_id=uid) for k, v in REQUESTS.items()}
    sups: dict[str, int] = {}
    for key, (email, host, req_keys) in SUPPLIERS.items():
        sups[key] = repo.upsert_supplier(workspace_id=ws, external_key=host, name=key, email=email, host=host, request_id=reqs[req_keys[0]])
        with repo.connect() as c:
            for rk in req_keys:
                c.execute("INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) "
                          "VALUES (?, ?, '[]', 'bench', 'manual', ?) ON CONFLICT DO NOTHING", (reqs[rk], sups[key], now))
    threads: dict[tuple[str, str], int] = {}
    ids: dict[str, tuple[str, int]] = {}
    with repo.connect() as c:
        for letter in letters:
            subject = re.sub(r"\[SD:([A-Z_]+)\]", lambda m: f"[SD-{reqs[m.group(1)]}]", letter["subject"])
            if letter["kind"] == "thread":
                pair = (letter["req"], letter["sup"])
                if pair not in threads:
                    c.execute("INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, "
                              "last_message_at, created_at) VALUES (?, ?, ?, ?, ?, 'Запрос', ?, ?)",
                              (ws, uid, reqs[letter["req"]], sups[letter["sup"]], account, now, now))
                    threads[pair] = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
                c.execute("INSERT INTO mail_messages(thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id, "
                          "provider_message_id, direction, from_email, to_email, subject, body_text, body_html, status, created_at, sent_at) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?, 'inbound', ?, 'buyer@example.invalid', ?, ?, '', 'received', ?, NULL)",
                          (threads[pair], ws, uid, reqs[letter["req"]], sups[letter["sup"]], account, f"bench-{letter['id']}",
                           letter["from"], subject, letter["body"], now))
                ids[letter["id"]] = ("mail_message", int(c.execute("SELECT last_insert_rowid()").fetchone()[0]))
            else:
                c.execute("INSERT INTO mail_inbox_messages(workspace_id, user_id, mail_account_id, provider_message_id, message_id, in_reply_to, "
                          "references_header, from_email, to_email, subject, body_text, body_html, received_at, status, created_at) "
                          "VALUES (?, ?, ?, ?, ?, '', '', ?, 'buyer@example.invalid', ?, ?, '', ?, 'unmatched', ?)",
                          (ws, uid, account, f"bench-{letter['id']}", f"<bench-{letter['id']}@x>", letter["from"], subject,
                           letter["body"], now, now))
                ids[letter["id"]] = ("inbox_message", int(c.execute("SELECT last_insert_rowid()").fetchone()[0]))
    return {"ws": ws, "uid": uid, "reqs": reqs, "sups": sups, "ids": ids, "account": account}


# --------------------------------------------------------------------------------------------- scoring
def _loose(s: str | None) -> str:
    return re.sub(r"[\s\-_./]+", "", (s or "").casefold())


def _same_price(a: dict, b: dict) -> bool:
    return abs(float(a["price"]) - float(b["price"])) < 0.005 and (a.get("currency") or "").upper() == (b.get("currency") or "").upper()


def match_items(expected: list[dict], actual: list[dict]) -> dict[str, int]:
    """Price/currency multiset matching and separate SKU matching."""
    pool = list(actual)
    price_tp = 0
    for e in expected:
        for a in pool:
            if _same_price(e, a):
                pool.remove(a)
                price_tp += 1
                break
    exp_skus = [_loose(e["sku"]) for e in expected if e.get("sku")]
    act_skus = [_loose(a["sku"]) for a in actual if a.get("sku")]
    sku_pool, sku_tp = list(act_skus), 0
    for s in exp_skus:
        if s in sku_pool:
            sku_pool.remove(s)
            sku_tp += 1
    return {"price_tp": price_tp, "price_fp": len(actual) - price_tp, "price_fn": len(expected) - price_tp,
            "sku_tp": sku_tp, "sku_fp": len(act_skus) - sku_tp, "sku_fn": len(exp_skus) - sku_tp}


def raw_items(raw: Any) -> list[dict]:
    """Items of a RAW model answer (before validation), tolerant of garbage."""
    out = []
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        for it in raw["items"]:
            if isinstance(it, dict) and isinstance(it.get("price"), (int, float)) and not isinstance(it.get("price"), bool):
                out.append({"sku": it.get("sku"), "price": it["price"], "currency": str(it.get("currency") or "").upper()})
    return out


def evaluate(letter: dict, res: dict, runs: list[dict], fx: dict, raws: list[dict]) -> dict[str, Any]:
    e = letter["expected"]
    ai_runs = [r for r in runs if r["provider"] != "rules"]
    facts = [{"sku": f["data"].get("sku"), "price": f["data"]["price"], "currency": f["data"]["currency"]} for f in res["facts"]]
    a = {"cls": res["message_type"], "ai": bool(ai_runs), "strong": any(r["stage"] == "strong" for r in ai_runs),
         "manual": res["status"] == "needs_review", "status": res["status"], "review_reason": res["review_reason"],
         "link": res["match_method"] or "none", "link_req": res["request_id"],
         "has_quote": res["message_type"] == "quote" and bool(facts), "items": facts}
    exp_req = fx["reqs"].get(e["link_req"]) if e["link_req"] else None
    if e["link"] in ("thread", "sd_label"):
        link_ok = a["link_req"] == exp_req and a["link"] == e["link"]
    else:
        link_ok = a["link_req"] is None
    m = match_items(e["items"], facts)
    cheap_raw = next((raw_items(x["raw"]) for x in raws if x["stage"] == "cheap"), None)
    strong_raw = next((raw_items(x["raw"]) for x in raws if x["stage"] == "strong"), None)
    ok_items = lambda items: (lambda mm: mm["price_fn"] == 0 and mm["price_fp"] == 0)(match_items(e["items"], items))  # noqa: E731
    return {
        "id": letter["id"], "cat": letter["cat"], "disputed": bool(e["dispute"]), "expected": e, "actual": a,
        "cls_ok": e["cls"] == a["cls"], "link_ok": link_ok, "items_ok": m["price_fn"] == 0 and m["price_fp"] == 0,
        "quote_ok": e["has_quote"] == a["has_quote"], "ai_ok": e["ai"] == a["ai"], "match": m,
        "cheap_raw_ok": None if cheap_raw is None else ok_items(cheap_raw),
        "strong_raw_ok": None if strong_raw is None else ok_items(strong_raw),
        "tokens": sum(r["input_tokens"] + r["output_tokens"] for r in ai_runs),
        "cost": sum(float(r["cost_rub"] or 0.0) for r in ai_runs),
        "latency_ms": sum(r["latency_ms"] for r in ai_runs), "retries": sum(r["retries"] for r in ai_runs),
        "cached_tokens": sum(r["cached_tokens"] for r in ai_runs),
        "cost_sources": sorted({r["cost_source"] for r in ai_runs}), "endpoints": sorted({r["endpoint"] for r in ai_runs if r["endpoint"]}),
        "models": sorted({r["model"] for r in ai_runs}), "run_statuses": [f"{r['stage']}:{r['status']}" for r in ai_runs],
        "run_details": [r["detail"] for r in ai_runs if r["detail"]],
    }


def prf(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None}


# --------------------------------------------------------------------------------------------- judge
JUDGE_SCHEMA = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["expected_ok", "system_ok", "both_arguable", "unclear"]},
                                                 "reason": {"type": "string"}}, "required": ["verdict", "reason"]}
JUDGE_SYSTEM = ("Ты независимый проверяющий. Тебе дают письмо, ОЖИДАЕМЫЙ результат, написанный человеком, и результат системы. "
                "Определи, кто прав: expected_ok, system_ok, both_arguable или unclear. Отвечай JSON. Не доверяй системе больше, чем человеку.")


def judge(models: RouterAiAnalysisModels, letter: dict, row: dict) -> dict[str, Any]:
    user = json.dumps({"letter_subject": letter["subject"], "letter_text": letter["body"], "expected": {
        "classification": row["expected"]["cls"], "items": row["expected"]["items"]},
        "system": {"classification": row["actual"]["cls"], "items": row["actual"]["items"]}}, ensure_ascii=False)
    reply = models.call("cheap", JUDGE_SYSTEM, user, JUDGE_SCHEMA)
    data = reply.data if isinstance(reply.data, dict) else {}
    return {"verdict": data.get("verdict", "unclear"), "reason": str(data.get("reason", ""))[:200], "cost": float(reply.cost_rub or 0.0)}


# --------------------------------------------------------------------------------------------- main
def ai_stats(rows: list[dict]) -> dict[str, Any]:
    ai = [r for r in rows if r["actual"]["ai"]]
    n = len(ai)
    return {"n": len(rows), "ai_letters": n, "avg_tokens": sum(r["tokens"] for r in ai) / n if n else 0.0,
            "avg_cost": sum(r["cost"] for r in ai) / n if n else 0.0, "avg_latency_ms": sum(r["latency_ms"] for r in ai) / n if n else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cheap", default=DEFAULT_CHEAP)
    ap.add_argument("--strong", default=DEFAULT_STRONG)
    ap.add_argument("--judge", default=DEFAULT_JUDGE)
    ap.add_argument("--budget", type=float, default=25.0)
    ap.add_argument("--tag", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--limit", type=int, default=0, help="only the first N letters (smoke test)")
    args = ap.parse_args()
    load_env_key()
    os.environ["MAIL_ANALYSIS_DAILY_BUDGET_RUB"] = str(args.budget)
    from backend.integrations.llm.routerai_client import RouterAiClient

    letters = DATASET[: args.limit] if args.limit else DATASET
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "benchmark.sqlite3"
    repo = MailRepository(db_path)
    fx = build_fixture(repo, letters)
    client = RouterAiClient()
    inner = RouterAiAnalysisModels(client, cheap_model=args.cheap, strong_model=args.strong)
    models = RecordingModels(inner, args.budget)
    ws = fx["ws"]

    rows: list[dict[str, Any]] = []
    stopped = ""
    t_start = time.time()
    for i, letter in enumerate(letters, 1):
        kind, mid = fx["ids"][letter["id"]]
        models.current = letter["id"]
        before = len(models.log)
        try:
            res = repo.analyze_message(ws, mid, kind=kind, models=models)
        except BudgetStop as exc:
            stopped = str(exc)
            break
        with repo.connect() as c:
            runs = [dict(r) for r in c.execute("SELECT * FROM mail_ai_runs WHERE analysis_id=? ORDER BY id", (res["id"],)).fetchall()]
        rows.append(evaluate(letter, res, runs, fx, models.log[before:]))
        print(f"[{i}/{len(letters)}] {letter['id']:4s} ai={'Y' if rows[-1]['actual']['ai'] else '-'} stage={res['stage']:6s} "
              f"type={res['message_type']:10s} status={res['status']:12s} spent={models.spent:.4f} rub", flush=True)

    # ---------------------------------------------------------------- idempotency on the live pipeline
    ledger_calls = lambda: repo.mail_ai_cost_report(ws)["ai_calls"]  # noqa: E731
    idem: dict[str, Any] = {}
    calls0, cost0 = models.calls, models.spent
    for letter in letters[: len(rows)]:
        kind, mid = fx["ids"][letter["id"]]
        repo.analyze_message(ws, mid, kind=kind, models=models)
    idem["rerun_pipeline"] = {"new_model_calls": models.calls - calls0, "extra_cost_rub": models.spent - cost0}
    from mail.types import IncomingMessage
    thread_letters = [x for x in letters[: len(rows)] if x["kind"] == "thread"]
    imp = repo.import_incoming_messages(workspace_id=ws, user_id=fx["uid"], account_id=fx["account"], messages=[
        IncomingMessage(provider_message_id=f"bench-{x['id']}", message_id=f"<bench-{x['id']}@x>", in_reply_to="", references="",
                        from_email=x["from"], to_email="buyer@example.invalid", subject=x["subject"], body_text=x["body"],
                        body_html="", received_at=datetime.now(timezone.utc)) for x in thread_letters])
    idem["repeat_sync"] = {"messages_offered": len(thread_letters), "imported": imp.get("imported"), "skipped_duplicates": imp.get("skipped")}
    calls1, cost1 = models.calls, models.spent
    repo2 = MailRepository(db_path)                                        # "login": a fresh process on the same database
    repo2.process_analysis_events(ws)
    for letter in letters[: len(rows)]:
        kind, mid = fx["ids"][letter["id"]]
        repo2.analyze_message(ws, mid, kind=kind, models=models)
    idem["repeat_login_new_process"] = {"new_model_calls": models.calls - calls1, "extra_cost_rub": models.spent - cost1}
    calls2, cost2 = models.calls, models.spent
    core.ANALYSIS_VERSION = "mail-extract/bench-v2"
    try:
        for letter in letters[: len(rows)]:
            kind, mid = fx["ids"][letter["id"]]
            repo.analyze_message(ws, mid, kind=kind, models=models)
        idem["new_version_without_reprocess"] = {"new_model_calls": models.calls - calls2, "extra_cost_rub": models.spent - cost2}
        calls3, cost3 = models.calls, models.spent
        pick = [x for x in letters[: len(rows)] if x["expected"]["has_quote"] and not x["expected"]["dispute"]][:3]
        for letter in pick:
            kind, mid = fx["ids"][letter["id"]]
            models.current = letter["id"]
            repo.analyze_message(ws, mid, kind=kind, models=models, reprocess=True)
        idem["explicit_reprocess_3_letters"] = {"letters": len(pick), "model_calls": models.calls - calls3, "cost_rub": models.spent - cost3}
    finally:
        core.ANALYSIS_VERSION = "mail-extract/v1"

    # ---------------------------------------------------------------- judge (mismatches + disputed only)
    judge_models = RouterAiAnalysisModels(client, cheap_model=args.judge, strong_model=None)
    judge_cost, verdicts = 0.0, {}
    by_id = {x["id"]: x for x in letters}
    for r in rows:
        needs = r["disputed"] or (r["actual"]["ai"] and (not r["items_ok"] or not r["cls_ok"]))
        if needs and models.spent + judge_cost < args.budget:
            verdicts[r["id"]] = judge(judge_models, by_id[r["id"]], r)
            judge_cost += verdicts[r["id"]]["cost"]

    # ---------------------------------------------------------------- aggregate
    scored = [r for r in rows if not r["disputed"]]
    for r in rows:
        r["correct"] = r["cls_ok"] and r["items_ok"] and r["link_ok"]
    categories = {}
    for cat in CATEGORY_ORDER:
        cr = [r for r in rows if r["cat"] == cat]
        if not cr:
            continue
        st = ai_stats(cr)
        categories[cat] = {**st, "no_ai": sum(1 for r in cr if not r["actual"]["ai"]),
                           "cheap_only": sum(1 for r in cr if r["actual"]["ai"] and not r["actual"]["strong"]),
                           "strong": sum(1 for r in cr if r["actual"]["strong"]),
                           "manual": sum(1 for r in cr if r["actual"]["manual"]),
                           "correct": sum(1 for r in cr if r["correct"] and not r["disputed"]),
                           "incorrect": sum(1 for r in cr if not r["correct"] and not r["disputed"]),
                           "disputed": sum(1 for r in cr if r["disputed"])}
    sums = Counter()
    for r in scored:
        for k, v in r["match"].items():
            sums[k] += v
    quote_tp = sum(1 for r in scored if r["expected"]["has_quote"] and r["actual"]["has_quote"])
    quote_fp = sum(1 for r in scored if not r["expected"]["has_quote"] and r["actual"]["has_quote"])
    quote_fn = sum(1 for r in scored if r["expected"]["has_quote"] and not r["actual"]["has_quote"])
    ai_rows = [r for r in rows if r["actual"]["ai"]]
    strong_rows = [r for r in ai_rows if r["actual"]["strong"]]
    total_cost = sum(r["cost"] for r in rows)
    useful = [r for r in scored if r["expected"]["has_quote"] and r["items_ok"] and r["actual"]["has_quote"]]
    cheap_costs = [r["cost"] for r in ai_rows if not r["actual"]["strong"]]
    strong_costs = [r["cost"] for r in strong_rows]
    per_received = total_cost / len(rows) if rows else 0.0
    monthly = None
    try:
        ro = sqlite3.connect(f"file:{(ROOT / 'mail-data' / 'supplier.sqlite3').as_posix()}?mode=ro", uri=True)
        monthly = ro.execute("SELECT (SELECT COUNT(*) FROM mail_messages WHERE direction='inbound' AND created_at >= date('now','-30 day')) + "
                             "(SELECT COUNT(*) FROM mail_inbox_messages WHERE created_at >= date('now','-30 day'))").fetchone()[0]
        ro.close()
    except Exception:  # noqa: BLE001
        pass
    summary = {
        "tag": args.tag, "models": {"cheap": args.cheap, "strong": args.strong, "judge": args.judge}, "budget_rub": args.budget,
        "stopped": stopped, "letters": len(rows), "disputed": sum(1 for r in rows if r["disputed"]), "seconds": round(time.time() - t_start),
        "spend_rub": {"analysis": round(models.spent, 6), "judge": round(judge_cost, 6), "total": round(models.spent + judge_cost, 6)},
        "cascade": {"no_ai": sum(1 for r in rows if not r["actual"]["ai"]), "cheap_final": sum(1 for r in ai_rows if not r["actual"]["strong"]),
                    "strong": len(strong_rows), "manual_review": sum(1 for r in rows if r["actual"]["manual"]),
                    "ai_letters": len(ai_rows), "strong_escalation_rate": len(strong_rows) / len(ai_rows) if ai_rows else 0.0,
                    "strong_justified": sum(1 for r in strong_rows if r["cheap_raw_ok"] is False and r["strong_raw_ok"]),
                    "strong_unnecessary_cheap_was_right": sum(1 for r in strong_rows if r["cheap_raw_ok"]),
                    "strong_did_not_help": sum(1 for r in strong_rows if not r["strong_raw_ok"])},
        "ai_necessity": {"unnecessary_ai_calls": sum(1 for r in scored if r["actual"]["ai"] and not r["expected"]["ai"]),
                         "missed_ai": sum(1 for r in scored if not r["actual"]["ai"] and r["expected"]["ai"])},
        "quality": {"classification": {"correct": sum(1 for r in scored if r["cls_ok"]), "of": len(scored)},
                    "request_matching": {"correct": sum(1 for r in scored if r["link_ok"]), "of": len(scored)},
                    "quote_detection": prf(quote_tp, quote_fp, quote_fn),
                    "price_extraction": prf(sums["price_tp"], sums["price_fp"], sums["price_fn"]),
                    "sku_extraction": prf(sums["sku_tp"], sums["sku_fp"], sums["sku_fn"])},
        "cost": {"per_ai_analysed_email": total_cost / len(ai_rows) if ai_rows else 0.0, "per_received_email": per_received,
                 "per_useful_result": total_cost / len(useful) if useful else None, "useful_results": len(useful),
                 "avg_cheap_only": sum(cheap_costs) / len(cheap_costs) if cheap_costs else 0.0,
                 "avg_with_strong": sum(strong_costs) / len(strong_costs) if strong_costs else 0.0,
                 "projected_1000_at_this_mix": per_received * 1000, "projected_10000_at_this_mix": per_received * 10000,
                 "projected_1000_all_ai": (total_cost / len(ai_rows) * 1000) if ai_rows else 0.0,
                 "real_workspace_inbound_last_30d": monthly,
                 "est_monthly_this_mix": per_received * monthly if monthly is not None else None,
                 "est_monthly_all_ai": (total_cost / len(ai_rows) * monthly) if ai_rows and monthly is not None else None,
                 "cost_sources": dict(Counter(s for r in ai_rows for s in r["cost_sources"])),
                 "endpoints": dict(Counter(e for r in ai_rows for e in r["endpoints"])),
                 "retries_total": sum(r["retries"] for r in ai_rows), "cached_tokens_total": sum(r["cached_tokens"] for r in ai_rows),
                 "avg_latency_ms_cheap": (sum(r["latency_ms"] for r in ai_rows if not r["actual"]["strong"]) / max(1, len(cheap_costs)))},
        "categories": categories, "idempotency": idem, "judge": Counter(v["verdict"] for v in verdicts.values()),
    }
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"mail_analysis_benchmark_{args.tag}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows, "judge": verdicts}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
    print("report:", path)
    tmp.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
