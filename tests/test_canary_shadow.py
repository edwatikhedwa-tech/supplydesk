"""EDW-40 shadow mode: the canary observes, it does not act. Downstream business state must not change; audit records are safe and complete."""

from __future__ import annotations

import hashlib
import json
import unittest
from datetime import UTC, datetime, timedelta

from mail import canary_shadow as SH
from mail.message_analysis import FOLLOWUP_TASK_TITLE
from tests.test_attachment_intelligence import QUOTE, xlsx
from tests.test_canary import CanaryBase, EchoModels, iso

BUSINESS_TABLES = ("tasks", "requests", "request_positions", "request_suppliers", "request_supplier_states", "suppliers", "global_supplier_links", "supplier_identity_evidence",
                   "canonical_company_contact_signals", "supplier_merges")


class ShadowBase(CanaryBase):
    def setUp(self) -> None:
        super().setUp()
        with self.repo.connect() as c:
            link = c.execute("SELECT global_supplier_id FROM global_supplier_links WHERE supplier_id=?", (self.supplier,)).fetchone()
        self.global_supplier = link["global_supplier_id"]
        self.followup = self.repo.create_or_refresh_followup_task(self.ws, self.fx.user_id, request_id=self.req, supplier_id=self.global_supplier, title=FOLLOWUP_TASK_TITLE)["task_id"]
        self.enable()

    def business_snapshot(self) -> str:
        parts = []
        with self.repo.connect() as c:
            for t in BUSINESS_TABLES:
                try:
                    rows = [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()]
                except Exception:  # noqa: BLE001 - a table that does not exist in this schema has no state to change
                    continue
                parts.append(f"{t}:{rows!r}")
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def followup_done(self) -> int:
        with self.repo.connect() as c:
            return int(c.execute("SELECT done FROM tasks WHERE id=?", (self.followup,)).fetchone()["done"])

    def work(self, models=None):
        return self.repo.canary_tick(self.ws, "w1", models=models or EchoModels())


class ShadowDownstreamTest(ShadowBase):
    def test_canary_shadow_analysis_quote_detected_facts_persisted_downstream_business_state_unchanged(self) -> None:
        self.receive(self.price_body(1), received=self.started + timedelta(minutes=1))       # a quote arrives in a thread with an open follow-up
        before = self.business_snapshot()
        self.assertEqual(self.followup_done(), 0)
        out = self.work()
        self.assertEqual(out["findings"], [])
        with self.repo.connect() as c:
            analysis = c.execute("SELECT status, message_type, request_id, supplier_id FROM mail_analyses").fetchone()
            facts = c.execute("SELECT state, request_id, supplier_id, source_quote FROM mail_facts").fetchall()
            events = c.execute("SELECT COUNT(*) AS n FROM mail_analysis_events").fetchone()["n"]
            suppressed = c.execute("SELECT COUNT(*) AS n FROM mail_intelligence_audit WHERE kind='event_suppressed'").fetchone()["n"]
        self.assertEqual((analysis["status"], analysis["message_type"]), ("final", "quote"))            # quote detected
        self.assertEqual([(f["state"], f["request_id"]) for f in facts], [("proposed", self.req)])       # fact persisted, non-production status, provenance kept
        self.assertTrue(facts[0]["source_quote"])
        self.assertEqual((events, suppressed), (0, 1))                                                    # no quote_received; the suppression itself is audited
        self.assertEqual(self.followup_done(), 0)                                                         # follow-up NOT closed
        self.assertEqual(self.repo.process_analysis_events(self.ws), {"events_handled": 0, "tasks_closed": 0, "suppressed_shadow": 1})
        self.assertEqual(self.business_snapshot(), before)                                                # requests, suppliers, contacts, tasks: unchanged

    def test_the_same_scenario_without_shadow_mode_does_close_the_follow_up_so_the_test_is_not_vacuous(self) -> None:
        with self.repo.connect() as c:
            c.execute("INSERT INTO mail_intelligence_canary_flags(workspace_id, downstream_enabled, updated_at) VALUES (?, 1, 'x')", (self.ws,))
        self.receive(self.price_body(2), received=self.started + timedelta(minutes=1))
        self.work()
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_analysis_events").fetchone()["n"], 1)
        self.assertEqual(self.repo.process_analysis_events(self.ws)["tasks_closed"], 1)
        self.assertEqual(self.followup_done(), 1)

    def test_an_existing_event_is_not_processed_in_shadow_mode(self) -> None:
        self.receive(self.price_body(3), received=self.started + timedelta(minutes=1))
        self.work()
        with self.repo.connect() as c:
            aid = c.execute("SELECT id FROM mail_analyses").fetchone()["id"]
            c.execute("INSERT INTO mail_analysis_events(workspace_id, analysis_id, event_type, payload_json, created_at) VALUES (?, ?, 'quote_received', ?, 'x')",
                      (self.ws, aid, json.dumps({"request_id": self.req, "supplier_id": self.supplier, "facts": 1})))
        self.assertEqual(self.repo.process_analysis_events(self.ws)["tasks_closed"], 0)
        self.assertEqual(self.followup_done(), 0)
        self.assertIn("downstream_event_in_shadow_mode", [f["rule"] for f in self.repo.evaluate_safety(self.ws)])   # and the stop rule notices such an event

    def test_a_manual_link_in_shadow_mode_rebinds_facts_but_raises_no_event(self) -> None:
        r = self.receive("Подшипник 6205-2RS1 — 555 руб.", subject="Предложение", sender="someone@else.example", received=self.started + timedelta(minutes=1))
        self.work()
        before_events = 0
        self.repo.attach_inbox_message(self.ws, self.fx.user_id, r["unmatched_inbox_ids"][0], self.req, self.supplier)
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_analysis_events").fetchone()["n"], before_events)
            self.assertEqual(c.execute("SELECT request_id FROM mail_facts").fetchone()["request_id"], self.req)      # rebound (analysis data), still no downstream
        self.assertEqual(self.followup_done(), 0)


