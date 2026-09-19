"""Review path for suspected duplicate supplier cards (EDW-21).

    GET  /api/supplier-merge-candidates[?status=]          queue
    GET  /api/supplier-merge-candidates/<id>               both cards, evidence, what would be transferred
    POST /api/supplier-merge-candidates/scan               register suspected pairs (changes no supplier data)
    POST /api/supplier-merge-candidates/<id>/decision      {decision: merge|reject|later|undo, confirm_unknown_inn}

Workspace comes from the session (never from the request); decisions are owner-only and go through the
reversible merge (mail/supplier_merge.py). CSRF and rate limiting are applied by do_POST before this runs.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


class MergeReviewRouteMixin:
    def _merge_review_get(self, session: dict, raw_path: str) -> None:
        parsed = urlparse(raw_path)
        parts = [p for p in parsed.path.split("/") if p]
        repo, workspace_id = self.app.repository, session["workspace_id"]
        if len(parts) == 2:
            status = (parse_qs(parsed.query).get("status") or [None])[0]
            self._json(200, {"items": repo.list_merge_candidates(workspace_id, status=status)})
            return
        try:
            candidate_id = int(parts[2])
            if len(parts) != 3:
                raise IndexError
        except (IndexError, ValueError):
            self._json(404, {"error": "Маршрут не найден."})
            return
        try:
            self._json(200, repo.get_merge_review(workspace_id, candidate_id))
        except ValueError as exc:
            self._json(404, {"error": str(exc)})

    def _merge_review_post(self, session: dict, path: str, body: dict) -> None:
        parts = [p for p in path.split("/") if p]
        repo, workspace_id, user_id = self.app.repository, session["workspace_id"], session["user_id"]
        if not repo.is_workspace_owner(user_id, workspace_id):
            self._json(403, {"error": "Объединение поставщиков может выполнять только владелец."})
            return
        try:
            if parts == ["api", "supplier-merge-candidates", "scan"]:
                self._json(200, {"ok": True, **repo.register_merge_candidates(workspace_id)})
                return
            if len(parts) == 4 and parts[3] == "decision":
                result = repo.decide_merge_candidate(
                    workspace_id, user_id, int(parts[2]), str(body.get("decision") or ""),
                    confirm_unknown_inn=body.get("confirm_unknown_inn") is True,
                )
                self._json(200, {"ok": True, **result})
                return
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(404, {"error": "Маршрут не найден."})
