"""Persistence and idempotency for attachment analysis (EDW-35). The reading itself is mail/attachment_intelligence.py.

analyze_message_attachments(workspace, message):
  - per attachment: (workspace, attachment id, analysis version) already stored -> nothing is done (reuse_count in the summary);
  - same bytes (sha256) already analysed under the same version, in another message -> the stored result is reused: 0 parsing, 0 OCR, 0 model calls;
  - otherwise parse -> OCR -> checksum -> vision only for pages that OCR could not finish;
  - facts (with locator and position match) are written per message; the whole message is merged (duplicates, conflicts, terms files).
The function is synchronous by design: callers that must not wait (mail sync) run it from a task queue.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from . import attachment_intelligence as AI


def _now() -> str:
    return datetime.now(UTC).isoformat()


class AttachmentAnalysisMixin:
    def _request_positions_for_matching(self, connection: Any, workspace_id: int, request_id: int | None) -> list[dict[str, Any]]:
        if not request_id:
            return []
        rows = connection.execute(
            "SELECT p.id, p.position_key, p.name, p.quantity FROM request_positions p JOIN requests r ON r.id=p.request_id WHERE p.request_id=? AND r.workspace_id=? ORDER BY p.id",
            (request_id, workspace_id)).fetchall()
        return [{"pid": str(r["position_key"] or r["id"]), "name": r["name"], "sku": None, "brand": "", "qty": r["quantity"], "unit": ""} for r in rows]

    def analyze_message_attachments(self, workspace_id: int, message_id: int, *, models: Any = None, vision: Any = None,
                                    version: str = AI.ANALYSIS_VERSION) -> dict[str, Any]:
        summary: dict[str, Any] = {"message_id": message_id, "attachments": 0, "analysed": 0, "reused_same_bytes": 0, "already_done": 0,
                                   "ai_calls": 0, "cost_rub": 0.0, "manual_review": False, "facts": 0, "conflicts": 0, "items": []}
        with self.connect() as connection:
            message = connection.execute("SELECT id, request_id, supplier_id FROM mail_messages WHERE id=? AND workspace_id=? AND direction='inbound'",
                                         (message_id, workspace_id)).fetchone()
            if not message:
                raise ValueError("Входящее письмо не найдено в текущем рабочем пространстве.")
            attachments = [dict(r) for r in connection.execute(
                "SELECT id, filename, mime_type, content FROM mail_attachments WHERE message_id=? ORDER BY id", (message_id,)).fetchall()]
        summary["attachments"] = len(attachments)
        results: list[dict[str, Any]] = []
        stored_ids: dict[int, int] = {}
        for att in attachments:
            data = bytes(att["content"] or b"")
            digest = AI.sha256_hex(data)
            with self.connect() as connection:
                done = connection.execute("SELECT id, result_json FROM mail_attachment_analyses WHERE workspace_id=? AND attachment_id=? AND analysis_version=?",
                                          (workspace_id, att["id"], version)).fetchone()
                if done:
                    results.append(json.loads(done["result_json"]))
                    stored_ids[att["id"]] = int(done["id"])
                    summary["already_done"] += 1
                    continue
                original = connection.execute(
                    "SELECT id, result_json FROM mail_attachment_analyses WHERE workspace_id=? AND sha256=? AND analysis_version=? ORDER BY id LIMIT 1",
                    (workspace_id, digest, version)).fetchone()
            if original:
                result = json.loads(original["result_json"])
                reused_from, ai_calls, cost, latency, ocr_pages = int(original["id"]), [], 0.0, 0, 0
                summary["reused_same_bytes"] += 1
            else:
                result = AI.analyze_attachment(data, att["filename"], models=models, cache=None, version=version, vision=vision)
                reused_from, ai_calls = None, result.get("ai_calls") or []
                cost = sum(float(c.get("cost_rub") or 0.0) for c in ai_calls)
                latency, ocr_pages = int(result.get("latency_ms") or 0), int(result.get("ocr_pages") or 0)
                summary["analysed"] += 1
            results.append(result)
            with self.connect() as connection:
                connection.execute(
                    """INSERT INTO mail_attachment_analyses(workspace_id, message_id, attachment_id, filename, sha256, analysis_version, status, kind, parser,
                           needs_ocr, is_quote, manual_review, reasons_json, terms_json, result_json, reused_from, ocr_pages, ai_calls, cost_rub, latency_ms, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (workspace_id, message_id, att["id"], att["filename"], digest, version, result["status"], result.get("kind") or "", result.get("parser") or "",
                     int(bool(result.get("needs_ocr"))), int(bool(result.get("is_quote"))), int(bool(result.get("manual_review"))),
                     json.dumps(result.get("reasons") or [], ensure_ascii=False),
                     json.dumps({k: result.get(k) for k in ("currency", "vat_mode", "delivery_days")}, ensure_ascii=False),
                     json.dumps(result, ensure_ascii=False), reused_from, ocr_pages, len(ai_calls), cost, latency, _now()))
                analysis_id = int(connection.execute("SELECT id FROM mail_attachment_analyses WHERE workspace_id=? AND attachment_id=? AND analysis_version=?",
                                                     (workspace_id, att["id"], version)).fetchone()["id"])
                for call in ai_calls:
                    connection.execute(
                        """INSERT INTO mail_attachment_ai_calls(workspace_id, attachment_analysis_id, reason, model, input_tokens, output_tokens, cost_rub, latency_ms, error, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (workspace_id, analysis_id, call.get("reason") or "", call.get("model") or "", int(call.get("input_tokens") or 0), int(call.get("output_tokens") or 0),
                         call.get("cost_rub"), int(call.get("latency_ms") or 0), call.get("error") or "", _now()))
                connection.commit()
            stored_ids[att["id"]] = analysis_id
            summary["ai_calls"] += len(ai_calls)
            summary["cost_rub"] += cost
            summary["items"].append({"attachment_id": att["id"], "filename": att["filename"], "status": result["status"], "reused": reused_from is not None,
                                     "latency_ms": latency, "cost_rub": round(cost, 6), "facts": len(result.get("facts") or [])})
        with self.connect() as connection:
            positions = self._request_positions_for_matching(connection, workspace_id, message["request_id"])
            merged = AI.merge_attachments(results, positions) if results else {"lines": [], "conflicts": [], "manual_review": False}
            first_analysis = next(iter(stored_ids.values()), None)
            existing = connection.execute("SELECT COUNT(*) AS n FROM mail_attachment_facts WHERE workspace_id=? AND message_id=?", (workspace_id, message_id)).fetchone()["n"]
            if not existing and first_analysis is not None:
                by_sha = {r["sha256"][:12]: aid for r, aid in ((res, stored_ids[a["id"]]) for res, a in zip(results, attachments))}
                for i, line in enumerate(merged["lines"]):
                    connection.execute(
                        """INSERT INTO mail_attachment_facts(workspace_id, attachment_analysis_id, message_id, request_id, supplier_id, position, data_json, loc_json, source_text, match_json, review, state, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?)""",
                        (workspace_id, by_sha.get(line["doc"], first_analysis), message_id, message["request_id"], message["supplier_id"], i,
                         json.dumps({k: line.get(k) for k in ("name", "sku", "qty", "unit", "price", "currency", "price_per", "delivery_days", "vat_mode", "source")}, ensure_ascii=False),
                         json.dumps(line["loc"], ensure_ascii=False), line.get("source_text") or "", json.dumps(line["match"], ensure_ascii=False),
                         line.get("review") or "", _now()))
                connection.commit()
            summary["facts"] = connection.execute("SELECT COUNT(*) AS n FROM mail_attachment_facts WHERE workspace_id=? AND message_id=?", (workspace_id, message_id)).fetchone()["n"]
        summary["conflicts"] = len(merged.get("conflicts") or [])
        summary["manual_review"] = bool(merged.get("manual_review"))
        summary["cost_rub"] = round(summary["cost_rub"], 6)
        return summary
