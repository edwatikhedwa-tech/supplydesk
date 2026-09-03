"""
Global-supplier sub-router HTTP handler methods, extracted from
SupplierHandler in supplier_app.py
(TASK-BOUNDED-SUPPLIER-APP-GLOBAL-SUPPLIER-ROUTES-EXTRACT-20260903) as
batch B of the routes/auth composition-entrypoint program.

GlobalSupplierRouteMixin is composed into SupplierHandler via multiple
inheritance, so every method below still resolves `self.app` and
`self._json` exactly as before. do_GET/do_POST and their route ordering are
unchanged and untouched by this extraction. No behavior changed: every
method body below is moved byte-for-byte.
"""

from __future__ import annotations


class GlobalSupplierRouteMixin:
    def _global_supplier_route(self, session: dict, path: str) -> None:
        """GET /api/global-suppliers/<id> — card detail (history + issues)."""
        parts = [part for part in path.split("/") if part]
        try:
            global_supplier_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор поставщика."})
            return
        if len(parts) != 3:
            self._json(404, {"error": "Маршрут не найден."})
            return
        detail = self.app.repository.global_supplier_detail(session["workspace_id"], global_supplier_id)
        if not detail:
            self._json(404, {"error": "Поставщик не найден."})
            return
        self._json(200, detail)

    def _global_supplier_action(self, session: dict, path: str, body: dict) -> None:
        parts = [part for part in path.split("/") if part]
        try:
            global_supplier_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор поставщика."})
            return
        if len(parts) == 3:
            note = body.get("note")
            self.app.repository.update_global_supplier(session["workspace_id"], global_supplier_id, note=str(note) if note is not None else None)
            self._json(200, {"ok": True})
            return
        if len(parts) == 4 and parts[3] == "relationship":
            try:
                self.app.repository.set_global_supplier_relationship(
                    session["workspace_id"], session["user_id"], global_supplier_id,
                    str(body.get("status", "none")), reason=str(body.get("reason", "")),
                )
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"ok": True})
            return
        if len(parts) == 4 and parts[3] == "issues":
            reason = str(body.get("reason", "other"))
            issue_id = self.app.repository.add_global_supplier_issue(
                session["workspace_id"], session["user_id"], global_supplier_id,
                reason=reason, comment=str(body.get("comment", "")),
                correct_inn=str(body.get("correct_inn", "")), source="manual",
            )
            if bool(body.get("blacklist")):
                # Store the issue's own reason code (not a translated label) — the
                # frontend already has issueReasonLabels for display, and reusing it
                # keeps one source of truth for "what does this code mean".
                self.app.repository.set_global_supplier_relationship(
                    session["workspace_id"], session["user_id"], global_supplier_id, "blacklisted", reason=reason,
                )
            self._json(201, {"ok": True, "issue_id": issue_id})
            return
        self._json(404, {"error": "Действие не найдено."})
