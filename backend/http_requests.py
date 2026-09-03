"""
Request (заявка) sub-router HTTP handler methods, extracted from
SupplierHandler in supplier_app.py
(TASK-BOUNDED-SUPPLIER-APP-REQUEST-ROUTES-EXTRACT-20260903) as batch A of
the routes/auth composition-entrypoint program (following the auth batch in
backend/http_auth.py).

RequestRouteMixin is composed into SupplierHandler via multiple inheritance,
so every method below still resolves `self.app` and `self._json` exactly as
before. do_GET/do_POST and their route ordering are unchanged and untouched
by this extraction -- they already delegated to these methods by name, and
continue to do so via inheritance. No behavior changed: every method body
below is moved byte-for-byte.
"""

from __future__ import annotations

from backend.domain.logistics.quote_service import LogisticsQuoteInput


class RequestRouteMixin:
    def _thread_messages(self, session: dict, query: dict[str, list[str]]) -> None:
        try:
            request_id = int((query.get("request_id") or [1043])[0])
            supplier_id = int((query.get("supplier_id") or [0])[0])
        except ValueError:
            self._json(400, {"error": "Некорректные идентификаторы переписки."})
            return
        if supplier_id <= 0:
            self._json(200, {"items": self.app.repository.list_threads(session["workspace_id"])})
            return
        self._json(200, {"items": self.app.repository.thread_messages(session["workspace_id"], request_id, supplier_id)})

    def _request_route(self, session: dict, path: str, query: dict[str, list[str]]) -> None:
        parts = [part for part in path.split("/") if part]
        try:
            request_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор заявки."})
            return
        if len(parts) == 3:
            request = self.app.repository.get_request(session["workspace_id"], request_id)
            if not request:
                self._json(404, {"error": "Заявка не найдена."})
                return
            self._json(200, {"request": request, "positions": self.app.repository.request_positions(session["workspace_id"], request_id), "items": self.app.repository.list_suppliers(session["workspace_id"], request_id)})
            return
        if len(parts) == 4 and parts[3] == "suppliers":
            self._json(200, {"items": self.app.repository.list_suppliers(session["workspace_id"], request_id)})
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "logistics":
            try:
                supplier_id = int(parts[4])
            except ValueError:
                self._json(400, {"error": "Некорректный идентификатор поставщика."})
                return
            quote = self.app.repository.get_latest_logistics_quote(session["workspace_id"], request_id, supplier_id)
            self._json(200, {"quote": quote})
            return
        self._json(404, {"error": "Маршрут заявки не найден."})

    def _request_action(self, session: dict, path: str, body: dict) -> None:
        parts = [part for part in path.split("/") if part]
        try:
            request_id = int(parts[2])
        except (IndexError, ValueError):
            self._json(400, {"error": "Некорректный идентификатор заявки."})
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "inn":
            try:
                supplier_id = int(parts[4])
            except ValueError:
                self._json(400, {"error": "Некорректный идентификатор поставщика."})
                return
            result = self.app.update_supplier_inn(
                session["workspace_id"], session["user_id"], request_id, supplier_id,
                str(body.get("inn", "")),
            )
            self._json(200, result)
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "rating":
            try:
                supplier_id = int(parts[4])
                rating = int(body.get("rating", 0))
            except (ValueError, TypeError):
                self._json(400, {"error": "Некорректная оценка."})
                return
            self.app.repository.set_deal_rating(session["workspace_id"], session["user_id"], request_id, supplier_id, rating)
            self._json(200, {"ok": True})
            return
        if len(parts) == 3:
            self.app.repository.update_request(
                session["workspace_id"], request_id, session["user_id"],
                name=body.get("name"), description=body.get("description"), deadline=body.get("deadline"),
            )
            self._json(200, {"ok": True})
            return
        if len(parts) == 4 and parts[3] == "search":
            result = self.app.repository.start_request_search(session["workspace_id"], request_id, session["user_id"])
            if request_id == 1043:
                # The existing page is a completed, enriched fixture; keep it available for the current workspace.
                self.app.repository.complete_request_search(session["workspace_id"], request_id)
                result["status"] = "completed"
                result["search_progress"] = result["search_total"]
            self._json(202, {"ok": True, **result})
            return
        if len(parts) == 5 and parts[3] == "search" and parts[4] == "step":
            result = self.app.process_search_step(session["workspace_id"], request_id)
            self._json(200, {"ok": True, **result})
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "logistics":
            try:
                supplier_id = int(parts[4])
            except ValueError:
                self._json(400, {"error": "Некорректный идентификатор поставщика."})
                return
            if not self.app.repository.request_supplier(session["workspace_id"], request_id, supplier_id):
                self._json(404, {"error": "Поставщик не найден в этой заявке."})
                return
            cargo = body.get("cargo") or {}
            quote_input = LogisticsQuoteInput(
                route_from=str(body.get("route_from") or ""),
                route_to=str(body.get("route_to") or ""),
                cargo_places=int(cargo.get("places") or 0),
                cargo_weight_kg=float(cargo.get("weight_kg") or 0),
                cargo_volume_m3=float(cargo.get("volume_m3") or 0),
                cargo_max_length_cm=float(cargo.get("max_length_cm") or 0),
                cargo_max_width_cm=float(cargo.get("max_width_cm") or 0),
                cargo_max_height_cm=float(cargo.get("max_height_cm") or 0),
            )
            result = self.app.logistics_quote_service.calculate(quote_input)
            dims = f"{quote_input.cargo_max_length_cm:g}x{quote_input.cargo_max_width_cm:g}x{quote_input.cargo_max_height_cm:g}"
            saved = self.app.repository.save_logistics_quote(
                session["workspace_id"], session["user_id"], request_id, supplier_id,
                carrier=result.carrier, route_from=quote_input.route_from, route_to=quote_input.route_to,
                cargo_places=quote_input.cargo_places, cargo_weight_kg=quote_input.cargo_weight_kg,
                cargo_volume_m3=quote_input.cargo_volume_m3, cargo_max_dims_cm=dims,
                price=result.price, currency=result.currency, vat_included=None, term_days=result.term_days,
                cost_breakdown=result.cost_breakdown, status=result.status, input_hash=result.input_hash,
                raw_response=result.raw_response, calculated_at=result.calculated_at,
            )
            self._json(200, {"quote": saved, "message": result.message})
            return
        if len(parts) == 6 and parts[3] == "suppliers" and parts[5] == "irrelevant":
            try:
                supplier_id = int(parts[4])
            except ValueError:
                self._json(400, {"error": "Некорректный идентификатор поставщика."})
                return
            self.app.repository.set_irrelevant(session["workspace_id"], session["user_id"], request_id, supplier_id, True)
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "Действие заявки не найдено."})
