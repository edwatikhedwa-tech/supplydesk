"""Pure planning for the explicitly confirmed supplier-import write step.

The plan deliberately performs no persistence.  It turns the CSV preview into
three mutually exclusive outcomes: create a new card, skip a duplicate by INN,
or skip a row that still needs attention.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CARD_FIELDS = ("name", "inn", "site", "email", "phone", "note")
PREVIEW_ONLY_FIELDS = ("region", "role")


def build_apply_plan(preview: Mapping[str, Any]) -> dict[str, Any]:
    """Return an apply-ready plan without changing the preview or database."""
    create_rows: list[dict[str, str | int]] = []
    skipped_duplicates: list[int] = []
    skipped_attention: list[int] = []
    seen_inns: set[str] = set()
    preview_only_fields: set[str] = set()

    for row in preview.get("rows", []):
        fields = dict(row.get("fields") or {})
        line = int(row["line"])
        inn = str(fields.get("inn") or "")
        for field in PREVIEW_ONLY_FIELDS:
            if fields.get(field):
                preview_only_fields.add(field)

        issue_codes = {str(issue.get("code") or "") for issue in row.get("issues", [])}
        if "possible_duplicate" in issue_codes or (inn and inn in seen_inns):
            skipped_duplicates.append(line)
            continue
        if issue_codes or not inn:
            skipped_attention.append(line)
            continue

        seen_inns.add(inn)
        create_rows.append({
            "line": line,
            **{field: str(fields.get(field) or "").strip() for field in CARD_FIELDS},
        })

    return {
        "requires_confirmation": True,
        "to_create": len(create_rows),
        "skipped_duplicates": len(skipped_duplicates),
        "skipped_attention": len(skipped_attention),
        "preview_only_fields": sorted(preview_only_fields),
        "create_rows": create_rows,
        "skipped_duplicate_lines": skipped_duplicates,
        "skipped_attention_lines": skipped_attention,
    }
