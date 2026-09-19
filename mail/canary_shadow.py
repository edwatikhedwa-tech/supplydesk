"""Shadow mode for the Mail Intelligence canary (EDW-40).

While downstream_enabled = 0 the canary only OBSERVES: analyses, facts (state 'proposed', i.e. non-production), provenance, cost, latency and manual-review
marks are stored; nothing that changes business state runs:
  - no quote_received event is created and no existing event is processed (no follow-up closing),
  - no request status, supplier or contact state change, no confirmation of a quote, no purchase-price history.
Suppression is decided by the presence of a canary row without downstream_enabled - independently of the environment flag - so a forgotten flag can
never let a canary workspace fire downstream actions.

Two limits of the automatic stop rules, stated plainly (they are structural guards, not proof of business correctness):
  - false_request_scoped_price_fact checks that the number IS in the source; it cannot prove the number is semantically a price;
  - fact_bound_to_wrong_request compares the fact's request with its message's request; it cannot notice a message linked to the wrong request.
Hence the audit records below and the owner's review during the shadow period.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

MIN_REVIEWED_PRICE_FACTS = 30        # rule of three: 0 false facts in 30 reviewed => false-positive rate <= ~10% at 95% confidence
MIN_PROCUREMENT_LETTERS = 10         # distinct letters behind those facts, so that one long letter cannot fill the sample
MIN_REVIEWED_MATCHES = 20
FALSE_FACT_REASONS = ("not_a_price", "wrong_value")
WRONG_REQUEST_REASONS = ("wrong_request",)


def _iso() -> str:
    return datetime.now(UTC).isoformat()


class ShadowMixin:
    def downstream_suppressed(self, workspace_id: int, connection: Any = None) -> bool:
        def read(c):
            if not c.execute("SELECT 1 FROM mail_intelligence_canary WHERE workspace_id=?", (workspace_id,)).fetchone():
                return False                                      # not a canary workspace: behaviour unchanged
            row = c.execute("SELECT downstream_enabled FROM mail_intelligence_canary_flags WHERE workspace_id=?", (workspace_id,)).fetchone()
            return not (row and row["downstream_enabled"])
        if connection is not None:
            return read(connection)
        with self.connect() as c:
            return read(c)

    def in_canary(self, workspace_id: int, connection: Any) -> bool:
        return bool(connection.execute("SELECT 1 FROM mail_intelligence_canary WHERE workspace_id=?", (workspace_id,)).fetchone())

    def _audit(self, connection: Any, workspace_id: int, kind: str, message_kind: str, message_id: int, *, request_id: int | None = None, supplier_id: int | None = None,
               fact_kind: str = "", fact_id: int = 0, value: dict | None = None, span: dict | None = None, match_method: str = "", confidence: str = "",
               evidence: dict | None = None) -> None:
        connection.execute(
            """INSERT INTO mail_intelligence_audit(workspace_id, kind, message_kind, message_id, request_id, supplier_id, fact_kind, fact_id, value_json, span_json,
                                                   match_method, confidence, evidence_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(workspace_id, kind, message_kind, message_id, fact_kind, fact_id) DO NOTHING""",
            (workspace_id, kind, message_kind, message_id, request_id, supplier_id, fact_kind, fact_id, json.dumps(value or {}, ensure_ascii=False),
             json.dumps(span or {}, ensure_ascii=False), match_method, confidence, json.dumps(evidence or {}, ensure_ascii=False), _iso()))

    def audit_list(self, workspace_id: int, *, state: str = "pending", limit: int = 50) -> list[dict[str, Any]]:
        """LOCAL review view, never exported: the audit row plus the source text of the fact, read through fact_id."""
        out = []
        with self.connect() as c:
            for r in c.execute("SELECT * FROM mail_intelligence_audit WHERE workspace_id=? AND review_state=? ORDER BY id LIMIT ?", (workspace_id, state, limit)).fetchall():
                d = dict(r)
                if d["fact_kind"] == "mail_fact":
                    f = c.execute("SELECT source_quote FROM mail_facts WHERE id=?", (d["fact_id"],)).fetchone()
                    d["source_text"] = f["source_quote"] if f else ""
                elif d["fact_kind"] == "attachment_fact":
                    f = c.execute("SELECT source_text FROM mail_attachment_facts WHERE id=?", (d["fact_id"],)).fetchone()
                    d["source_text"] = f["source_text"] if f else ""
                out.append(d)
        return out

    def audit_review(self, workspace_id: int, audit_id: int, decision: str, reason: str = "") -> dict[str, Any]:
        """Owner decision on one audit record. A rejection for a false price / wrong value / wrong request STOPS the canary at once."""
        if decision not in ("confirmed", "rejected"):
            raise ValueError("decision must be confirmed or rejected")
        with self.connect() as c:
            row = c.execute("SELECT * FROM mail_intelligence_audit WHERE id=? AND workspace_id=?", (audit_id, workspace_id)).fetchone()
            if not row:
                raise ValueError("audit record not found in this workspace")
            c.execute("UPDATE mail_intelligence_audit SET review_state=?, review_reason=?, reviewed_at=? WHERE id=?", (decision, reason[:100], _iso(), audit_id))
            if decision == "rejected" and row["fact_kind"] == "mail_fact":
                c.execute("UPDATE mail_facts SET state='rejected' WHERE id=?", (row["fact_id"],))
            if decision == "rejected" and row["fact_kind"] == "attachment_fact":
                c.execute("UPDATE mail_attachment_facts SET state='rejected' WHERE id=?", (row["fact_id"],))
            c.commit()
        stopped = ""
        if decision == "rejected" and reason in FALSE_FACT_REASONS:
            stopped = "confirmed_false_price_fact"
        elif decision == "rejected" and reason in WRONG_REQUEST_REASONS:
            stopped = "confirmed_wrong_request"
        if stopped:
            self.canary_stop(workspace_id, stopped, f"audit {audit_id}")
        return {"audit_id": audit_id, "decision": decision, "stopped": stopped}

    def shadow_exit_readiness(self, workspace_id: int) -> dict[str, Any]:
        """Objective check of the exit criteria. It never releases anything by itself."""
        with self.connect() as c:
            n = lambda sql: c.execute(sql, (workspace_id,)).fetchone()[0]
            facts_total = n("SELECT COUNT(*) FROM mail_intelligence_audit WHERE workspace_id=? AND kind='price_fact'")
            facts_reviewed = n("SELECT COUNT(*) FROM mail_intelligence_audit WHERE workspace_id=? AND kind='price_fact' AND review_state<>'pending'")
            letters = n("SELECT COUNT(*) FROM (SELECT DISTINCT message_kind, message_id FROM mail_intelligence_audit WHERE workspace_id=? AND kind='price_fact' AND review_state<>'pending') x")
            false_facts = n("SELECT COUNT(*) FROM mail_intelligence_audit WHERE workspace_id=? AND kind='price_fact' AND review_state='rejected' AND review_reason IN ('not_a_price', 'wrong_value')")
            matches_reviewed = n("SELECT COUNT(*) FROM mail_intelligence_audit WHERE workspace_id=? AND kind='request_match' AND review_state<>'pending'")
            wrong = n("SELECT COUNT(*) FROM mail_intelligence_audit WHERE workspace_id=? AND kind IN ('request_match', 'price_fact') AND review_state='rejected' AND review_reason='wrong_request'")
        safety = self.evaluate_safety(workspace_id)
        checks = {
            "reviewed_price_facts": {"ok": facts_reviewed >= MIN_REVIEWED_PRICE_FACTS, "have": facts_reviewed, "need": MIN_REVIEWED_PRICE_FACTS, "generated": facts_total},
            "distinct_reviewed_letters": {"ok": letters >= MIN_PROCUREMENT_LETTERS, "have": letters, "need": MIN_PROCUREMENT_LETTERS},
            "reviewed_request_matches": {"ok": matches_reviewed >= MIN_REVIEWED_MATCHES, "have": matches_reviewed, "need": MIN_REVIEWED_MATCHES},
            "confirmed_false_price_facts": {"ok": false_facts == 0, "have": false_facts},
            "confirmed_wrong_request_matches": {"ok": wrong == 0, "have": wrong},
            "budget_queue_worker_duplicates_safety": {"ok": not safety, "findings": [f["rule"] for f in safety]},
        }
        return {"ready": all(v["ok"] for v in checks.values()), "checks": checks}

    def release_shadow(self, workspace_id: int, *, owner_approved: bool = False) -> dict[str, Any]:
        """Lifts the suppression of the EXISTING downstream (quote_received). Needs the objective criteria AND an explicit owner decision."""
        if not owner_approved:
            raise ValueError("Выход из shadow mode требует явного решения владельца.")
        ready = self.shadow_exit_readiness(workspace_id)
        if not ready["ready"]:
            raise ValueError("Критерии выхода из shadow mode не выполнены.")
        with self.connect() as c:
            c.execute("""INSERT INTO mail_intelligence_canary_flags(workspace_id, downstream_enabled, updated_at) VALUES (?, 1, ?)
                         ON CONFLICT(workspace_id) DO UPDATE SET downstream_enabled=1, updated_at=excluded.updated_at""", (workspace_id, _iso()))
            c.commit()
        return {"released": True, **ready}

    def shadow_audit_metrics(self, workspace_id: int, lo: str, hi: str) -> dict[str, Any]:
        with self.connect() as c:
            def cnt(kind, state=None):
                sql = "SELECT COUNT(*) FROM mail_intelligence_audit WHERE workspace_id=? AND kind=? AND created_at>=? AND created_at<?" + (" AND review_state=?" if state else "")
                return c.execute(sql, (workspace_id, kind, lo, hi) + ((state,) if state else ())).fetchone()[0]
            out: dict[str, Any] = {"events_suppressed": cnt("event_suppressed")}
            for kind, label in (("price_fact", "price_facts"), ("request_match", "request_matches")):
                gen, conf, rej = cnt(kind), cnt(kind, "confirmed"), cnt(kind, "rejected")
                out[f"{label}_generated"], out[f"{label}_confirmed"], out[f"{label}_rejected"], out[f"{label}_pending"] = gen, conf, rej, gen - conf - rej
                out[f"{label}_false_positive_rate"] = round(rej / (conf + rej), 4) if conf + rej else None
        return out
