from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .models import DiscoveryResult, QueryVariant


class XmlRiverSubprocess:
    """Calls the existing parser as an unchanged, read-only subprocess."""

    def __init__(self, output_dir: str | Path, timeout: float = 150.0, parser_path: str | Path | None = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.parser_path = (
            Path(parser_path) if parser_path
            else Path(__file__).resolve().parents[1] / "backend" / "integrations" / "search" / "serp_parser.py"
        )

    def search(self, query: QueryVariant) -> tuple[list[DiscoveryResult], dict[str, object]]:
        safe_name = "".join(char if char.isalnum() else "_" for char in query.query.casefold())[:70].strip("_") or "query"
        json_path = self.output_dir / f"{query.position_key}_{query.kind}_{safe_name}.json"
        csv_path = self.output_dir / f"{query.position_key}_{query.kind}_{safe_name}.csv"
        command = [
            sys.executable,
            str(self.parser_path),
            query.query,
            "--pages", "1",
            "--no-suffix",
            "--delay", "0",
            "--retries", "2",
            "--out", str(csv_path),
            "--json", str(json_path),
            "--quiet",
        ]
        details: dict[str, object] = {"query": query.query, "kind": query.kind, "command": "existing_parser_subprocess", "status": "error"}
        try:
            proc = subprocess.run(command, cwd=self.parser_path.parent, capture_output=True, text=True, timeout=self.timeout, check=False)
        except subprocess.TimeoutExpired:
            details.update({"status": "timeout", "error": "existing_parser_timeout"})
            return [], details
        if proc.returncode != 0 or not json_path.exists():
            details.update({"status": "error", "returncode": proc.returncode, "error": "existing_parser_failed_or_no_json"})
            return [], details
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            details.update({"status": "error", "error": "invalid_parser_json"})
            return [], details
        docs = data.get("docs", []) if isinstance(data, dict) else data
        results: list[DiscoveryResult] = []
        for index, doc in enumerate(docs or [], start=1):
            if not isinstance(doc, dict) or not doc.get("url"):
                continue
            results.append(DiscoveryResult("xmlriver_serp", str(doc["url"]), str(doc.get("title") or ""), str(doc.get("snippet") or ""), query.query, index, {"query_kind": query.kind}))
        details.update({"status": "ok", "returncode": proc.returncode, "result_count": len(results), "output_json": str(json_path), "found_total": data.get("found_total") if isinstance(data, dict) else None})
        return results, details
