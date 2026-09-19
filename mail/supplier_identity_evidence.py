"""Supplier identity evidence: why an email is believed to belong to a supplier card.

Composed into MailRepository as a mixin (same zero-coupling pattern as
mail/contact_intelligence.py). See migrations/053_supplier_identity_evidence.sql
and docs/domain/SUPPLIER_MODEL.md for the contract.

Three separate concerns (do not blur them):

* request-level association -- `request_id` on an evidence row: this address
  was used for this supplier in this request;
* supplier identity -- the `suppliers` row; reused for a new contact ONLY when
  a confirmed link exists (decision='linked', strength='strong');
* contact evidence -- the rows themselves, with source + strength.

Similarity between a mailbox name and a company/site name is a WEAK candidate
signal (`name_token_similarity`); it is recorded for review and never links.
"""

from __future__ import annotations

from typing import Any

from backend.domain.supplier_identity.email_extractor import TECHNICAL_LOCALS

from .time_utils import iso_now

# source_type -> (strength, decision). Only 'linked'/'strong' may make the
# system reuse an existing supplier identity for a new send.
_POLICY: dict[str, tuple[str, str]] = {
    # SupplyDesk itself addressed this supplier card at this address in this request.
    "rfq_sent": ("strong", "linked"),
    # A real inbound message from this address landed in this supplier's thread
    # (matched by reply headers or confirmed by the user) -- also the strongest
    # contact-intelligence signal (mail/contact_intelligence.py).
    "inbound_reply": ("strong", "linked"),
    "manual_confirmed": ("strong", "linked"),
    "official_source": ("strong", "linked"),
    "import": ("medium", "candidate"),
    "name_token_similarity": ("weak", "candidate"),
}


def _clean_email(value: Any) -> str:
    return str(value or "").strip().lower()


def is_contactable_person_address(email: str) -> bool:
    """False for empty/malformed and machine addresses (bounces, no-reply)."""
    email = _clean_email(email)
    local, _, domain = email.partition("@")
    return bool(local and domain and "." in domain and local not in TECHNICAL_LOCALS)


