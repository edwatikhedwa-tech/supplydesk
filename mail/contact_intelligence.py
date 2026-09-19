"""Follow-up tracking and self-updating supplier contacts (SUP-030).

Two independent layers, composed into MailRepository as one mixin (same
zero-coupling pattern as mail/logistics_quotes.py, mail/canonical_companies.py):

1. **needs_followup** -- a purely derived (never stored) flag on a thread
   that has a successfully sent outbound message, no reply, and has been
   waiting at least the request's configured SLA (default 2 business days).
   Exactly the same kind of client-would-otherwise-compute-it derivation as
   ``frontend-v2/src/lib/derive.ts::threadResponseStatus`` -- computed once,
   server-side, so both the API and any future caller agree on one answer.

2. **Cross-tenant contact consensus** -- extends canonical_companies
   (DECISION-022, mail/canonical_companies.py) with a candidate/preferred/
   secondary/deprecated email registry per company (keyed by ИНН, not by any
   workspace's own global_suppliers.id -- see docs/domain/SUPPLIER_MODEL.md
   §6 and DECISION-024 for why). A per-workspace override
   (workspace_supplier_contact_overrides) takes effect immediately and only
   within that workspace, independent of the slower cross-tenant consensus.

See docs/domain/SUPPLIER_MODEL.md §7 for the full contract this implements.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .supplier_identity_evidence import is_contactable_person_address
from .time_utils import iso_now

UTC = timezone.utc

DEFAULT_FOLLOWUP_SLA_BUSINESS_DAYS = 2

_CONTACT_RESULTS = {
    "not_reached",
    "contact_confirmed",
    "new_email_provided",
    "call_back_later",
    "supplier_declines",
}

# Only a real inbound reply or an explicit official-source confirmation counts
# as "strong" per the product spec -- a phone-call confirmation (workspace_confirmed)
# is always weak, no matter how many workspaces report it.
_STRONG_SIGNAL_TYPES = ("inbound_reply", "official_source")
_POSITIVE_SIGNAL_TYPES = ("workspace_confirmed", "inbound_reply", "official_source")
_MIN_INDEPENDENT_WORKSPACES = 3


def _normalized_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _business_days_elapsed(since_iso: str | None, now: datetime) -> int:
    """Whole weekdays strictly between `since_iso` and `now` (Mon-Fri only).

    No public-holiday calendar -- disclosed scope boundary, see
    docs/domain/SUPPLIER_MODEL.md §7.
    """
    if not since_iso:
        return 0
    try:
        since = datetime.fromisoformat(str(since_iso))
    except ValueError:
        return 0
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    if now <= since:
        return 0
    count = 0
    cursor = since.date()
    end = now.date()
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            count += 1
    return count


class ContactIntelligenceMixin:
    # ------------------------------------------------------------------
    # needs_followup
    # ------------------------------------------------------------------

    def get_followup_settings(self, workspace_id: int, request_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            request = connection.execute(
                "SELECT id FROM requests WHERE workspace_id=? AND id=?", (workspace_id, request_id),
            ).fetchone()
            if not request:
                raise ValueError("Заявка не найдена.")
            row = connection.execute(
                "SELECT sla_business_days FROM request_followup_settings WHERE request_id=?",
                (request_id,),
            ).fetchone()
        return {
            "request_id": request_id,
            "sla_business_days": int(row["sla_business_days"]) if row else DEFAULT_FOLLOWUP_SLA_BUSINESS_DAYS,
            "is_default": row is None,
        }

    def set_followup_settings(self, workspace_id: int, user_id: int, request_id: int, sla_business_days: Any) -> dict[str, Any]:
        try:
            sla = int(sla_business_days)
        except (TypeError, ValueError):
            raise ValueError("Срок ожидания ответа должен быть целым числом рабочих дней.")
        if sla < 1 or sla > 30:
            raise ValueError("Срок ожидания ответа должен быть от 1 до 30 рабочих дней.")
        now = iso_now()
        with self.connect() as connection:
            request = connection.execute(
                "SELECT id FROM requests WHERE workspace_id=? AND id=?", (workspace_id, request_id),
            ).fetchone()
            if not request:
                raise ValueError("Заявка не найдена.")
            connection.execute(
                """INSERT INTO request_followup_settings(request_id, sla_business_days, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(request_id) DO UPDATE SET
                       sla_business_days=excluded.sla_business_days, updated_at=excluded.updated_at""",
                (request_id, sla, now),
            )
            self._audit_connection(
                connection, workspace_id, user_id, "mail.followup_settings.updated",
                "request", str(request_id), {"sla_business_days": sla},
            )
        return {"request_id": request_id, "sla_business_days": sla, "is_default": False}

    def annotate_needs_followup(self, workspace_id: int, items: list[dict[str, Any]]) -> None:
        """Mutates `items` (as returned by list_threads) in place, adding
        `needs_followup`. A thread needs follow-up only when: at least one
        message exists, there is no reply yet, the most recent outbound
        message actually reached SMTP ("sent" -- not queued/failed/bounced/
        delivery_unknown/cancelled), and the request's configured SLA (default
        2 business days) has elapsed since it was sent. This is a strictly
        derived read -- it never writes anything and is never itself a
        message/thread status (see docs/ui/MESSAGES_SCREEN_SPEC.md §13 for
        why conversation_status/threadResponseStatus stay untouched).
        """
        request_ids = {int(item["request_id"]) for item in items if item.get("request_id") is not None}
        sla_map: dict[int, int] = {}
        if request_ids:
            with self.connect() as connection:
                placeholders = ",".join("?" * len(request_ids))
                rows = connection.execute(
                    f"SELECT request_id, sla_business_days FROM request_followup_settings "
                    f"WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                ).fetchall()
            sla_map = {int(row["request_id"]): int(row["sla_business_days"]) for row in rows}
        now = datetime.now(UTC)
        for item in items:
            if item.get("manual_inbox_id") is not None:
                item["needs_followup"] = False
                continue
            messages_count = int(item.get("messages_count") or 0)
            replies_count = int(item.get("replies_count") or 0)
            if messages_count <= 0 or replies_count > 0 or item.get("last_outbound_status") != "sent":
                item["needs_followup"] = False
                continue
            sla = sla_map.get(int(item["request_id"]), DEFAULT_FOLLOWUP_SLA_BUSINESS_DAYS)
            item["needs_followup"] = _business_days_elapsed(item.get("last_message_at"), now) >= sla

    # ------------------------------------------------------------------
    # Cross-tenant contact consensus
    # ------------------------------------------------------------------

    def _ensure_canonical_company_id(self, connection: Any, workspace_id: int, global_supplier_id: int) -> int | None:
        row = connection.execute(
            "SELECT inn FROM global_suppliers WHERE workspace_id=? AND id=?",
            (workspace_id, global_supplier_id),
        ).fetchone()
        inn = str(row["inn"] or "").strip() if row else ""
        if not inn:
            return None
        now = iso_now()
        connection.execute(
            """INSERT INTO canonical_companies(inn, first_seen_at, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(inn) DO NOTHING""",
            (inn, now, now),
        )
        existing = connection.execute("SELECT id FROM canonical_companies WHERE inn=?", (inn,)).fetchone()
        return int(existing["id"]) if existing else None

    def _lookup_canonical_company_id(self, connection: Any, workspace_id: int, global_supplier_id: int) -> int | None:
        """Read-only counterpart to `_ensure_canonical_company_id` -- never
        creates a `canonical_companies` row. Used by `resolve_contact_priority`
        so that function stays genuinely side-effect-free (callable from a
        read-only preview on every keystroke without writing anything): if no
        row exists yet for this ИНН, no workspace has ever recorded a contact
        signal for this company, so there is certainly no global-preferred
        contact to find either way -- "not found" is already the correct,
        complete answer, and creating an empty placeholder row would not
        change it.
        """
        row = connection.execute(
            "SELECT inn FROM global_suppliers WHERE workspace_id=? AND id=?",
            (workspace_id, global_supplier_id),
        ).fetchone()
        inn = str(row["inn"] or "").strip() if row else ""
        if not inn:
            return None
        existing = connection.execute("SELECT id FROM canonical_companies WHERE inn=?", (inn,)).fetchone()
        return int(existing["id"]) if existing else None

    def _insert_contact_signal(
        self, connection: Any, *, canonical_company_id: int, email: str, signal_type: str,
        strength: str, workspace_id: int, source: str, basis: str, created_at: str,
    ) -> None:
        email = _normalized_email(email)
        if not email:
            return
        connection.execute(
            """INSERT INTO canonical_company_contact_signals(
                   canonical_company_id, email, signal_type, strength, workspace_id, source, basis, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(canonical_company_id, email, signal_type, source) DO NOTHING""",
            (canonical_company_id, email, signal_type, strength, workspace_id, source, basis, created_at),
        )

    def _unresolved_hard_bounce(self, connection: Any, canonical_company_id: int, email: str) -> bool:
        """True when this email's most recent hard bounce is not yet
        superseded by a later positive signal. Shared by `_recompute_contact_status`
        (promotion/demotion) and `resolve_contact_priority` (choosing who
        to send to) so the two never disagree about whether a contact is
        currently trusted.
        """
        last_hard = connection.execute(
            """SELECT MAX(created_at) AS ts FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
               WHERE canonical_company_id=? AND email=? AND signal_type='hard_bounce'""",
            (canonical_company_id, email),
        ).fetchone()["ts"]
        if not last_hard:
            return False
        last_positive = connection.execute(
            f"""SELECT MAX(created_at) AS ts FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
               WHERE canonical_company_id=? AND email=? AND signal_type IN
               ({','.join('?' * len(_POSITIVE_SIGNAL_TYPES))})""",
            (canonical_company_id, email, *_POSITIVE_SIGNAL_TYPES),
        ).fetchone()["ts"]
        return not last_positive or str(last_hard) > str(last_positive)

    def resolve_contact_priority(
        self, workspace_id: int, supplier_id: int | None, *, fallback_email: str, purpose: str = "rfq",
    ) -> dict[str, Any]:
        """THE single shared, side-effect-free resolver for "which address
        would we send this workspace's next outbound message to" -- callable
        from anywhere that needs the answer: `preflight_bulk`'s campaign
        preview, `resolve_supplier_for_send`'s actual send finalization
        (mail/repository.py), and any future place that displays the
        eventual recipient. Preview and send call this exact same function
        at the exact same relative point in each flow (right after
        `_select_contact_for_request` has picked which known contact to use
        for a company card) -- there is no separate, parallel copy of this
        priority logic anywhere, so the two can never disagree while the
        underlying data hasn't changed (FINDING-037).

        Performs no writes and no audit logging -- safe to call on every
        preview render. (The one read it does, `_lookup_canonical_company_id`,
        never creates a `canonical_companies` row -- see its docstring for
        why that is still a complete, correct answer.) A caller that acts on
        the result for a REAL send (`resolve_supplier_for_send`) is
        responsible for logging any reported `demotions` to the audit trail
        itself, once, at the moment it commits to actually sending -- never
        this function, which does not know or care whether its caller is
        a preview or a real send.

        Priority, per the product spec: (1) this workspace's own preferred
        override, unless it has an unresolved hard bounce; (2) the
        cross-tenant global preferred contact (DECISION-024), unless it too
        has an unresolved hard bounce; (3) the caller-supplied fallback
        (`suppliers.email`/whatever the existing flow already resolved --
        untouched, so a supplier with no override and no global preferred
        behaves exactly as before this feature existed). A hard-bounced
        candidate is never silently used: it is skipped in favor of the next
        tier and recorded in the returned `demotions` list, never applied
        blindly and never dropped without a trace.

        `supplier_id` is `suppliers.id` (request-scoped); resolution is
        strictly scoped to `workspace_id` -- a supplier id belonging to
        another workspace can never leak that workspace's override or be
        used to probe it (AC-05-equivalent isolation for send resolution).
        Always resolves fresh from current data -- nothing here is cached
        across calls, so a real send always re-resolves against whatever is
        true at that moment, even if a preview looked different earlier.
        """
        fallback_email = _normalized_email(fallback_email)
        result: dict[str, Any] = {
            "email": fallback_email, "source": "fallback",
            "global_supplier_id": None, "demotions": [],
        }
        if not supplier_id:
            return result
        with self.connect() as connection:
            link = connection.execute(
                """SELECT gl.global_supplier_id FROM suppliers s
                   JOIN global_supplier_links gl ON gl.supplier_id = s.id
                   WHERE s.id=? AND s.workspace_id=?""",
                (supplier_id, workspace_id),
            ).fetchone()
            if not link or link["global_supplier_id"] is None:
                return result
            global_supplier_id = int(link["global_supplier_id"])
            result["global_supplier_id"] = global_supplier_id
            canonical_company_id = self._lookup_canonical_company_id(connection, workspace_id, global_supplier_id)

            override_row = connection.execute(
                """SELECT email FROM workspace_supplier_contact_overrides
                   WHERE workspace_id=? AND global_supplier_id=? AND purpose=? AND superseded_at IS NULL
                   ORDER BY created_at DESC LIMIT 1""",
                (workspace_id, global_supplier_id, purpose),
            ).fetchone()
            if override_row:
                override_email = _normalized_email(override_row["email"])
                if canonical_company_id is not None and self._unresolved_hard_bounce(connection, canonical_company_id, override_email):
                    result["demotions"].append({"email": override_email, "source": "workspace_preferred", "reason": "hard_bounce"})
                else:
                    result.update(email=override_email, source="workspace_preferred")
                    return result

            if canonical_company_id is not None:
                preferred_row = connection.execute(
                    """SELECT email FROM canonical_company_contacts
                       WHERE canonical_company_id=? AND status='preferred'
                       ORDER BY updated_at DESC LIMIT 1""",
                    (canonical_company_id,),
                ).fetchone()
                if preferred_row:
                    preferred_email = _normalized_email(preferred_row["email"])
                    if self._unresolved_hard_bounce(connection, canonical_company_id, preferred_email):
                        result["demotions"].append({"email": preferred_email, "source": "global_preferred", "reason": "hard_bounce"})
                    else:
                        result.update(email=preferred_email, source="global_preferred")
                        return result
        return result

    def _recompute_contact_status(self, connection: Any, canonical_company_id: int, email: str, now: str) -> None:
        email = _normalized_email(email)
        if not email:
            return
        row = connection.execute(
            "SELECT id, status FROM canonical_company_contacts WHERE canonical_company_id=? AND email=?",
            (canonical_company_id, email),
        ).fetchone()
        if row:
            contact_id, current_status = int(row["id"]), str(row["status"])
        else:
            connection.execute(
                """INSERT INTO canonical_company_contacts(
                       canonical_company_id, email, purpose, status, first_seen_at, updated_at
                   ) VALUES (?, ?, 'unknown', 'candidate', ?, ?)""",
                (canonical_company_id, email, now, now),
            )
            created = connection.execute(
                "SELECT id FROM canonical_company_contacts WHERE canonical_company_id=? AND email=?",
                (canonical_company_id, email),
            ).fetchone()
            contact_id, current_status = int(created["id"]), "candidate"

        strong_ts = connection.execute(
            f"""SELECT MAX(created_at) AS ts FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
               WHERE canonical_company_id=? AND email=? AND signal_type IN
               ({','.join('?' * len(_STRONG_SIGNAL_TYPES))})""",
            (canonical_company_id, email, *_STRONG_SIGNAL_TYPES),
        ).fetchone()["ts"]
        if strong_ts:
            connection.execute(
                "UPDATE canonical_company_contacts SET last_verified_at=?, updated_at=? WHERE id=?",
                (strong_ts, now, contact_id),
            )

        distinct_workspaces = int(connection.execute(
            f"""SELECT COUNT(DISTINCT workspace_id) AS n FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
               WHERE canonical_company_id=? AND email=? AND signal_type IN
               ({','.join('?' * len(_POSITIVE_SIGNAL_TYPES))})""",
            (canonical_company_id, email, *_POSITIVE_SIGNAL_TYPES),
        ).fetchone()["n"])
        has_strong = bool(strong_ts)

        unresolved_hard_bounce = self._unresolved_hard_bounce(connection, canonical_company_id, email)

        eligible = distinct_workspaces >= _MIN_INDEPENDENT_WORKSPACES and has_strong and not unresolved_hard_bounce

        if eligible and current_status != "preferred":
            previous_preferred = connection.execute(
                """SELECT id, email FROM canonical_company_contacts
                   WHERE canonical_company_id=? AND status='preferred' AND email<>?""",
                (canonical_company_id, email),
            ).fetchall()
            for previous in previous_preferred:
                connection.execute(
                    "UPDATE canonical_company_contacts SET status='secondary', updated_at=? WHERE id=?",
                    (now, int(previous["id"])),
                )
                connection.execute(
                    """INSERT INTO canonical_company_contact_promotions(
                           canonical_company_id, email, from_status, to_status,
                           confirming_workspace_count, had_strong_signal, reason, decided_at
                       ) VALUES (?, ?, 'preferred', 'secondary', ?, ?, ?, ?)""",
                    (canonical_company_id, previous["email"], distinct_workspaces, int(has_strong),
                     "superseded by a newly promoted preferred contact", now),
                )
            connection.execute(
                "UPDATE canonical_company_contacts SET status='preferred', updated_at=? WHERE id=?",
                (now, contact_id),
            )
            connection.execute(
                """INSERT INTO canonical_company_contact_promotions(
                       canonical_company_id, email, from_status, to_status,
                       confirming_workspace_count, had_strong_signal, reason, decided_at
                   ) VALUES (?, ?, ?, 'preferred', ?, ?, ?, ?)""",
                (canonical_company_id, email, current_status, distinct_workspaces, int(has_strong),
                 f"{distinct_workspaces} independent workspaces confirmed + a strong signal was present", now),
            )
        elif current_status == "preferred" and not unresolved_hard_bounce and not eligible:
            # Supporting evidence was revoked / moved away (EDW-14): trust must follow the evidence.
            connection.execute(
                "UPDATE canonical_company_contacts SET status='secondary', updated_at=? WHERE id=?",
                (now, contact_id),
            )
            connection.execute(
                """INSERT INTO canonical_company_contact_promotions(
                       canonical_company_id, email, from_status, to_status,
                       confirming_workspace_count, had_strong_signal, reason, decided_at
                   ) VALUES (?, ?, 'preferred', 'secondary', ?, ?, ?, ?)""",
                (canonical_company_id, email, distinct_workspaces, int(has_strong),
                 "supporting evidence is no longer sufficient", now),
            )
        elif current_status == "preferred" and unresolved_hard_bounce:
            connection.execute(
                "UPDATE canonical_company_contacts SET status='secondary', updated_at=? WHERE id=?",
                (now, contact_id),
            )
            connection.execute(
                """INSERT INTO canonical_company_contact_promotions(
                       canonical_company_id, email, from_status, to_status,
                       confirming_workspace_count, had_strong_signal, reason, decided_at
                   ) VALUES (?, ?, 'preferred', 'secondary', ?, ?, ?, ?)""",
                (canonical_company_id, email, distinct_workspaces, int(has_strong),
                 "hard bounce reduced trust in this contact", now),
            )

    def _sync_workspace_contact_signals(self, connection: Any, workspace_id: int, global_supplier_id: int, now: str) -> int | None:
        """Idempotently derive signals from this workspace's OWN real
        correspondence with this global supplier. Deliberately pull-based
        (called from a read/write entrypoint below) rather than hooked into
        live inbound ingestion, to keep this additive feature out of the
        high-risk mail-receiving critical path -- see
        docs/domain/SUPPLIER_MODEL.md §7 for the disclosed trade-off.
        """
        canonical_company_id = self._ensure_canonical_company_id(connection, workspace_id, global_supplier_id)
        if canonical_company_id is None:
            return None
        # EDW-14: contact intelligence is a PROJECTION of supplier_identity_evidence. This no
        # longer derives signals from mail_messages itself (that was a second, independent rule
        # set for the same inbound reply): evidence is (re)built from existing mail/events by
        # the same rules as the live hooks, then projected by the single reconcile function.
        supplier_ids = [int(r["id"]) for r in connection.execute(
            """SELECT s.id FROM suppliers s JOIN global_supplier_links gl ON gl.supplier_id=s.id
               WHERE gl.global_supplier_id=? AND s.workspace_id=?""",
            (global_supplier_id, workspace_id),
        ).fetchall()]
        self._backfill_evidence_for_suppliers(connection, workspace_id, supplier_ids)
        for email in self._reconcile_contact_projection(connection, workspace_id, canonical_company_id):
            self._recompute_contact_status(connection, canonical_company_id, email, now)
        return canonical_company_id

    def resolve_global_supplier_id_for_thread(self, workspace_id: int, request_id: int, supplier_id: int) -> int | None:
        """The same (workspace_id, request_id, supplier_id) -> global_supplier_id
        lookup used by record_contact_result, exposed standalone for the
        "Напомнить" action, which creates a task against the global supplier
        картотека id (mail/tasks.py::create_task), not the request-scoped
        suppliers.id.
        """
        with self.connect() as connection:
            row = connection.execute(
                """SELECT gl.global_supplier_id FROM mail_threads t
                   JOIN suppliers s ON s.id=t.supplier_id AND s.workspace_id=t.workspace_id
                   LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                   WHERE t.workspace_id=? AND t.request_id=? AND t.supplier_id=?""",
                (workspace_id, request_id, supplier_id),
            ).fetchone()
        if not row or row["global_supplier_id"] is None:
            return None
        return int(row["global_supplier_id"])

    def record_contact_result(
        self, *, workspace_id: int, user_id: int, request_id: int, supplier_id: int,
        result: str, comment: str = "", new_email: str | None = None,
    ) -> dict[str, Any]:
        """Records one "Связаться" outcome. Only `contact_confirmed` and
        `new_email_provided` count as a (weak) workspace confirmation -- the
        other three outcomes are logged for history but never touch the
        contact model, matching the product spec exactly.
        """
        result = str(result or "")
        if result not in _CONTACT_RESULTS:
            raise ValueError("Недопустимый результат контакта.")
        comment = str(comment or "").strip()
        now = iso_now()
        with self.connect() as connection:
            thread = connection.execute(
                """SELECT s.email AS supplier_email, gl.global_supplier_id AS global_supplier_id
                   FROM mail_threads t
                   JOIN suppliers s ON s.id=t.supplier_id AND s.workspace_id=t.workspace_id
                   LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                   WHERE t.workspace_id=? AND t.request_id=? AND t.supplier_id=?""",
                (workspace_id, request_id, supplier_id),
            ).fetchone()
            if not thread:
                raise ValueError("Переписка поставщика в этой заявке не найдена.")
            global_supplier_id = thread["global_supplier_id"]
            global_supplier_id = int(global_supplier_id) if global_supplier_id is not None else None

            new_email_normalized = _normalized_email(new_email) if new_email else ""
            if result == "new_email_provided" and not new_email_normalized:
                raise ValueError("Укажите новый email поставщика.")

            cursor = connection.execute(
                """INSERT INTO workspace_supplier_contact_events(
                       workspace_id, request_id, supplier_id, global_supplier_id, user_id,
                       result, comment, new_email, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (workspace_id, request_id, supplier_id, global_supplier_id, user_id,
                 result, comment, new_email_normalized, now),
            )
            event_id = int(cursor.lastrowid)

            override_created = False
            if result == "new_email_provided" and global_supplier_id is not None:
                # Never overwrite the previous override in place -- supersede
                # it, so it stays visible in this workspace's own history
                # (AC-07).
                connection.execute(
                    """UPDATE workspace_supplier_contact_overrides SET superseded_at=?
                       WHERE workspace_id=? AND global_supplier_id=? AND purpose='rfq' AND superseded_at IS NULL""",
                    (now, workspace_id, global_supplier_id),
                )
                connection.execute(
                    """INSERT INTO workspace_supplier_contact_overrides(
                           workspace_id, global_supplier_id, email, purpose, source_event_id,
                           set_by_user_id, basis, created_at
                       ) VALUES (?, ?, ?, 'rfq', ?, ?, ?, ?)""",
                    (workspace_id, global_supplier_id, new_email_normalized, event_id,
                     user_id, f"contact_result:{result}", now),
                )
                override_created = True

            if result in ("contact_confirmed", "new_email_provided"):
                signal_email = new_email_normalized if result == "new_email_provided" else _normalized_email(thread["supplier_email"])
                if is_contactable_person_address(signal_email):
                    # Primary fact goes to the evidence store; contact intelligence is projected from it.
                    self._record_identity_evidence(
                        connection, workspace_id=workspace_id, supplier_id=supplier_id, request_id=request_id,
                        kind="email", value=signal_email, source_type="workspace_contact_result",
                        source_id=f"contact_event:{event_id}", occurred_at=now, reason=comment or result,
                    )
                    self.sync_contact_intelligence_for_supplier(connection, workspace_id, supplier_id)

            self._audit_connection(
                connection, workspace_id, user_id, "mail.contact_result.recorded",
                "mail_thread", f"{request_id}:{supplier_id}", {"result": result},
            )
        return {"event_id": event_id, "result": result, "override_created": override_created}

    def list_email_contacts_for_global_supplier(self, workspace_id: int, global_supplier_id: int) -> dict[str, Any]:
        """Merged contact view for the supplier card: this workspace's own
        override (if any) plus the cross-tenant candidate/preferred registry,
        with only counts and derived trust signals -- never another
        workspace's identity (AC-09).
        """
        now = iso_now()
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT id FROM global_suppliers WHERE workspace_id=? AND id=?",
                (workspace_id, global_supplier_id),
            ).fetchone()
            if not exists:
                return {"workspace_override": None, "global_contacts": []}

            canonical_company_id = self._sync_workspace_contact_signals(connection, workspace_id, global_supplier_id, now)

            override_row = connection.execute(
                """SELECT email, purpose, basis, created_at FROM workspace_supplier_contact_overrides
                   WHERE workspace_id=? AND global_supplier_id=? AND purpose='rfq' AND superseded_at IS NULL
                   ORDER BY created_at DESC LIMIT 1""",
                (workspace_id, global_supplier_id),
            ).fetchone()
            workspace_override = dict(override_row) if override_row else None

            global_contacts: list[dict[str, Any]] = []
            if canonical_company_id is not None:
                status_order = "CASE status WHEN 'preferred' THEN 0 WHEN 'secondary' THEN 1 WHEN 'candidate' THEN 2 ELSE 3 END"
                contact_rows = connection.execute(
                    f"""SELECT email, purpose, status, last_verified_at, first_seen_at, updated_at
                       FROM canonical_company_contacts WHERE canonical_company_id=?
                       ORDER BY {status_order}, email""",
                    (canonical_company_id,),
                ).fetchall()
                for row in contact_rows:
                    email = row["email"]
                    distinct_workspaces = int(connection.execute(
                        f"""SELECT COUNT(DISTINCT workspace_id) AS n FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
                           WHERE canonical_company_id=? AND email=? AND signal_type IN
                           ({','.join('?' * len(_POSITIVE_SIGNAL_TYPES))})""",
                        (canonical_company_id, email, *_POSITIVE_SIGNAL_TYPES),
                    ).fetchone()["n"])
                    has_strong = int(connection.execute(
                        f"""SELECT COUNT(*) AS n FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
                           WHERE canonical_company_id=? AND email=? AND signal_type IN
                           ({','.join('?' * len(_STRONG_SIGNAL_TYPES))})""",
                        (canonical_company_id, email, *_STRONG_SIGNAL_TYPES),
                    ).fetchone()["n"]) > 0
                    hard_bounces = int(connection.execute(
                        """SELECT COUNT(*) AS n FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
                           WHERE canonical_company_id=? AND email=? AND signal_type='hard_bounce'""",
                        (canonical_company_id, email),
                    ).fetchone()["n"])
                    soft_bounces = int(connection.execute(
                        """SELECT COUNT(*) AS n FROM (SELECT * FROM canonical_company_contact_signals sg WHERE NOT EXISTS (SELECT 1 FROM canonical_company_contact_signal_revocations rv WHERE rv.signal_id = sg.id)) AS active_signals
                           WHERE canonical_company_id=? AND email=? AND signal_type='soft_bounce'""",
                        (canonical_company_id, email),
                    ).fetchone()["n"])
                    global_contacts.append({
                        "email": email,
                        "purpose": row["purpose"],
                        "status": row["status"],
                        "last_verified_at": row["last_verified_at"],
                        "first_seen_at": row["first_seen_at"],
                        "confirming_workspace_count": distinct_workspaces,
                        "has_strong_signal": has_strong,
                        "hard_bounce_count": hard_bounces,
                        "soft_bounce_count": soft_bounces,
                    })
        return {"workspace_override": workspace_override, "global_contacts": global_contacts}
