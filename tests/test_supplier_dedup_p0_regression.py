"""P0 regression for GAP-003 / INV-SUP-002 (supplier identity duplication).

Real production case: заявка №1059 -- supplier id 2837 (external_key=
termo-sfera.pro) and supplier id 3315 (external_key=sfera.termo@yandex.ru) for
one real company.

INVARIANT under test (Documentation Pack V1.2.3, revised 2026-09-19):

    If a CONFIRMED link between a new contact and an existing supplier
    exists, the system must not create a second supplier identity.

"Confirmed" means strong evidence: SupplyDesk sent an RFQ to the address for
that card, a real inbound reply from the address landed in that card's thread,
or a user confirmed it. It deliberately does NOT mean "the mailbox name looks
like the company name" -- that is only a weak candidate signal and must never
unite identities by itself (covered by the negative test below). This test
therefore proves the invariant, not a string heuristic.

Do not weaken, skip or xfail these tests.
"""

from __future__ import annotations

import unittest

from tests.test_supplier_identity_evidence import PERSONAL, _Base


class SupplierDedupP0RegressionTest(_Base):
    def test_a_confirmed_real_reply_link_never_creates_a_second_identity(self) -> None:
        # Corporate card, RFQ sent, the company's staff replies from a personal
        # mailbox in the same thread (matched deterministically by reply headers).
        sid = self._send_rfq_and_get_reply_from(PERSONAL)
        before = self._count()

        result = self._send_to(PERSONAL)  # later manual/outgoing send to that mailbox

        self.assertEqual(result["supplier_id"], sid)
        self.assertEqual(self._count(), before, "GAP-003: a second supplier identity was created")

    def test_b_user_confirmed_link_never_creates_a_second_identity(self) -> None:
        sid = self._host_supplier()  # found by search via the corporate domain
        self.repo.confirm_supplier_contact(self.ws, self.user["id"], sid, PERSONAL, request_id=self.req)

        result = self._send_to(PERSONAL)

        self.assertEqual(result["supplier_id"], sid)
        self.assertEqual(self._count(), 1, "GAP-003: a second supplier identity was created")

    def test_c_without_confirmed_evidence_similarity_alone_does_not_unite_identities(self) -> None:
        sid = self._host_supplier()

        result = self._send_to(PERSONAL)  # no evidence, only a similar-looking mailbox name

        self.assertNotEqual(result["supplier_id"], sid)
        signals = self.repo.list_supplier_identity_evidence(self.ws, supplier_id=sid, email=PERSONAL)
        self.assertTrue(signals and all(s["decision"] == "candidate" and s["strength"] == "weak" for s in signals))


if __name__ == "__main__":
    unittest.main()
