"""EDW-22: run the WHOLE unittest suite (tests/) on SQLite or on a disposable PostgreSQL, one test at a
time, and record a per-test verdict as JSON so two runs can be compared.

    python scripts/full_suite_compare.py run --backend sqlite --out tmp/full_sqlite.json
    python scripts/full_suite_compare.py run --backend pg --shard 0/4 --out tmp/full_pg_0.json
    python scripts/full_suite_compare.py compare tmp/full_sqlite.json tmp/full_pg_*.json

PostgreSQL mode gives every test its own fresh DATABASE, exactly like the SQLite mode gives
every test its own file, and refuses anything except a local database whose name contains "test".
Nothing here changes application code or business logic.
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

DEFAULT_URL = "postgresql://postgres:sdtest@127.0.0.1:55432/sdtest"


# Tests that exercise SQLite-only machinery or assume one database file per repository. They cannot pass on
# PostgreSQL for reasons that are not SQL incompatibilities of the application (EDW-22 triage).
NOT_APPLICABLE_ON_PG = {
    "test_canonical_runtime.CanonicalRuntimeTests.test_backup_writes_source_identity_and_hash_metadata":
        "SQLite file backup/identity; mail/runtime.py documents that with DATABASE_URL PostgreSQL replaces the SQLite path guard",
    "test_canonical_runtime.CanonicalRuntimeTests.test_noncanonical_runtime_blocks_before_provider":
        "SQLite canonical-path guard; not applicable when DATABASE_URL is set (mail/runtime.py)",
    "test_canonical_runtime.CanonicalRuntimeTests.test_production_runtime_owns_one_lock_and_manifest_has_no_secret":
        "manifest hashes the SQLite file (database_sha256 is None on PostgreSQL)",
    "test_mail_integrity.MailIntegrityAcceptanceTests.test_01c_bulk_http_retry_with_same_key_does_not_create_second_batch":
        "test builds two repositories expecting two database files; on PG both share one database (request 1043 belongs to the first user)",
    "test_mail_integrity.MailIntegrityAcceptanceTests.test_01ca_bulk_http_same_request_email_guard_and_explicit_repeat":
        "same two-repositories-one-database harness artifact",
    "test_mail_integrity.MailIntegrityAcceptanceTests.test_01f_bulk_http_accepts_explicit_html_content_contract":
        "same two-repositories-one-database harness artifact",
    "test_mail_pacing.MailPacingAcceptanceTests.test_p03_two_processes_sqlite_one_permission":
        "spawns two OS processes on one SQLite file",
    "test_mail_pacing.MailPacingAcceptanceTests.test_u1_uncertain_delivery_unknown_consumes_stale_reservation_on_recovery":
        "asserts tuple(row): sqlite3.Row iterates values, CompatRow (dict) iterates keys; no application code does this (audited)",
    "test_supplier_duplicates_dry_run.DryRunTest.test_connection_is_physically_read_only":
        "SQLite-file read-only script (mode=ro)",
    "test_supplier_duplicates_dry_run.DryRunTest.test_report_classifies_pairs_and_changes_nothing":
        "SQLite-file read-only script (hashes the .sqlite3 file)",
    "test_supplier_identity.SupplierIdentityTests.test_merge_preserves_request_relation_and_mail_history":
        "tests scripts/supplier_identity_audit.py, a SQLite-only CLI ([table] quoting)",
    "test_supplier_identity.SupplierIdentityTests.test_merge_rolls_back_without_losing_duplicate":
        "same SQLite-only audit CLI",
    "test_supplier_identity.SupplierIdentityTests.test_strict_scan_does_not_merge_exact_email_without_legal_identity":
        "same SQLite-only audit CLI (sqlite_master)",
}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def guard(url: str) -> None:
    p = urlparse(url)
    if p.hostname not in ("127.0.0.1", "localhost") or "test" not in (p.path or ""):
        raise SystemExit(f"REFUSED: {p.hostname}{p.path} is not a local disposable test database")


def run(args) -> int:
    url = args.url
    if args.backend == "pg":
        guard(url)
        import psycopg
        admin = psycopg.connect(url, autocommit=True)
    else:
        os.environ.pop("DATABASE_URL", None)
        admin = None
    loader = unittest.defaultTestLoader
    tests = list(flatten(loader.discover("tests", top_level_dir=".")))
    idx, n = (int(x) for x in args.shard.split("/"))
    results: dict[str, dict] = {}
    t0 = time.time()
    only = None
    if args.only_failed_in:
        only = set()
        for pattern in args.only_failed_in:
            for f in glob.glob(pattern):
                only |= {k for k, v in json.loads(Path(f).read_text(encoding="utf-8")).items() if v["status"] == "fail"}
    for i, test in enumerate(tests):
        if i % n != idx:
            continue
        tid = test.id()
        if only is not None and tid not in only:
            continue
        # One fresh DATABASE per test (not one schema): the app's migration guards look at
        # information_schema without a schema filter, so sibling schemas in one database would leak
        # into each other and produce false failures.
        dbname = f"sdtest_s{idx}_{i}"
        if admin is not None:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
            admin.execute(f'CREATE DATABASE "{dbname}"')
            os.environ["DATABASE_URL"] = urlunparse(urlparse(url)._replace(path="/" + dbname))
        buf = io.StringIO()
        started = time.time()
        res = unittest.TextTestRunner(stream=buf, verbosity=0).run(unittest.TestSuite([test]))
        if admin is not None:
            try:
                admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
            except Exception:  # noqa: BLE001 - best-effort cleanup of a disposable database
                pass
        if res.skipped:
            status = "skip"
        elif res.wasSuccessful():
            status = "pass"
        else:
            status = "fail"
        results[tid] = {"status": status, "seconds": round(time.time() - started, 2),
                        "detail": buf.getvalue()[-2500:] if status == "fail" else ""}
        if (len(results)) % 50 == 0:
            print(f"[{args.backend} shard {args.shard}] {len(results)} done, {time.time() - t0:.0f}s", flush=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {s: sum(1 for r in results.values() if r["status"] == s) for s in ("pass", "fail", "skip")}
    print(f"[{args.backend} shard {args.shard}] DONE {counts} in {time.time() - t0:.0f}s", flush=True)
    return 0


def compare(args) -> int:
    def load(patterns):
        out = {}
        for pattern in patterns:
            for f in glob.glob(pattern):
                out.update(json.loads(Path(f).read_text(encoding="utf-8")))
        return out
    a, b = load([args.sqlite]), load(args.pg)
    both = sorted(set(a) & set(b))
    only_pg_fail = [t for t in both if a[t]["status"] == "pass" and b[t]["status"] == "fail"]
    both_fail = [t for t in both if a[t]["status"] == "fail" and b[t]["status"] == "fail"]
    only_sqlite_fail = [t for t in both if a[t]["status"] == "fail" and b[t]["status"] == "pass"]
    count = lambda d: {s: sum(1 for r in d.values() if r["status"] == s) for s in ("pass", "fail", "skip")}  # noqa: E731
    na = [t for t in only_pg_fail if t.replace("tests.", "") in NOT_APPLICABLE_ON_PG]
    only_pg_fail = [t for t in only_pg_fail if t not in na]
    print("SQLite:", count(a), "PostgreSQL:", count(b), "compared:", len(both), "missing in pg:", len(set(a) - set(b)))
    print(f"not applicable on PostgreSQL (documented, not application SQL): {len(na)}")
    for t in na:
        print("  ", t.replace("tests.", ""), "--", NOT_APPLICABLE_ON_PG[t.replace("tests.", "")])
    print(f"pass on SQLite, FAIL on PostgreSQL (unexplained): {len(only_pg_fail)}")
    for t in only_pg_fail:
        print("  ", t)
    print(f"fail on both: {len(both_fail)}; fail only on SQLite: {len(only_sqlite_fail)}")
    if args.details:
        for t in only_pg_fail:
            print(f"\n=== {t}\n{b[t]['detail']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--backend", choices=["sqlite", "pg"], required=True)
    r.add_argument("--url", default=os.getenv("SD_PG_TEST_URL", DEFAULT_URL))
    r.add_argument("--shard", default="0/1")
    r.add_argument("--out", required=True)
    r.add_argument("--only-failed-in", nargs="*", default=None,
                   help="re-run only the tests that failed in these earlier result files")
    c = sub.add_parser("compare")
    c.add_argument("sqlite")
    c.add_argument("pg", nargs="+")
    c.add_argument("--details", action="store_true")
    args = ap.parse_args()
    return run(args) if args.cmd == "run" else compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
