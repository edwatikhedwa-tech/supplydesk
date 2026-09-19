"""EDW-21: minimal review path  candidate pair -> show evidence -> merge / reject / later (+ undo).

Nothing is merged automatically: registering candidates changes no supplier data, every merge is an
explicit owner decision through the reversible merge, and similarity alone never decides."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import supplier_app
from mail.crypto import generate_key
from tests.test_contact_intelligence import _Fixture
from tests.test_supplier_merge import INN_A, INN_B, PERSONAL, _Base, _snapshot


class _Pair(_Base):
    """Host card A and a hostless card B keyed by the raw personal address (the GAP-003 shape)."""

    def setUp(self) -> None:
        super().setUp()
        self.a = self.card(self.fx, self.req, "termo-sfera.pro", PERSONAL)
        self.b = self.card(self.fx, self.req, "ivanov.local", PERSONAL)
        with self.repo.connect() as c:
            c.execute("UPDATE suppliers SET host='', external_key=? WHERE id=?", (PERSONAL, self.b))
        self.repo.backfill_email_evidence_from_messages(self.ws)

    def queue(self) -> int:
        self.repo.register_merge_candidates(self.ws)
        (item,) = self.repo.list_merge_candidates(self.ws)
        return int(item["id"])


class ReviewWorkflowTest(_Pair):
    def test_registering_candidates_is_read_only_for_supplier_data_and_idempotent(self) -> None:
        before = _snapshot(self.repo, self.ws)
        first = self.repo.register_merge_candidates(self.ws)
        second = self.repo.register_merge_candidates(self.ws)
        self.assertEqual((first["detected"], first["in_queue"], second["in_queue"]), (1, 1, 1))
        self.assertEqual(_snapshot(self.repo, self.ws), before)
        self.assertEqual(self.repo.list_supplier_merges(self.ws), [])
        (item,) = self.repo.list_merge_candidates(self.ws)
        self.assertEqual((item["survivor_supplier_id"], item["merged_supplier_id"], item["status"]), (self.a, self.b, "pending"))

    def test_review_shows_both_cards_evidence_and_what_would_be_transferred(self) -> None:
        review = self.repo.get_merge_review(self.ws, self.queue())
        self.assertEqual(review["survivor"]["id"], self.a)
        self.assertEqual(review["merged"]["id"], self.b)
        self.assertEqual(review["survivor"]["domains"], ["termo-sfera.pro"])
        self.assertEqual(review["merged"]["email"], PERSONAL)
        for side in ("survivor", "merged"):
            card = review[side]
            self.assertIn("inn", card)
            self.assertEqual([r["id"] for r in card["requests"]], [self.req])
            self.assertEqual(set(card["messages"]), {"outbound", "inbound"})
            self.assertTrue(card["recent_messages"])
            self.assertTrue(card["evidence"])
        self.assertTrue(review["why"])
        self.assertIn("request_suppliers", review["will_transfer"])
        self.assertEqual((review["inn_verdict"], review["can_merge"], review["needs_explicit_confirmation"]), ("unknown", True, True))
        self.assertTrue(review["reversible"])

    def test_merge_needs_explicit_confirmation_then_undo_restores_everything(self) -> None:
        cid = self.queue()
        before = _snapshot(self.repo, self.ws)
        with self.assertRaises(ValueError):
            self.repo.decide_merge_candidate(self.ws, self.uid, cid, "merge")        # INN unknown: not without confirm
        self.assertEqual(_snapshot(self.repo, self.ws), before)

        done = self.repo.decide_merge_candidate(self.ws, self.uid, cid, "merge", confirm_unknown_inn=True)
        self.assertEqual(done["status"], "merged")
        self.assertNotEqual(_snapshot(self.repo, self.ws), before)
        self.assertEqual(self.repo.list_merge_candidates(self.ws, status="merged")[0]["merge_id"], done["merge_id"])

        undone = self.repo.decide_merge_candidate(self.ws, self.uid, cid, "undo")
        self.assertEqual((undone["status"], undone["diverged"]), ("pending", 0))
        self.assertEqual(_snapshot(self.repo, self.ws), before)                       # exact previous state

    def test_later_keeps_the_pair_and_reject_is_sticky(self) -> None:
        cid = self.queue()
        before = _snapshot(self.repo, self.ws)
        self.assertEqual(self.repo.decide_merge_candidate(self.ws, self.uid, cid, "later")["status"], "later")
        self.assertEqual(self.repo.decide_merge_candidate(self.ws, self.uid, cid, "reject")["status"], "rejected")
        self.repo.register_merge_candidates(self.ws)                                  # re-scan must not resurrect it
        self.assertEqual(self.repo.list_merge_candidates(self.ws)[0]["status"], "rejected")
        with self.assertRaises(ValueError):
            self.repo.decide_merge_candidate(self.ws, self.uid, cid, "merge", confirm_unknown_inn=True)  # rejected: closed
        self.assertEqual(_snapshot(self.repo, self.ws), before)

    def test_different_confirmed_inn_can_never_be_merged_from_the_queue(self) -> None:
        with self.repo.connect() as c:
            for sid, inn in ((self.a, INN_A), (self.b, INN_B)):
                c.execute("UPDATE supplier_profiles SET inn=? WHERE supplier_id=?", (inn, sid))
                c.execute("INSERT INTO global_suppliers(workspace_id, inn, name, email, created_at, updated_at) VALUES (?, ?, 'g', '', 'x', 'x')", (self.ws, inn))
                g = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
                c.execute("INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?)", (sid, g))
        # B is now linked to a legal entity -> the detector no longer proposes it; register the pair by hand
        with self.repo.connect() as c:
            c.execute("INSERT INTO supplier_merge_candidates(workspace_id, survivor_supplier_id, merged_supplier_id, status, reason, detected_at) "
                      "VALUES (?, ?, ?, 'pending', 'exact_email_hostless', 'x')", (self.ws, self.a, self.b))
        (item,) = self.repo.list_merge_candidates(self.ws)
        review = self.repo.get_merge_review(self.ws, item["id"])
        self.assertEqual((review["inn_verdict"], review["can_merge"]), ("conflict", False))
        before = _snapshot(self.repo, self.ws)
        with self.assertRaises(ValueError):
            self.repo.decide_merge_candidate(self.ws, self.uid, item["id"], "merge", confirm_unknown_inn=True)
        self.assertEqual(_snapshot(self.repo, self.ws), before)

    def test_similarity_alone_never_creates_a_candidate_without_a_card_pair_and_never_merges(self) -> None:
        # a weak name-similarity evidence row for a card WITHOUT any hostless twin proposes nothing
        with self.repo.connect() as c:
            self.repo._record_identity_evidence(c, workspace_id=self.ws, supplier_id=self.a, kind="email",
                                                value="sfera.termo@yandex.ru", source_type="name_token_similarity", source_id="t")
        self.assertEqual(self.repo.register_merge_candidates(self.ws)["in_queue"], 1)   # only the exact-address pair
        self.assertEqual(self.repo.list_supplier_merges(self.ws), [])


class ReviewTenantAndOwnerTest(_Pair):
    def test_other_workspace_cannot_see_review_or_decide_and_non_owner_is_refused(self) -> None:
        cid = self.queue()
        other = _Fixture(self.repo, "review-other@example.com")
        with self.assertRaises(ValueError):
            self.repo.get_merge_review(other.workspace_id, cid)
        self.assertEqual(self.repo.list_merge_candidates(other.workspace_id), [])
        with self.assertRaises(ValueError):                    # foreign candidate id in the caller's own workspace
            self.repo.decide_merge_candidate(other.workspace_id, other.user_id, cid, "reject")
        with self.assertRaises(ValueError):                    # a user who does not own THIS workspace
            self.repo.decide_merge_candidate(self.ws, other.user_id, cid, "reject")
        self.assertEqual(self.repo.list_merge_candidates(self.ws)[0]["status"], "pending")


class ReviewHttpTest(_Pair):
    """The same workflow through the real HTTP handler: session + CSRF, workspace from the session."""

    def setUp(self) -> None:
        super().setUp()
        self.app = supplier_app.SupplierApp(supplier_app.Config(
            host="127.0.0.1", port=0, base_url="http://127.0.0.1", redirect_uri="http://127.0.0.1/oauth/yandex/callback",
            db_path=str(Path(self.temp.name) / "merge.sqlite3"), encryption_key=generate_key(), app_user_email=None,
            app_user_password=None, session_cookie_secure=False, queue_concurrency=1, max_retries=2, daily_limit=1000,
            environment="test"))
        self.token, self.csrf = self.app.repository.create_session(self.uid, self.ws)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), supplier_app.SupplierHandler)
        self.server.app = self.app  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = int(self.server.server_address[1])

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.app.runtime.close()
        super().tearDown()

    def call(self, method: str, path: str, payload: dict | None = None, *, token: str | None = None, csrf: str | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            headers = {"Content-Type": "application/json", "Cookie": f"session_id={token or self.token}", "X-CSRF-Token": csrf or self.csrf}
            conn.request(method, path, body=json.dumps(payload) if payload is not None else None, headers=headers)
            r = conn.getresponse()
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
        finally:
            conn.close()

    def test_scan_list_show_decide_undo_over_http(self) -> None:
        before = _snapshot(self.repo, self.ws)
        status, scan = self.call("POST", "/api/supplier-merge-candidates/scan", {})
        self.assertEqual((status, scan["in_queue"]), (200, 1))
        self.assertEqual(_snapshot(self.repo, self.ws), before)
        status, listing = self.call("GET", "/api/supplier-merge-candidates?status=pending")
        self.assertEqual((status, len(listing["items"])), (200, 1))
        cid = listing["items"][0]["id"]
        status, review = self.call("GET", f"/api/supplier-merge-candidates/{cid}")
        self.assertEqual((status, review["reversible"], review["needs_explicit_confirmation"]), (200, True, True))

        status, refused = self.call("POST", f"/api/supplier-merge-candidates/{cid}/decision", {"decision": "merge"})
        self.assertEqual(status, 400)
        self.assertEqual(_snapshot(self.repo, self.ws), before)
        status, merged = self.call("POST", f"/api/supplier-merge-candidates/{cid}/decision", {"decision": "merge", "confirm_unknown_inn": True})
        self.assertEqual((status, merged["status"]), (200, "merged"))
        status, undone = self.call("POST", f"/api/supplier-merge-candidates/{cid}/decision", {"decision": "undo"})
        self.assertEqual((status, undone["status"]), (200, "pending"))
        self.assertEqual(_snapshot(self.repo, self.ws), before)

    def test_csrf_is_required_and_another_tenant_gets_404(self) -> None:
        self.call("POST", "/api/supplier-merge-candidates/scan", {})
        cid = self.repo.list_merge_candidates(self.ws)[0]["id"]
        status, _ = self.call("POST", f"/api/supplier-merge-candidates/{cid}/decision", {"decision": "reject"}, csrf="wrong")
        self.assertNotEqual(status, 200)
        self.assertEqual(self.repo.list_merge_candidates(self.ws)[0]["status"], "pending")
        other = self.app.repository.seed_user("http-other@example.com", "correct-horse")
        token, csrf = self.app.repository.create_session(other["id"], other["workspace_id"])
        status, _ = self.call("GET", f"/api/supplier-merge-candidates/{cid}", token=token, csrf=csrf)
        self.assertEqual(status, 404)
        status, _ = self.call("POST", f"/api/supplier-merge-candidates/{cid}/decision", {"decision": "reject"}, token=token, csrf=csrf)
        self.assertEqual(status, 400)
        self.assertEqual(self.repo.list_merge_candidates(self.ws)[0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
