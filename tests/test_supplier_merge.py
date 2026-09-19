"""EDW-16: reversible supplier merge/unmerge -- no data loss, exact rollback, guards,
tenant isolation, redirect of the merged card, and coverage of every supplier-referencing table."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mail.repository import MailRepository
from mail.supplier_merge import _TABLES
from tests.test_contact_intelligence import _Fixture

INN_A, INN_B = "7707083893", "7736207543"
PERSONAL = "ivanov.petr@yandex.ru"


def _snapshot(repo: MailRepository, workspace_id: int) -> dict:
    """Every supplier-related row of one workspace, in a comparable form."""
    out: dict = {}
    with repo.connect() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM suppliers WHERE workspace_id=?", (workspace_id,)).fetchall()]
        out["suppliers"] = [dict(r) for r in c.execute("SELECT * FROM suppliers WHERE workspace_id=? ORDER BY id", (workspace_id,)).fetchall()]
        for spec in _TABLES:
            marks = ",".join("?" * len(ids)) or "NULL"
            rows = c.execute(f"SELECT * FROM {spec['table']} WHERE supplier_id IN ({marks})", ids).fetchall()
            out[spec["table"]] = sorted((sorted(dict(r).items()) for r in rows), key=repr)
    return out


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "merge.sqlite3")
        self.fx = _Fixture(self.repo, "merge-a@example.com")
        self.ws, self.uid = self.fx.workspace_id, self.fx.user_id
        self.req = self.fx.create_request()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def card(self, fx: _Fixture, req: int, host: str, email: str, inn: str = "") -> int:
        """A supplier card with a thread, an outbound RFQ and an inbound reply (optionally with an INN)."""
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.repo.connect() as c:
            c.execute("INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?)", (fx.workspace_id, host, host, email, host, now, now))
            sid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
            c.execute("INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) "
                      "VALUES (?, ?, '[]', 'x', 'manual', ?)", (req, sid, now))
            c.execute("INSERT INTO supplier_profiles(supplier_id, inn, updated_at) VALUES (?, ?, ?)", (sid, inn, now))
            if inn:
                c.execute("INSERT INTO global_suppliers(workspace_id, inn, name, email, created_at, updated_at) "
                          "VALUES (?, ?, ?, ?, ?, ?)", (fx.workspace_id, inn, host, email, now, now))
                gid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
                c.execute("INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?)", (sid, gid))
            c.execute("INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, "
                      "last_message_at, created_at) VALUES (?, ?, ?, ?, ?, 'Запрос', ?, ?)",
                      (fx.workspace_id, fx.user_id, req, sid, fx.account_id, now, now))
            c.execute("INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, updated_at) "
                      "VALUES (?, ?, ?, 'sent', ?)", (req, sid, fx.account_id, now))
            c.execute("INSERT INTO mail_thread_workspace_notes(workspace_id, request_id, supplier_id, author_user_id, note, "
                      "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (fx.workspace_id, req, sid, fx.user_id, f"заметка {host}", now, now))
        when = datetime.now(timezone.utc)
        fx.send_outbound(request_id=req, supplier_id=sid, to_email=email, sent_at=when)
        fx.receive_inbound(request_id=req, supplier_id=sid, from_email=email, received_at=when)
        return sid


class MergeUnmergeRoundTripTest(_Base):
    def test_merge_then_unmerge_restores_the_exact_previous_state(self) -> None:
        a = self.card(self.fx, self.req, "termo-sfera.pro", "info@termo-sfera.pro")
        b = self.card(self.fx, self.req, "ivanov.local", PERSONAL)   # same request: overlapping keys
        self.repo.backfill_email_evidence_from_messages(self.ws)
        before = _snapshot(self.repo, self.ws)

        merged = self.repo.merge_suppliers(self.ws, self.uid, a, b, reason="один поставщик", confirm_unknown_inn=True)
        self.assertGreater(merged["moved_rows"] + merged["set_aside_rows"], 0)
        mid = _snapshot(self.repo, self.ws)
        self.assertNotEqual(before, mid)

        result = self.repo.unmerge_supplier(self.ws, self.uid, merged["merge_id"])
        self.assertEqual(result["diverged"], 0)
        self.assertEqual(_snapshot(self.repo, self.ws), before)   # byte-for-byte the same rows

    def test_after_merge_nothing_is_lost_and_everything_is_under_the_survivor(self) -> None:
        a = self.card(self.fx, self.req, "termo-sfera.pro", "info@termo-sfera.pro")
        b = self.card(self.fx, self.req, "ivanov.local", PERSONAL)
        with self.repo.connect() as c:
            total = c.execute("SELECT COUNT(*) FROM mail_messages WHERE supplier_id IN (?, ?)", (a, b)).fetchone()[0]
        self.repo.backfill_email_evidence_from_messages(self.ws)
        self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mail_messages WHERE supplier_id=?", (a,)).fetchone()[0], total)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mail_messages WHERE supplier_id=?", (b,)).fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mail_threads WHERE request_id=? AND supplier_id IN (?, ?)",
                                       (self.req, a, b)).fetchone()[0], 1)          # threads merged, messages re-parented
            self.assertEqual(c.execute("SELECT COUNT(*) FROM request_suppliers WHERE request_id=?", (self.req,)).fetchone()[0], 1)
        # the merged card's address is now a known, confirmed contact of the survivor
        self.assertEqual(self.repo.contact_state(self.ws, PERSONAL), {"email": PERSONAL, "state": "confirmed", "supplier_ids": [a], "identity_confidence": "strong"})

    def test_merged_card_can_never_be_resurrected_as_a_second_identity(self) -> None:
        a = self.card(self.fx, self.req, "termo-sfera.pro", "info@termo-sfera.pro")
        b = self.card(self.fx, self.req, "ivanov.local", PERSONAL)
        self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        self.assertEqual(self.repo.upsert_supplier(workspace_id=self.ws, external_key="ivanov.local", name="x", email="", host="ivanov.local", request_id=self.req), a)
        again = self.repo.resolve_supplier_for_send(workspace_id=self.ws, request_id=self.req, supplier_id=None, email=PERSONAL,
                                                    name="", host="", external_key="", user_id=self.uid)
        self.assertEqual(again["supplier_id"], a)
        # sending to the survivor with the merged card's address is accepted (it is its confirmed contact)
        sent = self.repo.resolve_supplier_for_send(workspace_id=self.ws, request_id=self.req, supplier_id=a, email=PERSONAL,
                                                   name="", host="", external_key="", user_id=self.uid)
        self.assertEqual(sent["supplier_id"], a)
        ids = [r["supplier_id"] for r in self.repo.list_supplier_directory(self.ws) if r.get("supplier_id")]
        self.assertNotIn(b, ids)

    def test_merge_again_after_unmerge_and_double_operations_are_refused(self) -> None:
        a = self.card(self.fx, self.req, "termo-sfera.pro", "info@termo-sfera.pro")
        b = self.card(self.fx, self.req, "ivanov.local", PERSONAL)
        m = self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        with self.assertRaises(ValueError):
            self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)   # already merged
        self.repo.unmerge_supplier(self.ws, self.uid, m["merge_id"])
        with self.assertRaises(ValueError):
            self.repo.unmerge_supplier(self.ws, self.uid, m["merge_id"])                    # already reverted
        self.assertIsNotNone(self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True))

    def test_unmerge_is_refused_while_the_survivor_itself_is_merged_away(self) -> None:
        a = self.card(self.fx, self.req, "a.example", "a@a.example")
        b = self.card(self.fx, self.req, "b.example", "b@b.example")
        c = self.card(self.fx, self.req, "c.example", "c@c.example")
        first = self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        self.repo.merge_suppliers(self.ws, self.uid, c, a, confirm_unknown_inn=True)
        with self.assertRaises(ValueError):
            self.repo.unmerge_supplier(self.ws, self.uid, first["merge_id"])


class InnGuardTest(_Base):
    def test_different_confirmed_inn_is_refused_even_with_manual_override(self) -> None:
        a = self.card(self.fx, self.req, "a.example", "a@a.example", INN_A)
        b = self.card(self.fx, self.req, "b.example", "b@b.example", INN_B)
        before = _snapshot(self.repo, self.ws)
        for override in (False, True):
            with self.assertRaises(ValueError):
                self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=override)
        self.assertEqual(_snapshot(self.repo, self.ws), before)     # nothing changed
        self.assertEqual(self.repo.list_supplier_merges(self.ws), [])

    def test_unknown_inn_needs_explicit_confirmation(self) -> None:
        a = self.card(self.fx, self.req, "a.example", "a@a.example", INN_A)
        b = self.card(self.fx, self.req, "b.example", "b@b.example")          # no INN
        with self.assertRaises(ValueError):
            self.repo.merge_suppliers(self.ws, self.uid, a, b)
        self.assertEqual(self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)["inn_verdict"], "unknown")

    def test_same_inn_needs_no_override(self) -> None:
        a = self.card(self.fx, self.req, "a.example", "a@a.example")
        b = self.card(self.fx, self.req, "b.example", "b@b.example")
        with self.repo.connect() as c:          # both cards carry the same confirmed INN (one global card)
            gid = c.execute("SELECT id FROM global_suppliers LIMIT 1").fetchone()
            now = "2026-01-01T00:00:00+00:00"
            c.execute("INSERT INTO global_suppliers(workspace_id, inn, name, email, created_at, updated_at) VALUES (?, ?, 'g', '', ?, ?)",
                      (self.ws, INN_A, now, now))
            g = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
            for sid in (a, b):
                c.execute("UPDATE supplier_profiles SET inn=? WHERE supplier_id=?", (INN_A, sid))
            c.execute("INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?)", (a, g))
            c.execute("INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?)", (b, g))
        self.assertEqual(self.repo.merge_suppliers(self.ws, self.uid, a, b)["inn_verdict"], "same_company")


class TenantIsolationTest(_Base):
    def test_cannot_merge_or_unmerge_across_workspaces_and_other_tenant_data_is_untouched(self) -> None:
        other = _Fixture(self.repo, "merge-b@example.com")
        oreq = other.create_request()
        oa = self.card(other, oreq, "a.example", "a@a.example")
        ob = self.card(other, oreq, "b.example", "b@b.example")
        a = self.card(self.fx, self.req, "termo-sfera.pro", "info@termo-sfera.pro")
        b = self.card(self.fx, self.req, "ivanov.local", PERSONAL)
        other_before = _snapshot(self.repo, other.workspace_id)

        with self.assertRaises(ValueError):                                 # foreign supplier as survivor / merged
            self.repo.merge_suppliers(self.ws, self.uid, a, ob, confirm_unknown_inn=True)
        with self.assertRaises(ValueError):
            self.repo.merge_suppliers(self.ws, self.uid, oa, b, confirm_unknown_inn=True)

        merged = self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        self.assertEqual(_snapshot(self.repo, other.workspace_id), other_before)
        with self.assertRaises(ValueError):                                 # another tenant cannot roll it back
            self.repo.unmerge_supplier(other.workspace_id, other.user_id, merged["merge_id"])
        self.repo.unmerge_supplier(self.ws, self.uid, merged["merge_id"])
        self.assertEqual(_snapshot(self.repo, other.workspace_id), other_before)
        self.assertEqual(self.repo.list_supplier_merges(other.workspace_id), [])


class AtomicityAndTransactionSafetyTest(_Base):
    """A failed merge leaves NOTHING behind (also on PostgreSQL, where a failed SQL statement aborts the
    transaction), and no probe may leave a PostgreSQL transaction in the aborted state."""

    def _pair(self):
        a = self.card(self.fx, self.req, "termo-sfera.pro", "info@termo-sfera.pro")
        b = self.card(self.fx, self.req, "ivanov.local", PERSONAL)
        return a, b

    def test_a_python_error_midway_rolls_the_whole_merge_back(self) -> None:
        a, b = self._pair()
        before = _snapshot(self.repo, self.ws)
        original = self.repo._merge_log
        calls = {"n": 0}

        def boom(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 5:
                raise RuntimeError("simulated crash midway")
            return original(*args, **kwargs)

        self.repo._merge_log = boom
        with self.assertRaises(RuntimeError):
            self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        self.repo._merge_log = original
        self.assertEqual(_snapshot(self.repo, self.ws), before)
        self.assertEqual(self.repo.list_supplier_merges(self.ws), [])
        self.assertIsNotNone(self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True))  # still works

    def test_a_sql_error_midway_rolls_back_and_the_next_operation_is_not_poisoned(self) -> None:
        a, b = self._pair()
        before = _snapshot(self.repo, self.ws)
        original = self.repo._merge_table
        calls = {"n": 0}

        def bad_sql(connection, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 3:
                connection.execute("SELECT * FROM table_that_does_not_exist")   # real SQL error
            return original(connection, *args, **kwargs)

        self.repo._merge_table = bad_sql
        with self.assertRaises(Exception):
            self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        self.repo._merge_table = original
        self.assertEqual(_snapshot(self.repo, self.ws), before)
        self.assertEqual(self.repo.list_supplier_merges(self.ws), [])

    def test_table_exists_never_raises_and_never_aborts_the_transaction(self) -> None:
        from mail.supplier_merge import _table_exists
        with self.repo.connect() as c:
            self.assertTrue(_table_exists(c, "suppliers"))
            self.assertFalse(_table_exists(c, "table_that_does_not_exist"))
            # the same connection/transaction must still be usable afterwards
            self.assertEqual(c.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] >= 0, True)

    def test_preview_is_read_only_and_predicts_the_merge(self) -> None:
        a, b = self._pair()
        before = _snapshot(self.repo, self.ws)
        preview = self.repo.preview_merge_suppliers(self.ws, a, b)
        self.assertEqual(_snapshot(self.repo, self.ws), before)
        self.assertEqual(preview["inn_verdict"], "unknown")
        merged = self.repo.merge_suppliers(self.ws, self.uid, a, b, confirm_unknown_inn=True)
        planned = sum(t["would_move"] + t["would_set_aside"] for t in preview["plan"].values())
        # the merge additionally records the merged card's address as evidence (a ledger 'insert'), not a moved row
        self.assertEqual(planned, merged["moved_rows"] + merged["set_aside_rows"])


class RegistryCoverageTest(unittest.TestCase):
    def test_every_table_with_a_supplier_foreign_key_is_handled_by_merge(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            MailRepository(Path(d) / "cov.sqlite3")
            c = sqlite3.connect(Path(d) / "cov.sqlite3")
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            referencing = set()
            for t in tables:
                for fk in c.execute(f"PRAGMA foreign_key_list({t})"):
                    if fk[2] == "suppliers":
                        referencing.add(t)
            c.close()
        # supplier_merges/moves point at suppliers by design (the ledger itself), not data to move.
        missing = referencing - {s["table"] for s in _TABLES} - {"supplier_merges", "supplier_merge_candidates"}
        self.assertEqual(missing, set(), "new supplier-referencing table: add it to mail/supplier_merge.py::_TABLES")


if __name__ == "__main__":
    unittest.main()
