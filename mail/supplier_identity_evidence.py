"""Supplier identity evidence: THE store of primary facts about a supplier's contacts.

Composed into MailRepository as a mixin. See migrations/053 (evidence) and 054
(signal revocations) and docs/domain/SUPPLIER_MODEL.md §8.

One model, one writer per fact:

    supplier_identity_evidence   primary facts + provenance (this module writes them)
            |  single rule set per fact type (inbound / outbound / manual / contact result)
            v
    canonical_company_contact_signals   PROJECTION for cross-tenant contact intelligence,
            |  rebuilt only by `_reconcile_contact_projection` (idempotent; revoke / merge /
            |  unmerge just change evidence and re-run it)
            v
    canonical_company_contacts.status   quality of a contact (candidate/secondary/preferred/...)
                                        computed by mail/contact_intelligence.py

Three concerns stay separate:
* request-level association -- `assertion='association'` (`rfq_sent`): "we addressed this
  card at this address in this request". It NEVER proves the address belongs to the
  legal entity, so it is never sufficient to reuse a supplier identity;
* supplier identity -- reused for a new contact only on `assertion='ownership'`,
  `strength='strong'`, `state='confirmed'` (real inbound reply, manual/official confirmation);
* contact quality -- derived from confirmed evidence by the projection.

Name/domain similarity is a weak `candidate`; it never links anything.
"""

from __future__ import annotations

from typing import Any

from backend.domain.supplier_identity.email_extractor import TECHNICAL_LOCALS

from .bounce import classify_bounce, failed_recipients
from .time_utils import iso_now

# source_type -> (assertion, strength, initial state)
_POLICY: dict[str, tuple[str, str, str]] = {
    "rfq_sent": ("association", "medium", "confirmed"),
    "inbound_reply": ("ownership", "strong", "confirmed"),
    "manual_confirmed": ("ownership", "strong", "confirmed"),
    "official_source": ("ownership", "strong", "confirmed"),
    "workspace_contact_result": ("ownership", "weak", "confirmed"),
    "hard_bounce": ("deliverability", "weak", "confirmed"),
    "soft_bounce": ("deliverability", "weak", "confirmed"),
    "import": ("ownership", "medium", "candidate"),
    "name_token_similarity": ("ownership", "weak", "candidate"),
}

# TWO DIFFERENT QUESTIONS, never one score:
#   identity confidence -- "does this address belong to THIS supplier?"  -> `_POLICY`
#                          (assertion/strength/state of the evidence row itself);
#   contact quality     -- "is this address actually a working, useful contact?" -> `_SIGNAL_MAP`
#                          (the cross-tenant contact-intelligence signal the fact produces).
# They deliberately differ: `manual_confirmed` is STRONG identity evidence (a person vouched for it)
# but only a WEAK quality signal (nobody proved the mailbox answers); `inbound_reply` is strong for both;
# `rfq_sent` is neither; a bounce says nothing about identity but is negative for quality.
#
# Evidence -> cross-tenant contact-intelligence signal (signal_type, strength).
# Matches the pre-EDW-14 semantics: a real reply / official source is strong,
# a workspace's own confirmation is always weak, bounces are weak-negative.
_SIGNAL_MAP: dict[str, tuple[str, str]] = {
    "inbound_reply": ("inbound_reply", "strong"),
    "official_source": ("official_source", "strong"),
    "manual_confirmed": ("workspace_confirmed", "weak"),
    "workspace_contact_result": ("workspace_confirmed", "weak"),
    "hard_bounce": ("hard_bounce", "weak"),
    "soft_bounce": ("soft_bounce", "weak"),
}

# Signal sources written by the pre-EDW-14 independent paths; superseded by evidence.
_LEGACY_SIGNAL_SOURCE_PREFIXES = ("message:", "contact_event:")


def _clean_email(value: Any) -> str:
    return str(value or "").strip().lower()


def is_contactable_person_address(email: str) -> bool:
    """False for empty/malformed and machine addresses (bounces, no-reply, postmaster)."""
    local, _, domain = _clean_email(email).partition("@")
    return bool(local and domain and "." in domain and local not in TECHNICAL_LOCALS)


def sufficient_for_identity_reuse(assertion: str, strength: str, state: str) -> bool:
    """THE policy: only confirmed, strong ownership evidence may reuse a supplier identity."""
    return assertion == "ownership" and strength == "strong" and state == "confirmed"


