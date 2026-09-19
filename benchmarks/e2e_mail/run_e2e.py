"""Real-mailbox end-to-end run (EDW-31). Works on a COPY of the local database (tmp/e2e/e2e.sqlite3): the owner's live data is never written.

  python -m benchmarks.e2e_mail.run_e2e prep      copy DB, create two test requests + one test supplier (no network)
  python -m benchmarks.e2e_mail.run_e2e rfq       send the two RFQs A -> B through the production send path (REAL e-mail, own mailboxes only)
  python -m benchmarks.e2e_mail.run_e2e replies   B -> A letters of scenarios.py through the real provider (REAL e-mail, own mailboxes only)
  python -m benchmarks.e2e_mail.run_e2e sync      production sync_incoming on A with MAIL_INTELLIGENCE_ON_SYNC=1 (real IMAP)
  python -m benchmarks.e2e_mail.run_e2e resync    second sync + reanalysis + sync of B (idempotency, double objects)

Mailbox A = the buyer account connected to SupplyDesk (yandex), mailbox B = the "supplier" (mail.ru). Only these two addresses are ever used.
Secrets are read from .env into the process environment and are never printed or written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
WORK = ROOT / "tmp" / "e2e"
DB = WORK / "e2e.sqlite3"
STATE = WORK / "state.json"
A_EMAIL, B_EMAIL = "edwatik@yandex.ru", "edwatik@mail.ru"
ALLOWED = {A_EMAIL, B_EMAIL}


def load_env() -> None:
    for name in (".env", ".env.local"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#"):
                    os.environ.setdefault(m.group(1), m.group(2).strip("\"'"))
    os.environ["MAIL_DB_PATH"] = str(DB)
    os.environ["SUPPLYDESK_ENV"] = ""              # owner-approved: production runtime gate lifted for this TEST process on the copy only (disclosed in the report)
    os.environ["MAIL_OUTGOING_DISABLED"] = "0"     # owner-approved, THIS process only; .env and the live DB are untouched; recipients are hard-checked below


def state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save(st: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def services():
    load_env()
    from backend.app_config import yandex_provider_factory
    from mail.deliverability import RolloutSettings
    from mail.pacing import PacingSettings
    from mail.repository import MailRepository
    from mail.service import MailService
    repo = MailRepository(DB)
    service = MailService(repo, yandex_provider_factory, os.getenv("MAIL_TOKEN_ENCRYPTION_KEY"), daily_limit=250,
                          pacing_settings=PacingSettings.from_env(), rollout_settings=RolloutSettings.from_env(), campaign_max_recipients=50)
    return repo, service


def accounts(repo) -> dict[str, dict]:
    with repo.connect() as c:
        rows = [dict(r) for r in c.execute("SELECT id, user_id, workspace_id, provider, email FROM mail_accounts WHERE lower(email) IN (?, ?)", (A_EMAIL, B_EMAIL)).fetchall()]
    return {r["email"].lower(): r for r in rows}


def prep() -> None:
    from benchmarks.attachment_intelligence import catalog as C
    load_env()
    WORK.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    src = sqlite3.connect(f"file:{ROOT / 'mail-data' / 'supplier.sqlite3'}?mode=ro", uri=True)
    dst = sqlite3.connect(DB)
    src.backup(dst)
    src.close()
    dst.close()
    repo, _service = services()
    acc = accounts(repo)
    assert set(acc) == ALLOWED, acc
    ws, user = acc[A_EMAIL]["workspace_id"], acc[A_EMAIL]["user_id"]
    with repo.connect() as c:                                     # the copy only: allow sending from A in the test database
        cols = [r[1] for r in c.execute("PRAGMA table_info(mail_accounts)").fetchall()]
    st = {"workspace_id": ws, "user_id": user, "account_a": acc[A_EMAIL]["id"], "account_b": acc[B_EMAIL]["id"], "requests": {}}
    for key, rid in (("R1", "R1"), ("R2", "R2")):
        req = C.REQUESTS[rid]
        request_id = repo.create_request(ws, name=f"[E2E] {req['name']}", description="E2E benchmark (test copy)",
                                         positions=[{"name": p["name"], "quantity": f"{p['qty']} {p['unit']}"} for p in req["positions"]],
                                         sender_name="E2E", company_name="E2E", user_id=user)
        info = repo.get_request(ws, request_id)
        st["requests"][key] = {"id": request_id, "reference": info.get("email_reference"), "name": info["name"]}
    save(st)
    print(json.dumps({"prepared": True, "account_cols": [c for c in cols if "outgoing" in c], **{k: v for k, v in st.items() if k != "requests"}, "requests": st["requests"]}, ensure_ascii=False))


def rfq() -> None:
    """Production send path: queue_one -> claim_job -> send_claimed_job -> mark_job_sent. Only A -> B."""
    repo, service = services()
    assert Path(repo.db_path).resolve() == DB.resolve(), "REFUSED: not the test copy"
    with repo.connect() as c:                                     # durable switch of the COPY (the live database keeps its own)
        c.execute("UPDATE mail_runtime_controls SET outgoing_enabled=1 WHERE id=1")
    st = state()
    ws, user = st["workspace_id"], st["user_id"]
    for key, req in st["requests"].items():
        if req.get("rfq_message_id"):
            continue
        subject = f"Запрос цены: {req['name']} [{req['reference']}]"
        service.queue_one(user_id=user, workspace_id=ws, request_id=req["id"],
                          supplier={"name": "E2E Поставщик (тест)", "email": B_EMAIL, "host": "mail.ru"},
                          subject=subject, body="Добрый день! Просим прислать коммерческое предложение по позициям заявки. (E2E-тест, письмо между собственными ящиками)",
                          idempotency_key=f"e2e-rfq-{key}-{req['id']}", mail_account_id=st["account_a"])
        job = repo.claim_job()
        assert job is not None, "no job claimed"
        assert str(job.get("to_email") or "").lower() in ALLOWED, "REFUSED: recipient is not one of the two test mailboxes"
        result = service.send_claimed_job(job)
        repo.mark_job_sent(job["id"], job["message_id"], None, result.message_id, result.sent_at.isoformat())
        req.update({"rfq_message_id": result.message_id, "rfq_subject": subject, "rfq_db_message_id": job["message_id"], "rfq_sent_at": result.sent_at.isoformat()})
        save(st)
        print(json.dumps({"sent": key, "message_id": result.message_id}, ensure_ascii=False))


def replies() -> None:
    """B -> A: the scenario letters, sent through the real provider of mailbox B (the 'supplier'). Resumable."""
    import uuid
    from benchmarks.e2e_mail.scenarios import SCENARIOS
    from mail.types import Attachment, OutgoingMessage
    repo, service = services()
    assert Path(repo.db_path).resolve() == DB.resolve(), "REFUSED: not the test copy"
    st = state()
    truth = json.loads((ROOT / "benchmarks" / "attachment_intelligence" / "ground_truth.json").read_text(encoding="utf-8"))
    files = {f["id"]: f["file"] for f in truth["files"]}
    account, token = service._get_account_and_token(st["user_id"], st["workspace_id"], mail_account_id=st["account_b"])
    assert account["email"].lower() == B_EMAIL
    provider = service._provider_for_account(account, token)
    r1, r2 = st["requests"]["R1"], st["requests"]["R2"]
    sent = st.setdefault("sent", {})
    for sc in SCENARIOS:
        if sc["id"] in sent:
            continue
        subject = sc["subject"].replace("{RFQ_R1}", r1["rfq_subject"]).replace("{REF_R1}", f"[{r1['reference']}]")
        message_id = f"<e2e-{sc['id'].lower()}-{uuid.uuid4().hex[:12]}@mail.ru>"
        in_reply_to = references = None
        if sc["headers"] in ("thread", "chain"):
            in_reply_to = r1["rfq_message_id"]
            references = r1["rfq_message_id"]
        if sc["headers"] == "chain":
            prev = sent["S10"]["message_id"]
            in_reply_to, references = prev, f"{r1['rfq_message_id']} {prev}"
        atts = []
        for fid, name in sc.get("attach", []):
            path = ROOT / "benchmarks" / "attachment_intelligence" / "fixtures" / "files" / files[fid]
            mime = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[path.suffix.lstrip(".")]
            atts.append(Attachment(filename=name, mime_type=mime, content=path.read_bytes()))
        message = OutgoingMessage(from_email=B_EMAIL, to_email=A_EMAIL, subject=subject, body_text=sc["body"], body_html="", message_id=message_id,
                                  in_reply_to=in_reply_to, references=references, attachments=atts)
        assert message.to_email in ALLOWED and message.from_email in ALLOWED, "REFUSED: address outside the two test mailboxes"
        t0 = time.time()
        result = provider.send_message(token, message)
        sent[sc["id"]] = {"message_id": result.message_id, "subject": subject, "sent_at": result.sent_at.isoformat(), "send_seconds": round(time.time() - t0, 2)}
        save(st)
        print(json.dumps({"sent": sc["id"], "s": sent[sc["id"]]["send_seconds"]}))
        time.sleep(4)


def sync() -> None:
    """The production sync of mailbox A, analysis under the feature flag, polled until all test letters arrived."""
    os.environ["MAIL_INTELLIGENCE_ON_SYNC"] = "1"
    repo, service = services()
    assert Path(repo.db_path).resolve() == DB.resolve(), "REFUSED: not the test copy"
    st = state()
    wanted = {v["message_id"] for v in st["sent"].values()}
    runs = st.setdefault("sync_runs", [])
    for attempt in range(1, 9):
        t0 = time.time()
        result = service.sync_incoming(st["user_id"], st["workspace_id"], max_messages=500, mail_account_id=st["account_a"])
        with repo.connect() as c:
            have = {r[0] for r in c.execute("SELECT message_id FROM mail_messages WHERE mail_account_id=? UNION SELECT message_id FROM mail_inbox_messages WHERE mail_account_id=?",
                                            (st["account_a"], st["account_a"])).fetchall()}
        runs.append({"attempt": attempt, "seconds": round(time.time() - t0, 1), "scanned": result.get("scanned"), "imported": result.get("imported"),
                     "unmatched": result.get("unmatched"), "skipped": result.get("skipped"), "arrived": len(wanted & have),
                     "analysis_items": len(result.get("analysis") or [])})
        save(st)
        print(json.dumps(runs[-1], ensure_ascii=False))
        if wanted <= have:
            break
        time.sleep(15)


def _locate(c, mid: str):
    m = c.execute("SELECT id, request_id FROM mail_messages WHERE message_id=?", (mid,)).fetchall()
    i = c.execute("SELECT id FROM mail_inbox_messages WHERE message_id=?", (mid,)).fetchall()
    if m:
        return "mail_message", int(m[0]["id"]), m[0]["request_id"], len(m) + len(i)
    if i:
        return "inbox_message", int(i[0]["id"]), None, len(i)
    return None, None, None, 0


def verify() -> None:
    """Every scenario against the expectations committed before sending. Read-only on the test copy."""
    from benchmarks.e2e_mail.scenarios import SCENARIOS
    repo, _service = services()
    st = state()
    truth = {f["id"]: f for f in json.loads((ROOT / "benchmarks" / "attachment_intelligence" / "ground_truth.json").read_text(encoding="utf-8"))["files"]}
    r1 = st["requests"]["R1"]["id"]
    report = []
    with repo.connect() as c:
        for sc in SCENARIOS:
            ex, sent = sc["expect"], st["sent"][sc["id"]]
            checks: dict[str, tuple[bool, str]] = {}
            kind, ident, req, copies = _locate(c, sent["message_id"])
            checks["received_and_imported_exactly_once"] = (copies == 1, f"rows={copies}")
            an = c.execute("SELECT * FROM mail_analyses WHERE message_kind=? AND message_id=? ORDER BY id DESC LIMIT 1", (kind, ident)).fetchone() if kind else None
            linked = (req if kind == "mail_message" else (an["request_id"] if an else None))
            want = r1 if sc["request"] == "R1" else None
            checks["request_linking"] = (linked == want, f"linked={linked} expected={want} route={sc['route']} method={an['match_method'] if an else None}")
            if sc["route"] == "thread":
                checks["thread_by_headers"] = (kind == "mail_message", f"stored as {kind}")
            body_prices = sorted(json.loads(r["data_json"]).get("price") for r in c.execute("SELECT data_json FROM mail_facts WHERE message_kind=? AND message_id=? AND state='proposed'", (kind, ident))) if kind else []
            att_rows = [dict(r) for r in c.execute("SELECT * FROM mail_attachment_analyses WHERE message_id=?", (ident,)).fetchall()] if kind == "mail_message" else []
            att_facts = [dict(r) for r in c.execute("SELECT * FROM mail_attachment_facts WHERE message_id=?", (ident,)).fetchall()] if kind == "mail_message" else []
            manual = bool(an and an["status"] == "needs_review") or any(r["manual_review"] for r in att_rows)
            want_prices = sorted(p for _, p in ex["body_facts"])
            checks["body_facts"] = (body_prices == want_prices, f"got={body_prices} expected={want_prices}")
            for bad in ex.get("forbidden_prices", []):
                checks["forbidden_price_absent"] = (bad not in body_prices, f"forbidden={bad}")
            runs = [dict(r) for r in c.execute("SELECT * FROM mail_ai_runs WHERE analysis_id=?", (an["id"],)).fetchall()] if an else []
            model_runs = [r for r in runs if r["provider"] != "rules"]
            checks["body_ai_calls"] = (len(model_runs) <= ex["body_ai_calls_max"], f"calls={len(model_runs)} max={ex['body_ai_calls_max']}")
            checks["manual_review_decision"] = (manual == ex["manual_review"], f"got={manual} expected={ex['manual_review']} reason={an['review_reason'] if an else None}")
            if ex.get("irrelevant"):
                checks["irrelevant_recognised"] = (bool(an) and an["message_type"] in ("newsletter", "other") and not model_runs, f"type={an['message_type'] if an else None}")
            if ex.get("must_not_link"):
                checks["not_linked"] = (linked is None, f"linked={linked}")
            if ex["attachments"]:
                want_lines = [l for fid in ex["attachments"] for l in truth[fid]["lines"] if l["price"] is not None]
                got = sorted(round(json.loads(f["data_json"])["price"], 2) for f in att_facts if json.loads(f["data_json"]).get("price") is not None)
                exp = sorted({round(l["price"], 2) for l in want_lines} if ex.get("confirmed_by_two_sources") else [round(l["price"], 2) for l in want_lines])
                gotset = sorted(set(got)) if ex.get("confirmed_by_two_sources") else got
                must_not = {round(m["value"], 2) for fid in ex["attachments"] for m in truth[fid]["must_not_extract"]} - set(exp)
                checks["attachment_facts_extracted"] = (gotset == exp, f"facts={len(got)} expected_lines={len(exp)} missing={sorted(set(exp) - set(got))[:4]} extra={sorted(set(got) - set(exp))[:4]}")
                checks["attachment_no_forbidden_numbers"] = (not (set(got) & must_not), f"hit={sorted(set(got) & must_not)}")
                checks["provenance_saved"] = (bool(att_facts) and all(f["loc_json"] not in ("", "{}", "null") for f in att_facts), f"facts={len(att_facts)}")
                checks["attachment_processed"] = (len(att_rows) == len(ex["attachments"]) and all(r["status"] == "ok" for r in att_rows), f"rows={len(att_rows)} status={[r['status'] for r in att_rows]}")
            if "attachment_reuse" in ex:
                reused = sum(1 for r in att_rows if r["reused_from"] is not None)
                checks["attachment_reuse"] = (reused == ex["attachment_reuse"], f"reused={reused} expected={ex['attachment_reuse']}")
            if "attachment_ai_calls" in ex:
                calls = sum(r["ai_calls"] for r in att_rows)
                checks["attachment_ai_calls"] = (calls <= ex["attachment_ai_calls"], f"calls={calls}")
            checks["cost_and_latency_recorded"] = (all(r["cost_rub"] is not None and (r["latency_ms"] or 0) > 0 for r in model_runs) and all(r["latency_ms"] is not None for r in att_rows),
                                                  f"model_runs={len(model_runs)} cost={[round(r['cost_rub'] or 0, 5) for r in model_runs]} latency_ms={[r['latency_ms'] for r in model_runs]}")
            report.append({"scenario": sc["id"], "title": sc["title"], "passed": all(v[0] for v in checks.values()),
                           "checks": {k: {"ok": v[0], "detail": v[1]} for k, v in checks.items()},
                           "body_cost_rub": round(sum(r["cost_rub"] or 0 for r in runs), 6), "body_latency_ms": sum(r["latency_ms"] for r in runs),
                           "attachment_latency_ms": sum(r["latency_ms"] for r in att_rows), "attachment_cost_rub": round(sum(r["cost_rub"] for r in att_rows), 6)})
    st["verify"] = report
    save(st)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "e2e_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in report:
        print(("PASS " if r["passed"] else "FAIL ") + r["scenario"] + " " + r["title"])
        for k, v in r["checks"].items():
            if not v["ok"]:
                print("     x", k, "-", v["detail"])
    print("passed", sum(r["passed"] for r in report), "of", len(report), "| body cost", round(sum(r["body_cost_rub"] for r in report), 5), "rub, attachments cost", round(sum(r["attachment_cost_rub"] for r in report), 5))


def resync() -> None:
    """Second production sync of A, re-analysis of every test message, and a production sync of B (double-object check)."""
    os.environ["MAIL_INTELLIGENCE_ON_SYNC"] = "1"
    repo, service = services()
    assert Path(repo.db_path).resolve() == DB.resolve(), "REFUSED: not the test copy"
    st = state()
    ids = [v["message_id"] for v in st["sent"].values()] + [r["rfq_message_id"] for r in st["requests"].values()]
    out: dict = {}

    def count_rows() -> dict:
        with repo.connect() as c:
            marks = ",".join("?" * len(ids))
            return {"mail_messages": c.execute(f"SELECT COUNT(*) FROM mail_messages WHERE message_id IN ({marks})", ids).fetchone()[0],
                    "mail_inbox_messages": c.execute(f"SELECT COUNT(*) FROM mail_inbox_messages WHERE message_id IN ({marks})", ids).fetchone()[0],
                    "analyses": c.execute("SELECT COUNT(*) FROM mail_analyses").fetchone()[0], "runs": c.execute("SELECT COUNT(*) FROM mail_ai_runs WHERE provider<>'rules'").fetchone()[0],
                    "att_analyses": c.execute("SELECT COUNT(*) FROM mail_attachment_analyses").fetchone()[0], "att_facts": c.execute("SELECT COUNT(*) FROM mail_attachment_facts").fetchone()[0],
                    "attachments": c.execute("SELECT COUNT(*) FROM mail_attachments").fetchone()[0]}

    out["before"] = count_rows()
    r = service.sync_incoming(st["user_id"], st["workspace_id"], max_messages=500, mail_account_id=st["account_a"])
    out["second_sync_A"] = {k: r.get(k) for k in ("scanned", "imported", "unmatched", "skipped")}
    out["after_second_sync"] = count_rows()
    ai_body = ai_att = 0
    with repo.connect() as c:
        mids = [(r["id"], "mail_message") for r in c.execute("SELECT id FROM mail_messages WHERE message_id IN (%s)" % ",".join("?" * len(ids)), ids)]
        mids += [(r["id"], "inbox_message") for r in c.execute("SELECT id FROM mail_inbox_messages WHERE message_id IN (%s)" % ",".join("?" * len(ids)), ids)]
    for mid, kind in mids:
        try:
            res = repo.analyze_message(st["workspace_id"], mid, kind=kind, models=repo._default_analysis_models())
            ai_body += int(res.get("ai_calls") or 0)
        except Exception as exc:  # noqa: BLE001
            out.setdefault("errors", []).append(f"{kind}:{mid}:{type(exc).__name__}")
        if kind == "mail_message":
            try:
                ai_att += repo.analyze_message_attachments(st["workspace_id"], mid)["ai_calls"]
            except ValueError:
                pass
    out["reanalysis"] = {"body_ai_calls": ai_body, "attachment_ai_calls": ai_att, "after": count_rows()}
    b = service.sync_incoming(st["user_id"], st["workspace_id"], max_messages=500, mail_account_id=st["account_b"])
    out["sync_B"] = {k: b.get(k) for k in ("scanned", "imported", "unmatched", "skipped")}
    out["after_sync_B"] = count_rows()
    with repo.connect() as c:
        out["rfq_objects"] = [dict(zip(("message_id", "table", "account"), row)) for row in c.execute(
            "SELECT message_id, 'mail_messages', mail_account_id FROM mail_messages WHERE message_id IN (?, ?) UNION ALL SELECT message_id, 'mail_inbox_messages', mail_account_id FROM mail_inbox_messages WHERE message_id IN (?, ?)",
            [r["rfq_message_id"] for r in st["requests"].values()] * 2).fetchall()]
    st["resync"] = out
    save(st)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def pass2() -> None:
    """After the two production fixes found in pass 1 (subject terms, same-workspace copy): re-analyse under the new analysis version
    (no re-sending) and repeat the sync of B against real IMAP with B's sync cursor rewound over the two RFQs."""
    os.environ["MAIL_INTELLIGENCE_ON_SYNC"] = "1"
    repo, service = services()
    assert Path(repo.db_path).resolve() == DB.resolve(), "REFUSED: not the test copy"
    st = state()
    rfqs = [r["rfq_message_id"] for r in st["requests"].values()]
    marks = ",".join("?" * len(rfqs))
    with repo.connect() as c:                                     # remove pass-1 double objects (and their analyses) from the COPY
        ids = [r[0] for r in c.execute(f"SELECT id FROM mail_inbox_messages WHERE mail_account_id=? AND message_id IN ({marks})", [st["account_b"], *rfqs]).fetchall()]
        for i in ids:
            c.execute("DELETE FROM mail_analyses WHERE message_kind='inbox_message' AND message_id=?", (i,))
        c.execute(f"DELETE FROM mail_inbox_messages WHERE mail_account_id=? AND message_id IN ({marks})", [st["account_b"], *rfqs])
    out = {"removed_pass1_double_objects": len(ids)}
    ai = 0
    with repo.connect() as c:
        targets = [(r["id"], "mail_message") for r in c.execute("SELECT id FROM mail_messages WHERE direction='inbound' AND message_id IN (%s)" % ",".join("?" * 20), [v["message_id"] for v in st["sent"].values()])]
        targets += [(r["id"], "inbox_message") for r in c.execute("SELECT id FROM mail_inbox_messages WHERE message_id IN (%s)" % ",".join("?" * 20), [v["message_id"] for v in st["sent"].values()])]
    models = repo._default_analysis_models()
    for mid, kind in targets:
        res = repo.analyze_message(st["workspace_id"], mid, kind=kind, models=models, reprocess=True)
        ai += int(res.get("ai_calls") or 0)
    out["reprocess"] = {"messages": len(targets), "model_calls": ai}
    state_b = repo.get_mail_sync_state(st["account_b"]) or {}
    repo.save_mail_sync_state(st["account_b"], uidvalidity=state_b.get("uidvalidity"), last_uid=max(0, int(state_b.get("last_uid") or 0) - 2), imported_count=0, unmatched_count=0)
    b = service.sync_incoming(st["user_id"], st["workspace_id"], max_messages=500, mail_account_id=st["account_b"])
    out["sync_B_after_fix"] = {k: b.get(k) for k in ("scanned", "imported", "unmatched", "skipped")}
    with repo.connect() as c:
        out["rfq_objects_after_fix"] = c.execute(f"SELECT (SELECT COUNT(*) FROM mail_messages WHERE message_id IN ({marks})) + (SELECT COUNT(*) FROM mail_inbox_messages WHERE message_id IN ({marks}))", rfqs + rfqs).fetchone()[0]
        out["expected_objects"] = len(rfqs)
    st["pass2"] = out
    save(st)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage == "prep":
        prep()
    elif stage == "rfq":
        rfq()
    elif stage == "replies":
        replies()
    elif stage == "sync":
        sync()
    elif stage == "verify":
        verify()
    elif stage == "resync":
        resync()
    elif stage == "pass2":
        pass2()
    else:
        raise SystemExit("stages: prep | rfq | replies | sync | resync")


if __name__ == "__main__":
    main()
