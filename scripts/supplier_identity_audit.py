"""Audit and, only with --apply-strict-safe, merge verified supplier duplicates.

The normal mode is read-only.  Host rows that share a valid global supplier
are intentionally reported as multi-site contacts, not merged: a host is a
useful search/enrichment identity.  The apply path only moves an unlinked,
hostless exact-email row into one unambiguous host identity and keeps all
request/mail relations inside one transaction.  The former broad ``--apply``
mode is intentionally disabled: its 132 historical candidates are not a
valid apply set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "mail-data" / "supplier.sqlite3"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mail.repository import MailRepository

# Safety assertions for the current reviewed database state.  They are not
# used to select candidates: each candidate is checked again by
# strict_candidate_reasons() on every run.
EXPECTED_STRICT_SAFE = 103
EXPECTED_STRICT_UNRESOLVED = 30
EXPECTED_STRICT_AMBIGUOUS = 2

KNOWN_SUPPLIER_RELATIONS = frozenset({
    "blacklist_entries",
    "global_supplier_links",
    "mail_campaign_targets",
    "mail_delivery_resolutions",  # immutable snapshot; deliberately no FK
    "mail_messages",
    "mail_send_operation_targets",
    "mail_threads",
    "request_supplier_ratings",
    "request_supplier_states",
    "request_suppliers",
    "search_result_sources",
    "supplier_evidence",
    "supplier_inn_sources",
    "supplier_profiles",
})

MERGE_SUPPLIER_RELATIONS = KNOWN_SUPPLIER_RELATIONS - {"mail_delivery_resolutions"}


def valid_inn(value: Any) -> bool:
    value = str(value or "").strip()
    return (len(value) in (10, 12)) and value.isdigit()


def norm_email(value: Any) -> str:
    return str(value or "").strip().lower()


def rows_for_supplier(connection: sqlite3.Connection, table: str, supplier_id: int) -> list[sqlite3.Row]:
    return connection.execute(f"SELECT * FROM [{table}] WHERE supplier_id=?", (supplier_id,)).fetchall()


def scan_duplicates(connection: sqlite3.Connection) -> dict[str, Any]:
    suppliers = connection.execute(
        """SELECT s.id, s.workspace_id, s.external_key, s.name, s.email, s.host,
                  COALESCE(p.inn, '') AS inn, gl.global_supplier_id
           FROM suppliers s
           LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
           LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
           ORDER BY s.workspace_id, s.id"""
    ).fetchall()
    by_workspace_email: dict[tuple[int, str], list[sqlite3.Row]] = defaultdict(list)
    for row in suppliers:
        email = norm_email(row["email"])
        if email:
            by_workspace_email[(int(row["workspace_id"]), email)].append(row)

    candidates: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for row in suppliers:
        if str(row["host"] or "").strip() or not norm_email(row["email"]):
            continue
        if row["global_supplier_id"] is not None:
            ambiguous.append({"supplier_id": int(row["id"]), "email": norm_email(row["email"]), "reason": "hostless row already linked to global company"})
            continue
        email = norm_email(row["email"])
        hosts = [
            item for item in by_workspace_email[(int(row["workspace_id"]), email)]
            if str(item["host"] or "").strip() and int(item["id"]) != int(row["id"])
        ]
        if not hosts:
            unresolved.append({"supplier_id": int(row["id"]), "email": email, "reason": "no exact host contact"})
            continue
        global_ids = {int(item["global_supplier_id"]) for item in hosts if item["global_supplier_id"] is not None}
        if len(global_ids) > 1 or (not global_ids and len(hosts) > 1):
            ambiguous.append({
                "supplier_id": int(row["id"]), "email": email,
                "host_supplier_ids": [int(item["id"]) for item in hosts],
                "reason": "email maps to multiple company identities",
            })
            continue
        canonical = sorted(
            hosts,
            key=lambda item: (
                int(item["global_supplier_id"] is not None),
                int(valid_inn(item["inn"])),
                int(bool(str(item["name"] or "").strip())),
                -int(item["id"]),
            ),
            reverse=True,
        )[0]
        candidates.append({
            "duplicate_supplier_id": int(row["id"]),
            "canonical_supplier_id": int(canonical["id"]),
            "workspace_id": int(row["workspace_id"]),
            "email": email,
            "host": str(canonical["host"] or ""),
            "global_supplier_id": int(canonical["global_supplier_id"]) if canonical["global_supplier_id"] is not None else None,
        })

    request_stats: list[dict[str, Any]] = []
    requests = connection.execute("SELECT id, name FROM requests ORDER BY id").fetchall()
    for request in requests:
        rid = int(request["id"])
        raw_count = int(connection.execute("SELECT COUNT(*) FROM request_suppliers WHERE request_id=?", (rid,)).fetchone()[0])
        unique_inn = int(connection.execute(
            """SELECT COUNT(DISTINCT p.inn)
               FROM request_suppliers rs JOIN supplier_profiles p ON p.supplier_id=rs.supplier_id
               WHERE rs.request_id=? AND p.inn<>''""", (rid,)
        ).fetchone()[0])
        unique_global = int(connection.execute(
            """SELECT COUNT(DISTINCT gl.global_supplier_id)
               FROM request_suppliers rs JOIN global_supplier_links gl ON gl.supplier_id=rs.supplier_id
               WHERE rs.request_id=?""", (rid,)
        ).fetchone()[0])
        sites = int(connection.execute(
            """SELECT COUNT(DISTINCT NULLIF(LOWER(s.host), ''))
               FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
               WHERE rs.request_id=?""", (rid,)
        ).fetchone()[0])
        emails = int(connection.execute(
            """SELECT COUNT(DISTINCT NULLIF(LOWER(s.email), ''))
               FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
               WHERE rs.request_id=?""", (rid,)
        ).fetchone()[0])
        request_stats.append({
            "request_id": rid, "name": str(request["name"]),
            "request_supplier_rows": raw_count, "unique_valid_inn": unique_inn,
            "unique_global_companies": unique_global, "unique_sites": sites,
            "unique_emails": emails,
        })

    multi_site = [
        {"global_supplier_id": int(row["global_supplier_id"]), "supplier_count": int(row["supplier_count"]), "sites": int(row["sites"])}
        for row in connection.execute(
            """SELECT gl.global_supplier_id, COUNT(*) AS supplier_count,
                      COUNT(DISTINCT NULLIF(s.host, '')) AS sites
               FROM global_supplier_links gl JOIN suppliers s ON s.id=gl.supplier_id
               GROUP BY gl.global_supplier_id HAVING COUNT(*)>1 ORDER BY supplier_count DESC"""
        ).fetchall()
    ]
    return {
        "database": str(DEFAULT_DB),
        "supplier_count": len(suppliers),
        "candidate_count": len(candidates),
        "ambiguous_count": len(ambiguous),
        "unresolved_count": len(unresolved),
        "candidates": candidates,
        "ambiguous": ambiguous,
        "unresolved": unresolved,
        "multi_site_company_count": len(multi_site),
        "multi_site_companies": multi_site,
        "requests": request_stats,
    }


def quote_identifier(value: str) -> str:
    """Quote an identifier read from sqlite_master before using it in SQL."""
    return '"' + str(value).replace('"', '""') + '"'


def inspect_supplier_relations(connection: sqlite3.Connection) -> dict[str, Any]:
    """Discover every table that stores a supplier reference.

    The schema currently uses ``supplier_id`` consistently, except for
    ``mail_delivery_resolutions`` which intentionally stores an immutable
    historical snapshot without an FK.  We also inspect actual FK metadata so
    a future relation using another column cannot silently escape the merge.
    """
    tables = [
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]
    relations: set[str] = set()
    unknown: list[str] = []
    details: list[dict[str, Any]] = []
    for table in tables:
        quoted = quote_identifier(table)
        columns = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({quoted})").fetchall()
        }
        supplier_column = "supplier_id" in columns
        foreign_supplier_columns: list[str] = []
        for fk in connection.execute(f"PRAGMA foreign_key_list({quoted})").fetchall():
            if str(fk["table"]).lower() != "suppliers":
                continue
            source_column = str(fk["from"])
            foreign_supplier_columns.append(source_column)
            if source_column != "supplier_id":
                unknown.append(f"{table}.{source_column}")
        if supplier_column or foreign_supplier_columns:
            relations.add(table)
            if table not in KNOWN_SUPPLIER_RELATIONS:
                unknown.append(table)
            details.append({
                "table": table,
                "has_supplier_id_column": supplier_column,
                "foreign_supplier_columns": foreign_supplier_columns,
                "immutable_snapshot": table == "mail_delivery_resolutions",
            })
    return {
        "relations": sorted(relations),
        "unknown": sorted(set(unknown)),
        "details": details,
    }


def supplier_row(connection: sqlite3.Connection, supplier_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """SELECT s.id, s.workspace_id, s.external_key, s.name, s.email, s.host,
                  COALESCE(p.inn, '') AS inn, gl.global_supplier_id
           FROM suppliers s
           LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
           LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
           WHERE s.id=?""",
        (supplier_id,),
    ).fetchone()


def strict_candidate_reasons(
    connection: sqlite3.Connection,
    candidate: dict[str, Any],
    relation_report: dict[str, Any],
) -> list[str]:
    """Return all reasons a broad candidate is not strict-safe.

    No candidate IDs are embedded here.  This gate is evaluated from the live
    database both during dry-run and immediately before the apply transaction.
    """
    duplicate_id = int(candidate["duplicate_supplier_id"])
    canonical_id = int(candidate["canonical_supplier_id"])
    duplicate = supplier_row(connection, duplicate_id)
    canonical = supplier_row(connection, canonical_id)
    reasons: list[str] = []
    if duplicate is None or canonical is None:
        return ["duplicate or canonical supplier is missing"]
    if int(duplicate["workspace_id"]) != int(canonical["workspace_id"]):
        reasons.append("different workspace")
    if str(duplicate["host"] or "").strip():
        reasons.append("duplicate has a host; host rows are never auto-merged")
    duplicate_email = norm_email(duplicate["email"])
    canonical_email = norm_email(canonical["email"])
    if not duplicate_email or duplicate_email != canonical_email:
        reasons.append("exact required email contact is not confirmed")
    if not str(canonical["host"] or "").strip():
        reasons.append("canonical supplier has no host")

    canonical_has_legal_identity = (
        valid_inn(canonical["inn"]) or canonical["global_supplier_id"] is not None
    )
    if not canonical_has_legal_identity:
        reasons.append("canonical legal identity has no confirmed INN/global identity")
    duplicate_inn = str(duplicate["inn"] or "").strip()
    canonical_inn = str(canonical["inn"] or "").strip()
    if valid_inn(duplicate_inn) and valid_inn(canonical_inn) and duplicate_inn != canonical_inn:
        reasons.append("conflicting confirmed INN")

    # Re-evaluate the exact-email mapping instead of trusting the original
    # scan.  One global identity is unambiguous even when it has several host
    # rows; without a global identity, more than one host is ambiguous.
    host_rows = connection.execute(
        """SELECT s.id, COALESCE(p.inn, '') AS inn, gl.global_supplier_id
           FROM suppliers s
           LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
           LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
           WHERE s.workspace_id=? AND lower(trim(COALESCE(s.email, '')))=?
             AND trim(COALESCE(s.host, ''))<>''
           ORDER BY s.id""",
        (int(duplicate["workspace_id"]), duplicate_email),
    ).fetchall()
    global_ids = {int(row["global_supplier_id"]) for row in host_rows if row["global_supplier_id"] is not None}
    if len(global_ids) > 1 or (not global_ids and len(host_rows) != 1):
        reasons.append("exact host+email mapping is ambiguous")
    elif global_ids:
        if canonical["global_supplier_id"] is None or int(canonical["global_supplier_id"]) not in global_ids:
            reasons.append("canonical supplier is outside the exact global identity")
    elif int(host_rows[0]["id"]) != canonical_id:
        reasons.append("canonical supplier is not the unique exact host contact")

    active_blacklist = connection.execute(
        """SELECT supplier_id FROM blacklist_entries
           WHERE workspace_id=? AND restored_at IS NULL AND supplier_id IN (?, ?)""",
        (int(duplicate["workspace_id"]), duplicate_id, canonical_id),
    ).fetchall()
    if active_blacklist:
        reasons.append("duplicate/canonical supplier has an active blacklist entry")

    # A resolution is an immutable historical snapshot with no FK.  Keeping
    # it attached to a deleted duplicate would make the historical identity
    # orphaned, so the strict mode refuses such a candidate instead of
    # guessing whether the snapshot may be rewritten.
    if connection.execute(
        "SELECT 1 FROM mail_delivery_resolutions WHERE supplier_id=? LIMIT 1",
        (duplicate_id,),
    ).fetchone():
        reasons.append("immutable delivery-resolution history would retain duplicate supplier_id")
    unknown_relations = relation_report.get(
        "unknown", relation_report.get("unknown_supplier_relations", [])
    )
    if unknown_relations:
        reasons.append("unknown supplier relation exists in schema")
    return reasons


def strict_scan(connection: sqlite3.Connection) -> dict[str, Any]:
    base = scan_duplicates(connection)
    relation_report = inspect_supplier_relations(connection)
    strict_candidates: list[dict[str, Any]] = []
    strict_failures: list[dict[str, Any]] = []
    for candidate in base["candidates"]:
        reasons = strict_candidate_reasons(connection, candidate, relation_report)
        if reasons:
            strict_failures.append({
                **candidate,
                "reason": "; ".join(reasons),
            })
        else:
            strict_candidates.append(candidate)
    strict_unresolved = [*base["unresolved"], *strict_failures]
    return {
        **base,
        "supplier_fk_relations": relation_report["relations"],
        "supplier_fk_relation_details": relation_report["details"],
        "unknown_supplier_relations": relation_report["unknown"],
        "strict_safe_candidates": strict_candidates,
        "strict_safe_count": len(strict_candidates),
        "strict_failures": strict_failures,
        "strict_unresolved": strict_unresolved,
        "strict_unresolved_count": len(strict_unresolved),
        "strict_ambiguous_count": len(base["ambiguous"]),
    }


class StrictGateError(RuntimeError):
    def __init__(self, message: str, report: dict[str, Any]):
        super().__init__(message)
        self.report = report


def enforce_strict_gate(report: dict[str, Any], *, allow_empty: bool = False) -> None:
    actual = (
        int(report["strict_safe_count"]),
        int(report["strict_unresolved_count"]),
        int(report["strict_ambiguous_count"]),
    )
    expected = (
        EXPECTED_STRICT_SAFE,
        EXPECTED_STRICT_UNRESOLVED,
        EXPECTED_STRICT_AMBIGUOUS,
    )
    if report["unknown_supplier_relations"]:
        raise StrictGateError(
            "Обнаружена неизвестная supplier relation: "
            + ", ".join(report["unknown_supplier_relations"]),
            report,
        )
    if allow_empty and actual == (0, EXPECTED_STRICT_UNRESOLVED, EXPECTED_STRICT_AMBIGUOUS):
        return
    if actual != expected:
        raise StrictGateError(
            f"Strict pre-apply gate остановлен: получено SAFE/UNRESOLVED/AMBIGUOUS="
            f"{actual[0]}/{actual[1]}/{actual[2]}, ожидалось {expected[0]}/{expected[1]}/{expected[2]}",
            report,
        )


def merge_json_lists(left: str | None, right: str | None) -> str:
    values: list[Any] = []
    for raw in (left, right):
        try:
            parsed = json.loads(raw or "[]")
        except (TypeError, ValueError):
            parsed = []
        if isinstance(parsed, list):
            for value in parsed:
                if value not in values:
                    values.append(value)
    return json.dumps(values, ensure_ascii=False)


def merge_supplier_pair(connection: sqlite3.Connection, duplicate_id: int, canonical_id: int) -> None:
    if duplicate_id == canonical_id:
        raise ValueError("Нельзя объединить поставщика с самим собой.")
    duplicate = connection.execute("SELECT * FROM suppliers WHERE id=?", (duplicate_id,)).fetchone()
    canonical = connection.execute("SELECT * FROM suppliers WHERE id=?", (canonical_id,)).fetchone()
    if not duplicate or not canonical:
        raise ValueError("Один из поставщиков не найден.")
    if int(duplicate["workspace_id"]) != int(canonical["workspace_id"]):
        raise ValueError("Поставщики принадлежат разным рабочим пространствам.")
    if str(duplicate["host"] or "").strip() or not norm_email(duplicate["email"]):
        raise ValueError("Безопасный merge разрешён только для hostless email-only строки.")

    duplicate_profile = connection.execute("SELECT * FROM supplier_profiles WHERE supplier_id=?", (duplicate_id,)).fetchone()
    canonical_profile = connection.execute("SELECT * FROM supplier_profiles WHERE supplier_id=?", (canonical_id,)).fetchone()
    duplicate_inn = str(duplicate_profile["inn"] or "") if duplicate_profile else ""
    canonical_inn = str(canonical_profile["inn"] or "") if canonical_profile else ""
    if duplicate_inn and canonical_inn and duplicate_inn != canonical_inn:
        raise ValueError("У поставщиков разные ИНН.")

    # Merge thread collisions before changing supplier_id, otherwise the
    # UNIQUE(workspace_id, request_id, supplier_id) constraint would reject it.
    duplicate_threads = rows_for_supplier(connection, "mail_threads", duplicate_id)
    for thread in duplicate_threads:
        existing = connection.execute(
            """SELECT * FROM mail_threads
               WHERE workspace_id=? AND request_id=? AND supplier_id=?""",
            (thread["workspace_id"], thread["request_id"], canonical_id),
        ).fetchone()
        if existing:
            connection.execute("UPDATE mail_messages SET thread_id=?, supplier_id=? WHERE thread_id=?", (existing["id"], canonical_id, thread["id"]))
            connection.execute(
                """UPDATE mail_threads
                   SET last_message_at=CASE
                         WHEN last_message_at IS NULL OR (SELECT last_message_at FROM mail_threads WHERE id=?) > last_message_at
                         THEN (SELECT last_message_at FROM mail_threads WHERE id=?) ELSE last_message_at END
                   WHERE id=?""",
                (thread["id"], thread["id"], existing["id"]),
            )
            connection.execute("DELETE FROM mail_threads WHERE id=?", (thread["id"],))
        else:
            connection.execute("UPDATE mail_threads SET supplier_id=? WHERE id=?", (canonical_id, thread["id"]))
    connection.execute("UPDATE mail_messages SET supplier_id=? WHERE supplier_id=?", (canonical_id, duplicate_id))

    # Request relation and status tables have the same composite key.  Keep
    # the canonical row and union the durable facts when both rows exist.
    for table in ("request_suppliers", "request_supplier_states", "request_supplier_ratings"):
        for row in rows_for_supplier(connection, table, duplicate_id):
            keys = {"request_suppliers": "request_id", "request_supplier_states": "request_id", "request_supplier_ratings": "request_id"}
            request_id = int(row["request_id"])
            existing = connection.execute(f"SELECT * FROM [{table}] WHERE request_id=? AND supplier_id=?", (request_id, canonical_id)).fetchone()
            if not existing:
                connection.execute(f"UPDATE [{table}] SET supplier_id=? WHERE request_id=? AND supplier_id=?", (canonical_id, request_id, duplicate_id))
                continue
            if table == "request_suppliers":
                connection.execute(
                    """UPDATE request_suppliers SET position_keys_json=?, reason=?, source=?,
                              is_irrelevant=MAX(is_irrelevant, ?), updated_at=MAX(updated_at, ?)
                       WHERE request_id=? AND supplier_id=?""",
                    (merge_json_lists(existing["position_keys_json"], row["position_keys_json"]), existing["reason"] or row["reason"], existing["source"] or row["source"], row["is_irrelevant"], row["updated_at"], request_id, canonical_id),
                )
            elif table == "request_supplier_states":
                chosen = row if str(row["updated_at"] or "") > str(existing["updated_at"] or "") else existing
                connection.execute(
                    """UPDATE request_supplier_states SET mail_account_id=?, status=?, last_message_id=?, last_error=?, updated_at=?
                       WHERE request_id=? AND supplier_id=?""",
                    (chosen["mail_account_id"], chosen["status"], chosen["last_message_id"], chosen["last_error"], chosen["updated_at"], request_id, canonical_id),
                )
            else:
                chosen = row if str(row["updated_at"] or "") > str(existing["updated_at"] or "") else existing
                connection.execute("UPDATE request_supplier_ratings SET rating=?, updated_at=? WHERE request_id=? AND supplier_id=?", (chosen["rating"], chosen["updated_at"], request_id, canonical_id))
            connection.execute(f"DELETE FROM [{table}] WHERE request_id=? AND supplier_id=?", (request_id, duplicate_id))

    for row in rows_for_supplier(connection, "search_result_sources", duplicate_id):
        existing = connection.execute(
            "SELECT * FROM search_result_sources WHERE request_id=? AND supplier_id=? AND position_key=?",
            (row["request_id"], canonical_id, row["position_key"]),
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE search_result_sources SET url=CASE WHEN url='' THEN ? ELSE url END, title=CASE WHEN title='' THEN ? ELSE title END, updated_at=MAX(updated_at, ?) WHERE request_id=? AND supplier_id=? AND position_key=?",
                (row["url"], row["title"], row["updated_at"], row["request_id"], canonical_id, row["position_key"]),
            )
            connection.execute("DELETE FROM search_result_sources WHERE request_id=? AND supplier_id=? AND position_key=?", (row["request_id"], duplicate_id, row["position_key"]))
        else:
            connection.execute("UPDATE search_result_sources SET supplier_id=? WHERE request_id=? AND supplier_id=? AND position_key=?", (canonical_id, row["request_id"], duplicate_id, row["position_key"]))

    for row in rows_for_supplier(connection, "supplier_evidence", duplicate_id):
        connection.execute(
            """INSERT OR IGNORE INTO supplier_evidence(
                workspace_id, supplier_id, field_name, field_value, source_type, source_url,
                strength, score, decision, details_json, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["workspace_id"], canonical_id, row["field_name"], row["field_value"], row["source_type"], row["source_url"], row["strength"], row["score"], row["decision"], row["details_json"], row["first_seen_at"], row["last_seen_at"]),
        )
    connection.execute("DELETE FROM supplier_evidence WHERE supplier_id=?", (duplicate_id,))

    for table in ("blacklist_entries", "mail_campaign_targets", "mail_send_operation_targets"):
        if table != "mail_send_operation_targets":
            connection.execute(f"UPDATE [{table}] SET supplier_id=? WHERE supplier_id=?", (canonical_id, duplicate_id))
            continue
        for target in rows_for_supplier(connection, table, duplicate_id):
            existing = connection.execute(
                """SELECT * FROM mail_send_operation_targets
                   WHERE operation_id=? AND normalized_email=? AND id<>?""",
                (target["operation_id"], target["normalized_email"], target["id"]),
            ).fetchone()
            if existing:
                if existing["message_id"] is None and target["message_id"] is not None:
                    connection.execute("UPDATE mail_send_operation_targets SET message_id=?, updated_at=MAX(updated_at, ?) WHERE id=?", (target["message_id"], target["updated_at"], existing["id"]))
                connection.execute("DELETE FROM mail_send_operation_targets WHERE id=?", (target["id"],))
            else:
                connection.execute("UPDATE mail_send_operation_targets SET supplier_id=? WHERE id=?", (canonical_id, target["id"]))

    if duplicate_profile:
        if not canonical_profile:
            connection.execute("UPDATE supplier_profiles SET supplier_id=? WHERE supplier_id=?", (canonical_id, duplicate_id))
        else:
            fields = ("inn", "kind", "region", "role", "phone", "reason", "source")
            values = [canonical_profile[field] or duplicate_profile[field] for field in fields]
            values.extend([merge_json_lists(canonical_profile["covers_json"], duplicate_profile["covers_json"]), max(int(canonical_profile["site_unavailable"] or 0), int(duplicate_profile["site_unavailable"] or 0)), max(str(canonical_profile["updated_at"] or ""), str(duplicate_profile["updated_at"] or "")), canonical_id])
            connection.execute("UPDATE supplier_profiles SET inn=?, kind=?, region=?, role=?, phone=?, reason=?, source=?, covers_json=?, site_unavailable=?, updated_at=? WHERE supplier_id=?", values)
            connection.execute("DELETE FROM supplier_profiles WHERE supplier_id=?", (duplicate_id,))
    for row in rows_for_supplier(connection, "supplier_inn_sources", duplicate_id):
        existing = connection.execute("SELECT * FROM supplier_inn_sources WHERE supplier_id=?", (canonical_id,)).fetchone()
        if not existing:
            connection.execute("UPDATE supplier_inn_sources SET supplier_id=? WHERE supplier_id=?", (canonical_id, duplicate_id))
        else:
            if existing["source_type"] != "manual" and row["source_type"] == "manual":
                connection.execute("UPDATE supplier_inn_sources SET source_type=?, updated_by=?, updated_at=? WHERE supplier_id=?", (row["source_type"], row["updated_by"], row["updated_at"], canonical_id))
            connection.execute("DELETE FROM supplier_inn_sources WHERE supplier_id=?", (duplicate_id,))

    # A delivery resolution is intentionally an immutable snapshot and has no
    # FK.  It keeps the historical supplier_id by design.
    remaining: list[str] = []
    for table in ("blacklist_entries", "global_supplier_links", "mail_campaign_targets", "mail_messages", "mail_send_operation_targets", "mail_threads", "request_supplier_ratings", "request_supplier_states", "request_suppliers", "search_result_sources", "supplier_evidence", "supplier_inn_sources", "supplier_profiles"):
        if connection.execute(f"SELECT 1 FROM [{table}] WHERE supplier_id=? LIMIT 1", (duplicate_id,)).fetchone():
            remaining.append(table)
    if remaining:
        raise ValueError(f"Остались необработанные связи: {', '.join(remaining)}")
    connection.execute("DELETE FROM suppliers WHERE id=?", (duplicate_id,))


