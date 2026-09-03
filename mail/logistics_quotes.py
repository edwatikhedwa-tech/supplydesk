"""
Persistence for manual per-request, per-supplier logistics quotes
(TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903), extracted as its own mixin rather
than added to mail/repository.py directly — same zero-coupling pattern as
mail/mail_templates.py: this cluster only touches the universal
_audit_connection helper, nothing else in the file.

LogisticsQuotesMixin is composed into MailRepository via multiple
inheritance, so self.connect()/self._audit_connection() resolve exactly as
elsewhere. No workspace_id column on logistics_quotes (see
migrations/033_logistics_quotes.sql) — every query below scopes through
requests.workspace_id, the same pattern request_supplier_states already uses.
"""

from __future__ import annotations

import json
from typing import Any


def _quote_row_to_dict(row: Any) -> dict[str, Any]:
    result = dict(row)
    result["cost_breakdown"] = json.loads(result.pop("cost_breakdown_json") or "{}")
    raw_response_json = result.pop("raw_response_json", None)
    result["raw_response"] = json.loads(raw_response_json) if raw_response_json else None
    result["vat_included"] = bool(result["vat_included"]) if result.get("vat_included") is not None else None
    return result


class LogisticsQuotesMixin:
    def save_logistics_quote(
        self, workspace_id: int, user_id: int, request_id: int, supplier_id: int | None, *,
        carrier: str, route_from: str, route_to: str, cargo_places: int, cargo_weight_kg: float,
        cargo_volume_m3: float, cargo_max_dims_cm: str, price: float | None, currency: str,
        vat_included: bool | None, term_days: int | None, cost_breakdown: dict[str, Any],
        status: str, input_hash: str, raw_response: dict[str, Any] | None, calculated_at: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            owner = connection.execute(
                "SELECT id FROM requests WHERE id=? AND workspace_id=?", (request_id, workspace_id),
            ).fetchone()
            if not owner:
                raise ValueError("Заявка не найдена.")
            cursor = connection.execute(
                """INSERT INTO logistics_quotes(
                       request_id, supplier_id, carrier, route_from, route_to,
                       cargo_places, cargo_weight_kg, cargo_volume_m3, cargo_max_dims_cm,
                       price, currency, vat_included, term_days, cost_breakdown_json,
                       status, input_hash, raw_response_json, calculated_at, created_by_user_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request_id, supplier_id, carrier, route_from, route_to,
                    cargo_places, cargo_weight_kg, cargo_volume_m3, cargo_max_dims_cm,
                    price, currency, None if vat_included is None else int(vat_included), term_days,
                    json.dumps(cost_breakdown, ensure_ascii=False),
                    status, input_hash,
                    json.dumps(raw_response, ensure_ascii=False) if raw_response is not None else None,
                    calculated_at, user_id,
                ),
            )
            quote_id = int(cursor.lastrowid)
            self._audit_connection(
                connection, workspace_id, user_id, "logistics_quote.calculated",
                "logistics_quote", str(quote_id),
                {"request_id": request_id, "supplier_id": supplier_id, "carrier": carrier, "status": status},
            )
            row = connection.execute("SELECT * FROM logistics_quotes WHERE id=?", (quote_id,)).fetchone()
        return _quote_row_to_dict(row)

    def get_latest_logistics_quote(
        self, workspace_id: int, request_id: int, supplier_id: int | None,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT q.* FROM logistics_quotes q
                   JOIN requests r ON r.id = q.request_id
                   WHERE r.workspace_id=? AND q.request_id=?
                     AND ((q.supplier_id IS NULL AND ? IS NULL) OR q.supplier_id=?)
                   ORDER BY q.id DESC LIMIT 1""",
                (workspace_id, request_id, supplier_id, supplier_id),
            ).fetchone()
        return _quote_row_to_dict(row) if row else None

    def list_logistics_quotes_for_request(self, workspace_id: int, request_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT q.* FROM logistics_quotes q
                   JOIN requests r ON r.id = q.request_id
                   WHERE r.workspace_id=? AND q.request_id=?
                   ORDER BY q.id DESC""",
                (workspace_id, request_id),
            ).fetchall()
        return [_quote_row_to_dict(row) for row in rows]
