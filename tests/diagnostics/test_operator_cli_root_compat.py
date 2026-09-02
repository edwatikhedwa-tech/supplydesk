"""Regression coverage for the collect_contacts/benchmark_models root move.

Guards the two risks a naive move would introduce: a stale `.env` lookup that
resolves to the new package directory instead of the repository root, and a
root wrapper that silently forks into a second implementation instead of
delegating to the moved module.
"""

import unittest
from pathlib import Path

import benchmark_models as benchmark_models_wrapper
import collect_contacts as collect_contacts_wrapper
from benchmarks import benchmark_models
from scripts import collect_contacts

REPO_ROOT = Path(__file__).resolve().parents[2]


class OperatorCliRootCompatTests(unittest.TestCase):
    def test_collect_contacts_env_lookup_resolves_to_repo_root(self):
        self.assertEqual(collect_contacts.REPO_ROOT, REPO_ROOT)

    def test_benchmark_models_env_lookup_resolves_to_repo_root(self):
        self.assertEqual(benchmark_models.REPO_ROOT, REPO_ROOT)

    def test_collect_contacts_wrapper_delegates_without_duplicating_main(self):
        self.assertIs(collect_contacts_wrapper.main, collect_contacts.main)

    def test_benchmark_models_wrapper_delegates_without_duplicating_main(self):
        self.assertIs(benchmark_models_wrapper.main, benchmark_models.main)


if __name__ == "__main__":
    unittest.main()
