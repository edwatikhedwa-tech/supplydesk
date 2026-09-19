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
    """Existence check that NEVER raises a SQL error: on PostgreSQL a failed statement aborts the whole
    transaction ("current transaction is aborted"), so probing with try/except SELECT is not safe there.
    Used by the read-only dry-run on legacy SQLite databases that predate some tables."""
    if hasattr(connection, "raw"):  # PostgresConnection (mail/db_compat.py)
        row = connection.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?", (table,),
        ).fetchone()
    else:
        row = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


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


def find_merge_candidates(connection: Any, workspace_id: int) -> list[dict[str, Any]]:
    """READ-ONLY detection of suspected duplicate cards. Similarity NEVER decides anything: it only
    proposes a pair for a human. Two sources:
      * exact_email_hostless -- a card without a site whose address is the stored address of exactly one
        card that has a site (the historical shape of GAP-003);
      * name_similarity      -- an unconfirmed weak `name_token_similarity` evidence row points at the pair.
    Not proposed: one hostless card matching several site cards, and a hostless card that is already linked to
    a legal entity (INN) -- those need a separate, deliberate look (same rule as the legacy audit)."""
    shells = ""
    if _table_exists(connection, "supplier_merges"):
        shells = ("AND s.id NOT IN (SELECT merged_supplier_id FROM supplier_merges "
                  "WHERE workspace_id=s.workspace_id AND status='active')")
    rows = connection.execute(
        f"""SELECT d.id AS merged_id, s.id AS survivor_id
            FROM suppliers d
            JOIN suppliers s ON s.workspace_id=d.workspace_id AND s.id<>d.id AND LOWER(s.email)=LOWER(d.email)
            WHERE d.workspace_id=? AND COALESCE(d.host,'')='' AND COALESCE(d.email,'')<>'' AND COALESCE(s.host,'')<>''
              AND NOT EXISTS (SELECT 1 FROM global_supplier_links gl WHERE gl.supplier_id=d.id)
              {shells}""",
        (workspace_id,),
    ).fetchall()
    by_merged: dict[int, set[int]] = {}
    for r in rows:
        by_merged.setdefault(int(r["merged_id"]), set()).add(int(r["survivor_id"]))
    pairs: dict[tuple[int, int], set[str]] = {}
    for merged_id, survivors in by_merged.items():
        if len(survivors) == 1:
            pairs.setdefault((next(iter(survivors)), merged_id), set()).add("exact_email_hostless")
    if _table_exists(connection, "supplier_identity_evidence"):
        weak = connection.execute(
            """SELECT e.supplier_id AS survivor_id, d.id AS merged_id
               FROM supplier_identity_evidence e
               JOIN suppliers s ON s.id=e.supplier_id AND s.workspace_id=e.workspace_id
               JOIN suppliers d ON d.workspace_id=e.workspace_id AND d.id<>s.id AND LOWER(d.email)=e.value
               WHERE e.workspace_id=? AND e.kind='email' AND e.source_type='name_token_similarity' AND e.state='candidate'
                 AND COALESCE(s.host,'')<>'' AND COALESCE(d.host,'')=''""",
            (workspace_id,),
        ).fetchall()
        for r in weak:
            pairs.setdefault((int(r["survivor_id"]), int(r["merged_id"])), set()).add("name_similarity")
    return [{"survivor_supplier_id": a, "merged_supplier_id": b, "reason": "+".join(sorted(src))}
            for (a, b), src in sorted(pairs.items())]


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

    # ------------------------------------------------------------------ review workflow (EDW-21)
    def register_merge_candidates(self, workspace_id: int) -> dict[str, int]:
        """Put suspected duplicates into the review queue. Idempotent; changes no supplier data and never
        resurrects a rejected pair."""
        now = iso_now()
        with self.connect() as connection:
            found = find_merge_candidates(connection, workspace_id)
            for c in found:
                connection.execute(
                    """INSERT INTO supplier_merge_candidates(workspace_id, survivor_supplier_id, merged_supplier_id,
                                                             status, reason, detected_at)
                       VALUES (?, ?, ?, 'pending', ?, ?)
                       ON CONFLICT(workspace_id, survivor_supplier_id, merged_supplier_id) DO NOTHING""",
                    (workspace_id, c["survivor_supplier_id"], c["merged_supplier_id"], c["reason"], now),
                )
            total = connection.execute(
                "SELECT COUNT(*) AS n FROM supplier_merge_candidates WHERE workspace_id=?", (workspace_id,)).fetchone()["n"]
        return {"detected": len(found), "in_queue": int(total)}

    def list_merge_candidates(self, workspace_id: int, *, status: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT c.id, c.status, c.reason, c.detected_at, c.decided_at, c.merge_id,
                        c.survivor_supplier_id, c.merged_supplier_id,
                        s.name AS survivor_name, s.host AS survivor_host, d.name AS merged_name
                 FROM supplier_merge_candidates c
                 JOIN suppliers s ON s.id=c.survivor_supplier_id JOIN suppliers d ON d.id=c.merged_supplier_id
                 WHERE c.workspace_id=?"""
        params: list[Any] = [workspace_id]
        if status:
            sql += " AND c.status=?"
            params.append(status)
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(sql + " ORDER BY c.id", params).fetchall()]

    def _card_view(self, connection: Any, workspace_id: int, supplier_id: int) -> dict[str, Any]:
        card = dict(connection.execute(
            "SELECT id, name, host, external_key, email FROM suppliers WHERE id=? AND workspace_id=?",
            (supplier_id, workspace_id)).fetchone())
        prof = connection.execute("SELECT COALESCE(inn,'') AS inn FROM supplier_profiles WHERE supplier_id=?", (supplier_id,)).fetchone()
        link = connection.execute("SELECT global_supplier_id FROM global_supplier_links WHERE supplier_id=?", (supplier_id,)).fetchone()
        card["inn"] = prof["inn"] if prof else ""
        card["global_supplier_id"] = link["global_supplier_id"] if link else None
        card["domains"] = [card["host"]] if card["host"] else []
        card["requests"] = [dict(r) for r in connection.execute(
            """SELECT r.id, r.name FROM request_suppliers rs JOIN requests r ON r.id=rs.request_id
               WHERE rs.supplier_id=? AND r.workspace_id=? ORDER BY r.id""", (supplier_id, workspace_id)).fetchall()]
        card["messages"] = {
            r["direction"]: int(r["n"]) for r in connection.execute(
                "SELECT direction, COUNT(*) AS n FROM mail_messages WHERE supplier_id=? AND workspace_id=? GROUP BY direction",
                (supplier_id, workspace_id)).fetchall()}
        card["recent_messages"] = [dict(r) for r in connection.execute(
            """SELECT direction, created_at, subject, from_email, to_email FROM mail_messages
               WHERE supplier_id=? AND workspace_id=? ORDER BY created_at DESC, id DESC LIMIT 5""",
            (supplier_id, workspace_id)).fetchall()]
        card["evidence"] = [dict(r) for r in connection.execute(
            """SELECT value AS email, source_type, assertion, strength, state, request_id, occurred_at
               FROM supplier_identity_evidence WHERE workspace_id=? AND supplier_id=? AND kind='email' ORDER BY id""",
            (workspace_id, supplier_id)).fetchall()]
        return card

    _CANDIDATE_REASONS = {
        "exact_email_hostless": "Карточка без сайта имеет тот же адрес, что сохранён у карточки с сайтом.",
        "name_similarity": "Имя ящика похоже на название сайта (слабый признак, сам ничего не доказывает).",
    }

    def get_merge_review(self, workspace_id: int, candidate_id: int) -> dict[str, Any]:
        """Everything the owner needs to decide, read-only: both cards (INN, domains, emails, requests,
        correspondence, evidence), why they were proposed, what a merge would transfer, and that it is
        reversible."""
        with self.connect() as connection:
            cand = connection.execute(
                "SELECT * FROM supplier_merge_candidates WHERE id=? AND workspace_id=?", (candidate_id, workspace_id)).fetchone()
            if not cand:
                raise ValueError("Кандидат на объединение не найден в текущем рабочем пространстве.")
            a, b = int(cand["survivor_supplier_id"]), int(cand["merged_supplier_id"])
            survivor = self._card_view(connection, workspace_id, a)
            merged = self._card_view(connection, workspace_id, b)
            verdict = merge_verdict(survivor["inn"], merged["inn"])
            return {
                "candidate": {k: cand[k] for k in ("id", "status", "reason", "detected_at", "decided_at", "merge_id")},
                "survivor": survivor,
                "merged": merged,
                "why": [self._CANDIDATE_REASONS.get(r, r) for r in str(cand["reason"]).split("+")],
                "inn_verdict": verdict,
                "can_merge": verdict != "conflict",
                "needs_explicit_confirmation": verdict == "unknown",
                "blocked_reason": "Разные подтверждённые ИНН: объединение запрещено." if verdict == "conflict" else "",
                "will_transfer": merge_plan(connection, a, b),
                "after_merge": ("Заявки, переписка и evidence объединённой карточки перейдут к выжившей; "
                                "адрес объединённой карточки станет подтверждённым контактом выжившей."),
                "reversible": True,
                "how_to_undo": "decision='undo' возвращает все строки из журнала объединения.",
            }

    def decide_merge_candidate(
        self, workspace_id: int, user_id: int, candidate_id: int, decision: str, *, confirm_unknown_inn: bool = False,
    ) -> dict[str, Any]:
        """merge | reject | later | undo. Owner only (merging changes the whole workspace's data)."""
        if decision not in ("merge", "reject", "later", "undo"):
            raise ValueError("Допустимые решения: merge, reject, later, undo.")
        if not self.is_workspace_owner(user_id, workspace_id):
            raise ValueError("Решение об объединении может принять только владелец рабочего пространства.")
        with self.connect() as connection:
            cand = connection.execute(
                "SELECT * FROM supplier_merge_candidates WHERE id=? AND workspace_id=?", (candidate_id, workspace_id)).fetchone()
        if not cand:
            raise ValueError("Кандидат на объединение не найден в текущем рабочем пространстве.")
        status = cand["status"]
        result: dict[str, Any] = {"candidate_id": candidate_id}
        if decision == "merge":
            if status not in ("pending", "later"):
                raise ValueError("Это объединение уже решено.")
            merged = self.merge_suppliers(
                workspace_id, user_id, int(cand["survivor_supplier_id"]), int(cand["merged_supplier_id"]),
                reason=f"review:{cand['reason']}", confirm_unknown_inn=confirm_unknown_inn)
            new_status, merge_id = "merged", merged["merge_id"]
            result.update(merged)
        elif decision == "undo":
            if status != "merged" or cand["merge_id"] is None:
                raise ValueError("Отменять нечего: объединение не выполнено.")
            result.update(self.unmerge_supplier(workspace_id, user_id, int(cand["merge_id"])))
            new_status, merge_id = "pending", None
        else:
            if status == "merged":
                raise ValueError("Объединение выполнено: сначала отмените его (undo).")
            new_status, merge_id = ("rejected" if decision == "reject" else "later"), cand["merge_id"]
        with self.connect() as connection:
            connection.execute(
                """UPDATE supplier_merge_candidates SET status=?, decided_by_user_id=?, decided_at=?, merge_id=?
                   WHERE id=? AND workspace_id=?""",
                (new_status, user_id, iso_now(), merge_id, candidate_id, workspace_id))
            self._audit_connection(connection, workspace_id, user_id, f"supplier.merge_candidate.{decision}",
                                   "supplier_merge_candidate", str(candidate_id), {"status": new_status})
        result["status"] = new_status
        return result

    def list_supplier_merges(self, workspace_id: int, *, status: str | None = None) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM supplier_merges WHERE workspace_id=?", [workspace_id]
        if status:
            sql += " AND status=?"
            params.append(status)
        with self.connect() as connection:
            return [dict(r) for r in connection.execute(sql + " ORDER BY id", params).fetchall()]