class AuditTest(ShadowBase):
    def test_every_request_scoped_price_fact_and_the_request_match_get_a_safe_audit_record(self) -> None:
        body = self.price_body(4)
        self.receive(body, received=self.started + timedelta(minutes=1))
        self.work()
        with self.repo.connect() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM mail_intelligence_audit ORDER BY id").fetchall()]
        kinds = sorted(r["kind"] for r in rows)
        self.assertEqual(kinds, ["event_suppressed", "price_fact", "request_match"])
        fact = next(r for r in rows if r["kind"] == "price_fact")
        self.assertEqual((fact["request_id"], fact["fact_kind"], fact["match_method"], fact["confidence"], fact["review_state"]), (self.req, "mail_fact", "thread", "validated_verbatim", "pending"))
        self.assertEqual(json.loads(fact["value_json"])["price"], 504)
        self.assertIn("source_start", json.loads(fact["span_json"]))
        self.assertIn("quote_verbatim", json.loads(fact["evidence_json"])["checks"])
        match = next(r for r in rows if r["kind"] == "request_match")
        self.assertEqual((match["request_id"], match["match_method"]), (self.req, "thread"))
        self.assertNotIn("Подшипник", json.dumps(rows, ensure_ascii=False))                              # the letter text is not copied into the audit
        listed = self.repo.audit_list(self.ws)
        self.assertTrue(any("6205" in (x.get("source_text") or "") for x in listed))                     # the LOCAL review view can show it through fact_id

    def test_an_unscoped_source_fact_gets_no_price_fact_audit(self) -> None:
        self.receive("Подшипник 6205-2RS1 — 505 руб.", subject="Предложение", sender="someone@else.example", received=self.started + timedelta(minutes=1))
        self.work()
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_intelligence_audit WHERE kind='price_fact'").fetchone()["n"], 0)

    def test_attachment_price_facts_are_audited_with_the_file_location(self) -> None:
        self.receive("КП во вложении.", files=[("kp.xlsx", xlsx(QUOTE))], received=self.started + timedelta(minutes=1))
        self.work()
        with self.repo.connect() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM mail_intelligence_audit WHERE fact_kind='attachment_fact'").fetchall()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[0]["span_json"])["loc"], {"sheet": "Цены", "row": 4})
        self.assertEqual(rows[0]["confidence"], "parser")
        self.assertEqual(json.loads(rows[0]["value_json"])["price"], 1850.0)

    def test_review_confirm_and_reject_and_stop_rules(self) -> None:
        for i in range(3):
            self.receive(self.price_body(10 + i), received=self.started + timedelta(minutes=1 + i))
        self.work()
        facts = [a for a in self.repo.audit_list(self.ws) if a["kind"] == "price_fact"]
        self.assertEqual(len(facts), 3)
        self.assertEqual(self.repo.audit_review(self.ws, facts[0]["id"], "confirmed")["stopped"], "")
        self.assertEqual(self.repo.audit_review(self.ws, facts[1]["id"], "rejected", "other")["stopped"], "")          # not a false price: no stop
        self.assertIsNone(self.repo.canary_state(self.ws)["stopped_at"])
        out = self.repo.audit_review(self.ws, facts[2]["id"], "rejected", "not_a_price")
        self.assertEqual(out["stopped"], "confirmed_false_price_fact")
        self.assertEqual(self.repo.canary_state(self.ws)["stopped_reason"], "confirmed_false_price_fact")
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_facts WHERE state='rejected'").fetchone()["n"], 2)   # rejected facts leave the proposed set

    def test_a_wrong_request_verdict_stops_the_canary(self) -> None:
        self.receive(self.price_body(20), received=self.started + timedelta(minutes=1))
        self.work()
        match = next(a for a in self.repo.audit_list(self.ws) if a["kind"] == "request_match")
        self.assertEqual(self.repo.audit_review(self.ws, match["id"], "rejected", "wrong_request")["stopped"], "confirmed_wrong_request")

    def test_metrics_count_generated_confirmed_rejected_pending_and_rates(self) -> None:
        for i in range(4):
            self.receive(self.price_body(30 + i), received=self.started + timedelta(minutes=1 + i))
        self.work()
        facts = [a for a in self.repo.audit_list(self.ws) if a["kind"] == "price_fact"]
        self.repo.audit_review(self.ws, facts[0]["id"], "confirmed")
        self.repo.audit_review(self.ws, facts[1]["id"], "confirmed")
        self.repo.audit_review(self.ws, facts[2]["id"], "rejected", "other")
        m = self.repo.canary_metrics(self.ws)
        self.assertEqual((m["price_facts_generated"], m["price_facts_confirmed"], m["price_facts_rejected"], m["price_facts_pending"]), (4, 2, 1, 1))
        self.assertEqual(m["price_facts_false_positive_rate"], round(1 / 3, 4))
        self.assertEqual((m["request_matches_generated"], m["events_suppressed"], m["shadow_mode"]), (4, 4, True))
        self.assertIn("manual_review_rate", m)


