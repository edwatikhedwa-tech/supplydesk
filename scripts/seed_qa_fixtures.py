"""Deterministic synthetic QA fixtures for the disposable SAFE_TEST backend.

Seeds one request with three suppliers -- A (has correspondence), B (no
correspondence), C (has correspondence) -- into the SAFE_TEST SQLite
database, using the same MailRepository entry points production code uses
(upsert_supplier, create_request) plus the same mail_threads/mail_messages
insert pattern tests/test_ai_context_scoping.py already relies on. This
exists so frontend-v2 Playwright tests (Messages thread open, AI assistant
context selection) no longer have to SKIP for lack of test data.

Guarded to only ever run against a path that looks like a disposable test
database -- refuses anything else, including the real local-canonical DB.
Idempotent: re-running finds the fixture by its fixed request name and
does nothing if it is already present, so it is safe to call from
playwright.config.ts's globalSetup on every test run.

No real email addresses, no mailbox credentials, no production data.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mail.repository import MailRepository, iso_now  # noqa: E402

FIXTURE_REQUEST_NAME = "QA Fixture — AI контекст (не удалять)"
FIXTURE_USER_EMAIL = "test.user@example.invalid"

SUPPLIER_A = dict(external_key="qa-fixture-supplier-a.example", host="qa-fixture-supplier-a.example",
                   email="a@qa-fixture-supplier-a.example", name="ООО КЕЙС А (есть переписка)")
SUPPLIER_B = dict(external_key="qa-fixture-supplier-b.example", host="qa-fixture-supplier-b.example",
                   email="b@qa-fixture-supplier-b.example", name="ООО КЕЙС Б (без переписки)")
SUPPLIER_C = dict(external_key="qa-fixture-supplier-c.example", host="qa-fixture-supplier-c.example",
                   email="c@qa-fixture-supplier-c.example", name="ООО КЕЙС В (есть переписка)")


def _assert_disposable_path(db_path: Path) -> None:
    normalized = str(db_path).replace("\\", "/").lower()
    if "test-data" not in normalized and "disposable" not in normalized:
        raise SystemExit(
            f"REFUSING: {db_path} does not look like a disposable test database "
            "(expected 'test-data' or 'disposable' in the path). This script never "
            "runs against anything else."
        )


def _add_thread_with_message(connection, *, workspace_id: int, user_id: int, request_id: int,
                              supplier_id: int, account_id: int, subject: str, from_email: str) -> int:
    now = iso_now()
    connection.execute(
        """INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, last_message_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (workspace_id, user_id, request_id, supplier_id, account_id, subject, now, now),
    )
    thread_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    connection.execute(
        """INSERT INTO mail_messages(
               thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id,
               direction, from_email, to_email, subject, body_text, body_html, status, created_at, sent_at
           ) VALUES (?, ?, ?, ?, ?, ?, 'inbound', ?, ?, ?, ?, ?, 'sent', ?, ?)""",
        (
            thread_id, workspace_id, user_id, request_id, supplier_id, account_id,
            from_email, "buyer@example.invalid", f"Re: {subject}",
            "Добрый день! Готовы обсудить условия поставки.",
            "<p>Добрый день! Готовы обсудить условия поставки.</p>", now, now,
        ),
    )
    return thread_id


def seed(db_path: Path) -> dict:
    _assert_disposable_path(db_path)
    if not db_path.exists():
        raise SystemExit(f"REFUSING: {db_path} does not exist yet -- start the SAFE_TEST runtime first.")

    repo = MailRepository(db_path)
    with repo.connect() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE email = ?", (FIXTURE_USER_EMAIL,)
        ).fetchone()
        if not user_row:
            raise SystemExit(
                f"REFUSING: no user {FIXTURE_USER_EMAIL!r} in {db_path} -- log in once against the "
                "running SAFE_TEST backend first so the synthetic test user exists."
            )
        user_id = int(user_row["id"])
        workspace_row = connection.execute(
            "SELECT workspace_id FROM workspace_members WHERE user_id = ?", (user_id,)
        ).fetchone()
        workspace_id = int(workspace_row["workspace_id"])

        existing = connection.execute(
            "SELECT id FROM requests WHERE workspace_id = ? AND name = ?",
            (workspace_id, FIXTURE_REQUEST_NAME),
        ).fetchone()
        if existing:
            return {"status": "already_seeded", "request_id": int(existing["id"]), "workspace_id": workspace_id}

    request_id = repo.create_request(
        workspace_id, name=FIXTURE_REQUEST_NAME, description="Синтетическая заявка для QA-тестов (Playwright).",
        positions=[{"name": "Тестовая позиция", "quantity": "1"}],
        sender_name="QA", company_name="QA Fixture", user_id=user_id,
    )

    with repo.connect() as connection:
        account_row = connection.execute(
            "SELECT id FROM mail_accounts WHERE user_id = ? AND workspace_id = ? LIMIT 1",
            (user_id, workspace_id),
        ).fetchone()
        if account_row:
            account_id = int(account_row["id"])
        else:
            now = iso_now()
            connection.execute(
                """INSERT INTO mail_accounts(user_id, workspace_id, provider, email, status, created_at, updated_at)
                   VALUES (?, ?, 'fake', 'buyer@example.invalid', 'connected', ?, ?)""",
                (user_id, workspace_id, now, now),
            )
            account_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        supplier_a_id = repo.upsert_supplier(workspace_id=workspace_id, request_id=request_id, **SUPPLIER_A)
        supplier_b_id = repo.upsert_supplier(workspace_id=workspace_id, request_id=request_id, **SUPPLIER_B)
        supplier_c_id = repo.upsert_supplier(workspace_id=workspace_id, request_id=request_id, **SUPPLIER_C)

        thread_a = _add_thread_with_message(
            connection, workspace_id=workspace_id, user_id=user_id, request_id=request_id,
            supplier_id=supplier_a_id, account_id=account_id, subject="Тестовая позиция",
            from_email=SUPPLIER_A["email"],
        )
        # Supplier B intentionally gets no mail_threads/mail_messages row --
        # it is on the request but has no correspondence, per the AI-context
        # regression scenario (thread_ids must exclude B).
        thread_c = _add_thread_with_message(
            connection, workspace_id=workspace_id, user_id=user_id, request_id=request_id,
            supplier_id=supplier_c_id, account_id=account_id, subject="Тестовая позиция",
            from_email=SUPPLIER_C["email"],
        )

    return {
        "status": "seeded",
        "request_id": request_id,
        "workspace_id": workspace_id,
        "supplier_a_id": supplier_a_id,
        "supplier_b_id": supplier_b_id,
        "supplier_c_id": supplier_c_id,
        "thread_a_id": thread_a,
        "thread_c_id": thread_c,
    }


def main() -> None:
    default_path = ROOT / "runtime" / "test-data" / "supplier.sqlite3"
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    result = seed(db_path)
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
