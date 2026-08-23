from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .auth import hash_password, new_token, token_hash
from .content import (
    clean_email_text,
    collapse_quoted_html,
    collapse_quoted_text,
    email_has_remote_images,
    sanitize_email_html,
)


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

    def list_requests(self, workspace_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT r.id, r.name, r.description, r.sender_name, r.company_name, r.created_at,
                          COALESCE(m.status, 'draft') AS status, COALESCE(m.search_progress, 0) AS search_progress,
                          COALESCE(m.search_total, 0) AS search_total, m.last_error, m.updated_at,
                          (SELECT COUNT(*) FROM request_positions p WHERE p.request_id=r.id) AS positions_count,
                          (SELECT COUNT(*) FROM request_suppliers rs WHERE rs.request_id=r.id AND rs.is_irrelevant=0) AS suppliers_count,
                          (SELECT COUNT(*) FROM mail_messages mm WHERE mm.request_id=r.id AND mm.direction='outbound' AND mm.status='sent') AS sent_count,
                          (SELECT COUNT(*) FROM mail_messages mm WHERE mm.request_id=r.id AND mm.direction='inbound') AS replies_count
                   FROM requests r LEFT JOIN request_meta m ON m.request_id=r.id
                   WHERE r.workspace_id=? ORDER BY r.created_at DESC, r.id DESC""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_request(self, workspace_id: int, *, name: str, description: str, positions: list[dict[str, Any]], sender_name: str, company_name: str, user_id: int) -> int:
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
            new_replies = int(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE workspace_id=? AND direction='inbound'", (workspace_id,)).fetchone()[0])
            new_replies += int(connection.execute("SELECT COUNT(*) FROM mail_inbox_messages WHERE workspace_id=? AND status='unmatched'", (workspace_id,)).fetchone()[0])
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
                          COALESCE(st.status, 'not_sent') AS mail_status, st.last_error
                   FROM suppliers s LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                   {join} LEFT JOIN request_supplier_states st ON st.supplier_id=s.id AND st.request_id=COALESCE(rs.request_id, ?)
                   WHERE {' AND '.join(clauses)} ORDER BY s.name""",
                params,
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["covers"] = json.loads(item.pop("covers_json") or "[]")
            item["position_keys"] = json.loads(item.pop("position_keys_json") or "[]")
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
                connection.execute(
                    """INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at)
                       VALUES (?, ?, ?, 'replied', ?, NULL, ?)
                       ON CONFLICT(request_id, supplier_id) DO UPDATE SET mail_account_id=excluded.mail_account_id, status='replied', last_message_id=excluded.last_message_id, last_error=NULL, updated_at=excluded.updated_at""",
                    (thread["request_id"], thread["supplier_id"], account_id, message_id, created_at),
                )
                self._audit_connection(connection, workspace_id, user_id, "mail.incoming_imported", "mail_message", str(message_id), {"thread_id": thread["thread_id"]})
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
                "SELECT * FROM requests WHERE workspace_id = ? AND id = ?", (workspace_id, request_id)
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