class ExitCriteriaTest(ShadowBase):
    def seed_reviewed(self, facts: int, letters: int, matches: int, false_reason: str = "") -> None:
        now = iso(datetime.now(UTC))
        with self.repo.connect() as c:
            for i in range(facts):
                c.execute("INSERT INTO mail_intelligence_audit(workspace_id, kind, message_kind, message_id, request_id, fact_kind, fact_id, review_state, review_reason, created_at) VALUES (?, 'price_fact', 'mail_message', ?, ?, 'mail_fact', ?, ?, ?, ?)",
                          (self.ws, 1000 + i % max(1, letters), self.req, 5000 + i, "rejected" if (false_reason and i == 0) else "confirmed", false_reason if i == 0 else "", now))
            for i in range(matches):
                c.execute("INSERT INTO mail_intelligence_audit(workspace_id, kind, message_kind, message_id, request_id, review_state, created_at) VALUES (?, 'request_match', 'mail_message', ?, ?, 'confirmed', ?)", (self.ws, 2000 + i, self.req, now))

    def test_one_or_two_procurement_letters_never_make_it_ready(self) -> None:
        self.seed_reviewed(facts=2, letters=2, matches=2)
        r = self.repo.shadow_exit_readiness(self.ws)
        self.assertFalse(r["ready"])
        self.assertFalse(r["checks"]["reviewed_price_facts"]["ok"])
        with self.assertRaises(ValueError):
            self.repo.release_shadow(self.ws, owner_approved=True)

    def test_a_large_clean_reviewed_sample_is_ready_but_release_still_needs_the_owner(self) -> None:
        self.seed_reviewed(facts=SH.MIN_REVIEWED_PRICE_FACTS, letters=SH.MIN_PROCUREMENT_LETTERS, matches=SH.MIN_REVIEWED_MATCHES)
        self.assertTrue(self.repo.shadow_exit_readiness(self.ws)["ready"])
        with self.assertRaises(ValueError):
            self.repo.release_shadow(self.ws)                                   # no owner decision: refused
        self.assertTrue(self.repo.downstream_suppressed(self.ws))
        self.assertTrue(self.repo.release_shadow(self.ws, owner_approved=True)["released"])
        self.assertFalse(self.repo.downstream_suppressed(self.ws))

    def test_a_confirmed_false_fact_blocks_the_exit(self) -> None:
        self.seed_reviewed(facts=SH.MIN_REVIEWED_PRICE_FACTS, letters=SH.MIN_PROCUREMENT_LETTERS, matches=SH.MIN_REVIEWED_MATCHES, false_reason="not_a_price")
        r = self.repo.shadow_exit_readiness(self.ws)
        self.assertFalse(r["ready"])
        self.assertFalse(r["checks"]["confirmed_false_price_facts"]["ok"])

    def test_a_safety_finding_blocks_the_exit(self) -> None:
        self.seed_reviewed(facts=SH.MIN_REVIEWED_PRICE_FACTS, letters=SH.MIN_PROCUREMENT_LETTERS, matches=SH.MIN_REVIEWED_MATCHES)
        with self.repo.connect() as c:
            c.execute("INSERT INTO mail_ai_reply_cache(workspace_id, request_key, stage, model, reply_json, cost_rub, created_at) VALUES (?, 'k', 'cheap', 'm', '{}', 9.0, ?)", (self.ws, iso(datetime.now(UTC))))
        r = self.repo.shadow_exit_readiness(self.ws)
        self.assertFalse(r["ready"])
        self.assertIn("budget_cap_exceeded", r["checks"]["budget_queue_worker_duplicates_safety"]["findings"])


class NonCanaryUnchangedTest(unittest.TestCase):
    def test_a_workspace_without_a_canary_row_is_not_in_shadow_mode(self) -> None:
        import tempfile
        from pathlib import Path
        from mail.repository import MailRepository
        from tests.test_contact_intelligence import _Fixture
        with tempfile.TemporaryDirectory() as tmp:
            repo = MailRepository(Path(tmp) / "n.sqlite3")
            fx = _Fixture(repo, "nc@example.com")
            self.assertFalse(repo.downstream_suppressed(fx.workspace_id))


if __name__ == "__main__":
    unittest.main()