def open_database(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def sqlite_validation(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
    integrity_values = [str(row[0]) for row in integrity_rows]
    foreign_key_errors = [dict(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()]
    return {
        "integrity_check": integrity_values[0] if len(integrity_values) == 1 else integrity_values,
        "foreign_key_errors": foreign_key_errors,
        "ok": integrity_values == ["ok"] and not foreign_key_errors,
    }


def request_items_for_snapshot(connection: sqlite3.Connection, request_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT s.id, s.external_key, s.name, s.email, s.host,
                  COALESCE(p.inn, '') AS inn,
                  COALESCE(rs.position_keys_json, '[]') AS position_keys_json,
                  COALESCE(p.covers_json, '[]') AS covers_json,
                  COALESCE(st.status, 'not_sent') AS mail_pipeline_status,
                  st.last_error, gl.global_supplier_id
           FROM request_suppliers rs
           JOIN suppliers s ON s.id=rs.supplier_id
           LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
           LEFT JOIN request_supplier_states st
             ON st.request_id=rs.request_id AND st.supplier_id=rs.supplier_id
           LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
           WHERE rs.request_id=? AND COALESCE(rs.is_irrelevant, 0)=0
             AND NOT EXISTS (
                 SELECT 1 FROM blacklist_entries b
                 WHERE b.workspace_id=s.workspace_id AND b.restored_at IS NULL
                   AND (s.external_key=b.external_key OR s.external_key LIKE '%.' || b.external_key)
             )
           ORDER BY s.name, s.id""",
        (request_id,),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            position_keys = json.loads(row["position_keys_json"] or "[]")
        except (TypeError, ValueError):
            position_keys = []
        try:
            covers = json.loads(row["covers_json"] or "[]")
        except (TypeError, ValueError):
            covers = []
        raw_status = str(row["mail_pipeline_status"] or "not_sent")
        items.append({
            "id": int(row["id"]),
            "external_key": row["external_key"],
            "name": row["name"],
            "email": row["email"],
            "host": row["host"],
            "inn": row["inn"],
            "global_supplier_id": (
                int(row["global_supplier_id"])
                if row["global_supplier_id"] is not None else None
            ),
            "position_keys": position_keys if isinstance(position_keys, list) else [],
            "covers": covers if isinstance(covers, list) else [],
            "mail_pipeline_status": raw_status,
            "mail_status": raw_status,
            "last_error": row["last_error"],
            "registry": None,
            "delivery_issue_resolved": None,
            "unread_count": 0,
        })
    return items


def request_snapshot(connection: sqlite3.Connection, request_id: int) -> dict[str, Any]:
    raw_count = int(connection.execute(
        "SELECT COUNT(*) FROM request_suppliers WHERE request_id=?", (request_id,)
    ).fetchone()[0])
    visible_count = int(connection.execute(
        """SELECT COUNT(*) FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
           WHERE rs.request_id=? AND COALESCE(rs.is_irrelevant, 0)=0
             AND NOT EXISTS (
                 SELECT 1 FROM blacklist_entries b
                 WHERE b.workspace_id=s.workspace_id AND b.restored_at IS NULL
                   AND (s.external_key=b.external_key OR s.external_key LIKE '%.' || b.external_key)
             )""",
        (request_id,),
    ).fetchone()[0])
    unique_sites = int(connection.execute(
        """SELECT COUNT(DISTINCT NULLIF(LOWER(s.host), ''))
           FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
           WHERE rs.request_id=? AND COALESCE(rs.is_irrelevant, 0)=0
             AND NOT EXISTS (
                 SELECT 1 FROM blacklist_entries b
                 WHERE b.workspace_id=s.workspace_id AND b.restored_at IS NULL
                   AND (s.external_key=b.external_key OR s.external_key LIKE '%.' || b.external_key)
             )""",
        (request_id,),
    ).fetchone()[0])
    unique_emails = int(connection.execute(
        """SELECT COUNT(DISTINCT NULLIF(LOWER(s.email), ''))
           FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
           WHERE rs.request_id=? AND COALESCE(rs.is_irrelevant, 0)=0
             AND NOT EXISTS (
                 SELECT 1 FROM blacklist_entries b
                 WHERE b.workspace_id=s.workspace_id AND b.restored_at IS NULL
                   AND (s.external_key=b.external_key OR s.external_key LIKE '%.' || b.external_key)
             )""",
        (request_id,),
    ).fetchone()[0])
    raw_unique_sites = int(connection.execute(
        """SELECT COUNT(DISTINCT NULLIF(LOWER(s.host), ''))
           FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
           WHERE rs.request_id=?""",
        (request_id,),
    ).fetchone()[0])
    raw_unique_emails = int(connection.execute(
        """SELECT COUNT(DISTINCT NULLIF(LOWER(s.email), ''))
           FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
           WHERE rs.request_id=?""",
        (request_id,),
    ).fetchone()[0])
    facts = MailRepository._request_mail_facts(connection, request_id)
    metrics = MailRepository._request_mail_metrics(connection, request_id)
    cards = MailRepository._aggregate_request_suppliers(
        request_items_for_snapshot(connection, request_id), mail_facts=facts
    )
    group_sizes = Counter(len(item.get("related_supplier_ids", [])) for item in cards)
    card_delivery = Counter(str(item.get("delivery_status") or "not_sent") for item in cards)
    card_response = Counter(str(item.get("response_status") or "none") for item in cards)
    return {
        "request_id": request_id,
        "raw_request_supplier_rows": raw_count,
        "visible_request_supplier_rows": visible_count,
        "company_cards": len(cards),
        "companies_with_contacts": sum(int(item.get("email_count", 0) > 0) for item in cards),
        "unique_emails": unique_emails,
        "unique_sites": unique_sites,
        "raw_unique_emails": raw_unique_emails,
        "raw_unique_sites": raw_unique_sites,
        "group_size_distribution": {
            "1": int(group_sizes.get(1, 0)),
            "2": int(group_sizes.get(2, 0)),
            "3": int(group_sizes.get(3, 0)),
            "4+": int(sum(value for key, value in group_sizes.items() if key >= 4)),
        },
        "mail": metrics,
        "card_delivery_status_counts": dict(sorted(card_delivery.items())),
        "card_response_status_counts": dict(sorted(card_response.items())),
        "waiting": int(card_response.get("waiting", 0)),
        "answered": int(card_response.get("answered", 0)),
        "not_sent_cards": sum(int(item.get("unsent_contact_count", 0) > 0) for item in cards),
    }


def identity_snapshot(connection: sqlite3.Connection, supplier_ids: list[int]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for supplier_id in sorted(set(int(value) for value in supplier_ids)):
        supplier = connection.execute(
            "SELECT * FROM suppliers WHERE id=?", (supplier_id,)
        ).fetchone()
        profile = connection.execute(
            "SELECT * FROM supplier_profiles WHERE supplier_id=?", (supplier_id,)
        ).fetchone()
        links = connection.execute(
            "SELECT * FROM global_supplier_links WHERE supplier_id=? ORDER BY global_supplier_id",
            (supplier_id,),
        ).fetchall()
        snapshot[str(supplier_id)] = {
            "supplier": dict(supplier) if supplier else None,
            "profile": dict(profile) if profile else None,
            "global_links": [dict(row) for row in links],
        }
    return snapshot


def multi_site_snapshot(connection: sqlite3.Connection, inn: str = "7726347929") -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """SELECT s.id, s.email, s.host, p.inn, gl.global_supplier_id
               FROM suppliers s
               JOIN supplier_profiles p ON p.supplier_id=s.id
               LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
               WHERE p.inn=? ORDER BY s.id""",
            (inn,),
        ).fetchall()
    ]


def candidate_message_records(
    connection: sqlite3.Connection, supplier_ids: list[int]
) -> dict[str, dict[str, Any]]:
    if not supplier_ids:
        return {}
    placeholders = ",".join("?" for _ in supplier_ids)
    rows = connection.execute(
        f"""SELECT id, supplier_id, to_email, status, sent_at, message_id,
                      provider_message_id, created_at, error
               FROM mail_messages WHERE supplier_id IN ({placeholders})
               ORDER BY id""",
        supplier_ids,
    ).fetchall()
    return {str(int(row["id"])): dict(row) for row in rows}


def candidate_relation_records(
    connection: sqlite3.Connection,
    table: str,
    supplier_ids: list[int],
) -> list[dict[str, Any]]:
    if not supplier_ids:
        return []
    placeholders = ",".join("?" for _ in supplier_ids)
    return [
        dict(row)
        for row in connection.execute(
            f"SELECT * FROM {quote_identifier(table)} WHERE supplier_id IN ({placeholders}) ORDER BY id",
            supplier_ids,
        ).fetchall()
    ]


def message_records_by_ids(
    connection: sqlite3.Connection, message_ids: list[int]
) -> dict[str, dict[str, Any]]:
    if not message_ids:
        return {}
    placeholders = ",".join("?" for _ in message_ids)
    rows = connection.execute(
        f"""SELECT id, supplier_id, to_email, status, sent_at, message_id,
                      provider_message_id, created_at, error
               FROM mail_messages WHERE id IN ({placeholders})
               ORDER BY id""",
        message_ids,
    ).fetchall()
    return {str(int(row["id"])): dict(row) for row in rows}


def relation_counts(
    connection: sqlite3.Connection,
    supplier_ids: list[int],
    relation_report: dict[str, Any],
) -> dict[str, int]:
    relations = relation_report.get("relations", relation_report.get("supplier_fk_relations", []))
    if not supplier_ids:
        result = {table: 0 for table in relations}
        result["mail_send_attempts"] = 0
        result["statuses_events"] = 0
        return result
    placeholders = ",".join("?" for _ in supplier_ids)
    result: dict[str, int] = {}
    for table in relations:
        if "supplier_id" not in {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
        }:
            result[table] = 0
            continue
        result[table] = int(connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)} WHERE supplier_id IN ({placeholders})",
            supplier_ids,
        ).fetchone()[0])
    message_rows = connection.execute(
        f"SELECT id FROM mail_messages WHERE supplier_id IN ({placeholders})", supplier_ids
    ).fetchall()
    message_ids = [int(row[0]) for row in message_rows]
    if message_ids:
        message_placeholders = ",".join("?" for _ in message_ids)
        result["mail_send_attempts"] = int(connection.execute(
            f"SELECT COUNT(*) FROM mail_send_attempts WHERE message_id IN ({message_placeholders})",
            message_ids,
        ).fetchone()[0])
    else:
        result["mail_send_attempts"] = 0
    result["statuses_events"] = result.get("request_supplier_states", 0) + result["mail_send_attempts"]
    result["other_fk_relations"] = sum(
        value for table, value in result.items()
        if table in MERGE_SUPPLIER_RELATIONS
        and table not in {"request_suppliers", "mail_messages", "request_supplier_states"}
    )
    return result


def pre_apply_snapshot(
    connection: sqlite3.Connection,
    strict_report: dict[str, Any],
    request_id: int = 1059,
) -> dict[str, Any]:
    candidates = strict_report["strict_safe_candidates"]
    duplicate_ids = [int(item["duplicate_supplier_id"]) for item in candidates]
    protected_ids = [
        int(item.get("supplier_id", item.get("duplicate_supplier_id")))
        for item in strict_report["strict_unresolved"] + strict_report["ambiguous"]
    ]
    canonical_by_duplicate = {
        int(item["duplicate_supplier_id"]): int(item["canonical_supplier_id"])
        for item in candidates
    }
    request_relations = [
        dict(row)
        for row in connection.execute(
            """SELECT request_id, supplier_id FROM request_suppliers
               WHERE supplier_id IN ({}) ORDER BY request_id, supplier_id""".format(",".join("?" for _ in duplicate_ids)),
            duplicate_ids,
        ).fetchall()
    ] if duplicate_ids else []
    return {
        "supplier_count": int(connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]),
        "request_1059": request_snapshot(connection, request_id),
        "relation_counts": relation_counts(connection, duplicate_ids, strict_report),
        "candidate_duplicate_ids": duplicate_ids,
        "canonical_by_duplicate": canonical_by_duplicate,
        "candidate_message_records": candidate_message_records(connection, duplicate_ids),
        "operation_target_records": candidate_relation_records(
            connection, "mail_send_operation_targets", duplicate_ids
        ),
        "campaign_target_records": candidate_relation_records(
            connection, "mail_campaign_targets", duplicate_ids
        ),
        "request_relations": request_relations,
        "protected_identity_snapshot": identity_snapshot(connection, protected_ids),
        "multi_site_7726347929": multi_site_snapshot(connection),
    }


def post_apply_validation(
    connection: sqlite3.Connection,
    before: dict[str, Any],
    strict_report: dict[str, Any],
    request_id: int = 1059,
) -> dict[str, Any]:
    duplicate_ids = [int(value) for value in before["candidate_duplicate_ids"]]
    canonical_by_duplicate = {
        int(key): int(value) for key, value in before["canonical_by_duplicate"].items()
    }
    relation_report = inspect_supplier_relations(connection)
    survivors: dict[str, int] = {}
    if duplicate_ids:
        placeholders = ",".join("?" for _ in duplicate_ids)
        for table in relation_report["relations"]:
            columns = {
                str(row["name"])
                for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
            }
            if "supplier_id" in columns:
                survivors[table] = int(connection.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(table)} WHERE supplier_id IN ({placeholders})",
                    duplicate_ids,
                ).fetchone()[0])
            else:
                survivors[table] = 0
    else:
        survivors = {table: 0 for table in relation_report["relations"]}

    after_messages = message_records_by_ids(
        connection,
        [int(key) for key in before["candidate_message_records"]],
    )
    immutable_message_fields = (
        "to_email", "status", "sent_at", "message_id", "provider_message_id", "created_at", "error"
    )
    mail_history_preserved = set(after_messages) == set(before["candidate_message_records"])
    if mail_history_preserved:
        for key, old in before["candidate_message_records"].items():
            new = after_messages[key]
            if any(new[field] != old[field] for field in immutable_message_fields):
                mail_history_preserved = False
                break

    def relation_records_preserved(table: str, records: list[dict[str, Any]]) -> bool:
        for old in records:
            new_row = connection.execute(
                f"SELECT * FROM {quote_identifier(table)} WHERE id=?",
                (int(old["id"]),),
            ).fetchone()
            if new_row is None:
                return False
            new = dict(new_row)
            expected_supplier_id = canonical_by_duplicate.get(int(old["supplier_id"]))
            if expected_supplier_id is None or int(new.get("supplier_id")) != expected_supplier_id:
                return False
            if any(
                new[field] != value
                for field, value in old.items()
                if field != "supplier_id"
            ):
                return False
        return True

    operation_targets_preserved = relation_records_preserved(
        "mail_send_operation_targets", before["operation_target_records"]
    )
    campaign_targets_preserved = relation_records_preserved(
        "mail_campaign_targets", before["campaign_target_records"]
    )

    request_relations_preserved = True
    for row in before["request_relations"]:
        canonical_id = canonical_by_duplicate[int(row["supplier_id"])]
        if not connection.execute(
            "SELECT 1 FROM request_suppliers WHERE request_id=? AND supplier_id=?",
            (int(row["request_id"]), canonical_id),
        ).fetchone():
            request_relations_preserved = False
            break

    protected_ids = [int(key) for key in before["protected_identity_snapshot"]]
    protected_unchanged = (
        identity_snapshot(connection, protected_ids) == before["protected_identity_snapshot"]
    )
    multi_site_unchanged = multi_site_snapshot(connection) == before["multi_site_7726347929"]
    integrity = sqlite_validation(connection)
    return {
        "supplier_count": int(connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]),
        "request_1059": request_snapshot(connection, request_id),
        "duplicate_supplier_survivors": int(connection.execute(
            "SELECT COUNT(*) FROM suppliers WHERE id IN ({})".format(",".join("?" for _ in duplicate_ids)),
            duplicate_ids,
        ).fetchone()[0]) if duplicate_ids else 0,
        "relation_survivors": survivors,
        "mail_history_preserved": mail_history_preserved,
        "operation_targets_preserved": operation_targets_preserved,
        "campaign_targets_preserved": campaign_targets_preserved,
        "request_relations_preserved": request_relations_preserved,
        "protected_unresolved_ambiguous_unchanged": protected_unchanged,
        "multi_site_7726347929": multi_site_snapshot(connection),
        "multi_site_7726347929_unchanged": multi_site_unchanged,
        "integrity": integrity,
    }


def backup_database(db_path: Path) -> Path:
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"{db_path.stem}.{stamp}.bak.sqlite3"
    source_path = db_path.resolve()
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(backup_path)
    source_database_uuid: str | None = None
    try:
        try:
            identity = source.execute(
                "SELECT database_uuid FROM mail_database_identity WHERE id=1"
            ).fetchone()
            source_database_uuid = str(identity[0]) if identity else None
        except sqlite3.OperationalError:
            # Older databases do not have the runtime identity table yet.
            source_database_uuid = None
        source.backup(destination)
        destination.commit()
        validation = sqlite_validation(destination)
        if not validation["ok"]:
            raise RuntimeError(
                f"Backup не прошёл проверку SQLite: {json.dumps(validation, ensure_ascii=False)}"
            )
    finally:
        destination.close()
        source.close()
    backup_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    metadata_path = backup_path.with_name(backup_path.name + ".metadata.json")
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path),
        "source_database_uuid": source_database_uuid,
        "source_sha256": source_hash,
        "backup_path": str(backup_path.resolve()),
        "backup_sha256": backup_hash,
        "backup_integrity": "ok",
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return backup_path


def outgoing_enabled_value(connection: sqlite3.Connection) -> int | None:
    try:
        row = connection.execute(
            "SELECT outgoing_enabled FROM mail_runtime_controls ORDER BY id LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else int(row[0])


def summarize_for_text(report: dict[str, Any]) -> None:
    print(f"Режим: {report.get('mode', 'unknown')}")
    if report.get("error"):
        print(f"ОШИБКА: {report['error']}")
    print(f"Поставщиков: {report.get('supplier_count', report.get('suppliers_before', '?'))}")
    print(
        "Strict SAFE/UNRESOLVED/AMBIGUOUS: "
        f"{report.get('strict_safe_count', '?')}/"
        f"{report.get('strict_unresolved_count', '?')}/"
        f"{report.get('strict_ambiguous_count', '?')}"
    )
    print(
        f"Широкий audit candidates: {report.get('candidate_count', '?')}; "
        f"неизвестные supplier relations: {report.get('unknown_supplier_relations', [])}"
    )
    if report.get("backup"):
        print(f"Backup: {report['backup']}; integrity: {report.get('backup_integrity', 'ok')}")
    if "applied_count" in report:
        print(f"Применено strict-safe merge: {report['applied_count']}")
    if report.get("request_1059"):
        print("Заявка 1059:", json.dumps(report["request_1059"], ensure_ascii=False))
    if report.get("request_1059_before"):
        print("Заявка 1059 BEFORE:", json.dumps(report["request_1059_before"], ensure_ascii=False))
        print("Заявка 1059 AFTER:", json.dumps(report["request_1059_after"], ensure_ascii=False))
    if report.get("second_dry_run"):
        print("Второй strict-safe dry-run:", json.dumps(report["second_dry_run"], ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка и strict-safe merge дублей поставщиков.")
    parser.add_argument("--db", type=Path, default=Path(os.getenv("MAIL_DB_PATH", str(DEFAULT_DB))))
    parser.add_argument("--plan", action="store_true", help="Показать план изменений; синоним read-only режима.")
    parser.add_argument("--dry-run", action="store_true", help="Только отчёт, без записи в БД (режим по умолчанию).")
    parser.add_argument("--apply", action="store_true", help="Отключено: старый broad apply намеренно запрещён.")
    parser.add_argument(
        "--apply-strict-safe", action="store_true",
        help="Применить только кандидатов, прошедших strict SAFE gate 103/30/2.",
    )
    parser.add_argument("--json", action="store_true", help="Вывести отчёт JSON.")
    args = parser.parse_args()
    if args.apply:
        parser.error("Старый --apply отключён. Используйте отдельный --apply-strict-safe после strict pre-flight.")
    if args.apply_strict_safe and (args.plan or args.dry_run):
        parser.error("--apply-strict-safe нельзя совмещать с --plan/--dry-run")
    db_path = args.db.expanduser().resolve()
    if not db_path.exists():
        parser.error(f"База не найдена: {db_path}")

    connection: sqlite3.Connection | None = None
    report: dict[str, Any] = {}
    try:
        connection = open_database(db_path)
        report = strict_scan(connection)
        report["database"] = str(db_path)
        report["mode"] = "dry-run"
        report["changes_applied"] = 0
        if not args.apply_strict_safe:
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                summarize_for_text(report)
            return 0

        # A second invocation after a successful cleanup is an intentional
        # no-op.  The 29 weak records remain unresolved, but no strict-safe
        # candidate may reappear.
        if int(report["strict_safe_count"]) == 0:
            enforce_strict_gate(report, allow_empty=True)
            report["mode"] = "apply-strict-safe-noop"
            report["applied_count"] = 0
            report["changes_applied"] = 0
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                summarize_for_text(report)
            return 0

        # First pre-flight: the reviewed numbers are an assertion, never a
        # selection shortcut.  Any drift stops before backup/transaction.
        enforce_strict_gate(report)
        connection.close()
        connection = None
        backup_path = backup_database(db_path)

        # Re-open after the backup and acquire the write lock before the final
        # strict scan.  A concurrent change therefore fails the gate and rolls
        # back without applying a partial candidate set.
        connection = open_database(db_path)
        connection.execute("BEGIN IMMEDIATE")
        locked_report = strict_scan(connection)
        locked_report["database"] = str(db_path)
        enforce_strict_gate(locked_report)
        enabled = outgoing_enabled_value(connection)
        if enabled != 0:
            raise StrictGateError(
                f"outgoing_enabled должен быть 0, фактически {enabled!r}", locked_report
            )
        before = pre_apply_snapshot(connection, locked_report)
        applied_candidates = list(locked_report["strict_safe_candidates"])
        for candidate in applied_candidates:
            reasons = strict_candidate_reasons(connection, candidate, locked_report)
            if reasons:
                raise StrictGateError(
                    "Candidate перестал проходить strict gate перед merge: "
                    f"{candidate['duplicate_supplier_id']} -> {candidate['canonical_supplier_id']}: "
                    + "; ".join(reasons), locked_report
                )
            merge_supplier_pair(
                connection,
                int(candidate["duplicate_supplier_id"]),
                int(candidate["canonical_supplier_id"]),
            )
        tx_validation = post_apply_validation(connection, before, locked_report)
        if not (
            tx_validation["duplicate_supplier_survivors"] == 0
            and all(value == 0 for value in tx_validation["relation_survivors"].values())
            and tx_validation["mail_history_preserved"]
            and tx_validation["operation_targets_preserved"]
            and tx_validation["campaign_targets_preserved"]
            and tx_validation["request_relations_preserved"]
            and tx_validation["protected_unresolved_ambiguous_unchanged"]
            and tx_validation["multi_site_7726347929_unchanged"]
            and tx_validation["integrity"]["ok"]
        ):
            raise RuntimeError(
                "Внутритранзакционная post-merge validation не прошла: "
                + json.dumps(tx_validation, ensure_ascii=False)
            )
        connection.commit()
        connection.close()
        connection = None

        # Validate the committed database from a fresh connection, then run a
        # fresh strict dry-run for idempotency evidence.
        connection = open_database(db_path)
        after = post_apply_validation(connection, before, locked_report)
        second = strict_scan(connection)
        applied_ids = {int(item["duplicate_supplier_id"]) for item in applied_candidates}
        relisted_applied = {
            int(item["duplicate_supplier_id"])
            for item in second["strict_safe_candidates"]
        } & applied_ids
        if relisted_applied:
            raise RuntimeError(
                "Idempotency failure: applied duplicate IDs reappeared as strict candidates: "
                + ", ".join(str(value) for value in sorted(relisted_applied))
            )
        report = {
            **locked_report,
            "mode": "apply-strict-safe",
            "backup": str(backup_path),
            "backup_integrity": "ok",
            "pre_apply": {
                "strict_safe_count": locked_report["strict_safe_count"],
                "strict_unresolved_count": locked_report["strict_unresolved_count"],
                "strict_ambiguous_count": locked_report["strict_ambiguous_count"],
                "outgoing_enabled": enabled,
            },
            "applied_count": len(applied_candidates),
            "applied_duplicate_ids": sorted(applied_ids),
            "relations_repointed": before["relation_counts"],
            "suppliers_before": before["supplier_count"],
            "suppliers_after": after["supplier_count"],
            "request_1059_before": before["request_1059"],
            "request_1059_after": after["request_1059"],
            "mail_data_before": {
                "messages": before["request_1059"]["mail"]["outbound_total"],
                **before["request_1059"]["mail"],
            },
            "mail_data_after": {
                "messages": after["request_1059"]["mail"]["outbound_total"],
                **after["request_1059"]["mail"],
            },
            "unresolved_before": len(locked_report["strict_unresolved"]),
            "unresolved_after": len(second["strict_unresolved"]),
            "ambiguous_before": len(locked_report["ambiguous"]),
            "ambiguous_after": len(second["ambiguous"]),
            "protected_identity_unchanged": after["protected_unresolved_ambiguous_unchanged"],
            "multi_site_7726347929": {
                "before": before["multi_site_7726347929"],
                "after": after["multi_site_7726347929"],
                "unchanged": after["multi_site_7726347929_unchanged"],
            },
            "post_merge_validation": after,
            "second_dry_run": {
                "strict_safe_count": second["strict_safe_count"],
                "strict_unresolved_count": second["strict_unresolved_count"],
                "strict_ambiguous_count": second["strict_ambiguous_count"],
                "broad_candidate_count": second["candidate_count"],
                "applied_candidates_relisted": sorted(relisted_applied),
            },
            "outgoing_enabled_after": outgoing_enabled_value(connection),
            "changes_applied": len(applied_candidates),
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            summarize_for_text(report)
        return 0
    except StrictGateError as exc:
        if connection is not None and connection.in_transaction:
            connection.rollback()
        report = {**exc.report, "mode": "strict-gate-stopped", "error": str(exc), "changes_applied": 0}
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            summarize_for_text(report)
        return 2
    except Exception as exc:
        if connection is not None and connection.in_transaction:
            connection.rollback()
        report = {**report, "mode": "not-applied", "error": str(exc), "changes_applied": 0}
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            summarize_for_text(report)
        return 3
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
