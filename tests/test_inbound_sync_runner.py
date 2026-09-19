"""EDW-40: the inbound-only canary runner is a launcher around the production sync. It checks both accounts, dedups, enqueues only canary-accepted letters,
and provably does not send, queue outgoing mail, sync Sent or touch outgoing_enabled."""

from __future__ import annotations

import ast
import importlib.util
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

from mail.crypto import generate_key
from mail.repository import MailRepository
from mail.service import MailService
from mail.types import IncomingBatch, IncomingMessage, TokenSet
from tests.test_mail_integration import FakeProvider

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inbound_sync_runner", ROOT / "scripts" / "mail_intelligence_inbound_sync.py")
RUNNER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RUNNER)


class TwoMailboxProvider(FakeProvider):
    """One fake provider, a different inbox per mailbox address."""

    def __init__(self) -> None:
        super().__init__()
        self.inboxes: dict[str, list[IncomingMessage]] = {}
        self.forbidden_calls: list[str] = []

    def fetch_incoming(self, email, access_token, *, uidvalidity, last_uid, max_messages):
        self.incoming_tokens.append(access_token)
        msgs = self.inboxes.get(email, [])
        return IncomingBatch("77", len(msgs), list(msgs), len(msgs))

    def send_message(self, *a, **k):
        self.forbidden_calls.append("send_message")
        raise AssertionError("inbound-only runner must never send")

    def fetch_sent(self, *a, **k):
        self.forbidden_calls.append("fetch_sent")
        raise AssertionError("inbound-only runner must never sync Sent")


def letter(n: int, sender: str, received: datetime, subject: str = "Предложение") -> IncomingMessage:
    return IncomingMessage(provider_message_id=f"imap:INBOX:77:{n}", message_id=f"<in{n}@x>", in_reply_to=None, references=None, from_email=sender, to_email="me@example.com",
                           subject=subject, body_text="Подшипник 6205-2RS1 — 500 руб.", body_html="", received_at=received)


class InboundRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = MailRepository(Path(self.tmp.name) / "in.sqlite3")
        self.user = self.repo.seed_user("buyer@example.com", "correct-horse")
        self.ws, self.uid = self.user["workspace_id"], self.user["id"]
        self.repo.set_outgoing_enabled(False)                                   # the production default this canary must leave alone
        self.provider = TwoMailboxProvider()
        self.service = MailService(self.repo, lambda name, credential=None: self.provider, generate_key())
        self.a = self.service.save_oauth_tokens(user_id=self.uid, workspace_id=self.ws, token_set=TokenSet("acc-a", "ref-a", 3600), email="a@example.com")
        self.b = self.service.connect_mailru(user_id=self.uid, workspace_id=self.ws, email="b@example.com", app_password="app-password-b")["id"]      # like the real workspace: yandex OAuth + mail.ru app password
        patcher = mock.patch.dict(os.environ, {"MAIL_INTELLIGENCE_ON_SYNC": "1"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_both_accounts_of_the_workspace_are_checked_through_the_production_method(self) -> None:
        self.assertNotEqual(self.a, self.b)
        now = datetime.now(UTC)
        self.provider.inboxes = {"a@example.com": [letter(1, "s1@x.example", now)], "b@example.com": [letter(2, "s2@x.example", now)]}
        with mock.patch.object(self.service, "sync_all_incoming", wraps=self.service.sync_all_incoming) as spy:
            out = RUNNER.run_cycle(self.service, self.repo, self.ws, self.uid)
        spy.assert_called_once_with(self.uid, self.ws)                          # exactly the production method, nothing else
        self.assertEqual((out["accounts_checked"], out["accounts_failed"], out["imported"] + out["unmatched"]), (2, 0, 2))

    def test_a_second_cycle_creates_no_duplicates_and_no_new_jobs(self) -> None:
        self.repo.canary_enable(self.ws, started_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat())
        now = datetime.now(UTC)
        self.provider.inboxes = {"a@example.com": [letter(1, "s1@x.example", now), letter(3, "s3@x.example", now)], "b@example.com": [letter(2, "s2@x.example", now)]}
        first = RUNNER.run_cycle(self.service, self.repo, self.ws, self.uid)
        second = RUNNER.run_cycle(self.service, self.repo, self.ws, self.uid)
        self.assertEqual((first["imported"] + first["unmatched"], first["analysis_jobs_created"]), (3, 3))
        self.assertEqual((second["imported"], second["unmatched"], second["analysis_jobs_created"]), (0, 0, 0))
        self.assertEqual(second["skipped_duplicates"], 3)
        with self.repo.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) AS n FROM mail_inbox_messages").fetchone()["n"], 3)

    def test_only_letters_received_after_canary_started_at_reach_the_analysis_queue(self) -> None:
        started = datetime.now(UTC) - timedelta(minutes=30)
        self.repo.canary_enable(self.ws, started_at=started.isoformat())
        self.provider.inboxes = {"a@example.com": [letter(1, "old@x.example", started - timedelta(days=2)), letter(2, "new@x.example", started + timedelta(minutes=5))], "b@example.com": []}
        out = RUNNER.run_cycle(self.service, self.repo, self.ws, self.uid)
        self.assertEqual((out["imported"] + out["unmatched"], out["analysis_jobs_created"]), (2, 1))          # both stored, one analysed: no backfill into the AI queue

    def test_without_a_canary_row_letters_are_stored_but_nothing_is_enqueued(self) -> None:
        self.provider.inboxes = {"a@example.com": [letter(1, "s@x.example", datetime.now(UTC))], "b@example.com": []}
        out = RUNNER.run_cycle(self.service, self.repo, self.ws, self.uid)
        self.assertEqual((out["imported"] + out["unmatched"], out["analysis_jobs_created"]), (1, 0))

    def test_nothing_outgoing_happens_and_outgoing_enabled_is_untouched(self) -> None:
        self.provider.inboxes = {"a@example.com": [letter(1, "s@x.example", datetime.now(UTC))], "b@example.com": []}
        out = RUNNER.run_cycle(self.service, self.repo, self.ws, self.uid)
        self.assertEqual(out["outgoing_delta"], {"send_attempts": 0, "jobs": 0, "outbound_messages": 0})
        self.assertEqual(out["outgoing_enabled"], 0)
        self.assertEqual(self.provider.forbidden_calls, [])
        self.assertFalse(self.repo.outgoing_enabled())

    def test_the_runner_code_never_references_send_queue_or_sent_sync(self) -> None:
        tree = ast.parse((ROOT / "scripts" / "mail_intelligence_inbound_sync.py").read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
                {(a.name if isinstance(a, ast.alias) else "") for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
        forbidden = {"MailQueue", "queue_one", "queue_bulk", "send_claimed_job", "send_message", "sync_sent", "sync_sent_automatically", "set_outgoing_enabled",
                     "claim_job", "RuntimeSession", "Thread", "import_incoming_messages", "fetch_incoming", "_parse_incoming"}
        self.assertEqual(sorted(names & forbidden), [])                       # no own parser/importer, no send path: only sync_all_incoming is called
        self.assertIn("sync_all_incoming", names)

    def test_it_refuses_to_run_when_the_durable_outgoing_switch_is_on(self) -> None:
        self.repo.set_outgoing_enabled(True)
        with mock.patch.object(RUNNER, "build", return_value=(self.repo, self.service, self.uid, [{"id": self.a}])), mock.patch("sys.argv", ["x", "--workspace", str(self.ws), "--once"]):
            self.assertEqual(RUNNER.main(), 3)

    def test_it_halts_if_outgoing_activity_ever_appears(self) -> None:
        real = RUNNER.run_cycle

        def sneaky(*a, **k):
            out = real(*a, **k)
            out["outgoing_delta"]["outbound_messages"] = 1
            return out
        with mock.patch.object(RUNNER, "build", return_value=(self.repo, self.service, self.uid, [{"id": self.a}])), mock.patch.object(RUNNER, "run_cycle", sneaky), \
                mock.patch("sys.argv", ["x", "--workspace", str(self.ws), "--interval", "1"]):
            self.assertEqual(RUNNER.main(), 4)


if __name__ == "__main__":
    unittest.main()
