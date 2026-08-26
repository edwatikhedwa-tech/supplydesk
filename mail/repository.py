from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .auth import hash_password, new_token, token_hash
from .bounce import classify_bounce
from .content import (
    clean_email_text,
    collapse_quoted_html,
    collapse_quoted_text,
    email_has_remote_images,
    sanitize_email_html,
)


_MAIL_STATUS_LABELS = {
    "not_sent": "not_sent",
    "queued": "sent",     # in the outbound queue — from the user's view, already "sent"
    "sending": "sent",
    "sent": "waiting",    # delivered by us, no reply yet — waiting for the supplier
    "replied": "answered",
    "failed": "error",
}


def _normalize_mail_status(raw: str | None) -> str:
    """request_supplier_states.status is an internal send-pipeline state machine
    (queued/sending/sent/failed/replied) — not the user-facing vocabulary
    (not_sent/sent/waiting/answered/error). Every place that surfaces a
    supplier's mail status to the API/UI must go through this."""
    return _MAIL_STATUS_LABELS.get(raw or "not_sent", "not_sent")


def _readable_message(row: dict[str, Any]) -> dict[str, Any]:
    """Attach both renderings of a message: sanitized HTML and a plain-text fallback.

    Quote-folding runs strictly after sanitization — it only ever wraps chunks
    that already passed the allowlist, never raw sender content.
    """
    raw_html = row.get("body_html")
    safe_html = sanitize_email_html(raw_html)
    return {
        **row,
        "body_text": collapse_quoted_text(clean_email_text(row.get("body_text"), raw_html)),
        "body_html": collapse_quoted_html(safe_html),
        "has_remote_images": email_has_remote_images(raw_html),
    }


UTC = timezone.utc


class ManagedConnection(sqlite3.Connection):
    """Close every per-operation SQLite handle, including on Windows."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class CompatRow(dict):
    """Mapping row that also supports SQLite-style numeric indexes."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _postgres_row_factory(cursor: Any):
    columns = [column.name for column in (cursor.description or [])]

    def make_row(values: tuple[Any, ...]) -> CompatRow:
        return CompatRow(zip(columns, values))

    return make_row


