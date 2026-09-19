"""EDW-20: PostgreSQL gate for the supplier identity / evidence / merge work.

Runs against a DISPOSABLE PostgreSQL only (default: the docker container `sd-pg-test` on
127.0.0.1:55432). Refuses anything that is not localhost or that does not look like a test
database, so production DATABASE_URL can never be used by accident.

Phases:
  scratch  every migration from zero in an empty schema
  replay   ensure_schema() again on the same schema (the app replays migrations on every start)
  upgrade  schema built only up to migration 052 (pre-EDW state) with data -> apply 053-056 -> data intact
  tests    a chosen set of unittest modules, EACH TEST in its own fresh schema (real PostgreSQL)
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_URL = "postgresql://postgres:sdtest@127.0.0.1:55432/sdtest"
TEST_MODULES = [
    "tests.test_supplier_identity_evidence",
    "tests.test_contact_evidence_single_source",
    "tests.test_supplier_merge",
    "tests.test_supplier_merge_review",
    "tests.test_identity_vs_quality",
    "tests.test_mail_analysis_core",
    "tests.test_mail_analysis_validation",
    "tests.test_attachment_persistence",
    "tests.test_analysis_queue",
    "tests.test_canary",
    "tests.test_canary_shadow",
    "tests.test_supplier_dedup_p0_regression",
    "tests.test_contact_intelligence",
    "tests.test_contact_resolution_send_path",
]
# SQLite-file specific by design (opens the .sqlite3 file directly / PRAGMA introspection).
SQLITE_ONLY = {"RegistryCoverageTest"}


def guard(url: str) -> None:
    parsed = urlparse(url)
    if parsed.hostname not in ("127.0.0.1", "localhost") or "test" not in (parsed.path or ""):
        raise SystemExit(f"REFUSED: {parsed.hostname}{parsed.path} is not a local disposable test database")


def admin(url: str):
    import psycopg
    return psycopg.connect(url, autocommit=True)


def schema_url(url: str, schema: str) -> str:
    return f"{url}?options={quote('-csearch_path=' + schema)}"


def fresh_schema(url: str, name: str) -> str:
    with admin(url) as c:
        c.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
        c.execute(f'CREATE SCHEMA "{name}"')
    return schema_url(url, name)


def drop_schema(url: str, name: str) -> None:
    with admin(url) as c:
        c.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')


def make_repo(db_url: str, migration_limit: int | None = None):
    from mail.repository import MailRepository
    os.environ["DATABASE_URL"] = db_url
    repo = MailRepository.__new__(MailRepository)
    repo.database_url = db_url
    repo.db_path = Path("pg-gate.sqlite3").resolve()
    paths = sorted((ROOT / "migrations").glob("*.sql"))
    repo.migration_paths = [p for p in paths if migration_limit is None or int(p.name[:3]) <= migration_limit]
    repo.ensure_schema()
    return repo


def table_names(url: str, schema: str) -> set[str]:
    with admin(url) as c:
        return {r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s", (schema,))}


def phase_scratch_replay(url: str) -> bool:
    ok = True
    db = fresh_schema(url, "g_scratch")
    t0 = time.time()
    repo = make_repo(db)
    print(f"[scratch] all migrations applied from zero in {time.time() - t0:.1f}s; tables={len(table_names(url, 'g_scratch'))}")
    need = {"supplier_identity_evidence", "canonical_company_contact_signal_revocations", "supplier_merges",
            "supplier_merge_moves", "supplier_merge_candidates", "mail_analyses", "mail_ai_runs", "mail_facts", "mail_analysis_events",
            "mail_attachment_analyses", "mail_attachment_facts", "mail_attachment_ai_calls", "mail_analysis_jobs", "mail_ai_reply_cache",
            "mail_inbox_attachments", "mail_fact_bindings", "mail_intelligence_canary", "mail_intelligence_stop_events",
            "mail_intelligence_queue_samples", "mail_intelligence_metric_snapshots", "mail_intelligence_canary_flags", "mail_intelligence_audit"}
    missing = need - table_names(url, "g_scratch")
    print(f"[scratch] new tables present: {sorted(need - missing)}; missing={sorted(missing)}")
    ok &= not missing
    for i in (1, 2, 3):
        repo.ensure_schema()
    fresh = make_repo(db)  # a new process start = another replay
    print("[replay] ensure_schema x3 + new repository start on the same schema: OK")
    with admin(url) as c:  # constraints really exist
        n = c.execute("SELECT count(*) FROM pg_indexes WHERE schemaname='g_scratch' AND indexname IN "
                      "('uq_supplier_identity_evidence_fact','idx_supplier_merge_moves_merge','uq_mail_analysis_jobs_key','uq_mail_attachment_analyses_key','uq_mail_intelligence_metric_snapshots','uq_mail_intelligence_audit_key')").fetchone()[0]
    print(f"[replay] indexes present={n}/6")
    ok &= n == 6
    drop_schema(url, "g_scratch")
    return ok


def phase_upgrade(url: str) -> bool:
    db = fresh_schema(url, "g_upgrade")
    repo = make_repo(db, migration_limit=52)
    before = table_names(url, "g_upgrade")
    assert "supplier_identity_evidence" not in before
    user = repo.seed_user("upgrade@example.com", "correct-horse")
    rid = repo.create_request(user["workspace_id"], name="Заявка", description="", positions=[{"name": "P", "quantity": "1"}],
                              sender_name="B", company_name="ООО", user_id=user["id"])
    # Raw SQL on purpose: the NEW code is never run on the OLD schema (ensure_schema runs at startup,
    # before any request is served), so pre-upgrade data must be created without the new mixins.
    with repo.connect() as c:
        c.execute("INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at) "
                  "VALUES (%s, 'a.example', 'a', '', 'a.example', 'x', 'x')" % user["workspace_id"])
        sid = int(c.execute("SELECT id FROM suppliers WHERE external_key='a.example'").fetchone()[0])
        c.execute("INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) "
                  "VALUES (%s, %s, '[]', 'x', 'manual', 'x')" % (rid, sid))
    with repo.connect() as c:
        rows_before = c.execute("SELECT (SELECT count(*) FROM suppliers), (SELECT count(*) FROM requests), (SELECT count(*) FROM request_suppliers)").fetchone()
    upgraded = make_repo(db)  # now 053-055 on top of the existing, populated schema
    with upgraded.connect() as c:
        rows_after = c.execute("SELECT (SELECT count(*) FROM suppliers), (SELECT count(*) FROM requests), (SELECT count(*) FROM request_suppliers)").fetchone()
    added = table_names(url, "g_upgrade") - before
    print(f"[upgrade] existing data before={tuple(dict(rows_before).values())} after={tuple(dict(rows_after).values())}; tables added={sorted(added)}")
    ok = tuple(dict(rows_before).values()) == tuple(dict(rows_after).values()) and {"supplier_identity_evidence", "supplier_merges"} <= added
    upgraded.confirm_supplier_contact(user["workspace_id"], user["id"], sid, "someone@example.com", request_id=rid)
    print("[upgrade] new evidence API works on the upgraded schema")
    drop_schema(url, "g_upgrade")
    return ok


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def phase_tests(url: str, modules: list[str]) -> bool:
    loader = unittest.defaultTestLoader
    tests = [t for m in modules for t in flatten(loader.loadTestsFromName(m))]
    passed = failed = skipped = 0
    failures: list[tuple[str, str]] = []
    for n, test in enumerate(tests):
        cls = type(test).__name__
        if cls in SQLITE_ONLY:
            skipped += 1
            continue
        schema = f"t{n}"
        os.environ["DATABASE_URL"] = fresh_schema(url, schema)
        buf = io.StringIO()
        result = unittest.TextTestRunner(stream=buf, verbosity=0).run(unittest.TestSuite([test]))
        drop_schema(url, schema)
        if result.wasSuccessful():
            passed += 1
        else:
            failed += 1
            failures.append((test.id(), buf.getvalue()))
    print(f"[tests] PostgreSQL: run={len(tests) - skipped} passed={passed} failed={failed} skipped(sqlite-only)={skipped}")
    for name, out in failures:
        print(f"--- FAIL {name}\n{out[-1800:]}")
    return failed == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("SD_PG_TEST_URL", DEFAULT_URL))
    parser.add_argument("--phase", choices=["scratch", "upgrade", "tests", "all"], default="all")
    parser.add_argument("--modules", nargs="*", default=TEST_MODULES)
    args = parser.parse_args()
    guard(args.url)
    ok = True
    if args.phase in ("scratch", "all"):
        ok &= phase_scratch_replay(args.url)
    if args.phase in ("upgrade", "all"):
        ok &= phase_upgrade(args.url)
    if args.phase in ("tests", "all"):
        ok &= phase_tests(args.url, args.modules)
    print("GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