class SupplierIdentityEvidenceMixin:
    # ------------------------------------------------------------------ write side
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
        occurred_at: str | None = None,
        decided_by_user_id: int | None = None,
    ) -> None:
        """Idempotent append. Re-recording a fact only refreshes last_verified_at: it never
        creates a second row and never resurrects a rejected/revoked one."""
        value = _clean_email(value) if kind == "email" else str(value or "").strip().lower()
        if not value:
            return
        assertion, strength, state = _POLICY[source_type]
        if assertion == "ownership" and state == "confirmed" and source_type != "manual_confirmed":
            # A human decision beats an automatic signal: after a user rejected/revoked this
            # (card, address), new automatic evidence may not silently re-confirm it.
            overruled = connection.execute(
                """SELECT 1 FROM supplier_identity_evidence
                   WHERE workspace_id=? AND supplier_id=? AND kind=? AND value=? AND assertion='ownership'
                     AND state IN ('rejected','revoked') AND decided_by_user_id IS NOT NULL LIMIT 1""",
                (workspace_id, supplier_id, kind, value),
            ).fetchone()
            if overruled:
                state = "candidate"
        now = iso_now()
        connection.execute(
            """INSERT INTO supplier_identity_evidence(
                   workspace_id, supplier_id, request_id, kind, value, source_type, source_id,
                   assertion, strength, state, reason, occurred_at, created_at, last_verified_at,
                   decided_by_user_id, decided_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(workspace_id, supplier_id, kind, value, source_type, source_id)
               DO UPDATE SET last_verified_at=excluded.last_verified_at""",
            (workspace_id, supplier_id, int(request_id or 0), kind, value, source_type, str(source_id or ""),
             assertion, strength, state, reason[:300], occurred_at or now, now, now,
             decided_by_user_id, now if decided_by_user_id is not None else None),
        )

    def _record_rfq_evidence(
        self, connection: Any, *, workspace_id: int, supplier_id: int, request_id: int,
        message_id: int, email: str, occurred_at: str | None = None,
    ) -> None:
        """Outbound RFQ: request-level association only (never proves ownership)."""
        if not is_contactable_person_address(email):
            return
        self._record_identity_evidence(
            connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
            kind="email", value=email, source_type="rfq_sent", source_id=message_id, occurred_at=occurred_at,
            reason="RFQ отправлен на этот адрес по карточке поставщика в заявке (связь в заявке, не владение).",
        )

    def _record_inbound_message_evidence(
        self, connection: Any, *, workspace_id: int, supplier_id: int, request_id: int, message_id: int,
        from_email: str, subject: str = "", body_text: str = "", body_html: str = "",
        occurred_at: str | None = None, confirmed_by_user: bool = False,
    ) -> None:
        """THE single rule for an inbound message in a supplier's thread (live sync, manual
        attach and backfill all call this): a bounce is deliverability evidence for the
        failed recipients; anything else from a real person is ownership evidence for the sender."""
        kind = classify_bounce(from_email=from_email, subject=subject, body_text=body_text)
        if kind is not None:
            for address in {_clean_email(a) for a in failed_recipients(body_text, body_html)}:
                if address:
                    self._record_identity_evidence(
                        connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
                        kind="email", value=address, source_type="hard_bounce" if kind == "hard" else "soft_bounce",
                        source_id=message_id, occurred_at=occurred_at, reason=f"{kind} bounce",
                    )
            return
        if not is_contactable_person_address(from_email):
            return
        self._record_identity_evidence(
            connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
            kind="email", value=from_email,
            source_type="manual_confirmed" if confirmed_by_user else "inbound_reply",
            source_id=message_id, occurred_at=occurred_at,
            reason="Пользователь привязал письмо с этого адреса к поставщику."
            if confirmed_by_user else "Реальное входящее письмо с этого адреса в переписке поставщика.",
        )

    def _record_weak_name_candidates(
        self, connection: Any, workspace_id: int, request_id: int, email: str, candidates: list[tuple[int, str]],
    ) -> None:
        from backend.domain.supplier_identity.contact_linking import weak_candidate_supplier_ids

        for supplier_id in weak_candidate_supplier_ids(email, candidates):
            self._record_identity_evidence(
                connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
                kind="email", value=email, source_type="name_token_similarity", source_id=f"request:{request_id}",
                reason="Имя ящика похоже на название сайта; требует подтверждения, само не связывает.",
            )

    # ------------------------------------------------------------------ read side (identity)
    def _confirmed_supplier_ids_for_email(
        self, connection: Any, workspace_id: int, email: str, request_id: int,
    ) -> list[int]:
        """Supplier cards for which this workspace holds SUFFICIENT evidence that `email` is theirs
        (`sufficient_for_identity_reuse`). Request-scoped evidence wins, else workspace-wide.
        The join re-checks the tenant boundary even if a stray row existed."""
        rows = connection.execute(
            """SELECT DISTINCT e.supplier_id, e.request_id
               FROM supplier_identity_evidence e
               JOIN suppliers s ON s.id=e.supplier_id AND s.workspace_id=e.workspace_id
               WHERE e.workspace_id=? AND e.kind='email' AND e.value=?
                 AND e.assertion='ownership' AND e.strength='strong' AND e.state='confirmed'""",
            (workspace_id, _clean_email(email)),
        ).fetchall()
        in_request = sorted({int(r["supplier_id"]) for r in rows if int(r["request_id"]) == int(request_id)})
        return in_request or sorted({int(r["supplier_id"]) for r in rows})

    def contact_state(self, workspace_id: int, email: str) -> dict[str, Any]:
        """Derived state of an address in this workspace:
        confirmed | ambiguous | candidate | revoked | rejected | unknown (+ supplier ids)."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT e.supplier_id, e.assertion, e.strength, e.state
                   FROM supplier_identity_evidence e
                   JOIN suppliers s ON s.id=e.supplier_id AND s.workspace_id=e.workspace_id
                   WHERE e.workspace_id=? AND e.kind='email' AND e.value=? AND e.assertion='ownership'""",
                (workspace_id, _clean_email(email)),
            ).fetchall()
        sufficient = sorted({int(r["supplier_id"]) for r in rows
                             if sufficient_for_identity_reuse(r["assertion"], r["strength"], r["state"])})
        states = {r["state"] for r in rows}
        if len(sufficient) > 1:
            state = "ambiguous"
        elif sufficient:
            state = "confirmed"
        else:
            state = next((s for s in ("candidate", "revoked", "rejected", "confirmed") if s in states), "unknown")
        rank = {"strong": 3, "medium": 2, "weak": 1}
        identity_confidence = max(
            (r["strength"] for r in rows if r["state"] == "confirmed"), key=lambda x: rank.get(x, 0), default="none")
        return {"email": _clean_email(email), "state": state, "supplier_ids": sufficient,
                "identity_confidence": identity_confidence}

    def contact_quality(self, workspace_id: int, email: str) -> dict[str, int]:
        """Contact QUALITY of an address in this workspace (separate from identity confidence): how many
        confirmed positive-strong / positive-weak / negative signals its evidence produces."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT e.source_type FROM supplier_identity_evidence e
                   JOIN suppliers s ON s.id=e.supplier_id AND s.workspace_id=e.workspace_id
                   WHERE e.workspace_id=? AND e.kind='email' AND e.value=? AND e.state='confirmed'""",
                (workspace_id, _clean_email(email)),
            ).fetchall()
        out = {"positive_strong": 0, "positive_weak": 0, "negative": 0}
        for r in rows:
            signal = _SIGNAL_MAP.get(r["source_type"])
            if not signal:
                continue
            kind, strength = signal
            if kind in ("hard_bounce", "soft_bounce"):
                out["negative"] += 1
            else:
                out["positive_strong" if strength == "strong" else "positive_weak"] += 1
        return out

    # ------------------------------------------------------------------ decisions (safe API)
    def _require_supplier(self, connection: Any, workspace_id: int, supplier_id: int, request_id: int | None) -> None:
        if not connection.execute(
            "SELECT 1 FROM suppliers WHERE id=? AND workspace_id=?", (supplier_id, workspace_id),
        ).fetchone():
            raise ValueError("Поставщик не найден в текущем рабочем пространстве.")
        if request_id and not connection.execute(
            "SELECT 1 FROM request_suppliers rs JOIN requests r ON r.id=rs.request_id "
            "WHERE rs.request_id=? AND rs.supplier_id=? AND r.workspace_id=?",
            (request_id, supplier_id, workspace_id),
        ).fetchone():
            raise ValueError("Поставщик не найден в этой заявке.")

    def confirm_supplier_contact(
        self, workspace_id: int, user_id: int, supplier_id: int, email: str, *, request_id: int = 0,
    ) -> dict[str, Any]:
        """candidate -> confirmed: a user states that `email` belongs to this supplier card."""
        if not is_contactable_person_address(email):
            raise ValueError("Некорректный email.")
        with self.connect() as connection:
            self._require_supplier(connection, workspace_id, supplier_id, request_id)
            self._record_identity_evidence(
                connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
                kind="email", value=email, source_type="manual_confirmed", source_id=f"user:{user_id}",
                reason="Пользователь подтвердил принадлежность адреса поставщику.", decided_by_user_id=user_id,
            )
            # An explicit confirmation also re-confirms a previously revoked/rejected manual decision.
            connection.execute(
                """UPDATE supplier_identity_evidence SET state='confirmed', decided_by_user_id=?, decided_at=?
                   WHERE workspace_id=? AND supplier_id=? AND kind='email' AND value=? AND source_type='manual_confirmed'""",
                (user_id, iso_now(), workspace_id, supplier_id, _clean_email(email)),
            )
            connection.execute(
                """UPDATE supplier_identity_evidence SET state='confirmed', decided_by_user_id=?, decided_at=?
                   WHERE workspace_id=? AND supplier_id=? AND kind='email' AND value=? AND state='candidate'
                     AND assertion='ownership'""",
                (user_id, iso_now(), workspace_id, supplier_id, _clean_email(email)),
            )
            self._audit_connection(
                connection, workspace_id, user_id, "supplier.contact_confirmed", "supplier", str(supplier_id),
                {"email": _clean_email(email), "request_id": request_id},
            )
            self.sync_contact_intelligence_for_supplier(connection, workspace_id, supplier_id)
        return {"supplier_id": supplier_id, "email": _clean_email(email), "state": "confirmed"}

    def reject_supplier_contact(
        self, workspace_id: int, user_id: int, supplier_id: int, email: str, *, request_id: int = 0,
    ) -> dict[str, Any]:
        """candidate -> rejected: a user says this address does NOT belong to this card. Sticky:
        automatic evidence can no longer confirm this (card, address)."""
        with self.connect() as connection:
            self._require_supplier(connection, workspace_id, supplier_id, request_id)
            changed = connection.execute(
                """UPDATE supplier_identity_evidence SET state='rejected', decided_by_user_id=?, decided_at=?
                   WHERE workspace_id=? AND supplier_id=? AND kind='email' AND value=? AND state='candidate'
                     AND assertion='ownership'""",
                (user_id, iso_now(), workspace_id, supplier_id, _clean_email(email)),
            ).rowcount
            self._audit_connection(
                connection, workspace_id, user_id, "supplier.contact_rejected", "supplier", str(supplier_id),
                {"email": _clean_email(email), "rows": changed},
            )
        return {"supplier_id": supplier_id, "email": _clean_email(email), "state": "rejected", "rows": changed}

    def revoke_supplier_contact(
        self, workspace_id: int, user_id: int, supplier_id: int, email: str, *, reason: str = "", request_id: int = 0,
    ) -> dict[str, Any]:
        """confirmed -> revoked: withdraw ownership evidence. The card stops being reusable for this
        address and the contact-intelligence projection is recomputed immediately. Sticky like reject."""
        with self.connect() as connection:
            self._require_supplier(connection, workspace_id, supplier_id, request_id)
            now = iso_now()
            changed = connection.execute(
                """UPDATE supplier_identity_evidence SET state='revoked', decided_by_user_id=?, decided_at=?, revoke_reason=?
                   WHERE workspace_id=? AND supplier_id=? AND kind='email' AND value=?
                     AND assertion='ownership' AND state='confirmed'""",
                (user_id, now, str(reason or "")[:300], workspace_id, supplier_id, _clean_email(email)),
            ).rowcount
            self._audit_connection(
                connection, workspace_id, user_id, "supplier.contact_revoked", "supplier", str(supplier_id),
                {"email": _clean_email(email), "rows": changed, "reason": reason},
            )
            self.sync_contact_intelligence_for_supplier(connection, workspace_id, supplier_id)
        return {"supplier_id": supplier_id, "email": _clean_email(email), "state": "revoked", "rows": changed}

    def list_supplier_identity_evidence(
        self, workspace_id: int, *, supplier_id: int | None = None, email: str | None = None, state: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM supplier_identity_evidence WHERE workspace_id=?"
        params: list[Any] = [workspace_id]
        if supplier_id is not None:
            sql += " AND supplier_id=?"
            params.append(supplier_id)
        if email is not None:
            sql += " AND kind='email' AND value=?"
            params.append(_clean_email(email))
        if state is not None:
            sql += " AND state=?"
            params.append(state)
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(sql + " ORDER BY id", params).fetchall()]

    # ------------------------------------------------------------------ backfill
    def _backfill_evidence_for_suppliers(self, connection: Any, workspace_id: int, supplier_ids: list[int]) -> dict[str, int]:
        """Derive evidence from mail/contact events that already exist, through the SAME rules as the
        live hooks (idempotent: source_id is the message/event id, so re-running adds nothing)."""
        if not supplier_ids:
            return {"messages_scanned": 0, "events_scanned": 0}
        marks = ",".join("?" * len(supplier_ids))
        messages = connection.execute(
            f"""SELECT id, request_id, supplier_id, direction, from_email, to_email, subject,
                       body_text, body_html, created_at
                FROM mail_messages WHERE workspace_id=? AND supplier_id IN ({marks})""",
            (workspace_id, *supplier_ids),
        ).fetchall()
        for row in messages:
            if row["direction"] == "outbound":
                self._record_rfq_evidence(
                    connection, workspace_id=workspace_id, supplier_id=int(row["supplier_id"]),
                    request_id=int(row["request_id"]), message_id=int(row["id"]), email=row["to_email"],
                    occurred_at=row["created_at"],
                )
            elif row["direction"] == "inbound":
                self._record_inbound_message_evidence(
                    connection, workspace_id=workspace_id, supplier_id=int(row["supplier_id"]),
                    request_id=int(row["request_id"]), message_id=int(row["id"]), from_email=row["from_email"] or "",
                    subject=row["subject"] or "", body_text=row["body_text"] or "", body_html=row["body_html"] or "",
                    occurred_at=row["created_at"],
                )
        events = connection.execute(
            f"""SELECT e.id, e.request_id, e.supplier_id, e.result, e.new_email, e.created_at, s.email AS supplier_email
                FROM workspace_supplier_contact_events e JOIN suppliers s ON s.id=e.supplier_id
                WHERE e.workspace_id=? AND e.supplier_id IN ({marks})
                  AND e.result IN ('contact_confirmed', 'new_email_provided')""",
            (workspace_id, *supplier_ids),
        ).fetchall()
        for ev in events:
            email = ev["new_email"] if ev["result"] == "new_email_provided" else ev["supplier_email"]
            if is_contactable_person_address(email):
                self._record_identity_evidence(
                    connection, workspace_id=workspace_id, supplier_id=int(ev["supplier_id"]),
                    request_id=int(ev["request_id"]), kind="email", value=email,
                    source_type="workspace_contact_result", source_id=f"contact_event:{int(ev['id'])}",
                    occurred_at=ev["created_at"], reason=f"contact result: {ev['result']}",
                )
        return {"messages_scanned": len(messages), "events_scanned": len(events)}

    def backfill_email_evidence_from_messages(self, workspace_id: int) -> dict[str, int]:
        """Whole-workspace backfill (idempotent, no deletes)."""
        with self.connect() as connection:
            ids = [int(r["id"]) for r in connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id=?", (workspace_id,)).fetchall()]
            before = connection.execute(
                "SELECT COUNT(*) AS n FROM supplier_identity_evidence WHERE workspace_id=?", (workspace_id,)).fetchone()["n"]
            stats = self._backfill_evidence_for_suppliers(connection, workspace_id, ids)
            after = connection.execute(
                "SELECT COUNT(*) AS n FROM supplier_identity_evidence WHERE workspace_id=?", (workspace_id,)).fetchone()["n"]
        return {**stats, "evidence_recorded": int(after) - int(before)}

    # ------------------------------------------------------------------ projection into contact intelligence
    def sync_contact_intelligence_for_supplier(self, connection: Any, workspace_id: int, supplier_id: int) -> int | None:
        """The ONE entry point that brings the derived contact-intelligence state in line with
        evidence for a supplier card (called after any evidence decision, merge/unmerge, and by
        the pull-based contact read). Returns the canonical company id, or None if not linked."""
        link = connection.execute(
            """SELECT gl.global_supplier_id FROM global_supplier_links gl
               JOIN suppliers s ON s.id=gl.supplier_id WHERE s.id=? AND s.workspace_id=?""",
            (supplier_id, workspace_id),
        ).fetchone()
        if not link or link["global_supplier_id"] is None:
            return None
        return self._sync_workspace_contact_signals(connection, workspace_id, int(link["global_supplier_id"]), iso_now())

    def _reconcile_contact_projection(self, connection: Any, workspace_id: int, canonical_company_id: int) -> set[str]:
        """Make this workspace's signals for this company equal the projection of its CONFIRMED
        evidence: insert what is missing, un-revoke what is supported again, revoke what is no
        longer supported (revoked evidence, moved by merge, superseded legacy path). Idempotent.
        Returns the emails whose derived status must be recomputed."""
        company = connection.execute("SELECT inn FROM canonical_companies WHERE id=?", (canonical_company_id,)).fetchone()
        if not company:
            return set()
        marks = ",".join("?" * len(_SIGNAL_MAP))
        evidence = connection.execute(
            f"""SELECT e.id, e.value, e.source_type, e.occurred_at
                FROM supplier_identity_evidence e
                JOIN suppliers s ON s.id=e.supplier_id AND s.workspace_id=e.workspace_id
                JOIN global_supplier_links gl ON gl.supplier_id=s.id
                JOIN global_suppliers g ON g.id=gl.global_supplier_id AND g.workspace_id=e.workspace_id
                WHERE e.workspace_id=? AND g.inn=? AND e.kind='email' AND e.state='confirmed'
                  AND e.source_type IN ({marks})""",
            (workspace_id, company["inn"], *_SIGNAL_MAP),
        ).fetchall()
        desired = {f"evidence:{int(e['id'])}": (e["value"], *_SIGNAL_MAP[e["source_type"]], e["occurred_at"]) for e in evidence}

        now = iso_now()
        touched: set[str] = set()
        existing = {
            (r["source"], r["email"], r["signal_type"]): int(r["id"])
            for r in connection.execute(
                """SELECT id, source, email, signal_type FROM canonical_company_contact_signals
                   WHERE canonical_company_id=? AND workspace_id=?""",
                (canonical_company_id, workspace_id),
            ).fetchall()
        }
        revoked = {int(r["signal_id"]) for r in connection.execute(
            "SELECT signal_id FROM canonical_company_contact_signal_revocations").fetchall()}

        for source, (email, signal_type, strength, occurred_at) in desired.items():
            signal_id = existing.get((source, email, signal_type))
            if signal_id is None:
                self._insert_contact_signal(
                    connection, canonical_company_id=canonical_company_id, email=email, signal_type=signal_type,
                    strength=strength, workspace_id=workspace_id, source=source, basis="supplier_identity_evidence",
                    created_at=occurred_at,
                )
                touched.add(email)
            elif signal_id in revoked:
                connection.execute("DELETE FROM canonical_company_contact_signal_revocations WHERE signal_id=?", (signal_id,))
                touched.add(email)
        for (source, email, signal_type), signal_id in existing.items():
            if signal_id in revoked:
                continue
            if source.startswith("evidence:"):
                supported = source in desired and desired[source][0] == email and desired[source][1] == signal_type
                reason = "supporting evidence revoked or moved"
            elif source.startswith(_LEGACY_SIGNAL_SOURCE_PREFIXES):
                supported, reason = False, "superseded by supplier_identity_evidence (single source of truth)"
            else:
                continue  # signals from other writers are not ours to touch
            if not supported:
                connection.execute(
                    """INSERT INTO canonical_company_contact_signal_revocations(signal_id, reason, revoked_at)
                       VALUES (?, ?, ?) ON CONFLICT(signal_id) DO NOTHING""",
                    (signal_id, reason, now),
                )
                touched.add(email)
        return touched
