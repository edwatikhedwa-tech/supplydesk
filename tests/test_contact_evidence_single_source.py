"""EDW-14: one source of truth for contact facts.

supplier_identity_evidence holds primary facts; contact_intelligence is a projection
rebuilt by ONE reconcile function. Covers: single path for an inbound reply, legacy
signals superseded (not deleted), revoke/re-confirm recompute the derived status,
rfq_sent is association-only, sticky human decisions, candidate/confirmed/rejected/
revoked/ambiguous states, tenant isolation of the projection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mail.repository import MailRepository
from tests.test_contact_intelligence import _Fixture

INN = "7700000099"
EMAIL = "shared@example.com"


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "single-source.sqlite3")
        self.ws: list[_Fixture] = []
        self.req: list[int] = []
        self.sup: list[int] = []
        self.gsup: list[int] = []
        for i in range(3):
            fx = _Fixture(self.repo, f"tenant-{i}@example.com")
            rid = fx.create_request()
            sid, _tid, gid = fx.add_supplier_thread(rid, inn=INN, email=EMAIL, host=f"shared-{i}.example")
            self.ws.append(fx); self.req.append(rid); self.sup.append(sid); self.gsup.append(gid)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def reply(self, i: int, from_email: str = EMAIL) -> None:
        self.ws[i].receive_inbound(request_id=self.req[i], supplier_id=self.sup[i], from_email=from_email)

    def contacts(self, i: int) -> dict:
        return self.repo.list_email_contacts_for_global_supplier(self.ws[i].workspace_id, self.gsup[i])

    def status(self, i: int, email: str = EMAIL) -> str:
        return next(c["status"] for c in self.contacts(i)["global_contacts"] if c["email"] == email)

    def signals(self, sources_like: str | None = None) -> list[dict]:
        sql = ("SELECT s.*, (SELECT COUNT(*) FROM canonical_company_contact_signal_revocations r WHERE r.signal_id=s.id) AS revoked "
               "FROM canonical_company_contact_signals s")
        with self.repo.connect() as c:
            rows = [dict(r) for r in c.execute(sql + " ORDER BY id").fetchall()]
        return [r for r in rows if sources_like is None or str(r["source"]).startswith(sources_like)]


class SinglePathTest(_Base):
    def test_one_inbound_reply_is_one_evidence_and_one_signal(self) -> None:
        self.reply(0)
        self.contacts(0)
        self.contacts(0)  # repeated pull: idempotent
        evidence = self.repo.list_supplier_identity_evidence(self.ws[0].workspace_id, email=EMAIL)
        self.assertEqual([(e["source_type"], e["state"]) for e in evidence], [("inbound_reply", "confirmed")])
        signals = self.signals()
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["source"], f"evidence:{evidence[0]['id']}")
        self.assertEqual((signals[0]["signal_type"], signals[0]["strength"], signals[0]["workspace_id"]),
                         ("inbound_reply", "strong", self.ws[0].workspace_id))

    def test_legacy_signal_from_the_old_independent_path_is_superseded_not_deleted(self) -> None:
        self.reply(0)
        with self.repo.connect() as c:
            cid = c.execute("SELECT id FROM canonical_companies WHERE inn=?", (INN,)).fetchone() if False else None
            c.execute("INSERT INTO canonical_companies(inn, first_seen_at, updated_at) VALUES (?, 'x', 'x') ON CONFLICT(inn) DO NOTHING", (INN,))
            cid = c.execute("SELECT id FROM canonical_companies WHERE inn=?", (INN,)).fetchone()["id"]
            c.execute(
                """INSERT INTO canonical_company_contact_signals(canonical_company_id, email, signal_type, strength,
                       workspace_id, source, basis, created_at)
                   VALUES (?, ?, 'inbound_reply', 'strong', ?, 'message:999', 'legacy', '2026-01-01T00:00:00+00:00')""",
                (cid, EMAIL, self.ws[0].workspace_id),
            )
        self.contacts(0)
        legacy = self.signals("message:")
        self.assertEqual(len(legacy), 1)          # history kept
        self.assertEqual(legacy[0]["revoked"], 1)  # but no longer counted
        self.assertEqual([s["revoked"] for s in self.signals("evidence:")], [0])


class RevokeAndReconfirmRecomputeTest(_Base):
    def _promote(self) -> None:
        self.reply(0); self.reply(1); self.reply(2)
        for i in range(3):
            self.contacts(i)
        self.assertEqual(self.status(0), "preferred")

    def test_revoking_evidence_demotes_the_derived_contact_and_reconfirm_restores_it(self) -> None:
        self._promote()
        priority = self.repo.resolve_contact_priority(self.ws[0].workspace_id, self.sup[0], fallback_email="x@example.com")
        self.assertEqual(priority["source"], "global_preferred")

        self.repo.revoke_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[0], EMAIL, reason="wrong")
        self.assertEqual(self.status(1), "secondary")   # only 2 independent workspaces remain
        after = self.repo.resolve_contact_priority(self.ws[0].workspace_id, self.sup[0], fallback_email="x@example.com")
        self.assertNotEqual(after["source"], "global_preferred")
        # history retained: the revoked signal is still a row, just not counted
        self.assertEqual(sum(s["revoked"] for s in self.signals("evidence:")), 1)

        self.repo.confirm_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[0], EMAIL)
        self.assertEqual(self.status(1), "preferred")   # 3 workspaces again + strong signals of the others

    def test_revoke_is_idempotent_and_reconcile_is_stable(self) -> None:
        self._promote()
        for _ in range(2):
            self.repo.revoke_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[0], EMAIL)
            self.contacts(0)
        self.assertEqual(sum(s["revoked"] for s in self.signals("evidence:")), 1)

    def test_a_human_revoke_is_sticky_against_new_automatic_replies(self) -> None:
        self.reply(0)
        self.contacts(0)
        self.repo.revoke_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[0], EMAIL)
        self.reply(0)  # a NEW reply from the same address must not silently re-confirm it
        self.contacts(0)
        states = sorted(e["state"] for e in self.repo.list_supplier_identity_evidence(self.ws[0].workspace_id, email=EMAIL))
        self.assertEqual(states, ["candidate", "revoked"])
        self.assertEqual(self.repo.contact_state(self.ws[0].workspace_id, EMAIL)["state"], "candidate")


class RfqSentIsAssociationOnlyTest(_Base):
    def test_rfq_sent_never_proves_ownership_or_reuse(self) -> None:
        self.ws[0].send_outbound(request_id=self.req[0], supplier_id=self.sup[0], to_email="new.person@yandex.ru",
                                 sent_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        self.repo.backfill_email_evidence_from_messages(self.ws[0].workspace_id)
        rows = self.repo.list_supplier_identity_evidence(self.ws[0].workspace_id, email="new.person@yandex.ru")
        self.assertEqual([(r["source_type"], r["assertion"]) for r in rows], [("rfq_sent", "association")])
        self.assertEqual(self.repo.contact_state(self.ws[0].workspace_id, "new.person@yandex.ru")["state"], "unknown")
        with self.repo.connect() as c:
            self.assertEqual(self.repo._confirmed_supplier_ids_for_email(c, self.ws[0].workspace_id, "new.person@yandex.ru", self.req[0]), [])
        # ...and it is not projected into cross-tenant contact intelligence either
        self.contacts(0)
        self.assertEqual([s for s in self.signals() if s["email"] == "new.person@yandex.ru"], [])

    def test_a_real_reply_upgrades_the_same_address_to_confirmed_ownership(self) -> None:
        self.ws[0].send_outbound(request_id=self.req[0], supplier_id=self.sup[0], to_email="new.person@yandex.ru",
                                 sent_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        self.reply(0, "new.person@yandex.ru")
        self.repo.backfill_email_evidence_from_messages(self.ws[0].workspace_id)
        self.assertEqual(self.repo.contact_state(self.ws[0].workspace_id, "new.person@yandex.ru"),
                         {"email": "new.person@yandex.ru", "state": "confirmed", "supplier_ids": [self.sup[0]]})


class StatesAndApiTest(_Base):
    def test_candidate_confirm_reject_revoke_and_ambiguous(self) -> None:
        w, u = self.ws[0].workspace_id, self.ws[0].user_id
        with self.repo.connect() as c:
            self.repo._record_identity_evidence(c, workspace_id=w, supplier_id=self.sup[0], kind="email",
                                                value="maybe@yandex.ru", source_type="name_token_similarity", source_id="t")
        self.assertEqual(self.repo.contact_state(w, "maybe@yandex.ru")["state"], "candidate")
        self.repo.reject_supplier_contact(w, u, self.sup[0], "maybe@yandex.ru")
        self.assertEqual(self.repo.contact_state(w, "maybe@yandex.ru")["state"], "rejected")
        self.repo.confirm_supplier_contact(w, u, self.sup[0], "maybe@yandex.ru")
        self.assertEqual(self.repo.contact_state(w, "maybe@yandex.ru")["state"], "confirmed")
        # a second card confirmed for the same address -> ambiguous (never guessed)
        with self.repo.connect() as c:
            c.execute("INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at) "
                      "VALUES (?, 'second.example', 's', '', 'second.example', 'x', 'x')", (w,))
            second = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.repo.confirm_supplier_contact(w, u, second, "maybe@yandex.ru")
        self.assertEqual(self.repo.contact_state(w, "maybe@yandex.ru")["state"], "ambiguous")
        self.repo.revoke_supplier_contact(w, u, second, "maybe@yandex.ru")
        self.assertEqual(self.repo.contact_state(w, "maybe@yandex.ru")["state"], "confirmed")
        self.repo.revoke_supplier_contact(w, u, self.sup[0], "maybe@yandex.ru")
        self.assertEqual(self.repo.contact_state(w, "maybe@yandex.ru")["state"], "revoked")

    def test_decisions_are_tenant_scoped(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.confirm_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[1], EMAIL)
        with self.assertRaises(ValueError):
            self.repo.revoke_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[1], EMAIL)
        with self.assertRaises(ValueError):  # supplier exists in the workspace but not in that request
            self.repo.confirm_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[0], EMAIL,
                                               request_id=self.req[1])

    def test_revoking_in_one_workspace_never_touches_another_workspaces_signals(self) -> None:
        self.reply(0); self.reply(1)
        self.contacts(0); self.contacts(1)
        self.repo.revoke_supplier_contact(self.ws[0].workspace_id, self.ws[0].user_id, self.sup[0], EMAIL)
        by_ws = {}
        for s in self.signals("evidence:"):
            by_ws[s["workspace_id"]] = s["revoked"]
        self.assertEqual(by_ws, {self.ws[0].workspace_id: 1, self.ws[1].workspace_id: 0})
        self.assertEqual(self.repo.contact_state(self.ws[1].workspace_id, EMAIL)["state"], "confirmed")


if __name__ == "__main__":
    unittest.main()