class SupplierIdentityEvidenceMixin:
    def _record_identity_evidence(
        self,
        connection: Any,
        *,
        workspace_id: int,
        supplier_id: int,
        kind: str,
        value: str,
        source_type: str,
        source_id: Any = "",
        request_id: int = 0,
        reason: str = "",
    ) -> None:
        """Idempotent append: the same fact recorded twice only refreshes last_verified_at."""
        value = _clean_email(value) if kind == "email" else str(value or "").strip().lower()
        if not value:
            return
        strength, decision = _POLICY[source_type]
        now = iso_now()
        connection.execute(
            """INSERT INTO supplier_identity_evidence(
                   workspace_id, supplier_id, request_id, kind, value, source_type, source_id,
                   strength, decision, reason, created_at, last_verified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(workspace_id, supplier_id, kind, value, source_type, source_id)
               DO UPDATE SET last_verified_at=excluded.last_verified_at""",
            (workspace_id, supplier_id, int(request_id or 0), kind, value, source_type,
             str(source_id or ""), strength, decision, reason[:300], now, now),
        )

    def _record_email_evidence_for_message(
        self,
        connection: Any,
        *,
        workspace_id: int,
        supplier_id: int,
        request_id: int,
        message_id: int,
        direction: str,
        email: str,
        source_type: str | None = None,
    ) -> None:
        """Hook called next to every real mail_messages insert (outbound RFQ / inbound reply)."""
        if not is_contactable_person_address(email):
            return
        self._record_identity_evidence(
            connection,
            workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
            kind="email", value=email,
            source_type=source_type or ("rfq_sent" if direction == "outbound" else "inbound_reply"),
            source_id=message_id,
            reason="RFQ отправлен на этот адрес по карточке поставщика в заявке."
            if direction == "outbound" else "Реальное входящее письмо с этого адреса в переписке поставщика.",
        )

    def _confirmed_supplier_ids_for_email(
        self, connection: Any, workspace_id: int, email: str, request_id: int,
    ) -> list[int]:
        """Supplier cards this workspace has CONFIRMED evidence link `email` to.

        Request-scoped evidence wins; otherwise workspace-wide. The join to
        `suppliers` re-checks the tenant boundary even if a stray row existed.
        """
        rows = connection.execute(
            """SELECT DISTINCT e.supplier_id, e.request_id
               FROM supplier_identity_evidence e
               JOIN suppliers s ON s.id=e.supplier_id AND s.workspace_id=e.workspace_id
               WHERE e.workspace_id=? AND e.kind='email' AND e.value=?
                 AND e.decision='linked' AND e.strength='strong' AND e.reverted_by_id IS NULL""",
            (workspace_id, _clean_email(email)),
        ).fetchall()
        in_request = sorted({int(r["supplier_id"]) for r in rows if int(r["request_id"]) == int(request_id)})
        if in_request:
            return in_request
        return sorted({int(r["supplier_id"]) for r in rows})

    def _record_weak_name_candidates(
        self, connection: Any, workspace_id: int, request_id: int, email: str, candidates: list[tuple[int, str]],
    ) -> None:
        from backend.domain.supplier_identity.contact_linking import weak_candidate_supplier_ids

        for supplier_id in weak_candidate_supplier_ids(email, candidates):
            self._record_identity_evidence(
                connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
                kind="email", value=email, source_type="name_token_similarity",
                source_id=f"request:{request_id}",
                reason="Имя ящика похоже на название сайта; требует подтверждения, сама не связывает.",
            )

    def confirm_supplier_contact(
        self, workspace_id: int, user_id: int, supplier_id: int, email: str, *, request_id: int = 0,
    ) -> dict[str, Any]:
        """A user explicitly confirms that `email` belongs to this supplier card."""
        with self.connect() as connection:
            if not connection.execute(
                "SELECT 1 FROM suppliers WHERE id=? AND workspace_id=?", (supplier_id, workspace_id),
            ).fetchone():
                raise ValueError("Поставщик не найден в текущем рабочем пространстве.")
            if not is_contactable_person_address(email):
                raise ValueError("Некорректный email.")
            self._record_identity_evidence(
                connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
                kind="email", value=email, source_type="manual_confirmed", source_id=f"user:{user_id}",
                reason="Пользователь подтвердил принадлежность адреса поставщику.",
            )
            self._audit_connection(
                connection, workspace_id, user_id, "supplier.contact_confirmed", "supplier", str(supplier_id),
                {"email": _clean_email(email), "request_id": request_id},
            )
        return {"supplier_id": supplier_id, "email": _clean_email(email)}

    def list_supplier_identity_evidence(
        self, workspace_id: int, *, supplier_id: int | None = None, email: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM supplier_identity_evidence WHERE workspace_id=?"
        params: list[Any] = [workspace_id]
        if supplier_id is not None:
            sql += " AND supplier_id=?"
            params.append(supplier_id)
        if email is not None:
            sql += " AND kind='email' AND value=?"
            params.append(_clean_email(email))
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(sql + " ORDER BY id", params).fetchall()]

    def backfill_email_evidence_from_messages(self, workspace_id: int) -> dict[str, int]:
        """Derive evidence from mail that already exists (idempotent, no deletes)."""
        recorded = 0
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, request_id, supplier_id, direction, from_email, to_email
                   FROM mail_messages
                   WHERE workspace_id=? AND ((direction='outbound' AND status='sent')
                                             OR (direction='inbound' AND status='received'))""",
                (workspace_id,),
            ).fetchall()
            for row in rows:
                outbound = row["direction"] == "outbound"
                email = row["to_email"] if outbound else row["from_email"]
                if not is_contactable_person_address(email):
                    continue
                self._record_email_evidence_for_message(
                    connection, workspace_id=workspace_id, supplier_id=int(row["supplier_id"]),
                    request_id=int(row["request_id"]), message_id=int(row["id"]),
                    direction=str(row["direction"]), email=email,
                )
                recorded += 1
        return {"messages_scanned": len(rows), "evidence_recorded": recorded}
