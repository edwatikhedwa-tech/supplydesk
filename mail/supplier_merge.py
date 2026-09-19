"""Reversible supplier merge / unmerge (EDW-16, Documentation Pack V1.2.5).

Two supplier cards of ONE workspace that turned out to be one company are merged into a
survivor. Nothing is lost: every re-pointed row and every row set aside (because the survivor
already had the same fact) is written to `supplier_merge_moves`, so `unmerge_supplier` restores the
exact previous state. The merged card stays as a hidden shell; `_follow_merge` redirects its
external_key / email to the survivor so it can never be resurrected as a second identity.

Guards: same workspace only (tenant boundary); different confirmed INNs can never be merged (not
even with a manual override, `merge_guard`); an unknown INN on either side needs an explicit user
confirmation (`confirm_unknown_inn`). Contact intelligence is recomputed through the single
projection (`sync_contact_intelligence_for_supplier`) after both merge and unmerge.
"""

from __future__ import annotations

import json
from typing import Any

from backend.domain.supplier_identity.merge_guard import merge_verdict

from .supplier_identity_evidence import is_contactable_person_address
from .time_utils import iso_now

# Every table with a FOREIGN KEY to suppliers(id) or a supplier_id that means suppliers.id.
# (`tasks.supplier_id` is a GLOBAL supplier id and is intentionally not here.)
# id_col=None -> the row is identified by `conflict` columns + supplier_id (natural key).
# conflict -> columns that, together with supplier_id, are unique: the survivor already having such a
#             row means the merged card's row is set aside (snapshotted), not duplicated.
# Order matters: mail_threads first (re-parents messages), mail_messages after it.
_TABLES: list[dict[str, Any]] = [
    {"table": "mail_threads", "id_col": "id", "conflict": ["workspace_id", "request_id"], "hook": "thread"},
    {"table": "mail_messages", "id_col": "id", "conflict": None},
    {"table": "request_suppliers", "id_col": None, "conflict": ["request_id"]},
    {"table": "request_supplier_states", "id_col": None, "conflict": ["request_id"], "hook": "state"},
    {"table": "request_supplier_ratings", "id_col": None, "conflict": ["request_id"]},
    {"table": "search_result_sources", "id_col": None, "conflict": ["request_id", "position_key"]},
    {"table": "mail_thread_user_metadata", "id_col": None, "conflict": ["workspace_id", "user_id", "request_id"]},
    {"table": "mail_thread_notes", "id_col": None, "conflict": ["workspace_id", "user_id", "request_id"]},
    {"table": "mail_thread_status", "id_col": None, "conflict": ["workspace_id", "user_id", "request_id"]},
    {"table": "mail_thread_workspace_notes", "id_col": None, "conflict": ["workspace_id", "request_id"]},
    {"table": "supplier_profiles", "id_col": None, "conflict": []},
    {"table": "global_supplier_links", "id_col": None, "conflict": []},
    {"table": "supplier_inn_sources", "id_col": None, "conflict": []},
    {"table": "supplier_evidence", "id_col": "id", "conflict": ["field_name", "field_value", "source_type", "source_url"]},
    {"table": "supplier_identity_evidence", "id_col": "id",
     "conflict": ["workspace_id", "kind", "value", "source_type", "source_id"]},
    {"table": "workspace_supplier_contact_events", "id_col": "id", "conflict": None},
    {"table": "mail_send_operation_targets", "id_col": "id", "conflict": None},
    {"table": "mail_campaign_targets", "id_col": "id", "conflict": None},
    {"table": "mail_cross_provider_retries", "id_col": "id", "conflict": None},
    {"table": "mail_inbox_request_links", "id_col": "id", "conflict": None},
    {"table": "mail_delivery_resolutions", "id_col": "id", "conflict": None},
    {"table": "mail_reconciled_outbound_events", "id_col": "id", "conflict": None},
    {"table": "logistics_quotes", "id_col": "id", "conflict": None},
    {"table": "blacklist_entries", "id_col": "id", "conflict": None},
]

