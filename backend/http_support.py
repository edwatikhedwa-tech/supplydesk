"""HTTP routes for the compact SupplyDesk technical-support chat."""

from __future__ import annotations

from urllib.parse import quote


class SupportRouteMixin:
    def _support_get_route(self, session: dict, path: str) -> None:
        if path == "/api/support/conversations":
            self._json(200, {"items": self.app.repository.list_support_conversations(session["workspace_id"], session["user_id"])})
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) == 4 and parts[:3] == ["api", "support", "conversations"]:
            try:
                conversation_id = int(parts[3])
            except ValueError:
                self._json(400, {"error": "Некорректный идентификатор обращения."})
                return
            self._json(200, {"conversation": self.app.repository.get_support_conversation(session["workspace_id"], session["user_id"], conversation_id)})
            return
        if len(parts) == 4 and parts[:3] == ["api", "support", "attachments"]:
            try:
                message_id = int(parts[3])
                attachment = self.app.repository.get_support_attachment(session["workspace_id"], session["user_id"], message_id)
            except ValueError as exc:
                self._json(404, {"error": str(exc)})
                return
            content = bytes(attachment["attachment_content"])
            self.send_response(200)
            self.send_header("Content-Type", str(attachment["attachment_mime_type"]))
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(str(attachment['attachment_filename']))}")
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
            return
        self._json(404, {"error": "Маршрут поддержки не найден."})

    def _support_post_route(self, session: dict, path: str, body: dict) -> None:
        if path == "/api/support/conversations":
            linked_request_id = body.get("linked_request_id")
            result = self.app.repository.create_support_conversation(
                session["workspace_id"], session["user_id"], text=str(body.get("text") or ""),
                category=str(body.get("category") or "general"),
                linked_request_id=int(linked_request_id) if linked_request_id not in (None, "") else None,
                current_url=str(body.get("current_url") or ""), current_section=str(body.get("current_section") or ""),
                browser=str(self.headers.get("User-Agent") or ""), app_version=str(body.get("app_version") or ""),
                attachment=body.get("attachment"),
            )
            self._json(201, {"conversation": result})
            return
        parts = [part for part in path.split("/") if part]
        if len(parts) != 5 or parts[:3] != ["api", "support", "conversations"]:
            self._json(404, {"error": "Маршрут поддержки не найден."})
            return
        try:
            conversation_id = int(parts[3])
        except ValueError:
            self._json(400, {"error": "Некорректный идентификатор обращения."})
            return
        if parts[4] == "messages":
            result = self.app.repository.add_support_message(
                session["workspace_id"], session["user_id"], conversation_id,
                text=str(body.get("text") or ""), attachment=body.get("attachment"),
            )
            self._json(201, {"conversation": result})
            return
        if parts[4] == "support-message":
            result = self.app.repository.add_support_reply(
                session["workspace_id"], session["user_id"], conversation_id,
                text=str(body.get("text") or ""), status=str(body.get("status") or "waiting_user"),
                attachment=body.get("attachment"),
            )
            self._json(201, {"conversation": result})
            return
        self._json(404, {"error": "Маршрут поддержки не найден."})
