"""E2E replay v2 (EDW-38): real mailboxes, fresh COPY of the database (tmp/e2e_v2), asynchronous analysis.

  prep2 -> rfq -> replies -> sync2 -> worker2 -> sentsync -> resync2 -> verify2        (rfq and replies are the v1 senders, unchanged)

Same rules as the first run: own mailboxes only (hard-checked), test process only for the disclosed gate overrides, no secrets printed.
Old results (results/e2e_report_pass*.json, docs/benchmarks/E2E_MAIL_BENCHMARK_20260919.md) are not rewritten.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.e2e_mail import run_e2e as E  # noqa: E402

E.WORK = ROOT / "tmp" / "e2e_v2"
E.DB = E.WORK / "e2e.sqlite3"
E.STATE = E.WORK / "state.json"


def prep2() -> None:
    from benchmarks.attachment_intelligence import catalog as C
    E.load_env()
    E.WORK.mkdir(parents=True, exist_ok=True)
    if E.DB.exists():
        E.DB.unlink()
    src = sqlite3.connect(f"file:{ROOT / 'mail-data' / 'supplier.sqlite3'}?mode=ro", uri=True)
    dst = sqlite3.connect(E.DB)
    src.backup(dst)
    src.close()
    dst.close()
    os.environ.pop("MAIL_INTELLIGENCE_ON_SYNC", None)
    repo, service = E.services()
    acc = E.accounts(repo)
    ws, user = acc[E.A_EMAIL]["workspace_id"], acc[E.A_EMAIL]["user_id"]
    for i in range(3):                                            # shift request ids so that [SD-n] of this replay differs from the first run's letters
        repo.create_request(ws, name=f"[E2E2 spacer {i}]", description="", positions=[{"name": "x", "quantity": "1"}], sender_name="E2E", company_name="E2E", user_id=user)
    st = {"workspace_id": ws, "user_id": user, "account_a": acc[E.A_EMAIL]["id"], "account_b": acc[E.B_EMAIL]["id"], "requests": {}, "variant": "v2"}
    for key in ("R1", "R2"):
        req = C.REQUESTS[key]
        rid = repo.create_request(ws, name=f"[E2E2] {req['name']}", description="E2E replay v2 (test copy)",
                                  positions=[{"name": p["name"], "quantity": f"{p['qty']} {p['unit']}"} for p in req["positions"]], sender_name="E2E", company_name="E2E", user_id=user)
        st["requests"][key] = {"id": rid, "reference": repo.get_request(ws, rid).get("email_reference"), "name": repo.get_request(ws, rid)["name"]}
    E.save(st)
    # persist-only sync (flag OFF): advances both mailbox cursors past the history of the first run so that only replay letters are new
    with repo.connect() as c:
        c.execute("UPDATE mail_runtime_controls SET outgoing_enabled=1 WHERE id=1")
    for name in ("account_a", "account_b"):
        r = service.sync_incoming(user, ws, max_messages=500, mail_account_id=st[name])
        print(json.dumps({"baseline_sync": name, **{k: r.get(k) for k in ("scanned", "imported", "unmatched", "skipped")}}))
    print(json.dumps(st["requests"], ensure_ascii=False))


def _counts(repo) -> dict:
    with repo.connect() as c:
        q = lambda sql: c.execute(sql).fetchone()[0]
        return {"analyses": q("SELECT COUNT(*) FROM mail_analyses"), "attachment_analyses": q("SELECT COUNT(*) FROM mail_attachment_analyses"),
                "jobs": q("SELECT COUNT(*) FROM mail_analysis_jobs"), "jobs_done": q("SELECT COUNT(*) FROM mail_analysis_jobs WHERE status='done'"),
                "reply_cache": q("SELECT COUNT(*) FROM mail_ai_reply_cache"), "runs": q("SELECT COUNT(*) FROM mail_ai_runs WHERE provider<>'rules'"),
                "facts": q("SELECT COUNT(*) FROM mail_facts"), "att_facts": q("SELECT COUNT(*) FROM mail_attachment_facts")}


def sync2() -> None:
    os.environ["MAIL_INTELLIGENCE_ON_SYNC"] = "1"
    repo, service = E.services()
    st = E.state()
    wanted = {v["message_id"] for v in st["sent"].values()}
    before = _counts(repo)
    t0 = time.time()
    runs = []
    for attempt in range(1, 9):
        r = service.sync_incoming(st["user_id"], st["workspace_id"], max_messages=500, mail_account_id=st["account_a"])
        with repo.connect() as c:
            have = {x[0] for x in c.execute("SELECT message_id FROM mail_messages WHERE mail_account_id=? UNION SELECT message_id FROM mail_inbox_messages WHERE mail_account_id=?", (st["account_a"], st["account_a"])).fetchall()}
        runs.append({"attempt": attempt, "seconds": round(time.time() - t0, 2), **{k: r.get(k) for k in ("scanned", "imported", "unmatched", "skipped", "analysis_jobs_enqueued")}, "arrived": len(wanted & have)})
        print(json.dumps(runs[-1]))
        if wanted <= have:
            break
        time.sleep(15)
    st["sync2"] = {"runs": runs, "sync_seconds": round(time.time() - t0, 2), "before": before, "after": _counts(repo)}
    E.save(st)
    print(json.dumps(st["sync2"]))


def worker2() -> None:
    os.environ["MAIL_INTELLIGENCE_ON_SYNC"] = "1"
    repo, _service = E.services()
    st = E.state()
    results: list = []
    t0 = time.time()
    threads = [threading.Thread(target=lambda n=n: results.append(repo.run_analysis_jobs(n, workspace_id=st["workspace_id"], limit=100))) for n in ("worker-1", "worker-2")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    st["worker2"] = {"seconds": round(time.time() - t0, 2), "results": [{k: v for k, v in r.items() if k != "jobs"} for r in results],
                     "jobs": sorted([j for r in results for j in r["jobs"]], key=lambda j: j["job"]), "counts": _counts(repo)}
    E.save(st)
    print(json.dumps({k: v for k, v in st["worker2"].items() if k != "jobs"}, ensure_ascii=False))


def _objects(repo, ids) -> dict:
    out = {}
    with repo.connect() as c:
        for mid in ids:
            out[mid] = sum(c.execute(f"SELECT COUNT(*) FROM {t} WHERE message_id=?", (mid,)).fetchone()[0] for t in ("mail_messages", "mail_inbox_messages", "mail_sent_messages"))
    return out


def sentsync() -> None:
    """sync_sent of BOTH mailboxes (A -> B RFQs live in A's Sent, B -> A replies live in B's Sent)."""
    repo, service = E.services()
    st = E.state()
    ids = [v["message_id"] for v in st["sent"].values()] + [r["rfq_message_id"] for r in st["requests"].values()]
    with repo.connect() as c:
        suppliers_before = c.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        sent_rows_before = c.execute("SELECT COUNT(*) FROM mail_sent_messages").fetchone()[0]
        total_before = c.execute("SELECT (SELECT COUNT(*) FROM mail_messages)+(SELECT COUNT(*) FROM mail_inbox_messages)+(SELECT COUNT(*) FROM mail_sent_messages)").fetchone()[0]
    before = _objects(repo, ids)
    out = {"objects_before": before, "runs": []}
    for side in ("account_a", "account_b"):
        for _ in range(6):
            r = service.sync_sent(st["user_id"], st["workspace_id"], mail_account_id=st[side], confirmed=True, max_messages=25)
            out["runs"].append({"side": side, **{k: r.get(k) for k in ("scanned", "imported", "linked", "history_imported", "skipped", "conflicts", "invalid")}})
            if int(r.get("scanned") or 0) < 25:
                break
    out["objects_after"] = _objects(repo, ids)
    with repo.connect() as c:
        out["suppliers_added"] = c.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] - suppliers_before
        out["sent_rows_added"] = c.execute("SELECT COUNT(*) FROM mail_sent_messages").fetchone()[0] - sent_rows_before
        out["objects_added_total"] = c.execute("SELECT (SELECT COUNT(*) FROM mail_messages)+(SELECT COUNT(*) FROM mail_inbox_messages)+(SELECT COUNT(*) FROM mail_sent_messages)").fetchone()[0] - total_before
    st["sentsync"] = out
    E.save(st)
    print(json.dumps({k: v for k, v in out.items() if not k.startswith("objects_b") and not k.startswith("objects_a") or k == "objects_added_total"}, ensure_ascii=False))
    print("objects per test Message-ID (expected 1 each):", sorted(set(out["objects_after"].values())))


def resync2() -> None:
    os.environ["MAIL_INTELLIGENCE_ON_SYNC"] = "1"
    repo, service = E.services()
    st = E.state()
    before = _counts(repo)
    ra = service.sync_incoming(st["user_id"], st["workspace_id"], max_messages=500, mail_account_id=st["account_a"])
    rb = service.sync_incoming(st["user_id"], st["workspace_id"], max_messages=500, mail_account_id=st["account_b"])
    enq = repo.enqueue_missing_analysis_jobs(st["workspace_id"])
    w = repo.run_analysis_jobs("worker-3", workspace_id=st["workspace_id"], limit=100)
    st["resync2"] = {"sync_A": {k: ra.get(k) for k in ("scanned", "imported", "unmatched", "skipped")}, "sync_B": {k: rb.get(k) for k in ("scanned", "imported", "unmatched", "skipped")},
                     "reconcile_enqueued": enq, "worker": {k: v for k, v in w.items() if k != "jobs"}, "before": before, "after": _counts(repo)}
    E.save(st)
    print(json.dumps(st["resync2"], ensure_ascii=False))


def verify2() -> None:
    from benchmarks.e2e_mail.scenarios_v2 import GLOBAL_EXPECT, SCENARIOS
    repo, _service = E.services()
    st = E.state()
    truth = {f["id"]: f for f in json.loads((ROOT / "benchmarks" / "attachment_intelligence" / "ground_truth.json").read_text(encoding="utf-8"))["files"]}
    r1 = st["requests"]["R1"]["id"]
    report = []
    with repo.connect() as c:
        for sc in SCENARIOS:
            ex, sent = sc["expect"], st["sent"][sc["id"]]
            checks: dict = {}
            kind, ident, req, copies = E._locate(c, sent["message_id"])
            checks["received_imported_once"] = (copies == 1, f"rows={copies}")
            an = c.execute("SELECT * FROM mail_analyses WHERE message_kind=? AND message_id=? ORDER BY id DESC LIMIT 1", (kind, ident)).fetchone() if kind else None
            linked = req if kind == "mail_message" else (an["request_id"] if an else None)
            want = r1 if sc["request"] == "R1" else None
            checks["request_linking"] = (linked == want, f"linked={linked} expected={want}")
            if sc["route"] == "thread":
                checks["thread_by_headers"] = (kind == "mail_message", f"stored as {kind}")
            facts = [dict(f) for f in c.execute("SELECT * FROM mail_facts WHERE message_kind=? AND message_id=? AND state='proposed'", (kind, ident))] if kind else []
            prices = sorted(json.loads(f["data_json"]).get("price") for f in facts)
            want_prices = sorted(p if not isinstance(p, tuple) else p[1] for p in ex["body_facts"])
            want_prices = sorted(x[1] if isinstance(x, (tuple, list)) else x for x in ex["body_facts"])
            checks["body_facts"] = (prices == want_prices, f"got={prices} expected={want_prices}")
            scoped = [f for f in facts if f["request_id"] is not None]
            checks["request_scoped_facts"] = (len(scoped) == ex["request_scoped_facts"], f"scoped={len(scoped)} expected={ex['request_scoped_facts']}")
            for bad in ex.get("forbidden_prices", []):
                checks["forbidden_price_absent"] = (bad not in prices, f"forbidden={bad}")
            runs = [dict(r) for r in c.execute("SELECT * FROM mail_ai_runs WHERE analysis_id=?", (an["id"],)).fetchall()] if an else []
            model_runs = [r for r in runs if r["provider"] != "rules"]
            checks["body_ai_calls"] = (len(model_runs) <= ex["body_ai_calls_max"], f"calls={len(model_runs)} max={ex['body_ai_calls_max']}")
            if "message_type" in ex:
                checks["message_type"] = (bool(an) and an["message_type"] == ex["message_type"], f"type={an['message_type'] if an else None} expected={ex['message_type']}")
            if "message_type_not" in ex:
                checks["message_type_not_quote"] = (bool(an) and an["message_type"] != ex["message_type_not"], f"type={an['message_type'] if an else None}")
            att_rows = [dict(r) for r in c.execute("SELECT * FROM mail_attachment_analyses WHERE message_id=?", (ident,)).fetchall()] if kind == "mail_message" else []
            att_facts = [dict(r) for r in c.execute("SELECT * FROM mail_attachment_facts WHERE message_id=?", (ident,)).fetchall()] if kind == "mail_message" else []
            manual = bool(an and an["status"] == "needs_review") or any(r["manual_review"] for r in att_rows)
            checks["manual_review_decision"] = (manual == ex["manual_review"], f"got={manual} expected={ex['manual_review']} reason={an['review_reason'] if an else None}")
            if ex.get("must_not_link"):
                checks["not_linked"] = (linked is None, f"linked={linked}")
            if ex.get("irrelevant"):
                checks["irrelevant_recognised"] = (bool(an) and an["message_type"] in ("newsletter", "other") and not model_runs, f"type={an['message_type'] if an else None}")
            if ex["attachments"]:
                want_lines = [l for fid in ex["attachments"] for l in truth[fid]["lines"] if l["price"] is not None]
                got = sorted(round(json.loads(f["data_json"])["price"], 2) for f in att_facts if json.loads(f["data_json"]).get("price") is not None)
                exp = sorted({round(l["price"], 2) for l in want_lines} if ex.get("confirmed_by_two_sources") else [round(l["price"], 2) for l in want_lines])
                gotset = sorted(set(got)) if ex.get("confirmed_by_two_sources") else got
                checks["attachment_facts_extracted"] = (gotset == exp, f"facts={len(got)} expected={len(exp)}")
                checks["provenance_saved"] = (bool(att_facts) and all(f["loc_json"] not in ("", "{}", "null") for f in att_facts), f"facts={len(att_facts)}")
                checks["attachment_processed"] = (len(att_rows) == len(ex["attachments"]) and all(r["status"] == "ok" for r in att_rows), f"rows={len(att_rows)}")
            if "attachment_reuse" in ex:
                reused = sum(1 for r in att_rows if r["reused_from"] is not None)
                checks["attachment_reuse"] = (reused == ex["attachment_reuse"], f"reused={reused} expected={ex['attachment_reuse']}")
            if "attachment_ai_calls" in ex:
                checks["attachment_ai_calls"] = (sum(r["ai_calls"] for r in att_rows) <= ex["attachment_ai_calls"], "")
            checks["cost_and_latency_recorded"] = (all(r["cost_rub"] is not None and (r["latency_ms"] or 0) > 0 for r in model_runs) and all(r["latency_ms"] is not None for r in att_rows), f"runs={len(model_runs)}")
            report.append({"scenario": sc["id"], "title": sc["title"], "passed": all(v[0] for v in checks.values()), "ai_calls": len(model_runs),
                           "checks": {k: {"ok": v[0], "detail": v[1]} for k, v in checks.items()}})
        # global checks
        ids = [v["message_id"] for v in st["sent"].values()] + [r["rfq_message_id"] for r in st["requests"].values()]
        dup_messages = sum(1 for n in _objects(repo, ids).values() if n != 1)
        dup_facts = c.execute("SELECT COUNT(*) FROM (SELECT analysis_id, position FROM mail_facts GROUP BY analysis_id, position HAVING COUNT(*)>1) x").fetchone()[0]
        dup_facts += c.execute("SELECT COUNT(*) FROM (SELECT message_id, position, data_json FROM mail_attachment_facts GROUP BY message_id, position HAVING COUNT(*)>1) x").fetchone()[0]
        dup_facts += c.execute("SELECT COUNT(*) FROM (SELECT message_kind, message_id, analysis_version FROM mail_analyses a JOIN mail_facts f ON f.analysis_id=a.id WHERE f.state='proposed' GROUP BY message_kind, message_id, analysis_version, a.id HAVING COUNT(DISTINCT a.id)>1) x").fetchone()[0]
        paid = c.execute("SELECT COUNT(*), COALESCE(SUM(cost_rub),0) FROM mail_ai_reply_cache").fetchone()
        replays = c.execute("SELECT COALESCE(SUM(replays),0) FROM mail_ai_reply_cache").fetchone()[0]
        cost_runs = c.execute("SELECT COALESCE(SUM(cost_rub),0) FROM mail_ai_runs WHERE provider<>'rules'").fetchone()[0]
        dup_ai = c.execute("SELECT COUNT(*) FROM (SELECT request_key FROM mail_ai_reply_cache GROUP BY workspace_id, request_key HAVING COUNT(*)>1) x").fetchone()[0]
        repeat_runs = c.execute("SELECT COUNT(*) FROM mail_ai_runs WHERE repeat_of_same_content=1 AND provider<>'rules'").fetchone()[0]
        job_states = dict(c.execute("SELECT status, COUNT(*) FROM mail_analysis_jobs GROUP BY status").fetchall())
    s2, w2, rs, ss = st["sync2"], st["worker2"], st["resync2"], st["sentsync"]
    glob = {
        "sync_does_no_analysis": (s2["after"]["analyses"] == s2["before"]["analyses"] and s2["after"]["attachment_analyses"] == s2["before"]["attachment_analyses"] and s2["after"]["reply_cache"] == s2["before"]["reply_cache"],
                                  f"analyses {s2['before']['analyses']}->{s2['after']['analyses']}, attachment analyses {s2['before']['attachment_analyses']}->{s2['after']['attachment_analyses']}, model replies {s2['before']['reply_cache']}->{s2['after']['reply_cache']}"),
        "jobs_enqueued_for_persisted_messages": (s2["after"]["jobs"] - s2["before"]["jobs"] >= 20, f"jobs {s2['before']['jobs']}->{s2['after']['jobs']}"),
        "worker_finishes_all_jobs": (job_states.get("queued", 0) + job_states.get("running", 0) + job_states.get("failed", 0) == 0, f"states={job_states}"),
        "two_workers_no_lost_claims": (all(r["lost_claim"] == 0 for r in w2["results"]), f"workers={[(r['worker'], r['done']) for r in w2['results']]}"),
        "duplicate_ai_calls": (dup_ai == 0 and repeat_runs == 0, f"duplicate request keys={dup_ai}, repeat runs={repeat_runs}, replays={replays}"),
        "duplicated_messages": (dup_messages == 0, f"messages with !=1 object={dup_messages}"),
        "duplicated_facts": (dup_facts == 0, f"duplicates={dup_facts}"),
        "second_sync_and_worker_no_new_work": (rs["sync_A"]["imported"] == 0 and rs["sync_A"]["unmatched"] == 0 and rs["worker"]["model_calls"] == 0 and rs["after"]["reply_cache"] == rs["before"]["reply_cache"] and rs["after"]["facts"] == rs["before"]["facts"],
                                               f"A={rs['sync_A']} B={rs['sync_B']} worker_calls={rs['worker']['model_calls']}"),
        "sent_sync_A_and_B_no_new_objects": (ss["objects_added_total"] == 0 and ss["suppliers_added"] == 0 and all(n == 1 for n in ss["objects_after"].values()),
                                              f"added_total={ss['objects_added_total']} suppliers_added={ss['suppliers_added']} sent_rows_added={ss['sent_rows_added']}"),
        "total_cost_within_cap": (paid[1] <= GLOBAL_EXPECT["max_total_cost_rub"], f"cost={round(paid[1], 5)} rub"),
    }
    summary = {"scenarios_passed": sum(r["passed"] for r in report), "scenarios": len(report), "ai_calls_paid": paid[0], "replays": replays, "duplicated_messages": dup_messages,
               "duplicated_facts": dup_facts, "total_cost_rub": round(paid[1], 6), "ledger_cost_rub": round(cost_runs, 6), "total_sync_seconds": s2["sync_seconds"],
               "async_analysis_seconds": w2["seconds"], "worker_jobs": {r["worker"]: r["done"] for r in w2["results"]}, "sentsync_runs": ss["runs"]}
    st["verify2"] = {"scenarios": report, "global": {k: {"ok": v[0], "detail": v[1]} for k, v in glob.items()}, "summary": summary}
    E.save(st)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "e2e_report_v2.json").write_text(json.dumps(st["verify2"], ensure_ascii=False, indent=1), encoding="utf-8")
    for r in report:
        print(("PASS " if r["passed"] else "FAIL ") + r["scenario"] + " " + r["title"] + f"  (ai_calls={r['ai_calls']})")
        for k, v in r["checks"].items():
            if not v["ok"]:
                print("     x", k, "-", v["detail"])
    for k, v in glob.items():
        print(("PASS " if v[0] else "FAIL ") + "GLOBAL " + k + " - " + v[1])
    print(json.dumps(summary, ensure_ascii=False))


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    {"prep2": prep2, "rfq": E.rfq, "replies": E.replies, "sync2": sync2, "worker2": worker2, "sentsync": sentsync, "resync2": resync2, "verify2": verify2}.get(stage, lambda: sys.exit("stages: prep2 rfq replies sync2 worker2 sentsync resync2 verify2"))()


if __name__ == "__main__":
    main()