_STATE_RANK = {"replied": 3, "sent": 2, "sending": 2, "queued": 1}


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _table_exists(connection: Any, table: str) -> bool:
    try:
        connection.execute(f"SELECT 1 FROM {table} LIMIT 1")
        return True
    except Exception:  # noqa: BLE001 - older schema without the table (read-only dry-run on a legacy DB)
        return False


def merge_plan(connection: Any, survivor_id: int, merged_id: int) -> dict[str, dict[str, int]]:
    """READ-ONLY preview of what `merge_suppliers` would do, per table: rows re-pointed vs set aside
    because the survivor already has the same fact. Writes nothing (safe on a read-only connection)."""
    plan: dict[str, dict[str, int]] = {}
    for spec in _TABLES:
        table, conflict = spec["table"], spec["conflict"]
        if not _table_exists(connection, table):
            continue
        moved = aside = 0
        for row in connection.execute(f"SELECT * FROM {table} WHERE supplier_id=?", (merged_id,)).fetchall():
            row = dict(row)
            clash = False
            if conflict is not None:
                cond = " AND ".join(f"{c}=?" for c in conflict)
                sql = f"SELECT 1 FROM {table} WHERE supplier_id=?" + (f" AND {cond}" if cond else "")
                clash = connection.execute(sql, (survivor_id, *[row[c] for c in conflict])).fetchone() is not None
            aside += 1 if clash else 0
            moved += 0 if clash else 1
        if moved or aside:
            plan[table] = {"would_move": moved, "would_set_aside": aside}
    return plan


