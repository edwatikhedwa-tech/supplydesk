from __future__ import annotations

import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
from pathlib import Path

from mail.crypto import generate_key
from mail.deliverability import DeliverabilityPreflightError
from mail.repository import MailRepository, iso_now
from mail.service import MailService
from mail.types import TokenSet
from scripts.supplier_identity_audit import merge_supplier_pair, scan_duplicates, strict_scan


class SupplierIdentityTests(unittest.TestCase):
    """Regression coverage for company/contact identity and safe cleanup."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = MailRepository(Path(self.temp.name) / "identity.sqlite3")
        self.user = self.repo.seed_user("identity@example.com", "correct-horse")
        self.workspace_id = int(self.user["workspace_id"])
        self.user_id = int(self.user["id"])
        self.request_id = 1043

    def tearDown(self) -> None:
        self.temp.cleanup()

    def add_host(self, host: str, email: str, *, name: str = "Company", inn: str | None = None) -> int:
        supplier_id = self.repo.upsert_search_result(
            self.workspace_id, self.request_id, host,
            host=host, title=name, snippet="test result",
        )
        if inn:
            self.repo.apply_supplier_enrichment(
                self.workspace_id, host, email=email, inn=inn,
                phone="+70000000000", region="Москва", company_name=name,
            )
        else:
            with self.repo.connect() as connection:
                connection.execute("UPDATE suppliers SET email=? WHERE id=?", (email, supplier_id))
        return supplier_id

    def add_hostless(self, email: str, *, name: str = "Company") -> int:
        return self.repo.upsert_supplier(
            workspace_id=self.workspace_id, external_key=email,
            name=name, email=email, host="", request_id=self.request_id,
        )

    def service_with_account(self) -> MailService:
        service = MailService(self.repo, lambda _provider: object(), generate_key())
        service.save_oauth_tokens(
            user_id=self.user_id, workspace_id=self.workspace_id,
            token_set=TokenSet("access", "refresh", 3600),
            email="identity@example.com",
        )
        return service

    def test_request_view_collapses_same_inn_and_keeps_contacts(self) -> None:
        first = self.add_host("one-company.example", "one@example.com", inn="7726347929")
        second = self.add_host("two-company.example", "two@example.com", inn="7726347929")
        self.add_hostless("one@example.com")
        items = self.repo.list_suppliers(self.workspace_id, self.request_id)
        company = next(item for item in items if item["global_supplier_id"] is not None and first in item["related_supplier_ids"])
        self.assertIn(second, company["related_supplier_ids"])
        self.assertEqual(set(company["contact_sites"]), {"one-company.example", "two-company.example"})
        self.assertEqual(set(company["contact_emails"]), {"one@example.com", "two@example.com"})

    def test_hiding_company_group_hides_all_request_contacts(self) -> None:
        first = self.add_host("hide-one.example", "hide-one@example.com", inn="7726347929")
        second = self.add_host("hide-two.example", "hide-two@example.com", inn="7726347929")
        self.repo.set_irrelevant(self.workspace_id, self.user_id, self.request_id, first, True)
        with self.repo.connect() as connection:
            rows = connection.execute(
                "SELECT supplier_id, is_irrelevant FROM request_suppliers WHERE request_id=? AND supplier_id IN (?,?) ORDER BY supplier_id",
                (self.request_id, first, second),
            ).fetchall()
        self.assertEqual([(int(row[0]), int(row[1])) for row in rows], [(first, 1), (second, 1)])
        self.assertFalse(any(item["id"] in {first, second} for item in self.repo.list_suppliers(self.workspace_id, self.request_id)))

    def test_same_name_with_different_inn_stays_separate(self) -> None:
        self.add_host("first-identity.example", "first@example.com", name="Same name", inn="7726347929")
        self.add_host("second-identity.example", "second@example.com", name="Same name", inn="5903096662")
        items = [item for item in self.repo.list_suppliers(self.workspace_id, self.request_id) if item["name"] == "Same name"]
        self.assertEqual(len(items), 2)
        self.assertEqual({item["inn"] for item in items}, {"7726347929", "5903096662"})

    def test_selected_supplier_id_is_reused_without_row_growth(self) -> None:
        supplier_id = self.add_host("reuse.example", "reuse@example.com")
        service = self.service_with_account()
        with self.repo.connect() as connection:
            before = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        queued = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "email": "reuse@example.com", "name": "Reuse", "host": "reuse.example"},
            subject="Request", body="Body", idempotency_key="reuse-1",
        )
        with self.repo.connect() as connection:
            after = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
            target = connection.execute("SELECT supplier_id FROM mail_send_operation_targets WHERE operation_id=?", (queued["operation_id"],)).fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(int(target), supplier_id)

    def test_grouped_company_card_queues_one_primary_email_when_all_contacts_are_new(self) -> None:
        self.add_host("multi-a.example", "multi-a@example.com", inn="7726347929")
        self.add_host("multi-b.example", "multi-b@example.com", inn="7726347929")
        self.add_host("multi-c.example", "multi-c@example.com", inn="7726347929")
        self.add_host("multi-d.example", "multi-d@example.com", inn="7726347929")
        company = next(item for item in self.repo.list_suppliers(self.workspace_id, self.request_id) if item["email_count"] == 4)
        service = self.service_with_account()

        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={
                "id": company["id"], "email": company["email"], "name": company["name"],
                "host": company["host"], "external_key": company["external_key"],
            },
            subject="Request", body="Body", idempotency_key="multi-email-one-card",
        )

        with self.repo.connect() as connection:
            messages = connection.execute(
                "SELECT supplier_id, to_email FROM mail_messages WHERE request_id=? ORDER BY id",
                (self.request_id,),
            ).fetchall()
        self.assertEqual(len(messages), 1)
        self.assertEqual(int(messages[0]["supplier_id"]), int(company["id"]))
        self.assertEqual(messages[0]["to_email"], company["email"])

    def test_grouped_status_and_unsent_filter_semantics(self) -> None:
        ids = [
            self.add_host("status-a.example", "status-a@example.com", inn="7726347929"),
            self.add_host("status-b.example", "status-b@example.com", inn="7726347929"),
            self.add_host("status-c.example", "status-c@example.com", inn="7726347929"),
            self.add_host("status-d.example", "status-d@example.com", inn="7726347929"),
        ]
        service = self.service_with_account()
        with self.repo.connect() as connection:
            account_id = int(connection.execute("SELECT id FROM mail_accounts WHERE workspace_id=? LIMIT 1", (self.workspace_id,)).fetchone()[0])
            for supplier_id, status in zip(ids[:3], ("sent", "queued", "failed")):
                connection.execute(
                    "INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at) VALUES (?, ?, ?, ?, NULL, NULL, ?)",
                    (self.request_id, supplier_id, account_id, status, iso_now()),
                )

        company = next(item for item in self.repo.list_suppliers(self.workspace_id, self.request_id) if item["email_count"] == 4)
        self.assertEqual(company["mail_status"], "waiting")
        self.assertEqual(company["unsent_contact_count"], 1)
        self.assertEqual(len([item for item in self.repo.list_suppliers(self.workspace_id, self.request_id) if item["unsent_contact_count"] > 0]), 1)

        # A primary that was already used yields to the one untouched contact.
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": company["id"], "email": company["email"], "name": company["name"], "host": company["host"]},
            subject="Request", body="Body", idempotency_key="status-card-send",
        )
        with self.repo.connect() as connection:
            messages = connection.execute(
                "SELECT supplier_id, to_email FROM mail_messages WHERE request_id=? ORDER BY id",
                (self.request_id,),
            ).fetchall()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["to_email"], "status-d@example.com")

        all_sent_ids = [
            self.add_host("all-sent-a.example", "all-sent-a@example.com", inn="5903096662"),
            self.add_host("all-sent-b.example", "all-sent-b@example.com", inn="5903096662"),
        ]
        with self.repo.connect() as connection:
            account_id = int(connection.execute("SELECT id FROM mail_accounts WHERE workspace_id=? LIMIT 1", (self.workspace_id,)).fetchone()[0])
            for supplier_id in all_sent_ids:
                connection.execute(
                    "INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at) VALUES (?, ?, ?, 'sent', NULL, NULL, ?)",
                    (self.request_id, supplier_id, account_id, iso_now()),
                )
        all_sent = next(item for item in self.repo.list_suppliers(self.workspace_id, self.request_id) if item["email_count"] == 2 and item["email"].startswith("all-sent"))
        self.assertEqual(all_sent["unsent_contact_count"], 0)

        untouched_ids = [
            self.add_host("untouched-a.example", "untouched-a@example.com", inn="7707083893"),
            self.add_host("untouched-b.example", "untouched-b@example.com", inn="7707083893"),
        ]
        self.assertEqual(len(untouched_ids), 2)
        untouched = next(item for item in self.repo.list_suppliers(self.workspace_id, self.request_id) if item["email_count"] == 2 and item["email"].startswith("untouched"))
        self.assertEqual(untouched["unsent_contact_count"], 2)

    def test_ten_sends_keep_the_same_supplier_identity(self) -> None:
        supplier_id = self.add_host("ten.example", "ten@example.com")
        service = self.service_with_account()
        for index in range(10):
            service.queue_one(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
                supplier={"id": supplier_id, "email": "ten@example.com", "name": "Ten", "host": "ten.example"},
                subject=f"Request {index}", body="Body", idempotency_key=f"ten-{index}",
                allow_repeat=index > 0,
            )
        with self.repo.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM suppliers WHERE email='ten@example.com'").fetchone()[0]
        self.assertEqual(count, 1)

    def test_same_request_email_is_blocked_after_first_operation(self) -> None:
        supplier_id = self.add_host("guard.example", "guard@example.com")
        service = self.service_with_account()
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "email": "guard@example.com", "name": "Guard", "host": "guard.example"},
            subject="First", body="Body", idempotency_key="guard-first",
        )
        with self.assertRaises(DeliverabilityPreflightError):
            service.queue_one(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
                supplier={"id": supplier_id, "email": "guard@example.com", "name": "Guard", "host": "guard.example"},
                subject="Second", body="Body", idempotency_key="guard-second",
            )
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 1)

    def test_missing_single_send_key_does_not_grant_repeat_permission(self) -> None:
        supplier_id = self.add_host("no-key-guard.example", "no-key-guard@example.com")
        service = self.service_with_account()
        supplier = {"id": supplier_id, "email": "no-key-guard@example.com", "name": "No key", "host": "no-key-guard.example"}
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="First", body="Body",
        )
        with self.assertRaises(DeliverabilityPreflightError):
            service.queue_one(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
                supplier=supplier, subject="Second", body="Body",
            )
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 1)

    def test_explicit_repeat_bypasses_guard_but_still_creates_one_message(self) -> None:
        supplier_id = self.add_host("repeat.example", "repeat@example.com")
        service = self.service_with_account()
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "email": "repeat@example.com", "name": "Repeat", "host": "repeat.example"},
            subject="First", body="Body", idempotency_key="repeat-first",
        )
        repeated = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "email": "repeat@example.com", "name": "Repeat", "host": "repeat.example"},
            subject="Second", body="Body", idempotency_key="repeat-second", allow_repeat=True,
        )
        self.assertIn("message_id", repeated)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 2)

    def test_explicit_repeat_same_key_is_one_new_message(self) -> None:
        supplier_id = self.add_host("repeat-double-click.example", "repeat-double-click@example.com")
        service = self.service_with_account()
        supplier = {"id": supplier_id, "email": "repeat-double-click@example.com", "name": "Repeat", "host": "repeat-double-click.example"}
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="First", body="Body", idempotency_key="repeat-double-first",
        )
        first_repeat = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="Repeat", body="Body", idempotency_key="repeat-double-action", allow_repeat=True,
        )
        second_repeat = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="Repeat", body="Body", idempotency_key="repeat-double-action", allow_repeat=True,
        )
        self.assertEqual(first_repeat["message_id"], second_repeat["message_id"])
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 2)

    def test_explicit_repeats_with_different_keys_are_two_distinct_actions(self) -> None:
        supplier_id = self.add_host("repeat-separate.example", "repeat-separate@example.com")
        service = self.service_with_account()
        supplier = {"id": supplier_id, "email": "repeat-separate@example.com", "name": "Repeat", "host": "repeat-separate.example"}
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="First", body="Body", idempotency_key="repeat-separate-first",
        )
        first_repeat = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="Repeat", body="Body", idempotency_key="repeat-separate-a", allow_repeat=True,
        )
        second_repeat = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="Repeat", body="Body", idempotency_key="repeat-separate-b", allow_repeat=True,
        )
        self.assertNotEqual(first_repeat["message_id"], second_repeat["message_id"])
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 3)

    def test_guard_and_operation_roll_back_when_message_creation_fails(self) -> None:
        service = self.service_with_account()
        supplier = {"name": "Rollback", "email": "rollback-message@example.com", "host": "rollback-message.example", "external_key": "rollback-message.example"}
        with self.assertRaisesRegex(RuntimeError, "injected mail_message failure"):
            with patch.object(self.repo, "_create_queued_message_connection", side_effect=RuntimeError("injected mail_message failure")):
                service.queue_one(
                    user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
                    supplier=supplier, subject="Rollback", body="Body", idempotency_key="rollback-message",
                )
        with self.repo.connect() as connection:
            for query in (
                "SELECT COUNT(*) FROM mail_send_operations",
                "SELECT COUNT(*) FROM mail_request_email_guards",
                "SELECT COUNT(*) FROM mail_send_operation_targets",
                "SELECT COUNT(*) FROM mail_messages WHERE direction='outbound'",
                "SELECT COUNT(*) FROM mail_jobs",
            ):
                self.assertEqual(connection.execute(query).fetchone()[0], 0)
        queued = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="After rollback", body="Body", idempotency_key="rollback-message-retry",
        )
        self.assertIn("message_id", queued)

    def test_email_normalization_does_not_bypass_guard(self) -> None:
        service = self.service_with_account()
        supplier = {"name": "Normalized", "email": " Info@Example.RU ", "host": "example.ru", "external_key": "example.ru"}
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="First", body="Body", idempotency_key="normalized-first",
        )
        with self.assertRaises(DeliverabilityPreflightError):
            service.queue_one(
                user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
                supplier={**supplier, "email": "info@example.ru"}, subject="Second", body="Body", idempotency_key="normalized-second",
            )
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT normalized_email FROM mail_request_email_guards").fetchone()[0], "info@example.ru")

    def test_cross_workspace_same_email_is_not_blocked(self) -> None:
        first_service = self.service_with_account()
        first_service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"name": "Workspace A", "email": "isolated@example.com", "host": "isolated.example", "external_key": "isolated.example"},
            subject="A", body="Body", idempotency_key="workspace-a",
        )
        other = self.repo.seed_user("workspace-b@example.com", "correct-horse")
        other_workspace = int(other["workspace_id"])
        other_request = self.repo.create_request(
            other_workspace, user_id=int(other["id"]), name="Workspace B request", description="B",
            positions=[{"name": "B", "quantity": "1"}], sender_name="Buyer", company_name="Company",
        )
        other_service = MailService(self.repo, lambda _provider: object(), generate_key())
        other_service.save_oauth_tokens(
            user_id=int(other["id"]), workspace_id=other_workspace,
            token_set=TokenSet("access-b", "refresh-b", 3600), email="workspace-b@example.com",
        )
        queued = other_service.queue_one(
            user_id=int(other["id"]), workspace_id=other_workspace, request_id=other_request,
            supplier={"name": "Workspace B", "email": "isolated@example.com", "host": "isolated.example", "external_key": "isolated.example"},
            subject="B", body="Body", idempotency_key="workspace-b",
        )
        self.assertIn("message_id", queued)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_request_email_guards WHERE normalized_email='isolated@example.com'").fetchone()[0], 2)

    def test_preflight_recipient_matches_queue_for_never_used_alternate(self) -> None:
        primary = self.add_host("alternate-primary.example", "info@example.ru", inn="7726347929")
        sales = self.add_host("alternate-sales.example", "sales@example.ru", inn="7726347929")
        office = self.add_host("alternate-office.example", "office@example.ru", inn="7726347929")
        service = self.service_with_account()
        with self.repo.connect() as connection:
            account_id = int(connection.execute("SELECT id FROM mail_accounts WHERE workspace_id=? LIMIT 1", (self.workspace_id,)).fetchone()[0])
            connection.execute(
                "INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at) VALUES (?, ?, ?, 'sent', NULL, NULL, ?)",
                (self.request_id, primary, account_id, iso_now()),
            )
        company = next(item for item in self.repo.list_suppliers(self.workspace_id, self.request_id) if item["email_count"] == 3 and primary in item["related_supplier_ids"])
        supplier = {"id": company["id"], "email": "info@example.ru", "name": company["name"], "host": company["host"]}
        preflight = service.preflight_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            suppliers=[supplier], subject="Request", body="Body", attachments=[],
        )
        selected_email = preflight["recipient_results"][0]["email"]
        self.assertEqual(preflight["contact_selection"]["alternate_selected"], 1)
        self.assertEqual(preflight["contact_selection"]["would_create"], 1)
        self.assertIn(selected_email, {"sales@example.ru", "office@example.ru"})
        queued = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier=supplier, subject="Request", body="Body", idempotency_key="alternate-acceptance",
        )
        with self.repo.connect() as connection:
            messages = connection.execute("SELECT to_email FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchall()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], selected_email)
        self.assertIn("message_id", queued)

    def test_cross_request_history_does_not_block_new_request(self) -> None:
        supplier_id = self.add_host("cross-request.example", "cross@example.com")
        service = self.service_with_account()
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": supplier_id, "email": "cross@example.com", "name": "Cross", "host": "cross-request.example"},
            subject="Request A", body="Body", idempotency_key="cross-a",
        )
        request_b = self.repo.create_request(
            self.workspace_id, user_id=self.user_id, name="Request B", description="B",
            positions=[{"name": "B", "quantity": "1"}], sender_name="Buyer", company_name="Company",
        )
        queued = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=request_b,
            supplier={"email": "cross@example.com", "name": "Cross", "host": "cross-request.example"},
            subject="Request B", body="Body", idempotency_key="cross-b",
        )
        self.assertIn("message_id", queued)

    def test_shared_email_between_companies_warns_without_merging(self) -> None:
        first = self.add_host("shared-one.example", "shared@example.com", inn="7726347929")
        self.add_host("shared-two.example", "shared@example.com", inn="5903096662")
        service = self.service_with_account()
        result = service.preflight_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            suppliers=[{"id": first, "email": "shared@example.com", "name": "Shared", "host": "shared-one.example"}],
            subject="Request", body="Body", attachments=[],
        )
        self.assertEqual(result["status"], "WARNING")
        self.assertIn("shared_email_across_companies", result["warnings"])
        self.assertEqual(result["contact_selection"]["would_create"], 1)

    def test_two_company_rows_with_same_email_are_blocked_as_duplicate_recipient(self) -> None:
        first = self.add_host("duplicate-one.example", "duplicate@example.com", inn="7726347929")
        second = self.add_host("duplicate-two.example", "duplicate@example.com", inn="5903096662")
        service = self.service_with_account()
        result = service.preflight_bulk(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            suppliers=[
                {"id": first, "email": "duplicate@example.com", "name": "One", "host": "duplicate-one.example"},
                {"id": second, "email": "duplicate@example.com", "name": "Two", "host": "duplicate-two.example"},
            ],
            subject="Request", body="Body", attachments=[],
        )
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("duplicate_recipient", result["blocks"])

    def test_different_idempotency_keys_race_to_one_initial_message(self) -> None:
        supplier_id = self.add_host("race.example", "race@example.com")
        service = self.service_with_account()

        def send(index: int):
            try:
                return service.queue_one(
                    user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
                    supplier={"id": supplier_id, "email": "race@example.com", "name": "Race", "host": "race.example"},
                    subject=f"Race {index}", body="Body", idempotency_key=f"race-{index}",
                )
            except Exception as exc:  # the loser must fail closed, not send twice
                return exc

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, (1, 2)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(sum(isinstance(result, DeliverabilityPreflightError) for result in results), 1)
        with self.repo.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE request_id=? AND direction='outbound'", (self.request_id,)).fetchone()[0], 1)

    def test_unidentified_manual_email_reuses_unambiguous_host(self) -> None:
        supplier_id = self.add_host("fallback.example", "fallback@example.com")
        service = self.service_with_account()
        queued = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"email": "fallback@example.com", "name": "Fallback"},
            subject="Request", body="Body", idempotency_key="fallback-1",
        )
        with self.repo.connect() as connection:
            target = connection.execute("SELECT supplier_id FROM mail_send_operation_targets WHERE operation_id=?", (queued["operation_id"],)).fetchone()[0]
        self.assertEqual(int(target), supplier_id)

    def test_new_manual_email_creates_one_supplier(self) -> None:
        service = self.service_with_account()
        with self.repo.connect() as connection:
            before = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"email": "brand-new@example.com", "name": "New"},
            subject="Request", body="Body", idempotency_key="new-1",
        )
        with self.repo.connect() as connection:
            after = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        self.assertEqual(after, before + 1)

    def test_ambiguous_email_is_not_auto_resolved(self) -> None:
        self.add_host("ambiguous-a.example", "shared@example.com", inn="7726347929")
        self.add_host("ambiguous-b.example", "shared@example.com", inn="5903096662")
        self.add_hostless("shared@example.com")
        with self.repo.connect() as connection:
            report = scan_duplicates(connection)
        self.assertTrue(any(item["email"] == "shared@example.com" for item in report["ambiguous"]))

    def test_merge_preserves_request_relation_and_mail_history(self) -> None:
        canonical = self.add_host("canonical.example", "merge@example.com")
        duplicate = self.add_hostless("merge@example.com")
        service = self.service_with_account()
        queued = service.queue_one(
            user_id=self.user_id, workspace_id=self.workspace_id, request_id=self.request_id,
            supplier={"id": duplicate, "email": "merge@example.com", "name": "Merge"},
            subject="Request", body="Body", idempotency_key="merge-1",
        )
        with self.repo.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            merge_supplier_pair(connection, duplicate, canonical)
            connection.commit()
        with self.repo.connect() as connection:
            self.assertIsNotNone(connection.execute("SELECT 1 FROM request_suppliers WHERE request_id=? AND supplier_id=?", (self.request_id, canonical)).fetchone())
            message = connection.execute("SELECT supplier_id FROM mail_messages WHERE id=?", (queued["message_id"],)).fetchone()
            operation_target = connection.execute("SELECT supplier_id FROM mail_send_operation_targets WHERE operation_id=?", (queued["operation_id"],)).fetchone()
        self.assertIsNotNone(message)
        self.assertEqual(int(message[0]), canonical)
        self.assertIsNotNone(operation_target)
        self.assertEqual(int(operation_target[0]), canonical)

    def test_strict_scan_does_not_merge_exact_email_without_legal_identity(self) -> None:
        self.add_host("weak.example", "weak@example.com")
        self.add_hostless("weak@example.com")
        with self.repo.connect() as connection:
            report = strict_scan(connection)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["strict_safe_count"], 0)
        self.assertEqual(report["strict_unresolved_count"], 1)
        self.assertIn("confirmed INN/global identity", report["strict_failures"][0]["reason"])

    def test_merge_rolls_back_without_losing_duplicate(self) -> None:
        canonical = self.add_host("rollback.example", "rollback@example.com")
        duplicate = self.add_hostless("rollback@example.com")
        with self.repo.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            merge_supplier_pair(connection, duplicate, canonical)
            connection.rollback()
        with self.repo.connect() as connection:
            self.assertIsNotNone(connection.execute("SELECT 1 FROM suppliers WHERE id=?", (duplicate,)).fetchone())
            self.assertIsNotNone(connection.execute("SELECT 1 FROM request_suppliers WHERE request_id=? AND supplier_id=?", (self.request_id, duplicate)).fetchone())

    def test_dry_run_is_idempotent_and_does_not_write(self) -> None:
        self.add_host("idempotent.example", "idempotent@example.com")
        duplicate = self.add_hostless("idempotent@example.com")
        with self.repo.connect() as connection:
            first = scan_duplicates(connection)
            second = scan_duplicates(connection)
            supplier_count = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        self.assertEqual(first["candidate_count"], second["candidate_count"])
        self.assertGreaterEqual(first["candidate_count"], 1)
        self.assertIsNotNone(duplicate)
        self.assertGreater(supplier_count, 0)


if __name__ == "__main__":
    unittest.main()