def _adapt_postgres_sql(sql: str) -> str:
    """Translate the small SQLite dialect surface used by this repository."""
    adapted = sql.replace("BEGIN IMMEDIATE", "BEGIN")
    adapted = adapted.replace("last_insert_rowid()", "LASTVAL()")
    was_insert_or_ignore = bool(re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO", adapted, flags=re.IGNORECASE))
    adapted = re.sub(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", adapted, count=1, flags=re.IGNORECASE)
    if was_insert_or_ignore and "ON CONFLICT" not in adapted.upper() and "requests(id, workspace_id" in adapted:
        adapted = adapted.rstrip() + " ON CONFLICT DO NOTHING"
    return adapted.replace("?", "%s")


class PostgresCursor:
    def __init__(self, cursor: Any, connection: Any) -> None:
        self._cursor = cursor
        self._connection = connection

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    @property
    def lastrowid(self) -> int:
        row = self._connection.execute("SELECT LASTVAL()").fetchone()
        return int(row[0])


class PostgresConnection:
    """Small DB-API compatibility layer for the existing SQLite repository."""

    def __init__(self, raw_connection: Any) -> None:
        self.raw = raw_connection

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        try:
            if exc_type:
                self.raw.rollback()
            else:
                self.raw.commit()
        finally:
            self.raw.close()

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> PostgresCursor:
        params = tuple(parameters)
        cursor = self.raw.execute(_adapt_postgres_sql(sql), params)
        return PostgresCursor(cursor, self)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()


def _postgres_migration_sql(script: str) -> str:
    script = re.sub(r"^\s*PRAGMA[^;]+;", "", script, flags=re.IGNORECASE | re.MULTILINE)
    script = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", script, flags=re.IGNORECASE)
    return re.sub(r"\bBLOB\b", "BYTEA", script, flags=re.IGNORECASE)


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


def iso_after(seconds: int) -> str:
    return (utc_now() + timedelta(seconds=seconds)).isoformat()


class MailRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.db_path = Path(db_path).expanduser().resolve()
        if not self.database_url:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
        self.migration_paths = sorted(migrations_dir.glob("*.sql"))
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection | PostgresConnection:
        if self.database_url:
            try:
                import psycopg
            except ImportError as exc:  # pragma: no cover - exercised only in a misconfigured deployment
                raise RuntimeError("DATABASE_URL настроен, но пакет psycopg не установлен.") from exc
            return PostgresConnection(psycopg.connect(self.database_url, row_factory=_postgres_row_factory, autocommit=False))
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None, factory=ManagedConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def ensure_schema(self) -> None:
        with self.connect() as connection:
            for migration_path in self.migration_paths:
                migration = migration_path.read_text(encoding="utf-8")
                if self.database_url:
                    migration = _postgres_migration_sql(migration)
                connection.executescript(migration)
            # A process can stop after claiming a job. Recover it on restart instead of leaving it in "sending" forever.
            connection.execute(
                "UPDATE mail_jobs SET status='queued', next_attempt_at=?, last_error='Предыдущий процесс остановился во время отправки.', updated_at=? WHERE status='sending'",
                (iso_now(), iso_now()),
            )
            connection.execute(
                "UPDATE mail_messages SET status='queued', error='Предыдущий процесс остановился во время отправки.' WHERE status='sending'"
            )
            connection.execute(
                "UPDATE request_supplier_states SET status='queued', last_error='Предыдущий процесс остановился во время отправки.', updated_at=? WHERE status='sending'",
                (iso_now(),),
            )
            # A заявка's search runs on a background thread with no persistent
            # queue behind it (see SupplierApp.start_search) — if the process
            # is killed mid-search (crash, redeploy, `taskkill`), the thread
            # dies with it and nothing ever calls complete_request_search().
            # Left alone that заявка shows "Идёт поиск" forever. Recover it the
            # same way mail_jobs recovers above: surface it as a real error
            # instead of a silent infinite spinner.
            connection.execute(
                "UPDATE request_meta SET status='error', last_error='Поиск прерван перезапуском сервера. Запустите поиск заново.', updated_at=? WHERE status='searching'",
                (iso_now(),),
            )

    def seed_fixture_catalog(self, workspace_id: int, fixture: dict[str, Any]) -> None:
        """Persist the existing result fixture so dashboard views use real workspace data."""
        now = iso_now()
        positions = fixture.get("positions") or []
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO request_meta(request_id, status, search_progress, search_total, updated_at) VALUES (1043, 'completed', ?, ?, ?) ON CONFLICT(request_id) DO UPDATE SET status='completed', search_progress=excluded.search_progress, search_total=excluded.search_total, updated_at=excluded.updated_at",
                (len(positions), len(positions), now),
            )
            for position in positions:
                key = str(position.get("id") or "").strip()
                name = str(position.get("name") or "").strip()
                if not key or not name:
                    continue
                connection.execute(
                    "INSERT INTO request_positions(request_id, position_key, name, quantity, created_at) VALUES (1043, ?, ?, ?, ?) ON CONFLICT(request_id, position_key) DO UPDATE SET name=excluded.name, quantity=excluded.quantity",
                    (key, name, str(position.get("qty") or ""), now),
                )
            for item in fixture.get("suppliers") or []:
                host = str(item.get("host") or "").strip().lower()
                emails = item.get("emails") or []
                email = str(emails[0].get("e") if emails else "").strip().lower()
                if not host or not email:
                    continue
                registration = item.get("reg") or {}
                name = str(registration.get("name") or item.get("title") or host).strip()[:240]
                connection.execute(
                    "INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(workspace_id, external_key) DO UPDATE SET name=excluded.name, email=excluded.email, host=excluded.host, updated_at=excluded.updated_at",
                    (workspace_id, host, name, email, host, now, now),
                )
                supplier_id = int(connection.execute("SELECT id FROM suppliers WHERE workspace_id=? AND external_key=?", (workspace_id, host)).fetchone()[0])
                phones = registration.get("phones") or []
                connection.execute(
                    "INSERT INTO supplier_profiles(supplier_id, inn, kind, region, role, phone, reason, source, covers_json, site_unavailable, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(supplier_id) DO UPDATE SET inn=excluded.inn, kind=excluded.kind, region=excluded.region, role=excluded.role, phone=excluded.phone, reason=excluded.reason, source=excluded.source, covers_json=excluded.covers_json, site_unavailable=excluded.site_unavailable, updated_at=excluded.updated_at",
                    (supplier_id, str(item.get("inn") or ""), str(item.get("kind") or ""), str(item.get("region") or registration.get("region") or ""), str(registration.get("role") or ""), str(phones[0] if phones else ""), str(item.get("snippet") or "Компания найдена в поисковой выдаче по позициям заявки.")[:500], "xmlriver-fixture", json.dumps(item.get("covers") or [], ensure_ascii=False), int(bool(item.get("web"))), now),
                )
                connection.execute(
                    "INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) VALUES (1043, ?, ?, ?, ?, ?) ON CONFLICT(request_id, supplier_id) DO UPDATE SET position_keys_json=excluded.position_keys_json, reason=excluded.reason, source=excluded.source, updated_at=excluded.updated_at",
                    (supplier_id, json.dumps(item.get("covers") or [], ensure_ascii=False), str(item.get("snippet") or "Компания найдена в поисковой выдаче по позициям заявки.")[:500], "xmlriver-fixture", now),
                )

    # Shared by list_requests() and get_request() — a bare `SELECT * FROM requests`
    # (as get_request() used to do) is missing every computed/joined field
    # RequestListItem expects (status, search_progress, positions_count, ...),
    # which rendered as blank/undefined on the request detail page (e.g. the
    # "N позиций" fact and the workflow-step highlight both went silently empty).
    _REQUEST_SELECT_COLUMNS = """r.id, r.name, r.description, r.sender_name, r.company_name, r.created_at,
                          COALESCE(d.deadline, '') AS deadline,
                          COALESCE(m.status, 'draft') AS status, COALESCE(m.search_progress, 0) AS search_progress,
                          COALESCE(m.search_total, 0) AS search_total, m.last_error, m.updated_at,
                          (SELECT COUNT(*) FROM request_positions p WHERE p.request_id=r.id) AS positions_count,
                          (SELECT COUNT(*) FROM request_suppliers rs WHERE rs.request_id=r.id AND rs.is_irrelevant=0) AS suppliers_count,
                          (SELECT COUNT(*) FROM mail_messages mm WHERE mm.request_id=r.id AND mm.direction='outbound' AND mm.status='sent') AS sent_count,
                          (SELECT COUNT(*) FROM mail_messages mm WHERE mm.request_id=r.id AND mm.direction='inbound') AS replies_count"""
    _REQUEST_SELECT_JOIN = "LEFT JOIN request_meta m ON m.request_id=r.id LEFT JOIN request_details d ON d.request_id=r.id"

    def list_requests(self, workspace_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT {self._REQUEST_SELECT_COLUMNS}
                   FROM requests r {self._REQUEST_SELECT_JOIN}
                   WHERE r.workspace_id=? ORDER BY r.created_at DESC, r.id DESC""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_request(
        self, workspace_id: int, request_id: int, user_id: int, *,
        name: str | None = None, description: str | None = None, deadline: str | None = None,
    ) -> None:
        with self.connect() as connection:
            exists = connection.execute("SELECT id FROM requests WHERE id=? AND workspace_id=?", (request_id, workspace_id)).fetchone()
            if not exists:
                raise ValueError("Заявка не найдена в текущем рабочем пространстве.")
            if name is not None:
                clean_name = name.strip()[:240]
                if not clean_name:
                    raise ValueError("Название заявки обязательно.")
                connection.execute("UPDATE requests SET name=? WHERE id=?", (clean_name, request_id))
            if description is not None:
                connection.execute("UPDATE requests SET description=? WHERE id=?", (description.strip()[:5000], request_id))
            if deadline is not None:
                connection.execute(
                    "INSERT INTO request_details(request_id, deadline) VALUES (?, ?) "
                    "ON CONFLICT(request_id) DO UPDATE SET deadline=excluded.deadline",
                    (request_id, deadline.strip()[:32]),
                )
            self._audit_connection(connection, workspace_id, user_id, "request.updated", "request", str(request_id), {
                k: v for k, v in {"name": name, "description": description, "deadline": deadline}.items() if v is not None
            })

    def create_request(self, workspace_id: int, *, name: str, description: str, positions: list[dict[str, Any]], sender_name: str, company_name: str, user_id: int, deadline: str = "") -> int:
        name = str(name or "").strip()[:240]
        if not name:
            raise ValueError("Название заявки обязательно.")
        cleaned = []
        for index, item in enumerate(positions[:100], start=1):
            position_name = str(item.get("name") or "").strip()[:240]
            if position_name:
                cleaned.append((f"p{index}", position_name, str(item.get("quantity") or item.get("qty") or "").strip()[:120]))
        if not cleaned:
            raise ValueError("Добавьте хотя бы одну позицию в заявку.")
        now = iso_now()
        with self.connect() as connection:
            next_id = int(connection.execute("SELECT COALESCE(MAX(id), 1042) + 1 FROM requests").fetchone()[0])
            connection.execute(
                "INSERT INTO requests(id, workspace_id, name, description, sender_name, company_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (next_id, workspace_id, name, str(description or "").strip()[:5000], str(sender_name or "").strip()[:120], str(company_name or "").strip()[:240], now),
            )
            connection.execute("INSERT INTO request_meta(request_id, status, search_progress, search_total, updated_at) VALUES (?, 'draft', 0, ?, ?)", (next_id, len(cleaned), now))
            if deadline:
                connection.execute("INSERT INTO request_details(request_id, deadline) VALUES (?, ?)", (next_id, deadline.strip()[:32]))
            for key, position_name, quantity in cleaned:
                connection.execute("INSERT INTO request_positions(request_id, position_key, name, quantity, created_at) VALUES (?, ?, ?, ?, ?)", (next_id, key, position_name, quantity, now))
            self._audit_connection(connection, workspace_id, user_id, "request.created", "request", str(next_id), {"positions": len(cleaned)})
        return next_id

    def start_request_search(self, workspace_id: int, request_id: int, user_id: int) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            exists = connection.execute("SELECT id FROM requests WHERE id=? AND workspace_id=?", (request_id, workspace_id)).fetchone()
            if not exists:
                raise ValueError("Заявка не найдена в текущем рабочем пространстве.")
            meta = connection.execute("SELECT status, search_progress, search_total, updated_at FROM request_meta WHERE request_id=?", (request_id,)).fetchone()
            if meta and meta["status"] == "completed":
                try:
                    cache_age = utc_now() - datetime.fromisoformat(str(meta["updated_at"]))
                    if cache_age < timedelta(days=60):
                        return {
                            "request_id": request_id,
                            "status": "completed",
                            "search_progress": int(meta["search_progress"] or 0),
                            "search_total": int(meta["search_total"] or 0),
                            "cached": True,
                        }
                except (TypeError, ValueError):
                    pass
            total = int(connection.execute("SELECT COUNT(*) FROM request_positions WHERE request_id=?", (request_id,)).fetchone()[0])
            connection.execute("UPDATE request_meta SET status='searching', search_progress=0, search_total=?, last_error=NULL, updated_at=? WHERE request_id=?", (total, now, request_id))
            self._audit_connection(connection, workspace_id, user_id, "request.search_started", "request", str(request_id), {})
        return {"request_id": request_id, "status": "searching", "search_total": total}

    def complete_request_search(self, workspace_id: int, request_id: int, *, error: str | None = None) -> None:
        now = iso_now()
        with self.connect() as connection:
            total = int(connection.execute("SELECT search_total FROM request_meta WHERE request_id=?", (request_id,)).fetchone()[0])
            connection.execute("UPDATE request_meta SET status=?, search_progress=?, last_error=?, updated_at=? WHERE request_id=? AND EXISTS (SELECT 1 FROM requests WHERE id=? AND workspace_id=?)", ("error" if error else "completed", 0 if error else total, error, now, request_id, request_id, workspace_id))

    def dashboard_summary(self, workspace_id: int) -> dict[str, Any]:
        requests = self.list_requests(workspace_id)
        with self.connect() as connection:
            # Only inbound replies matched to a заявка/поставщик thread that the
            # buyer hasn't opened yet (see thread_messages(), which marks read
            # on open). Deliberately excludes mail_inbox_messages: those are
            # unmatched senders — newsletters, notifications — not supplier
            # replies, so they never counted as a "new reply" once fixed
            # (see PROJECT_DOCUMENTATION.md §18, 23 Aug audit finding: this KPI
            # used to count every inbound message ever, including those, and
            # never decreased).
            new_replies = int(connection.execute(
                "SELECT COUNT(*) FROM mail_messages m WHERE m.workspace_id=? AND m.direction='inbound' "
                "AND NOT EXISTS (SELECT 1 FROM mail_message_reads r WHERE r.message_id=m.id)",
                (workspace_id,),
            ).fetchone()[0])
            attention = int(connection.execute("SELECT COUNT(*) FROM mail_jobs j JOIN mail_messages m ON m.id=j.message_id WHERE m.workspace_id=? AND j.status='failed'", (workspace_id,)).fetchone()[0])
            active = sum(1 for item in requests if item["status"] in {"draft", "searching", "updating"})
            searching = sum(1 for item in requests if item["status"] == "searching")
        return {"kpis": {"active_requests": active, "searching_requests": searching, "new_replies": new_replies, "attention": attention}, "requests": requests}

    def list_suppliers(self, workspace_id: int, request_id: int | None = None, *, query: str = "", region: str = "", kind: str = "", role: str = "", include_excluded: bool = False) -> list[dict[str, Any]]:
        clauses = ["s.workspace_id=?"]
        where_params: list[Any] = [workspace_id]
        if request_id is not None:
            clauses.append("rs.request_id=?")
            where_params.append(request_id)
            if not include_excluded:
                clauses.append("COALESCE(rs.is_irrelevant, 0)=0")
        if query:
            clauses.append("lower(s.name || ' ' || s.host || ' ' || s.email) LIKE ?")
            where_params.append(f"%{query.lower()}%")
        if region:
            clauses.append("p.region=?")
            where_params.append(region)
        if kind:
            clauses.append("p.kind=?")
            where_params.append(kind)
        if role:
            clauses.append("p.role=?")
            where_params.append(role)
        active_blacklist = "NOT EXISTS (SELECT 1 FROM blacklist_entries b WHERE b.workspace_id=s.workspace_id AND b.external_key=s.external_key AND b.restored_at IS NULL)"
        if not include_excluded:
            clauses.append(active_blacklist)
        join = "LEFT JOIN request_suppliers rs ON rs.supplier_id=s.id" if request_id is None else "LEFT JOIN request_suppliers rs ON rs.supplier_id=s.id AND rs.request_id=?"
        params: list[Any] = []
        if request_id is not None:
            params.append(request_id)
        params.append(request_id or 0)
        params.extend(where_params)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT s.id, s.external_key, s.name, s.email, s.host, s.created_at, s.updated_at,
                          COALESCE(p.inn, '') AS inn, COALESCE(p.kind, '') AS kind, COALESCE(p.region, '') AS region,
                          COALESCE(p.role, '') AS role, COALESCE(p.phone, '') AS phone, COALESCE(p.reason, '') AS reason,
                          COALESCE(p.source, '') AS source, COALESCE(p.covers_json, '[]') AS covers_json,
                          COALESCE(p.site_unavailable, 0) AS site_unavailable,
                          COALESCE(rs.position_keys_json, '[]') AS position_keys_json,
                          COALESCE(st.status, 'not_sent') AS mail_status, st.last_error,
                          gl.global_supplier_id, gr.ogrn AS registry_ogrn, gr.status AS registry_status,
                          gr.is_active AS registry_is_active, gr.registered_at AS registry_registered_at,
                          gf.report_year AS finance_report_year, gf.revenue AS finance_revenue, gf.profit AS finance_profit
                   FROM suppliers s LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                   {join} LEFT JOIN request_supplier_states st ON st.supplier_id=s.id AND st.request_id=COALESCE(rs.request_id, ?)
                   LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                   LEFT JOIN global_supplier_registry gr ON gr.global_supplier_id=gl.global_supplier_id
                   LEFT JOIN global_supplier_finances gf ON gf.global_supplier_id=gl.global_supplier_id
                   WHERE {' AND '.join(clauses)} ORDER BY s.name""",
                params,
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["covers"] = json.loads(item.pop("covers_json") or "[]")
            item["position_keys"] = json.loads(item.pop("position_keys_json") or "[]")
            item["mail_status"] = _normalize_mail_status(item["mail_status"])
            has_registry = item.pop("global_supplier_id") is not None and (
                item["registry_ogrn"] or item["registry_status"] or item["registry_registered_at"]
            )
            item["registry"] = (
                {
                    "ogrn": item["registry_ogrn"],
                    "status": item["registry_status"],
                    "is_active": None if item["registry_is_active"] is None else bool(item["registry_is_active"]),
                    "registered_at": item["registry_registered_at"],
                }
                if has_registry else None
            )
            for key in ("registry_ogrn", "registry_status", "registry_is_active", "registry_registered_at"):
                item.pop(key, None)
            item["finances"] = (
                {"report_year": item["finance_report_year"], "revenue": item["finance_revenue"], "profit": item["finance_profit"]}
                if item["finance_report_year"] is not None else None
            )
            for key in ("finance_report_year", "finance_revenue", "finance_profit"):
                item.pop(key, None)
            result.append(item)
        return result

    def list_blacklist(self, workspace_id: int, *, include_restored: bool = False) -> list[dict[str, Any]]:
        clause = "" if include_restored else "AND b.restored_at IS NULL"
        with self.connect() as connection:
            rows = connection.execute(f"SELECT b.id, b.external_key, b.company_name, b.level, b.reason, b.created_at, b.restored_at, s.host, s.email FROM blacklist_entries b LEFT JOIN suppliers s ON s.id=b.supplier_id WHERE b.workspace_id=? {clause} ORDER BY b.created_at DESC", (workspace_id,)).fetchall()
        return [dict(row) for row in rows]

    def add_blacklist(self, workspace_id: int, user_id: int, *, external_key: str, company_name: str, reason: str, supplier_id: int | None = None) -> int:
        external_key = str(external_key or "").strip().lower()
        if not external_key:
            raise ValueError("Не указан поставщик для чёрного списка.")
        now = iso_now()
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM blacklist_entries WHERE workspace_id=? AND external_key=? AND restored_at IS NULL ORDER BY id DESC LIMIT 1", (workspace_id, external_key)).fetchone()
            if row:
                return int(row[0])
            cursor = connection.execute("INSERT INTO blacklist_entries(workspace_id, supplier_id, external_key, company_name, reason, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (workspace_id, supplier_id, external_key, str(company_name or external_key)[:240], str(reason or "").strip()[:500], user_id, now))
            entry_id = int(cursor.lastrowid)
            self._audit_connection(connection, workspace_id, user_id, "supplier.blacklisted", "supplier", external_key, {"reason": reason})
            return entry_id

    def restore_blacklist(self, workspace_id: int, user_id: int, entry_id: int) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE blacklist_entries SET restored_at=? WHERE id=? AND workspace_id=? AND restored_at IS NULL", (iso_now(), entry_id, workspace_id))
            self._audit_connection(connection, workspace_id, user_id, "supplier.blacklist_restored", "blacklist", str(entry_id), {})

    def set_irrelevant(self, workspace_id: int, user_id: int, request_id: int, supplier_id: int, value: bool) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE request_suppliers SET is_irrelevant=?, updated_at=? WHERE request_id=? AND supplier_id=? AND EXISTS (SELECT 1 FROM requests WHERE id=? AND workspace_id=?)", (int(value), iso_now(), request_id, supplier_id, request_id, workspace_id))
            self._audit_connection(connection, workspace_id, user_id, "supplier.irrelevant" if value else "supplier.relevant", "request_supplier", f"{request_id}:{supplier_id}", {})

    def list_threads(self, workspace_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT t.id, t.request_id, t.supplier_id, t.subject, t.last_message_at, t.created_at,
                          r.name AS request_name, s.name AS supplier_name, s.email AS supplier_email,
                          s.host AS supplier_host, s.external_key AS supplier_external_key,
                          (SELECT COUNT(*) FROM mail_messages m WHERE m.thread_id=t.id) AS messages_count,
                          (SELECT COUNT(*) FROM mail_messages m WHERE m.thread_id=t.id AND m.direction='inbound') AS replies_count
                   FROM mail_threads t JOIN requests r ON r.id=t.request_id JOIN suppliers s ON s.id=t.supplier_id
                   WHERE t.workspace_id=? ORDER BY COALESCE(t.last_message_at, t.created_at) DESC""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_mail_sync_state(self, account_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM mail_sync_states WHERE mail_account_id=?", (account_id,)).fetchone()
        return dict(row) if row else None

    def save_mail_sync_state(
        self,
        account_id: int,
        *,
        uidvalidity: str,
        last_uid: int,
        imported_count: int,
        unmatched_count: int,
    ) -> None:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_sync_states(mail_account_id, folder, uidvalidity, last_uid, last_sync_at, last_imported_count, last_unmatched_count, last_error_at, last_error_message, created_at, updated_at)
                   VALUES (?, 'INBOX', ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                   ON CONFLICT(mail_account_id) DO UPDATE SET folder='INBOX', uidvalidity=excluded.uidvalidity, last_uid=excluded.last_uid, last_sync_at=excluded.last_sync_at, last_imported_count=excluded.last_imported_count, last_unmatched_count=excluded.last_unmatched_count, last_error_at=NULL, last_error_message=NULL, updated_at=excluded.updated_at""",
                (account_id, uidvalidity, int(last_uid), now, int(imported_count), int(unmatched_count), now, now),
            )

    def mark_mail_sync_error(self, account_id: int, error: str) -> None:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_sync_states(mail_account_id, folder, last_sync_at, last_error_at, last_error_message, created_at, updated_at)
                   VALUES (?, 'INBOX', NULL, ?, ?, ?, ?)
                   ON CONFLICT(mail_account_id) DO UPDATE SET last_error_at=excluded.last_error_at, last_error_message=excluded.last_error_message, updated_at=excluded.updated_at""",
                (account_id, now, str(error or "Ошибка синхронизации входящих сообщений.")[:500], now, now),
            )

    def import_incoming_messages(
        self,
        *,
        workspace_id: int,
        user_id: int,
        account_id: int,
        messages: Iterable[Any],
    ) -> dict[str, int]:
        imported = 0
        skipped = 0
        unmatched = 0
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for incoming in messages:
                duplicate = connection.execute(
                    "SELECT id FROM mail_messages WHERE mail_account_id=? AND (provider_message_id=? OR (message_id<>'' AND message_id=?)) LIMIT 1",
                    (account_id, incoming.provider_message_id, incoming.message_id),
                ).fetchone()
                if duplicate:
                    skipped += 1
                    continue
                inbox_duplicate = connection.execute(
                    "SELECT id FROM mail_inbox_messages WHERE mail_account_id=? AND (provider_message_id=? OR (message_id<>'' AND message_id=?)) LIMIT 1",
                    (account_id, incoming.provider_message_id, incoming.message_id),
                ).fetchone()
                if inbox_duplicate:
                    skipped += 1
                    continue
                thread = self._find_incoming_thread(connection, workspace_id, account_id, incoming)
                if not thread:
                    received_at = incoming.received_at.astimezone(UTC).isoformat()
                    connection.execute(
                        """INSERT INTO mail_inbox_messages(workspace_id, user_id, mail_account_id, provider_message_id, message_id, in_reply_to, references_header, from_email, to_email, subject, body_text, body_html, received_at, status, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unmatched', ?)
                           ON CONFLICT(mail_account_id, provider_message_id) DO NOTHING""",
                        (workspace_id, user_id, account_id, incoming.provider_message_id, incoming.message_id, incoming.in_reply_to, incoming.references, incoming.from_email, incoming.to_email, incoming.subject, incoming.body_text, incoming.body_html, received_at, received_at),
                    )
                    unmatched += 1
                    continue
                created_at = incoming.received_at.astimezone(UTC).isoformat()
                connection.execute(
                    """INSERT INTO mail_messages(thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id, provider_message_id, message_id, in_reply_to, references_header, direction, from_email, to_email, subject, body_text, body_html, status, created_at, sent_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'inbound', ?, ?, ?, ?, ?, 'received', ?, ?)""",
                    (thread["thread_id"], workspace_id, user_id, thread["request_id"], thread["supplier_id"], account_id, incoming.provider_message_id, incoming.message_id, incoming.in_reply_to, incoming.references, incoming.from_email, incoming.to_email, incoming.subject, incoming.body_text, incoming.body_html, created_at, created_at),
                )
                message_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                connection.execute(
                    """UPDATE mail_threads SET last_message_at=CASE WHEN last_message_at IS NULL OR last_message_at < ? THEN ? ELSE last_message_at END WHERE id=?""",
                    (created_at, created_at, thread["thread_id"]),
                )
                # A bounce isn't a reply — see docs/suppliers-screen.md раздел 7. Only a
                # "hard" bounce (address doesn't exist) is a reliable enough signal to
                # record automatically; a "soft" one just means "try again later" and
                # is left as whatever state it already had.
                bounce = classify_bounce(from_email=incoming.from_email, subject=incoming.subject, body_text=incoming.body_text)
                if bounce == "hard":
                    connection.execute(
                        """INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at)
                           VALUES (?, ?, ?, 'failed', ?, ?, ?)
                           ON CONFLICT(request_id, supplier_id) DO UPDATE SET mail_account_id=excluded.mail_account_id, status='failed', last_message_id=excluded.last_message_id, last_error=excluded.last_error, updated_at=excluded.updated_at""",
                        (thread["request_id"], thread["supplier_id"], account_id, message_id, "Письмо не доставлено (bounce).", created_at),
                    )
                    self._record_auto_bounce_issue(connection, thread["supplier_id"], incoming.subject, created_at)
                else:
                    connection.execute(
                        """INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at)
                           VALUES (?, ?, ?, 'replied', ?, NULL, ?)
                           ON CONFLICT(request_id, supplier_id) DO UPDATE SET mail_account_id=excluded.mail_account_id, status='replied', last_message_id=excluded.last_message_id, last_error=NULL, updated_at=excluded.updated_at""",
                        (thread["request_id"], thread["supplier_id"], account_id, message_id, created_at),
                    )
                self._audit_connection(connection, workspace_id, user_id, "mail.incoming_imported", "mail_message", str(message_id), {"thread_id": thread["thread_id"], "bounce": bounce})
                imported += 1
            connection.commit()
        return {"imported": imported, "skipped": skipped, "unmatched": unmatched}

    def list_unmatched_incoming(self, workspace_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, from_email, to_email, subject, body_text, body_html, received_at, status, provider_message_id
                   FROM mail_inbox_messages
                   WHERE workspace_id=? AND status='unmatched'
                   ORDER BY received_at DESC, id DESC LIMIT ?""",
                (workspace_id, limit),
            ).fetchall()
        return [_readable_message(dict(row)) for row in rows]

    @classmethod
    def _find_incoming_thread(cls, connection: sqlite3.Connection, workspace_id: int, account_id: int, incoming: Any) -> dict[str, int] | None:
        wanted = cls._header_tokens(incoming.in_reply_to) | cls._header_tokens(incoming.references)
        if wanted:
            rows = connection.execute(
                "SELECT thread_id, request_id, supplier_id, message_id, in_reply_to, references_header FROM mail_messages WHERE workspace_id=? AND mail_account_id=? ORDER BY created_at DESC",
                (workspace_id, account_id),
            ).fetchall()
            for row in rows:
                stored = cls._header_tokens(row["message_id"]) | cls._header_tokens(row["in_reply_to"]) | cls._header_tokens(row["references_header"])
                if wanted & stored:
                    return {"thread_id": int(row["thread_id"]), "request_id": int(row["request_id"]), "supplier_id": int(row["supplier_id"])}
        normalized_subject = cls._normalize_subject(incoming.subject)
        if normalized_subject and incoming.from_email:
            rows = connection.execute(
                """SELECT t.id AS thread_id, t.request_id, t.supplier_id, t.subject
                   FROM mail_threads t JOIN suppliers s ON s.id=t.supplier_id
                   WHERE t.workspace_id=? AND t.mail_account_id=? AND lower(s.email)=lower(?) ORDER BY t.last_message_at DESC""",
                (workspace_id, account_id, incoming.from_email),
            ).fetchall()
            for row in rows:
                if cls._normalize_subject(row["subject"]) == normalized_subject:
                    return {"thread_id": int(row["thread_id"]), "request_id": int(row["request_id"]), "supplier_id": int(row["supplier_id"])}
        return None

    @staticmethod
    def _header_tokens(value: str | None) -> set[str]:
        return {token for token in re.split(r"\s+", str(value or "").strip()) if token}

    @staticmethod
    def _normalize_subject(value: str | None) -> str:
        subject = str(value or "").strip().lower()
        subject = re.sub(r"^(?:(?:re|fw|fwd)\s*:\s*)+", "", subject)
        return re.sub(r"\s+", " ", subject)

    def record_audit(self, workspace_id: int, user_id: int, action: str, entity_type: str, entity_id: str, details: dict[str, Any] | None = None) -> None:
        with self.connect() as connection:
            self._audit_connection(connection, workspace_id, user_id, action, entity_type, entity_id, details or {})

    @staticmethod
    def _audit_connection(connection: sqlite3.Connection, workspace_id: int, user_id: int, action: str, entity_type: str, entity_id: str, details: dict[str, Any]) -> None:
        connection.execute("INSERT INTO audit_events(workspace_id, user_id, action, entity_type, entity_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (workspace_id, user_id, action, entity_type, entity_id, json.dumps(details, ensure_ascii=False), iso_now()))

    def is_blacklisted(self, workspace_id: int, external_key: str) -> bool:
        with self.connect() as connection:
            return bool(connection.execute("SELECT 1 FROM blacklist_entries WHERE workspace_id=? AND external_key=? AND restored_at IS NULL LIMIT 1", (workspace_id, str(external_key or "").strip().lower())).fetchone())

    def seed_user(self, email: str | None, password: str | None) -> dict[str, Any] | None:
        if not email or not password:
            return None
        email = email.strip().lower()
        if "@" not in email or len(password) < 8:
            raise ValueError("APP_USER_EMAIL должен быть email, а APP_USER_PASSWORD — не короче 8 символов.")
        now = iso_now()
        with self.connect() as connection:
            row = connection.execute("SELECT id, email, display_name FROM users WHERE email = ?", (email,)).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO users(email, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (email, email.split("@", 1)[0], hash_password(password), now),
                )
                row = connection.execute(
                    "SELECT id, email, display_name FROM users WHERE email = ?", (email,)
                ).fetchone()
            workspace = connection.execute(
                "SELECT w.id, w.name FROM workspaces w JOIN workspace_members wm ON wm.workspace_id = w.id WHERE wm.user_id = ? ORDER BY w.id LIMIT 1",
                (row["id"],),
            ).fetchone()
            if workspace is None:
                connection.execute(
                    "INSERT INTO workspaces(name, created_at) VALUES (?, ?)",
                    ("Рабочее пространство снабжения", now),
                )
                workspace_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.execute(
                    "INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'owner')",
                    (workspace_id, row["id"]),
                )
            else:
                workspace_id = workspace["id"]
            self._seed_request(connection, workspace_id)
            return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "workspace_id": workspace_id}

    @staticmethod
    def _seed_request(connection: sqlite3.Connection, workspace_id: int) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO requests(id, workspace_id, name, description, sender_name, company_name, created_at)
               VALUES (1043, ?, ?, ?, ?, ?, ?)""",
            (
                workspace_id,
                "Строительные материалы",
                "Кирпич облицовочный — 12 000 шт; кирпич рядовой — 20 000 шт; печной шамотный — 800 шт; газобетонный блок D500 — 40 м³.",
                "Снабжение",
                "Рабочее пространство снабжения",
                iso_now(),
            ),
        )

    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        from .auth import verify_password

        with self.connect() as connection:
            row = connection.execute(
                """SELECT u.id, u.email, u.display_name, u.password_hash, w.id AS workspace_id, w.name AS workspace_name
                   FROM users u JOIN workspace_members wm ON wm.user_id = u.id
                   JOIN workspaces w ON w.id = wm.workspace_id
                   WHERE lower(u.email) = lower(?) AND u.is_active = 1 ORDER BY w.id LIMIT 1""",
                (email.strip(),),
            ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return dict(row)

    def create_session(self, user_id: int, workspace_id: int, *, lifetime_seconds: int = 28800) -> tuple[str, str]:
        session_token = new_token(32)
        # Derive the CSRF token from the opaque session secret so it can be recovered after a server restart.
        csrf_token = token_hash(session_token + ":csrf")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(token_hash, user_id, workspace_id, csrf_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (token_hash(session_token), user_id, workspace_id, token_hash(csrf_token), iso_after(lifetime_seconds), iso_now()),
            )
        return session_token, csrf_token

    def get_session(self, session_token: str | None) -> dict[str, Any] | None:
        if not session_token:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """SELECT s.token_hash, s.user_id, s.workspace_id, s.csrf_hash, s.expires_at,
                          u.email, u.display_name, w.name AS workspace_name
                   FROM sessions s JOIN users u ON u.id = s.user_id JOIN workspaces w ON w.id = s.workspace_id
                   WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1""",
                (token_hash(session_token), iso_now()),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_token: str | None) -> None:
        if not session_token:
            return
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(session_token),))

    def create_oauth_state(self, *, state: str, session_token: str, user_id: int, workspace_id: int, code_verifier: str, redirect_uri: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO oauth_states(state_hash, session_hash, user_id, workspace_id, code_verifier, redirect_uri, expires_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (token_hash(state), token_hash(session_token), user_id, workspace_id, code_verifier, redirect_uri, iso_after(600), iso_now()),
            )

    def consume_oauth_state(self, state: str, session_token: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM oauth_states WHERE state_hash = ? AND session_hash = ?
                   AND used_at IS NULL AND expires_at > ?""",
                (token_hash(state), token_hash(session_token), iso_now()),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute("UPDATE oauth_states SET used_at = ? WHERE state_hash = ?", (iso_now(), token_hash(state)))
            connection.commit()
            return dict(row)

    def create_oauth_login_state(self, *, state: str, code_verifier: str, redirect_uri: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO oauth_login_states(state_hash, code_verifier, redirect_uri, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (token_hash(state), code_verifier, redirect_uri, iso_after(600), iso_now()),
            )

    def consume_oauth_login_state(self, state: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM oauth_login_states WHERE state_hash = ? AND used_at IS NULL AND expires_at > ?",
                (token_hash(state), iso_now()),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute("UPDATE oauth_login_states SET used_at = ? WHERE state_hash = ?", (iso_now(), token_hash(state)))
            connection.commit()
            return dict(row)

    def get_or_create_oauth_user(self, email: str, display_name: str | None) -> dict[str, Any]:
        email = email.strip().lower()
        now = iso_now()
        with self.connect() as connection:
            row = connection.execute("SELECT id, email, display_name FROM users WHERE email = ?", (email,)).fetchone()
            if row is None:
                # No password login is possible for an OAuth-only account, so store an
                # unguessable, unused hash rather than relaxing the NOT NULL column.
                connection.execute(
                    "INSERT INTO users(email, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (email, (display_name or email.split("@", 1)[0]).strip() or email, hash_password(new_token(32)), now),
                )
                row = connection.execute("SELECT id, email, display_name FROM users WHERE email = ?", (email,)).fetchone()
            workspace = connection.execute(
                "SELECT w.id FROM workspaces w JOIN workspace_members wm ON wm.workspace_id = w.id WHERE wm.user_id = ? ORDER BY w.id LIMIT 1",
                (row["id"],),
            ).fetchone()
            if workspace is None:
                connection.execute(
                    "INSERT INTO workspaces(name, created_at) VALUES (?, ?)",
                    ("Рабочее пространство снабжения", now),
                )
                workspace_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.execute(
                    "INSERT INTO workspace_members(workspace_id, user_id, role) VALUES (?, ?, 'owner')",
                    (workspace_id, row["id"]),
                )
            else:
                workspace_id = workspace["id"]
            return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "workspace_id": workspace_id}

    def get_mail_account(self, user_id: int, workspace_id: int, provider: str = "yandex") -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mail_accounts WHERE user_id = ? AND workspace_id = ? AND provider = ?",
                (user_id, workspace_id, provider),
            ).fetchone()
        return dict(row) if row else None

    def get_mail_account_by_id(self, account_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM mail_accounts WHERE id = ?", (account_id,)).fetchone()
        return dict(row) if row else None

    def get_request(self, workspace_id: int, request_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                f"""SELECT {self._REQUEST_SELECT_COLUMNS}
                   FROM requests r {self._REQUEST_SELECT_JOIN}
                   WHERE r.workspace_id=? AND r.id=?""",
                (workspace_id, request_id),
            ).fetchone()
        return dict(row) if row else None

    def request_positions(self, workspace_id: int, request_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT p.id, p.position_key, p.name, p.quantity FROM request_positions p JOIN requests r ON r.id=p.request_id WHERE p.request_id=? AND r.workspace_id=? ORDER BY p.id",
                (request_id, workspace_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_mail_account(
        self,
        *,
        user_id: int,
        workspace_id: int,
        provider: str,
        email: str,
        access_token_encrypted: str,
        refresh_token_encrypted: str,
        token_expires_at: str,
    ) -> int:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_accounts(user_id, workspace_id, provider, email, access_token_encrypted, refresh_token_encrypted, token_expires_at, status, created_at, updated_at, last_error_at, last_error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'connected', ?, ?, NULL, NULL)
                   ON CONFLICT(user_id, workspace_id, provider) DO UPDATE SET
                     email=excluded.email, access_token_encrypted=excluded.access_token_encrypted,
                     refresh_token_encrypted=excluded.refresh_token_encrypted, token_expires_at=excluded.token_expires_at,
                     status='connected', updated_at=excluded.updated_at, last_error_at=NULL, last_error_message=NULL""",
                (user_id, workspace_id, provider, email, access_token_encrypted, refresh_token_encrypted, token_expires_at, iso_now(), iso_now()),
            )
            return int(connection.execute(
                "SELECT id FROM mail_accounts WHERE user_id = ? AND workspace_id = ? AND provider = ?",
                (user_id, workspace_id, provider),
            ).fetchone()[0])

    def update_mail_tokens(self, account_id: int, access_token_encrypted: str, refresh_token_encrypted: str, token_expires_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_accounts SET access_token_encrypted = ?, refresh_token_encrypted = ?, token_expires_at = ?, status = 'connected', updated_at = ?, last_error_at = NULL, last_error_message = NULL WHERE id = ?",
                (access_token_encrypted, refresh_token_encrypted, token_expires_at, iso_now(), account_id),
            )

    def mark_mail_error(self, account_id: int, message: str, *, status: str | None = None) -> None:
        with self.connect() as connection:
            if status:
                connection.execute(
                    "UPDATE mail_accounts SET status = ?, last_error_at = ?, last_error_message = ?, updated_at = ? WHERE id = ?",
                    (status, iso_now(), message[:500], iso_now(), account_id),
                )
            else:
                connection.execute(
                    "UPDATE mail_accounts SET last_error_at = ?, last_error_message = ?, updated_at = ? WHERE id = ?",
                    (iso_now(), message[:500], iso_now(), account_id),
                )

    def disconnect_mail_account(self, user_id: int, workspace_id: int, provider: str = "yandex") -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_accounts SET access_token_encrypted = NULL, refresh_token_encrypted = NULL, token_expires_at = NULL, status = 'disconnected', updated_at = ?, last_error_at = NULL, last_error_message = NULL WHERE user_id = ? AND workspace_id = ? AND provider = ?",
                (iso_now(), user_id, workspace_id, provider),
            )

    def suppliers_with_email(self, workspace_id: int, hosts: list[str]) -> set[str]:
        """Hosts in this workspace that already have an email from a past search.

        Used to skip re-crawling/re-paying for a site whose contact we already
        found in an earlier заявка — see PROJECT_DOCUMENTATION.md §16.
        """
        hosts = [h.strip().lower() for h in hosts if h and h.strip()]
        if not hosts:
            return set()
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in hosts)
            rows = connection.execute(
                f"SELECT external_key FROM suppliers WHERE workspace_id=? AND email<>'' AND external_key IN ({placeholders})",
                (workspace_id, *hosts),
            ).fetchall()
        return {row[0] for row in rows}

    def suppliers_missing_registry(self, workspace_id: int, hosts: list[str]) -> list[tuple[str, str]]:
        """(host, ИНН) pairs that have an ИНН but no ЕГРЮЛ/финансы row yet.

        The crawl skip above (suppliers_with_email) would otherwise strand
        these forever: a host whose email was found before the registry
        columns existed — or on a day the Checko quota was already spent —
        never gets re-crawled, so its реестр/финансы would stay empty on
        every future заявка. This lets the caller run a Checko-only pass for
        them without paying for a full re-crawl.
        """
        hosts = [h.strip().lower() for h in hosts if h and h.strip()]
        if not hosts:
            return []
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in hosts)
            rows = connection.execute(
                f"""SELECT s.external_key, p.inn FROM suppliers s
                    JOIN supplier_profiles p ON p.supplier_id = s.id
                    LEFT JOIN global_supplier_links gl ON gl.supplier_id = s.id
                    LEFT JOIN global_supplier_registry gr ON gr.global_supplier_id = gl.global_supplier_id
                    WHERE s.workspace_id=? AND p.inn <> '' AND gr.global_supplier_id IS NULL
                      AND s.external_key IN ({placeholders})""",
                (workspace_id, *hosts),
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def upsert_supplier(self, *, workspace_id: int, external_key: str, name: str, email: str, host: str) -> int:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(workspace_id, external_key) DO UPDATE SET name=excluded.name, email=CASE WHEN excluded.email <> '' THEN excluded.email ELSE suppliers.email END, host=excluded.host, updated_at=excluded.updated_at""",
                (workspace_id, external_key, name, email, host, iso_now(), iso_now()),
            )
            return int(connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id = ? AND external_key = ?", (workspace_id, external_key)
            ).fetchone()[0])

    def update_search_progress(self, workspace_id: int, request_id: int, progress: int) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE request_meta SET search_progress=?, updated_at=? WHERE request_id=? AND EXISTS (SELECT 1 FROM requests WHERE id=? AND workspace_id=?)", (progress, iso_now(), request_id, request_id, workspace_id))

    def upsert_search_result(self, workspace_id: int, request_id: int, position_key: str, *, host: str, title: str, snippet: str, source: str = "xmlriver") -> int:
        host = str(host or "").strip().lower()
        if not host:
            raise ValueError("Поисковый результат не содержит домен.")
        now = iso_now()
        supplier_id = self.upsert_supplier(workspace_id=workspace_id, external_key=host, name=(title or host)[:240], email="", host=host)
        with self.connect() as connection:
            profile = connection.execute("SELECT covers_json FROM supplier_profiles WHERE supplier_id=?", (supplier_id,)).fetchone()
            covers = json.loads(profile[0] if profile and profile[0] else "[]")
            if position_key not in covers:
                covers.append(position_key)
            connection.execute(
                "INSERT INTO supplier_profiles(supplier_id, reason, source, covers_json, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(supplier_id) DO UPDATE SET reason=CASE WHEN excluded.reason<>'' THEN excluded.reason ELSE supplier_profiles.reason END, source=excluded.source, covers_json=excluded.covers_json, updated_at=excluded.updated_at",
                (supplier_id, str(snippet or "Компания найдена в поисковой выдаче.")[:500], source, json.dumps(covers, ensure_ascii=False), now),
            )
            relation = connection.execute("SELECT position_keys_json FROM request_suppliers WHERE request_id=? AND supplier_id=?", (request_id, supplier_id)).fetchone()
            position_keys = json.loads(relation[0] if relation and relation[0] else "[]")
            if position_key not in position_keys:
                position_keys.append(position_key)
            connection.execute(
                "INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(request_id, supplier_id) DO UPDATE SET position_keys_json=excluded.position_keys_json, reason=excluded.reason, source=excluded.source, updated_at=excluded.updated_at",
                (request_id, supplier_id, json.dumps(position_keys, ensure_ascii=False), str(snippet or "Компания найдена в поисковой выдаче.")[:500], source, now),
            )
        return supplier_id

    def apply_supplier_enrichment(
        self, workspace_id: int, host: str, *,
        email: str = "", inn: str = "", phone: str = "", region: str = "",
        role: str = "", company_name: str = "",
        registry_ogrn: str = "", registry_status: str = "",
        registry_active: bool | None = None, registry_registered_at: str = "",
        finance_report_year: int | None = None,
        finance_revenue: int | None = None, finance_profit: int | None = None,
    ) -> None:
        """Fold crawler/LLM/Checko results into an existing supplier + profile row.

        Called strictly after upsert_search_result for the same host in this
        request, so both rows are guaranteed to already exist — this only fills
        in blanks (CASE WHEN ...<>'' guards), it never overwrites a real value
        with an empty one from a source that simply didn't find anything.
        """
        host = host.strip().lower()
        if not host:
            return
        now = iso_now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id=? AND external_key=?", (workspace_id, host)
            ).fetchone()
            if not row:
                return
            supplier_id = int(row[0])
            connection.execute(
                "UPDATE suppliers SET "
                "email=CASE WHEN ?<>'' THEN ? ELSE email END, "
                "name=CASE WHEN ?<>'' THEN ? ELSE name END, "
                "updated_at=? WHERE id=?",
                (email, email, company_name, company_name, now, supplier_id),
            )
            connection.execute(
                "UPDATE supplier_profiles SET "
                "inn=CASE WHEN ?<>'' THEN ? ELSE inn END, "
                "phone=CASE WHEN ?<>'' THEN ? ELSE phone END, "
                "region=CASE WHEN ?<>'' THEN ? ELSE region END, "
                "role=CASE WHEN ?<>'' THEN ? ELSE role END, "
                "updated_at=? WHERE supplier_id=?",
                (inn, inn, phone, phone, region, region, role, role, now, supplier_id),
            )
            if inn:
                global_id = self._get_or_create_global_supplier(
                    connection, workspace_id, inn, name=company_name, site=host, email=email, phone=phone,
                )
                self._link_supplier_global(connection, supplier_id, global_id)
                if registry_ogrn or registry_status or registry_registered_at:
                    self._upsert_registry_facts(
                        connection, global_id, ogrn=registry_ogrn, status=registry_status,
                        is_active=registry_active, registered_at=registry_registered_at,
                    )
                if finance_report_year is not None:
                    self._upsert_finance_facts(
                        connection, global_id, report_year=finance_report_year,
                        revenue=finance_revenue, profit=finance_profit,
                    )

    # --------------------------------------------------------- global suppliers
    #
    # See docs/suppliers-screen.md. A "global supplier" is a workspace-wide
    # identity keyed by ИНН — one card even if the company was found under two
    # different domains. `suppliers` keeps its host-based identity (right for
    # crawling); `global_supplier_links` maps host-suppliers onto it.

    @staticmethod
    def _get_or_create_global_supplier(
        connection: sqlite3.Connection, workspace_id: int, inn: str, *,
        name: str = "", site: str = "", email: str = "", phone: str = "",
    ) -> int:
        now = iso_now()
        connection.execute(
            "INSERT INTO global_suppliers(workspace_id, inn, name, site, email, phone, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(workspace_id, inn) DO UPDATE SET "
            "name=CASE WHEN excluded.name<>'' AND global_suppliers.name='' THEN excluded.name ELSE global_suppliers.name END, "
            "site=CASE WHEN excluded.site<>'' AND global_suppliers.site='' THEN excluded.site ELSE global_suppliers.site END, "
            "email=CASE WHEN excluded.email<>'' AND global_suppliers.email='' THEN excluded.email ELSE global_suppliers.email END, "
            "phone=CASE WHEN excluded.phone<>'' AND global_suppliers.phone='' THEN excluded.phone ELSE global_suppliers.phone END, "
            "updated_at=excluded.updated_at",
            (workspace_id, inn, name, site, email, phone, now, now),
        )
        return int(connection.execute(
            "SELECT id FROM global_suppliers WHERE workspace_id=? AND inn=?", (workspace_id, inn)
        ).fetchone()[0])

    @staticmethod
    def _link_supplier_global(connection: sqlite3.Connection, supplier_id: int, global_supplier_id: int) -> None:
        connection.execute(
            "INSERT INTO global_supplier_links(supplier_id, global_supplier_id) VALUES (?, ?) "
            "ON CONFLICT(supplier_id) DO UPDATE SET global_supplier_id=excluded.global_supplier_id",
            (supplier_id, global_supplier_id),
        )

    @staticmethod
    def _upsert_registry_facts(
        connection: sqlite3.Connection, global_supplier_id: int, *,
        ogrn: str, status: str, is_active: bool | None, registered_at: str,
    ) -> None:
        connection.execute(
            "INSERT INTO global_supplier_registry(global_supplier_id, ogrn, status, is_active, registered_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(global_supplier_id) DO UPDATE SET "
            "ogrn=CASE WHEN excluded.ogrn<>'' THEN excluded.ogrn ELSE global_supplier_registry.ogrn END, "
            "status=CASE WHEN excluded.status<>'' THEN excluded.status ELSE global_supplier_registry.status END, "
            "is_active=COALESCE(excluded.is_active, global_supplier_registry.is_active), "
            "registered_at=CASE WHEN excluded.registered_at<>'' THEN excluded.registered_at ELSE global_supplier_registry.registered_at END, "
            "updated_at=excluded.updated_at",
            (global_supplier_id, ogrn, status, is_active, registered_at, iso_now()),
        )

    @staticmethod
    def _upsert_finance_facts(
        connection: sqlite3.Connection, global_supplier_id: int, *,
        report_year: int, revenue: int | None, profit: int | None,
    ) -> None:
        # Overwrite on a newer report_year (Checko publishes a new year once a
        # year), keep the existing figures if this call brought an older one.
        connection.execute(
            "INSERT INTO global_supplier_finances(global_supplier_id, report_year, revenue, profit, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(global_supplier_id) DO UPDATE SET "
            "report_year=excluded.report_year, revenue=excluded.revenue, profit=excluded.profit, updated_at=excluded.updated_at "
            "WHERE excluded.report_year >= global_supplier_finances.report_year",
            (global_supplier_id, report_year, revenue, profit, iso_now()),
        )

    @staticmethod
    def _record_auto_bounce_issue(connection: sqlite3.Connection, supplier_id: int, subject: str, reported_at: str) -> None:
        """Called from within import_incoming_messages's own transaction — no
        nested self.connect(), reuses the connection already open there."""
        link = connection.execute(
            "SELECT global_supplier_id FROM global_supplier_links WHERE supplier_id=?", (supplier_id,)
        ).fetchone()
        if not link:
            return  # no ИНН known for this host yet — nothing to attach the issue to
        global_supplier_id = int(link["global_supplier_id"])
        # Avoid piling up a duplicate auto-issue for the same bounce subject on the same day.
        today_prefix = reported_at[:10]
        existing = connection.execute(
            "SELECT id FROM global_supplier_issues WHERE global_supplier_id=? AND source='auto' AND reason='email_invalid' AND reported_at LIKE ?",
            (global_supplier_id, f"{today_prefix}%"),
        ).fetchone()
        if existing:
            return
        connection.execute(
            "INSERT INTO global_supplier_issues(global_supplier_id, reason, comment, source, reported_at) VALUES (?, 'email_invalid', ?, 'auto', ?)",
            (global_supplier_id, f"Автоматически обнаружено: письмо вернулось с ошибкой доставки ({subject[:200]}).", reported_at),
        )

    def backfill_global_suppliers(self, workspace_id: int) -> None:
        """Link any supplier that already has an ИНН but no global card yet.

        Idempotent — safe to call on every startup (ensure_schema does).
        Covers suppliers that got their ИНН before this feature existed
        (fixture seed, earlier enrichment runs).
        """
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT s.id, s.name, s.host, s.email, p.inn, p.phone
                   FROM suppliers s JOIN supplier_profiles p ON p.supplier_id=s.id
                   LEFT JOIN global_supplier_links l ON l.supplier_id=s.id
                   WHERE s.workspace_id=? AND p.inn<>'' AND l.supplier_id IS NULL""",
                (workspace_id,),
            ).fetchall()
            for row in rows:
                global_id = self._get_or_create_global_supplier(
                    connection, workspace_id, row["inn"],
                    name=row["name"] or "", site=row["host"] or "", email=row["email"] or "", phone=row["phone"] or "",
                )
                self._link_supplier_global(connection, int(row["id"]), global_id)
            connection.commit()

    def list_global_suppliers(self, workspace_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            gs_rows = connection.execute(
                "SELECT id, inn, name, site, email, phone, note, is_favorite FROM global_suppliers WHERE workspace_id=?",
                (workspace_id,),
            ).fetchall()
            if not gs_rows:
                return []
            gs_ids = [int(r["id"]) for r in gs_rows]
            summaries = self._global_supplier_summaries(connection, workspace_id, gs_ids)
        return [self._compose_global_supplier(dict(row), summaries.get(int(row["id"]), {})) for row in gs_rows]

    def global_supplier_detail(self, workspace_id: int, global_supplier_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            gs_row = connection.execute(
                "SELECT id, inn, name, site, email, phone, note, is_favorite FROM global_suppliers WHERE workspace_id=? AND id=?",
                (workspace_id, global_supplier_id),
            ).fetchone()
            if not gs_row:
                return None
            summaries = self._global_supplier_summaries(connection, workspace_id, [global_supplier_id])
            supplier = self._compose_global_supplier(dict(gs_row), summaries.get(global_supplier_id, {}))

            link_rows = connection.execute(
                "SELECT supplier_id FROM global_supplier_links WHERE global_supplier_id=?", (global_supplier_id,)
            ).fetchall()
            supplier_ids = [int(r["supplier_id"]) for r in link_rows]
            history: list[dict[str, Any]] = []
            if supplier_ids:
                sp_ph = ",".join("?" * len(supplier_ids))
                rows = connection.execute(
                    f"""SELECT rs.request_id, rs.supplier_id, r.name AS request_title, r.created_at,
                               st.status AS raw_status, rr.rating
                        FROM request_suppliers rs
                        JOIN requests r ON r.id = rs.request_id
                        LEFT JOIN request_supplier_states st ON st.request_id=rs.request_id AND st.supplier_id=rs.supplier_id
                        LEFT JOIN request_supplier_ratings rr ON rr.request_id=rs.request_id AND rr.supplier_id=rs.supplier_id
                        WHERE rs.supplier_id IN ({sp_ph}) AND rs.request_id IN (SELECT id FROM requests WHERE workspace_id=?)
                        ORDER BY r.created_at DESC""",
                    (*supplier_ids, workspace_id),
                ).fetchall()
                history = [
                    {
                        "request_id": int(row["request_id"]),
                        "supplier_id": int(row["supplier_id"]),
                        "request_title": row["request_title"],
                        "date": row["created_at"],
                        "outcome": _normalize_mail_status(row["raw_status"]),
                        "rating": row["rating"],
                    }
                    for row in rows
                ]

            issue_rows = connection.execute(
                "SELECT reason, comment, correct_inn, source, reported_at FROM global_supplier_issues "
                "WHERE global_supplier_id=? ORDER BY reported_at DESC",
                (global_supplier_id,),
            ).fetchall()
            registry_row = connection.execute(
                "SELECT ogrn, status, is_active, registered_at FROM global_supplier_registry WHERE global_supplier_id=?",
                (global_supplier_id,),
            ).fetchone()
            finance_row = connection.execute(
                "SELECT report_year, revenue, profit FROM global_supplier_finances WHERE global_supplier_id=?",
                (global_supplier_id,),
            ).fetchone()
            supplier["history"] = history
            supplier["issues"] = [dict(row) for row in issue_rows]
            supplier["registry"] = (
                {
                    "ogrn": registry_row["ogrn"],
                    "status": registry_row["status"],
                    "is_active": None if registry_row["is_active"] is None else bool(registry_row["is_active"]),
                    "registered_at": registry_row["registered_at"],
                }
                if registry_row else None
            )
            supplier["finances"] = (
                {
                    "report_year": finance_row["report_year"],
                    "revenue": finance_row["revenue"],
                    "profit": finance_row["profit"],
                }
                if finance_row else None
            )
        return supplier

    def _global_supplier_summaries(
        self, connection: sqlite3.Connection, workspace_id: int, gs_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        """One grouped pass over links/requests/messages/ratings for a set of global suppliers.

        Kept as plain Python aggregation rather than one large nested-subquery
        SQL statement — the dataset here is small (a workspace's supplier
        list), and this is far easier to verify line by line.
        """
        if not gs_ids:
            return {}
        gs_ph = ",".join("?" * len(gs_ids))
        link_rows = connection.execute(
            f"SELECT supplier_id, global_supplier_id FROM global_supplier_links WHERE global_supplier_id IN ({gs_ph})",
            gs_ids,
        ).fetchall()
        supplier_to_global = {int(r["supplier_id"]): int(r["global_supplier_id"]) for r in link_rows}
        supplier_ids = list(supplier_to_global.keys())
        summaries: dict[int, dict[str, Any]] = {gid: {
            "total_requests": 0, "sent_count": 0, "answered_count": 0,
            "last_contact_at": None, "avg_deal_rating": None, "is_blacklisted": False,
            "blacklist_reason": "", "blacklisted_at": None,
            "registry": None, "finances": None,
            "categories": set(),
        } for gid in gs_ids}
        for row in connection.execute(
            f"SELECT global_supplier_id, reason, blacklisted_at FROM global_supplier_blacklist WHERE global_supplier_id IN ({gs_ph})",
            gs_ids,
        ).fetchall():
            gid = int(row["global_supplier_id"])
            summaries[gid]["blacklist_reason"] = row["reason"]
            summaries[gid]["blacklisted_at"] = row["blacklisted_at"]
        for row in connection.execute(
            f"SELECT global_supplier_id, ogrn, status, is_active, registered_at FROM global_supplier_registry WHERE global_supplier_id IN ({gs_ph})",
            gs_ids,
        ).fetchall():
            gid = int(row["global_supplier_id"])
            if row["ogrn"] or row["status"] or row["registered_at"]:
                summaries[gid]["registry"] = {
                    "ogrn": row["ogrn"], "status": row["status"],
                    "is_active": None if row["is_active"] is None else bool(row["is_active"]),
                    "registered_at": row["registered_at"],
                }
        for row in connection.execute(
            f"SELECT global_supplier_id, report_year, revenue, profit FROM global_supplier_finances WHERE global_supplier_id IN ({gs_ph})",
            gs_ids,
        ).fetchall():
            gid = int(row["global_supplier_id"])
            if row["report_year"] is not None:
                summaries[gid]["finances"] = {"report_year": row["report_year"], "revenue": row["revenue"], "profit": row["profit"]}
        if not supplier_ids:
            return summaries
        sp_ph = ",".join("?" * len(supplier_ids))

        for row in connection.execute(
            f"SELECT DISTINCT request_id, supplier_id FROM request_suppliers WHERE supplier_id IN ({sp_ph})", supplier_ids
        ).fetchall():
            gid = supplier_to_global[int(row["supplier_id"])]
            summaries[gid]["total_requests"] += 1

        for row in connection.execute(
            f"SELECT supplier_id, status FROM request_supplier_states WHERE supplier_id IN ({sp_ph})", supplier_ids
        ).fetchall():
            gid = supplier_to_global[int(row["supplier_id"])]
            # Raw pipeline states (see _normalize_mail_status): any state means we
            # attempted contact; 'replied' is the only one that means an answer came back.
            if row["status"] in ("queued", "sending", "sent", "replied", "failed"):
                summaries[gid]["sent_count"] += 1
            if row["status"] == "replied":
                summaries[gid]["answered_count"] += 1

        for row in connection.execute(
            f"SELECT supplier_id, MAX(created_at) AS last FROM mail_messages WHERE supplier_id IN ({sp_ph}) GROUP BY supplier_id", supplier_ids
        ).fetchall():
            gid = supplier_to_global[int(row["supplier_id"])]
            current = summaries[gid]["last_contact_at"]
            if current is None or row["last"] > current:
                summaries[gid]["last_contact_at"] = row["last"]

        ratings: dict[int, list[int]] = {}
        for row in connection.execute(
            f"SELECT supplier_id, rating FROM request_supplier_ratings WHERE supplier_id IN ({sp_ph})", supplier_ids
        ).fetchall():
            gid = supplier_to_global[int(row["supplier_id"])]
            ratings.setdefault(gid, []).append(int(row["rating"]))
        for gid, values in ratings.items():
            summaries[gid]["avg_deal_rating"] = round(sum(values) / len(values), 1)

        for row in connection.execute(
            f"""SELECT s.id AS supplier_id FROM suppliers s
                JOIN blacklist_entries b ON b.workspace_id=s.workspace_id AND b.external_key=s.external_key AND b.restored_at IS NULL
                WHERE s.id IN ({sp_ph})""", supplier_ids
        ).fetchall():
            gid = supplier_to_global.get(int(row["supplier_id"]))
            if gid:
                summaries[gid]["is_blacklisted"] = True

        position_rows = connection.execute(
            f"""SELECT rs.supplier_id, rs.position_keys_json, rp.request_id, rp.position_key, rp.name
                FROM request_suppliers rs
                JOIN request_positions rp ON rp.request_id = rs.request_id
                WHERE rs.supplier_id IN ({sp_ph})""", supplier_ids
        ).fetchall()
        for row in position_rows:
            gid = supplier_to_global[int(row["supplier_id"])]
            try:
                keys = set(json.loads(row["position_keys_json"] or "[]"))
            except (TypeError, ValueError):
                keys = set()
            if row["position_key"] in keys:
                summaries[gid]["categories"].add(row["name"])

        # Average reply time: first outbound -> first inbound per (request, supplier).
        message_rows = connection.execute(
            f"SELECT request_id, supplier_id, direction, created_at FROM mail_messages WHERE supplier_id IN ({sp_ph}) ORDER BY created_at",
            supplier_ids,
        ).fetchall()
        first_out: dict[tuple[int, int], str] = {}
        reply_hours: dict[int, list[float]] = {}
        for row in message_rows:
            key = (int(row["request_id"]), int(row["supplier_id"]))
            if row["direction"] == "outbound" and key not in first_out:
                first_out[key] = row["created_at"]
            elif row["direction"] == "inbound" and key in first_out:
                gid = supplier_to_global[key[1]]
                try:
                    sent = datetime.fromisoformat(first_out.pop(key))
                    received = datetime.fromisoformat(row["created_at"])
                    hours = max((received - sent).total_seconds() / 3600.0, 0.0)
                    reply_hours.setdefault(gid, []).append(hours)
                except (TypeError, ValueError):
                    pass
        for gid, values in reply_hours.items():
            summaries[gid]["avg_response_hours"] = sum(values) / len(values)

        return summaries

    @staticmethod
    def _compose_global_supplier(row: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
        total_requests = summary.get("total_requests", 0)
        sent_count = summary.get("sent_count", 0)
        answered_count = summary.get("answered_count", 0)
        response_rate = round(answered_count / sent_count * 100) if sent_count else 0
        avg_hours = summary.get("avg_response_hours")
        relationship = "blacklisted" if summary.get("is_blacklisted") else "favorite" if row.get("is_favorite") else "none"
        return {
            "id": row["id"],
            "inn": row["inn"],
            "name": row["name"],
            "site": row["site"],
            "email": row["email"] or None,
            "phone": row["phone"] or None,
            "note": row["note"],
            "categories": sorted(summary.get("categories", set())),
            "total_requests": total_requests,
            "response_rate": response_rate,
            "avg_response_hours": round(avg_hours, 1) if avg_hours is not None else None,
            "last_contact_at": summary.get("last_contact_at"),
            "relationship_status": relationship,
            "avg_deal_rating": summary.get("avg_deal_rating"),
            "blacklist_reason": summary.get("blacklist_reason") or None,
            "blacklisted_at": summary.get("blacklisted_at"),
            "registry": summary.get("registry"),
            "finances": summary.get("finances"),
        }

    def update_global_supplier(self, workspace_id: int, global_supplier_id: int, *, note: str | None = None) -> None:
        if note is None:
            return
        with self.connect() as connection:
            connection.execute(
                "UPDATE global_suppliers SET note=?, updated_at=? WHERE workspace_id=? AND id=?",
                (note, iso_now(), workspace_id, global_supplier_id),
            )

    def set_global_supplier_relationship(
        self, workspace_id: int, user_id: int, global_supplier_id: int, status: str, *, reason: str = "",
    ) -> None:
        """status: 'none' | 'favorite' | 'blacklisted'. Blacklist reuses the existing
        workspace blacklist_entries mechanism (applied to every linked host-supplier)
        rather than a second, parallel flag — one source of truth for "don't contact".
        A reason is mandatory for 'blacklisted' (see global_supplier_blacklist,
        migration 010) — the caller decides where that text comes from (a typed
        reason on manual toggle, or the issue-modal's selected reason)."""
        if status not in ("none", "favorite", "blacklisted"):
            raise ValueError("Некорректный статус отношений.")
        reason = reason.strip()
        if status == "blacklisted" and not reason:
            raise ValueError("Укажите причину, чтобы добавить поставщика в чёрный список.")
        now = iso_now()
        with self.connect() as connection:
            gs = connection.execute(
                "SELECT name FROM global_suppliers WHERE workspace_id=? AND id=?", (workspace_id, global_supplier_id)
            ).fetchone()
            if not gs:
                raise ValueError("Поставщик не найден.")
            connection.execute(
                "UPDATE global_suppliers SET is_favorite=?, updated_at=? WHERE workspace_id=? AND id=?",
                (1 if status == "favorite" else 0, now, workspace_id, global_supplier_id),
            )
            if status == "blacklisted":
                connection.execute(
                    "INSERT INTO global_supplier_blacklist(global_supplier_id, reason, blacklisted_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(global_supplier_id) DO UPDATE SET reason=excluded.reason, blacklisted_at=excluded.blacklisted_at",
                    (global_supplier_id, reason, now),
                )
            else:
                connection.execute("DELETE FROM global_supplier_blacklist WHERE global_supplier_id=?", (global_supplier_id,))
            linked = connection.execute(
                "SELECT s.external_key FROM suppliers s JOIN global_supplier_links l ON l.supplier_id=s.id WHERE l.global_supplier_id=?",
                (global_supplier_id,),
            ).fetchall()
            for row in linked:
                external_key = row["external_key"]
                if status == "blacklisted":
                    existing = connection.execute(
                        "SELECT id FROM blacklist_entries WHERE workspace_id=? AND external_key=? AND restored_at IS NULL",
                        (workspace_id, external_key),
                    ).fetchone()
                    if not existing:
                        connection.execute(
                            "INSERT INTO blacklist_entries(workspace_id, external_key, company_name, reason, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (workspace_id, external_key, gs["name"], reason, user_id, now),
                        )
                else:
                    connection.execute(
                        "UPDATE blacklist_entries SET restored_at=? WHERE workspace_id=? AND external_key=? AND restored_at IS NULL",
                        (now, workspace_id, external_key),
                    )
            self._audit_connection(connection, workspace_id, user_id, "global_supplier.relationship_changed", "global_supplier", str(global_supplier_id), {"status": status, "reason": reason})

    def add_global_supplier_issue(
        self, workspace_id: int, user_id: int, global_supplier_id: int, *,
        reason: str, comment: str = "", correct_inn: str = "", source: str = "manual",
    ) -> int:
        now = iso_now()
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT id FROM global_suppliers WHERE workspace_id=? AND id=?", (workspace_id, global_supplier_id)
            ).fetchone()
            if not exists:
                raise ValueError("Поставщик не найден.")
            cursor = connection.execute(
                "INSERT INTO global_supplier_issues(global_supplier_id, reason, comment, correct_inn, source, reported_at) VALUES (?, ?, ?, ?, ?, ?)",
                (global_supplier_id, reason, comment, correct_inn or None, source, now),
            )
            issue_id = int(cursor.lastrowid)
            self._audit_connection(connection, workspace_id, user_id, "global_supplier.issue_reported", "global_supplier", str(global_supplier_id), {"reason": reason, "source": source})
        return issue_id

    def set_deal_rating(self, workspace_id: int, user_id: int, request_id: int, supplier_id: int, rating: int) -> None:
        if not 1 <= rating <= 5:
            raise ValueError("Оценка должна быть от 1 до 5.")
        now = iso_now()
        with self.connect() as connection:
            owned = connection.execute(
                "SELECT 1 FROM request_suppliers rs JOIN requests r ON r.id=rs.request_id "
                "WHERE rs.request_id=? AND rs.supplier_id=? AND r.workspace_id=?",
                (request_id, supplier_id, workspace_id),
            ).fetchone()
            if not owned:
                raise ValueError("Заявка или поставщик не найдены в этом рабочем пространстве.")
            connection.execute(
                "INSERT INTO request_supplier_ratings(request_id, supplier_id, rating, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(request_id, supplier_id) DO UPDATE SET rating=excluded.rating, updated_at=excluded.updated_at",
                (request_id, supplier_id, rating, now),
            )
            self._audit_connection(connection, workspace_id, user_id, "request_supplier.rated", "request_supplier", f"{request_id}:{supplier_id}", {"rating": rating})

    def create_queued_message(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        supplier_id: int,
        account_id: int,
        from_email: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str,
        message_id_header: str,
        attachments: Iterable[dict[str, Any]],
        in_reply_to: str | None = None,
        references_header: str | None = None,
    ) -> dict[str, int]:
        now = iso_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            thread = connection.execute(
                "SELECT id FROM mail_threads WHERE workspace_id = ? AND request_id = ? AND supplier_id = ?",
                (workspace_id, request_id, supplier_id),
            ).fetchone()
            if thread is None:
                connection.execute(
                    "INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (workspace_id, user_id, request_id, supplier_id, account_id, subject, now),
                )
                thread_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            else:
                thread_id = int(thread["id"])
                connection.execute("UPDATE mail_threads SET subject = ?, mail_account_id = ? WHERE id = ?", (subject, account_id, thread_id))
            connection.execute(
                """INSERT INTO mail_messages(thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id, message_id, in_reply_to, references_header, direction, from_email, to_email, subject, body_text, body_html, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'outbound', ?, ?, ?, ?, ?, 'queued', ?)""",
                (thread_id, workspace_id, user_id, request_id, supplier_id, account_id, message_id_header, in_reply_to, references_header, from_email, to_email, subject, body_text, body_html, now),
            )
            message_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            for attachment in attachments:
                connection.execute(
                    "INSERT INTO mail_attachments(message_id, filename, mime_type, size_bytes, content) VALUES (?, ?, ?, ?, ?)",
                    (message_id, attachment["filename"], attachment["mime_type"], attachment["size_bytes"], attachment["content"]),
                )
            connection.execute(
                "INSERT INTO mail_jobs(message_id, mail_account_id, status, attempts, created_at, updated_at) VALUES (?, ?, 'queued', 0, ?, ?)",
                (message_id, account_id, now, now),
            )
            job_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                """INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at)
                   VALUES (?, ?, ?, 'queued', ?, NULL, ?)
                   ON CONFLICT(request_id, supplier_id) DO UPDATE SET mail_account_id=excluded.mail_account_id, status='queued', last_message_id=excluded.last_message_id, last_error=NULL, updated_at=excluded.updated_at""",
                (request_id, supplier_id, account_id, message_id, now),
            )
            connection.execute("UPDATE mail_threads SET last_message_at = ? WHERE id = ?", (now, thread_id))
            connection.commit()
        return {"job_id": job_id, "message_id": message_id, "thread_id": thread_id}

    def claim_job(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT j.*, m.thread_id, m.workspace_id, m.user_id, m.request_id, m.supplier_id,
                          m.from_email, m.to_email, m.subject, m.body_text, m.body_html, m.in_reply_to,
                          m.references_header, m.message_id AS message_id_header, m.status AS message_status,
                          a.email AS account_email, a.provider, a.access_token_encrypted, a.refresh_token_encrypted, a.token_expires_at, a.status AS account_status
                   FROM mail_jobs j JOIN mail_messages m ON m.id = j.message_id
                   JOIN mail_accounts a ON a.id = j.mail_account_id
                   WHERE j.status = 'queued' AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= ?)
                   ORDER BY j.created_at LIMIT 1""",
                (iso_now(),),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            job_id = row["id"]
            connection.execute("UPDATE mail_jobs SET status='sending', attempts=attempts+1, updated_at=? WHERE id=?", (iso_now(), job_id))
            connection.execute("UPDATE mail_messages SET status='sending' WHERE id=?", (row["message_id"],))
            connection.execute("UPDATE request_supplier_states SET status='sending', updated_at=? WHERE request_id=? AND supplier_id=?", (iso_now(), row["request_id"], row["supplier_id"]))
            connection.commit()
            payload = dict(row)
            payload["attempts"] = int(row["attempts"]) + 1
            payload["attachments"] = [dict(item) for item in connection.execute("SELECT filename, mime_type, content FROM mail_attachments WHERE message_id = ?", (row["message_id"],)).fetchall()]
            return payload

    def mark_job_sent(self, job_id: int, message_id: int, provider_message_id: str | None, generated_message_id: str, sent_at: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE mail_jobs SET status='sent', provider_message_id=?, last_error=NULL, updated_at=? WHERE id=?", (provider_message_id, sent_at, job_id))
            connection.execute("UPDATE mail_messages SET status='sent', provider_message_id=?, message_id=?, sent_at=?, error=NULL WHERE id=?", (provider_message_id, generated_message_id, sent_at, message_id))
            connection.execute("UPDATE request_supplier_states SET status='sent', last_error=NULL, updated_at=? WHERE last_message_id=?", (sent_at, message_id))

    def retry_job(self, job_id: int, message_id: int, error: str, next_attempt_at: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE mail_jobs SET status='queued', next_attempt_at=?, last_error=?, updated_at=? WHERE id=?", (next_attempt_at, error[:500], iso_now(), job_id))
            connection.execute("UPDATE mail_messages SET status='queued', error=? WHERE id=?", (error[:500], message_id))
            connection.execute("UPDATE request_supplier_states SET status='queued', last_error=?, updated_at=? WHERE last_message_id=?", (error[:500], iso_now(), message_id))

    def fail_job(self, job_id: int, message_id: int, error: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE mail_jobs SET status='failed', last_error=?, updated_at=? WHERE id=?", (error[:500], iso_now(), job_id))
            connection.execute("UPDATE mail_messages SET status='failed', error=? WHERE id=?", (error[:500], message_id))
            connection.execute("UPDATE request_supplier_states SET status='failed', last_error=?, updated_at=? WHERE last_message_id=?", (error[:500], iso_now(), message_id))

    def count_sent_today(self, account_id: int) -> int:
        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE mail_account_id = ? AND status='sent' AND sent_at >= ?", (account_id, start)).fetchone()[0])

    def request_statuses(self, workspace_id: int, request_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT s.external_key, s.name, s.email, s.host, COALESCE(r.status, 'not_sent') AS status,
                          r.last_error, r.updated_at
                   FROM suppliers s LEFT JOIN request_supplier_states r ON r.supplier_id = s.id AND r.request_id = ?
                   WHERE s.workspace_id = ? ORDER BY s.id""",
                (request_id, workspace_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def queue_stats(self, workspace_id: int) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT j.status, COUNT(*) AS count FROM mail_jobs j JOIN mail_messages m ON m.id = j.message_id
                   WHERE m.workspace_id = ? GROUP BY j.status""",
                (workspace_id,),
            ).fetchall()
        return {row["status"]: int(row["count"]) for row in rows}

    def thread_messages(self, workspace_id: int, request_id: int, supplier_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, direction, from_email, to_email, subject, body_text, body_html, status, error, message_id, in_reply_to, references_header, created_at, sent_at FROM mail_messages WHERE workspace_id=? AND request_id=? AND supplier_id=? ORDER BY created_at",
                (workspace_id, request_id, supplier_id),
            ).fetchall()
            # Opening a thread is how a reply gets acknowledged — feeds the
            # "Новые ответы" dashboard KPI (see dashboard_summary()).
            now = iso_now()
            connection.executemany(
                "INSERT OR IGNORE INTO mail_message_reads(message_id, read_at) VALUES (?, ?)",
                [(row["id"], now) for row in rows if row["direction"] == "inbound"],
            )
        return [_readable_message(dict(row)) for row in rows]

    # ------------------------------------------------------ inbox reply threads
    #
    # A reply to an unmatched inbox message (no заявка/поставщик) cannot live in
    # mail_threads/mail_messages: their request_id/supplier_id are NOT NULL by
    # design. These methods back a small, separate model instead — see
    # migrations/006_inbox_reply.sql for why.

    def get_inbox_message(self, workspace_id: int, message_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, from_email, to_email, subject, body_text, body_html, received_at, status, message_id, references_header, mail_account_id"
                " FROM mail_inbox_messages WHERE workspace_id=? AND id=?",
                (workspace_id, message_id),
            ).fetchone()
        return _readable_message(dict(row)) if row else None

    def get_or_create_inbox_thread(self, *, workspace_id: int, user_id: int, mail_account_id: int, peer_email: str, subject: str) -> int:
        now = iso_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM mail_inbox_threads WHERE workspace_id=? AND mail_account_id=? AND peer_email=?",
                (workspace_id, mail_account_id, peer_email),
            ).fetchone()
            if row:
                thread_id = int(row["id"])
            else:
                connection.execute(
                    "INSERT INTO mail_inbox_threads(workspace_id, user_id, mail_account_id, peer_email, subject, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (workspace_id, user_id, mail_account_id, peer_email, subject, now),
                )
                thread_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.commit()
        return thread_id

    def record_inbox_reply(
        self,
        *,
        inbox_thread_id: int,
        workspace_id: int,
        user_id: int,
        mail_account_id: int,
        from_email: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str,
        message_id_header: str,
        in_reply_to: str | None,
        references_header: str | None,
    ) -> int:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_inbox_replies(inbox_thread_id, workspace_id, user_id, mail_account_id, message_id, in_reply_to, references_header, from_email, to_email, subject, body_text, body_html, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sending', ?)""",
                (inbox_thread_id, workspace_id, user_id, mail_account_id, message_id_header, in_reply_to, references_header, from_email, to_email, subject, body_text, body_html, now),
            )
            reply_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute("UPDATE mail_inbox_threads SET last_message_at=? WHERE id=?", (now, inbox_thread_id))
            connection.commit()
        return reply_id

    def mark_inbox_reply_sent(self, reply_id: int, provider_message_id: str | None, generated_message_id: str, sent_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_inbox_replies SET status='sent', provider_message_id=?, message_id=?, sent_at=?, error=NULL WHERE id=?",
                (provider_message_id, generated_message_id, sent_at, reply_id),
            )
            connection.commit()

    def mark_inbox_reply_failed(self, reply_id: int, error: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE mail_inbox_replies SET status='failed', error=? WHERE id=?", (error[:500], reply_id))
            connection.commit()

    def inbox_conversation(self, workspace_id: int, message_id: int) -> dict[str, Any] | None:
        original = self.get_inbox_message(workspace_id, message_id)
        if not original:
            return None
        with self.connect() as connection:
            thread = connection.execute(
                "SELECT id FROM mail_inbox_threads WHERE workspace_id=? AND mail_account_id=? AND peer_email=?",
                (workspace_id, original["mail_account_id"], original["from_email"]),
            ).fetchone()
            replies = []
            if thread:
                rows = connection.execute(
                    "SELECT id, from_email, to_email, subject, body_text, body_html, status, error, message_id, in_reply_to, references_header, created_at, sent_at FROM mail_inbox_replies WHERE inbox_thread_id=? ORDER BY created_at",
                    (int(thread["id"]),),
                ).fetchall()
                replies = [_readable_message(dict(row)) for row in rows]
        return {**original, "replies": replies}
