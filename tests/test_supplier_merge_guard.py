"""EDW-15: different confirmed INNs are never mergeable, whatever the names/contacts say."""

from __future__ import annotations

import unittest

from backend.domain.supplier_identity.merge_guard import can_auto_merge, merge_verdict

INN_A, INN_B, INN_PERSON = "7707083893", "7736207543", "500100732259"


class MergeGuardTest(unittest.TestCase):
    def test_same_confirmed_inn_is_same_company(self) -> None:
        self.assertEqual(merge_verdict(INN_A, "7707 083 893"), "same_company")
        self.assertTrue(can_auto_merge(INN_A, INN_A))

    def test_different_confirmed_inn_is_blocking_conflict(self) -> None:
        self.assertEqual(merge_verdict(INN_A, INN_B), "conflict")
        self.assertEqual(merge_verdict(INN_A, INN_PERSON), "conflict")
        self.assertFalse(can_auto_merge(INN_A, INN_B))

    def test_missing_or_invalid_inn_is_unknown_and_never_auto(self) -> None:
        for a, b in [(INN_A, ""), ("", ""), (None, INN_A), (INN_A, "7707083894"), ("abc", INN_A)]:
            self.assertEqual(merge_verdict(a, b), "unknown", (a, b))
            self.assertFalse(can_auto_merge(a, b))


if __name__ == "__main__":
    unittest.main()