class SupplierMergeMixin:
    # ------------------------------------------------------------------ alias
    def _follow_merge(self, connection: Any, workspace_id: int, supplier_id: int) -> int:
        """Survivor id if this card was merged away (follows chains); else the id itself."""
        current = int(supplier_id)
        for _ in range(10):
            row = connection.execute(
                """SELECT survivor_supplier_id FROM supplier_merges
                   WHERE workspace_id=? AND merged_supplier_id=? AND status='active'""",
                (workspace_id, current),
            ).fetchone()
            if not row:
                return current
            current = int(row["survivor_supplier_id"])
        return current

    # ------------------------------------------------------------------ ledger helpers
    def _merge_log(self, connection: Any, merge_id: int, seq: list[int], **fields: Any) -> None:
        seq[0] += 1
        connection.execute(
            """INSERT INTO supplier_merge_moves(merge_id, seq, table_name, op, key_json, column_name,
                                                old_value, new_value, row_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (merge_id, seq[0], fields["table"], fields["op"], _j(fields.get("key", {})),
             fields.get("column", ""), _j(fields.get("old")) if "old" in fields else None,
             _j(fields.get("new")) if "new" in fields else None, _j(fields["row"]) if "row" in fields else ""),
        )

    def _merge_update(self, connection: Any, merge_id: int, seq: list[int], table: str, key: dict[str, Any],
                      column: str, old: Any, new: Any) -> None:
        where = " AND ".join(f"{c}=?" for c in key)
        connection.execute(f"UPDATE {table} SET {column}=? WHERE {where}", (new, *key.values()))
        self._merge_log(connection, merge_id, seq, table=table, op="update", key=key, column=column, old=old, new=new)

    def _merge_set_aside(self, connection: Any, merge_id: int, seq: list[int], table: str, row: dict[str, Any],
                         where: dict[str, Any]) -> None:
        self._merge_log(connection, merge_id, seq, table=table, op="delete", key=where, row=row)
        connection.execute(f"DELETE FROM {table} WHERE " + " AND ".join(f"{c}=?" for c in where), tuple(where.values()))

    # ------------------------------------------------------------------ merge
    def merge_suppliers(
        self, workspace_id: int, user_id: int, survivor_id: int, merged_id: int, *,
        reason: str = "", confirm_unknown_inn: bool = False,
    ) -> dict[str, Any]:
        survivor_id, merged_id = int(survivor_id), int(merged_id)
        if survivor_id == merged_id:
            raise ValueError("Нельзя объединить поставщика с самим собой.")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cards = {int(r["id"]): r for r in connection.execute(
                "SELECT id, external_key, email FROM suppliers WHERE workspace_id=? AND id IN (?, ?)",
                (workspace_id, survivor_id, merged_id)).fetchall()}
            if len(cards) != 2:
                raise ValueError("Оба поставщика должны принадлежать текущему рабочему пространству.")
            for sid in (survivor_id, merged_id):
                if connection.execute(
                    "SELECT 1 FROM supplier_merges WHERE workspace_id=? AND merged_supplier_id=? AND status='active'",
                    (workspace_id, sid)).fetchone():
                    raise ValueError("Один из поставщиков уже объединён с другим.")
            inns = {}
            for sid in (survivor_id, merged_id):
                row = connection.execute("SELECT COALESCE(inn,'') AS inn FROM supplier_profiles WHERE supplier_id=?", (sid,)).fetchone()
                inns[sid] = row["inn"] if row else ""
            verdict = merge_verdict(inns[survivor_id], inns[merged_id])
            if verdict == "conflict":
                raise ValueError("Разные подтверждённые ИНН: объединение запрещено.")
            if verdict == "unknown" and not confirm_unknown_inn:
                raise ValueError("ИНН не подтверждён у одного из поставщиков: нужно явное подтверждение пользователя.")
            globals_ = {int(r["supplier_id"]): r["global_supplier_id"] for r in connection.execute(
                "SELECT supplier_id, global_supplier_id FROM global_supplier_links WHERE supplier_id IN (?, ?)",
                (survivor_id, merged_id)).fetchall()}
            if len(globals_) == 2 and len(set(globals_.values())) == 2:
                raise ValueError("Поставщики привязаны к разным юридическим лицам: объединение запрещено.")

            now = iso_now()
            connection.execute(
                """INSERT INTO supplier_merges(workspace_id, survivor_supplier_id, merged_supplier_id, status, reason,
                                               inn_verdict, merged_by_user_id, merged_at)
                   VALUES (?, ?, ?, 'active', ?, ?, ?, ?)""",
                (workspace_id, survivor_id, merged_id, str(reason or "")[:300], verdict, user_id, now),
            )
            merge_id = int(connection.execute(
                "SELECT id FROM supplier_merges WHERE workspace_id=? AND merged_supplier_id=? AND status='active'",
                (workspace_id, merged_id)).fetchone()["id"])
            seq = [0]
            stats = {"moved": 0, "set_aside": 0}
            for spec in _TABLES:
                self._merge_table(connection, merge_id, seq, spec, survivor_id, merged_id, stats)
            # The user decided the two cards are one company: the merged card's own address is now a
            # confirmed contact of the survivor (recorded as a ledger 'insert' so unmerge removes it).
            merged_email = str(cards[merged_id]["email"] or "").strip().lower()
            if is_contactable_person_address(merged_email):
                fact = (workspace_id, survivor_id, "email", merged_email, "manual_confirmed", f"merge:{merge_id}")
                if not connection.execute(
                    """SELECT 1 FROM supplier_identity_evidence WHERE workspace_id=? AND supplier_id=? AND kind=? AND value=?
                       AND source_type=? AND source_id=?""", fact).fetchone():
                    self._record_identity_evidence(
                        connection, workspace_id=workspace_id, supplier_id=survivor_id, kind="email", value=merged_email,
                        source_type="manual_confirmed", source_id=f"merge:{merge_id}", decided_by_user_id=user_id,
                        reason="Адрес объединённой карточки поставщика.")
                    new_id = connection.execute(
                        """SELECT id FROM supplier_identity_evidence WHERE workspace_id=? AND supplier_id=? AND kind=? AND value=?
                           AND source_type=? AND source_id=?""", fact).fetchone()["id"]
                    self._merge_log(connection, merge_id, seq, table="supplier_identity_evidence", op="insert", key={"id": new_id})
            conflicts = {"moved_rows": stats["moved"], "set_aside_rows": stats["set_aside"]}
            connection.execute("UPDATE supplier_merges SET conflicts_json=? WHERE id=?", (_j(conflicts), merge_id))
            self.sync_contact_intelligence_for_supplier(connection, workspace_id, survivor_id)
            self._audit_connection(connection, workspace_id, user_id, "supplier.merged", "supplier", str(survivor_id),
                                   {"merge_id": merge_id, "merged_supplier_id": merged_id, "verdict": verdict, **conflicts})
            connection.commit()
        return {"merge_id": merge_id, "survivor_supplier_id": survivor_id, "merged_supplier_id": merged_id,
                "inn_verdict": verdict, **conflicts}

    def _merge_table(self, connection: Any, merge_id: int, seq: list[int], spec: dict[str, Any],
                     survivor_id: int, merged_id: int, stats: dict[str, int]) -> None:
        table, id_col, conflict = spec["table"], spec["id_col"], spec["conflict"]
        rows = [dict(r) for r in connection.execute(f"SELECT * FROM {table} WHERE supplier_id=?", (merged_id,)).fetchall()]
        for row in rows:
            identity = {id_col: row[id_col]} if id_col else {**{c: row[c] for c in (conflict or [])}, "supplier_id": merged_id}
            clash = None
            if conflict is not None:
                cond = " AND ".join(f"{c}=?" for c in conflict)
                sql = f"SELECT * FROM {table} WHERE supplier_id=?" + (f" AND {cond}" if cond else "")
                found = connection.execute(sql, (survivor_id, *[row[c] for c in conflict])).fetchone()
                clash = dict(found) if found else None
            if clash is not None:
                hook = spec.get("hook")
                if hook == "thread":
                    for m in connection.execute("SELECT id FROM mail_messages WHERE thread_id=?", (row["id"],)).fetchall():
                        self._merge_update(connection, merge_id, seq, "mail_messages", {"id": m["id"]}, "thread_id", row["id"], clash["id"])
                    newest = max(str(row.get("last_message_at") or ""), str(clash.get("last_message_at") or "")) or None
                    if newest and newest != (clash.get("last_message_at") or ""):
                        self._merge_update(connection, merge_id, seq, "mail_threads", {"id": clash["id"]},
                                           "last_message_at", clash.get("last_message_at"), newest)
                elif hook == "state" and _STATE_RANK.get(row["status"], 0) > _STATE_RANK.get(clash["status"], 0):
                    survivor_key = {"request_id": clash["request_id"], "supplier_id": survivor_id}
                    for col in ("status", "last_message_id", "mail_account_id"):
                        self._merge_update(connection, merge_id, seq, table, survivor_key, col, clash[col], row[col])
                self._merge_set_aside(connection, merge_id, seq, table, row, identity)
                stats["set_aside"] += 1
            else:
                self._merge_update(connection, merge_id, seq, table, identity, "supplier_id", merged_id, survivor_id)
                stats["moved"] += 1

    # ------------------------------------------------------------------ unmerge
    def unmerge_supplier(self, workspace_id: int, user_id: int, merge_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            merge = connection.execute(
                "SELECT * FROM supplier_merges WHERE id=? AND workspace_id=?", (merge_id, workspace_id)).fetchone()
            if not merge:
                raise ValueError("Объединение не найдено в текущем рабочем пространстве.")
            if merge["status"] != "active":
                raise ValueError("Объединение уже отменено.")
            if connection.execute(
                "SELECT 1 FROM supplier_merges WHERE workspace_id=? AND merged_supplier_id=? AND status='active'",
                (workspace_id, merge["survivor_supplier_id"])).fetchone():
                raise ValueError("Сначала отмените более позднее объединение, в которое вошёл этот поставщик.")
            survivor_id, merged_id = int(merge["survivor_supplier_id"]), int(merge["merged_supplier_id"])
            moves = connection.execute(
                "SELECT * FROM supplier_merge_moves WHERE merge_id=? ORDER BY seq DESC", (merge_id,)).fetchall()
            restored = diverged = 0
            for mv in moves:
                table, key = mv["table_name"], json.loads(mv["key_json"] or "{}")
                if mv["op"] == "update":
                    old, new = json.loads(mv["old_value"]), json.loads(mv["new_value"])
                    where_key = dict(key)
                    if mv["column_name"] == "supplier_id" and "supplier_id" in where_key:
                        where_key["supplier_id"] = new      # natural-key row: it now lives under the survivor
                    cond = " AND ".join(f"{c}=?" for c in where_key)
                    done = connection.execute(
                        f"UPDATE {table} SET {mv['column_name']}=? WHERE {cond} AND {mv['column_name']}=?",
                        (old, *where_key.values(), new)).rowcount
                elif mv["op"] == "insert":
                    done = connection.execute(
                        f"DELETE FROM {table} WHERE " + " AND ".join(f"{c}=?" for c in key), tuple(key.values())).rowcount
                else:
                    row = json.loads(mv["row_json"])
                    cols = list(row)
                    exists = connection.execute(
                        f"SELECT 1 FROM {table} WHERE " + " AND ".join(f"{c}=?" for c in key), tuple(key.values())).fetchone()
                    done = 0
                    if not exists:
                        connection.execute(
                            f"INSERT INTO {table}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                            tuple(row[c] for c in cols))
                        done = 1
                restored += 1 if done else 0
                diverged += 0 if done else 1
            now = iso_now()
            connection.execute(
                "UPDATE supplier_merges SET status='reverted', reverted_by_user_id=?, reverted_at=? WHERE id=?",
                (user_id, now, merge_id))
            self.sync_contact_intelligence_for_supplier(connection, workspace_id, survivor_id)
            self.sync_contact_intelligence_for_supplier(connection, workspace_id, merged_id)
            self._audit_connection(connection, workspace_id, user_id, "supplier.unmerged", "supplier", str(survivor_id),
                                   {"merge_id": merge_id, "restored": restored, "diverged": diverged})
            connection.commit()
        return {"merge_id": merge_id, "restored": restored, "diverged": diverged,
                "survivor_supplier_id": survivor_id, "merged_supplier_id": merged_id}

    def preview_merge_suppliers(self, workspace_id: int, survivor_id: int, merged_id: int) -> dict[str, Any]:
        """Dry-run of a merge: verdict + per-table plan. Changes nothing."""
        with self.connect() as connection:
            ids = {int(r["id"]) for r in connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id=? AND id IN (?, ?)", (workspace_id, survivor_id, merged_id)).fetchall()}
            if ids != {int(survivor_id), int(merged_id)}:
                raise ValueError("Оба поставщика должны принадлежать текущему рабочему пространству.")
            inns = [(connection.execute("SELECT COALESCE(inn,'') AS inn FROM supplier_profiles WHERE supplier_id=?", (sid,)).fetchone() or {"inn": ""})["inn"]
                    for sid in (survivor_id, merged_id)]
            return {"inn_verdict": merge_verdict(inns[0], inns[1]), "plan": merge_plan(connection, int(survivor_id), int(merged_id))}

    def list_supplier_merges(self, workspace_id: int, *, status: str | None = None) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM supplier_merges WHERE workspace_id=?", [workspace_id]
        if status:
            sql += " AND status=?"
            params.append(status)
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(sql + " ORDER BY id", params).fetchall()]
