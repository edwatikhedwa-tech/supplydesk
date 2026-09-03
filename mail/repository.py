from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from email.utils import make_msgid
from html import escape
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4

from .auth import new_token
from .auth_accounts import AuthAccountsMixin
from .bounce import classify_bounce, failed_recipients
from .content import (
    clean_email_text,
    collapse_quoted_html,
    collapse_quoted_text,
    email_has_remote_images,
    sanitize_email_html,
)
from .db_compat import (
    CompatRow,
    ManagedConnection,
    PostgresConnection,
    PostgresCursor,
    _adapt_postgres_sql,
    _postgres_migration_sql,
    _postgres_row_factory,
)
from .time_utils import (  # noqa: F401 -- re-exported for mail/queue.py, backend/app_config.py and tests
    UTC,
    DEFAULT_SESSION_LIFETIME_SECONDS,
    iso_after,
    iso_now,
    utc_now,
)
from backend.domain.supplier_identity.inn_extractor import validate_inn_checksum
from .pacing import PacingSettings
from .deliverability import transient_health_metrics


_MAIL_STATUS_LABELS = {
    "not_sent": "not_sent",
    "queued": "sent",     # in the outbound queue — from the user's view, already "sent"
    "sending": "sent",
    "sent": "waiting",    # delivered by us, no reply yet — waiting for the supplier
    "replied": "answered",
    "failed": "error",
    "cancelled": "not_sent",
    "delivery_unknown": "delivery_unknown",
}

SEARCH_DEPTH_MIN = 1
SEARCH_DEPTH_MAX = 100
MAIL_INTEGRITY_SCHEMA_VERSION = 1
MAIL_LEASE_SECONDS = 15 * 60
_CAMPAIGN_STAGE_TERMINAL_JOB_STATES = frozenset({"sent", "failed", "delivery_unknown", "cancelled"})
_CROSS_PROVIDER_RETRY_FINAL_STAGES = frozenset({"mail_from", "rcpt_to", "data_command", "post_data"})


log = logging.getLogger(__name__)


class DeliveryResolutionRequiredError(ValueError):
    """Raised when a request still contains an unresolved send uncertainty."""


class ContactSendGuardConflictError(ValueError):
    """Raised when initial outreach already claimed this request/email."""


class ContinuationPlanConflictError(ValueError):
    """Raised when an apply request no longer names the original plan."""


class CrossProviderRetryBlockedError(ValueError):
    """Raised when a proven rejection is not safe to retry through another provider."""


def _normalize_mail_status(raw: str | None) -> str:
    """request_supplier_states.status is an internal send-pipeline state machine
    (queued/sending/sent/failed/replied) — not the user-facing vocabulary
    (not_sent/sent/waiting/answered/error). Every place that surfaces a
    supplier's mail status to the API/UI must go through this."""
    return _MAIL_STATUS_LABELS.get(raw or "not_sent", "not_sent")


_REQUEST_STATUS_ORDER = {
    "delivery_unknown": 0,
    "answered": 1,
    "waiting": 2,
    "sent": 3,
    "error": 4,
    "not_sent": 5,
}

_DELIVERY_STATUS_KEYS = (
    "not_sent",
    "queued",
    "accepted",
    "failed",
    "delivery_unknown",
    "bounced",
    "cancelled",
)


def _normalized_mail_address(value: Any) -> str:
    return str(value or "").strip().lower()


def _masked_mail_address(value: Any) -> str:
    """Return a safe recipient label for operator confirmations and previews."""

    address = _normalized_mail_address(value)
    local, separator, domain = address.partition("@")
    if not separator or not local or not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


def _empty_delivery_counts() -> dict[str, int]:
    return {key: 0 for key in _DELIVERY_STATUS_KEYS}


def _effective_delivery_status(raw_status: str | None, *, bounced: bool = False) -> str:
    """Translate the persisted transport state into a user-facing fact.

    ``sent`` means that SMTP accepted the message.  A later hard bounce is a
    separate effective outcome and must not erase the accepted history.
    """
    if bounced:
        return "bounced"
    return {
        "queued": "queued",
        "sending": "queued",
        "sent": "accepted",
        "failed": "failed",
        "delivery_unknown": "delivery_unknown",
        "cancelled": "cancelled",
        "bounced": "bounced",
    }.get(str(raw_status or ""), "not_sent")


def _is_valid_company_inn(value: Any) -> bool:
    """Only a checked 10/12-digit INN can collapse host identities."""
    inn = str(value or "").strip()
    if not re.fullmatch(r"(?:\d{10}|\d{12})", inn):
        return False
    try:
        return bool(validate_inn_checksum(inn))
    except (TypeError, ValueError):
        return False


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


class MailRepository(AuthAccountsMixin):
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
                is_postgres_only = migration.lstrip().startswith("-- postgres-only")
                if is_postgres_only and not self.database_url:
                    continue  # SQLite has no ALTER COLUMN TYPE; not needed there anyway (no fixed-width ints)
                if self.database_url:
                    migration = _postgres_migration_sql(migration)
                connection.executescript(migration)
            # Establish lineage once, immediately after the schema exists. A
            # copied database keeps its UUID and original canonical path, so a
            # production runtime can fail closed instead of trusting the UUID
            # by itself.
            identity = connection.execute(
                "SELECT database_uuid FROM mail_database_identity WHERE id=1"
            ).fetchone()
            if not identity:
                connection.execute(
                    "INSERT INTO mail_database_identity(id, database_uuid, canonical_path, created_at) VALUES (1, ?, ?, ?)",
                    (str(uuid4()), str(self.db_path), iso_now()),
                )
            # Recovery is deliberately based on lease and the durable gate,
            # never on status alone. A missing companion row means an old job:
            # old sending jobs are unknown, while old queued jobs stay queued.
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            now = iso_now()
            recovery_message = "Невозможно подтвердить, ушло ли письмо после остановки процесса."
            connection.execute(
                """UPDATE mail_jobs
                   SET status='delivery_unknown', next_attempt_at=NULL, last_error=?, updated_at=?
                   WHERE status='sending'
                     AND (
                       NOT EXISTS (SELECT 1 FROM mail_job_integrity ji WHERE ji.job_id=mail_jobs.id)
                       OR EXISTS (
                         SELECT 1 FROM mail_job_integrity ji
                         WHERE ji.job_id=mail_jobs.id
                           AND (ji.lease_expires_at IS NULL OR ji.lease_expires_at < ?)
                           AND ji.irreversible_at IS NOT NULL
                       )
                     )""",
                (recovery_message, now, now),
            )
            connection.execute(
                """UPDATE mail_jobs
                   SET status='queued', next_attempt_at=?, last_error=?, updated_at=?
                   WHERE status='sending'
                     AND EXISTS (
                       SELECT 1 FROM mail_job_integrity ji
                       WHERE ji.job_id=mail_jobs.id
                         AND ji.irreversible_at IS NULL
                         AND ji.lease_expires_at IS NOT NULL
                         AND ji.lease_expires_at < ?
                     )""",
                (now, "Процесс остановился до начала передачи письма.", now, now),
            )
            connection.execute(
                """UPDATE mail_messages
                   SET status=(SELECT j.status FROM mail_jobs j WHERE j.message_id=mail_messages.id),
                       error=CASE WHEN (SELECT j.status FROM mail_jobs j WHERE j.message_id=mail_messages.id)='delivery_unknown' THEN ? ELSE error END
                   WHERE status='sending'
                     AND EXISTS (SELECT 1 FROM mail_jobs j WHERE j.message_id=mail_messages.id AND j.status IN ('queued','delivery_unknown'))""",
                (recovery_message,),
            )
            connection.execute(
                """UPDATE request_supplier_states
                   SET status=(SELECT m.status FROM mail_messages m WHERE m.id=request_supplier_states.last_message_id),
                       last_error=CASE WHEN (SELECT m.status FROM mail_messages m WHERE m.id=request_supplier_states.last_message_id)='delivery_unknown' THEN ? ELSE last_error END,
                       updated_at=?
                   WHERE status='sending'
                     AND EXISTS (SELECT 1 FROM mail_messages m WHERE m.id=request_supplier_states.last_message_id AND m.status IN ('queued','delivery_unknown'))""",
                (recovery_message, now),
            )
            connection.execute(
                """UPDATE mail_job_integrity
                   SET claim_owner=NULL, claim_token=NULL, lease_expires_at=NULL, updated_at=?
                   WHERE job_id IN (SELECT id FROM mail_jobs WHERE status='queued')""",
                (now,),
            )
            # A pacing reservation is not a second retry mechanism.  Startup
            # recovery closes reservations that belong to terminal jobs and
            # completes their in-progress audit row with the same uncertainty
            # that the I1 lease recovery recorded for the job.
            connection.execute(
                """UPDATE mail_send_attempts SET ended_at=?, outcome='uncertain',
                       provider_classification='restart-recovery', sanitized_error=?
                   WHERE outcome='in_progress' AND job_id IN (
                       SELECT id FROM mail_jobs WHERE status='delivery_unknown'
                   )""",
                (now, recovery_message),
            )
            connection.execute(
                """UPDATE mail_send_attempts SET ended_at=?, outcome='accepted',
                       provider_classification='restart-recovery'
                   WHERE outcome='in_progress' AND job_id IN (
                       SELECT id FROM mail_jobs WHERE status='sent'
                   )""",
                (now,),
            )
            # The companion evidence row is created when the irreversible
            # attempt starts.  If process recovery has to close that attempt,
            # retain an explicit local-recovery marker without inventing an
            # SMTP code, response, or stage that was not observed.
            connection.execute(
                """UPDATE mail_send_attempt_evidence
                   SET exception_class=COALESCE(exception_class, 'restart-recovery'), updated_at=?
                   WHERE attempt_id IN (
                       SELECT id FROM mail_send_attempts
                       WHERE outcome='uncertain' AND provider_classification='restart-recovery'
                   )""",
                (now,),
            )
            connection.execute(
                """UPDATE mail_send_attempt_evidence
                   SET exception_class=COALESCE(exception_class, 'restart-recovery'), updated_at=?
                   WHERE attempt_id IN (
                       SELECT id FROM mail_send_attempts
                       WHERE outcome='accepted' AND provider_classification='restart-recovery'
                   )""",
                (now,),
            )
            connection.execute(
                """UPDATE mail_send_reservations SET status='consumed', consumed_at=?, release_reason='restart-recovery'
                   WHERE status IN ('reserved','started') AND owner_type='job' AND owner_id IN (
                       SELECT id FROM mail_jobs WHERE status IN ('sent','failed','delivery_unknown')
                   )""",
                (now,),
            )
            if not self.database_url:
                connection.commit()

    def get_database_identity(self) -> dict[str, Any] | None:
        """Read the durable DB lineage without exposing credentials."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT database_uuid, canonical_path, created_at FROM mail_database_identity WHERE id=1"
            ).fetchone()
        return dict(row) if row else None

    def create_runtime_session(
        self,
        *,
        runtime_id: str,
        environment: str,
        started_at: str,
        pid: int,
        cwd: str,
        db_path: str,
        db_identity: str | None,
        git_revision: str | None,
        outgoing_allowed: bool,
        canonical_check_passed: bool,
        live_mail_lock_acquired: bool,
    ) -> None:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_runtime_sessions(
                       runtime_id, environment, started_at, ended_at, pid,
                       cwd, db_path, db_identity, git_revision,
                       outgoing_allowed, canonical_check_passed,
                       live_mail_lock_acquired, created_at
                   ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    runtime_id, environment, started_at, int(pid), cwd, db_path,
                    db_identity, git_revision, int(outgoing_allowed),
                    int(canonical_check_passed), int(live_mail_lock_acquired), now,
                ),
            )
            connection.commit()

    def end_runtime_session(self, runtime_id: str, ended_at: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_runtime_sessions SET ended_at=? WHERE runtime_id=? AND ended_at IS NULL",
                (ended_at or iso_now(), runtime_id),
            )
            connection.commit()

    def recover_stale_runtime_sessions(
        self,
        *,
        current_pid: int,
        is_pid_alive: Callable[[int], bool],
        ended_at: str | None = None,
    ) -> int:
        """Close durable sessions whose owning process is no longer alive.

        The canonical OS lock is the authority for outgoing ownership. This
        cleanup only makes the durable audit trail truthful after a crash; it
        never grants the lock or enables outgoing mail.
        """

        closed_at = ended_at or iso_now()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT runtime_id, pid FROM mail_runtime_sessions WHERE ended_at IS NULL"
            ).fetchall()
            stale_ids = [
                str(row["runtime_id"])
                for row in rows
                if int(row["pid"] or 0) != int(current_pid)
                and not is_pid_alive(int(row["pid"] or 0))
            ]
            for runtime_id in stale_ids:
                connection.execute(
                    "UPDATE mail_runtime_sessions SET ended_at=? WHERE runtime_id=? AND ended_at IS NULL",
                    (closed_at, runtime_id),
                )
            connection.commit()
        return len(stale_ids)

    def list_all_mail_accounts_for_runtime_manifest(self) -> list[dict[str, Any]]:
        """Return the non-secret account fields needed by runtime diagnostics."""

        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.id, a.provider, a.email, a.status,
                          COALESCE(p.auth_mode, CASE WHEN a.provider='yandex' THEN 'oauth' ELSE 'app_password' END) AS auth_mode,
                          COALESCE(p.credential_reference, CASE WHEN a.provider='yandex' THEN 'oauth-account:' || a.id ELSE 'app-password-account:' || a.id END) AS credential_reference,
                          COALESCE(p.incoming_enabled, 1) AS account_incoming_enabled,
                          COALESCE(p.outgoing_enabled, 0) AS account_outgoing_enabled
                   FROM mail_accounts a
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   ORDER BY a.id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def record_send_attempt_runtime(
        self,
        *,
        attempt_id: int,
        runtime_id: str,
        db_identity: str,
        canonical_check_passed: bool,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_send_attempt_runtime(
                       attempt_id, runtime_id, db_identity,
                       canonical_check_passed, recorded_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(attempt_id) DO UPDATE SET
                       runtime_id=excluded.runtime_id,
                       db_identity=excluded.db_identity,
                       canonical_check_passed=excluded.canonical_check_passed,
                       recorded_at=excluded.recorded_at""",
                (int(attempt_id), runtime_id, db_identity, int(canonical_check_passed), iso_now()),
            )
            connection.commit()
            # Search progress is durable now. A claimed step has a lease in
            # request_search_jobs and can be reclaimed after a function
            # recycle, so a cold start must not turn a truthful "searching"
            # state into a misleading error.

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
                           COALESCE(m.search_total, 0) AS search_total, COALESCE(c.search_depth, o.search_depth, 1) AS search_depth,
                           m.last_error, m.updated_at,
                          (SELECT COUNT(*) FROM request_positions p WHERE p.request_id=r.id) AS positions_count,
                          (SELECT COUNT(*) FROM request_suppliers rs WHERE rs.request_id=r.id AND rs.is_irrelevant=0) AS suppliers_count,
                          (SELECT COUNT(*) FROM mail_messages mm WHERE mm.request_id=r.id AND mm.direction='outbound' AND mm.status='sent') AS sent_count,
                          (SELECT COUNT(*) FROM mail_messages mm WHERE mm.request_id=r.id AND mm.direction='inbound' AND lower(COALESCE(mm.from_email,'')) NOT LIKE 'mailer-daemon@%' AND lower(COALESCE(mm.from_email,'')) NOT LIKE 'postmaster@%') AS replies_count"""
    _REQUEST_SELECT_JOIN = "LEFT JOIN request_meta m ON m.request_id=r.id LEFT JOIN request_details d ON d.request_id=r.id LEFT JOIN request_search_config c ON c.request_id=r.id LEFT JOIN request_search_options o ON o.request_id=r.id"

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

    def delete_request(self, workspace_id: int, request_id: int, user_id: int) -> None:
        """Delete one request and its request-scoped data after ownership check.

        Foreign keys on request-related tables use ON DELETE CASCADE. Suppliers
        themselves remain in the workspace catalogue because they can belong to
        multiple requests; the request-to-supplier links and conversations are
        removed with this request.
        """
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT id FROM requests WHERE id=? AND workspace_id=?",
                (request_id, workspace_id),
            ).fetchone()
            if not exists:
                raise ValueError("Заявка не найдена в текущем рабочем пространстве.")
            unresolved = connection.execute(
                """SELECT m.id FROM mail_messages m
                   WHERE m.request_id=? AND m.status='delivery_unknown'
                     AND NOT EXISTS (
                       SELECT 1 FROM mail_delivery_resolutions dr WHERE dr.message_id=m.id
                     ) LIMIT 1""",
                (request_id,),
            ).fetchone()
            if unresolved:
                raise DeliveryResolutionRequiredError(
                    "Нельзя удалить заявку: по одному или нескольким письмам не подтверждено, была ли отправка. Сначала закройте вопрос в переписке."
                )
            self._audit_connection(connection, workspace_id, user_id, "request.deleted", "request", str(request_id), {})
            connection.execute("DELETE FROM requests WHERE id=? AND workspace_id=?", (request_id, workspace_id))

    def create_request(
        self, workspace_id: int, *, name: str, description: str,
        positions: list[dict[str, Any]], sender_name: str, company_name: str,
        user_id: int, deadline: str = "", search_depth: int = 1,
    ) -> int:
        name = str(name or "").strip()[:240]
        if not name:
            raise ValueError("Название заявки обязательно.")
        try:
            search_depth = int(search_depth)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Глубина поиска должна быть целым числом от {SEARCH_DEPTH_MIN} до {SEARCH_DEPTH_MAX}.") from exc
        if not SEARCH_DEPTH_MIN <= search_depth <= SEARCH_DEPTH_MAX:
            raise ValueError(f"Глубина поиска должна быть от {SEARCH_DEPTH_MIN} до {SEARCH_DEPTH_MAX} страниц.")
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
            connection.execute("INSERT INTO request_search_config(request_id, search_depth) VALUES (?, ?)", (next_id, search_depth))
            if deadline:
                connection.execute("INSERT INTO request_details(request_id, deadline) VALUES (?, ?)", (next_id, deadline.strip()[:32]))
            for key, position_name, quantity in cleaned:
                connection.execute("INSERT INTO request_positions(request_id, position_key, name, quantity, created_at) VALUES (?, ?, ?, ?, ?)", (next_id, key, position_name, quantity, now))
            self._audit_connection(connection, workspace_id, user_id, "request.created", "request", str(next_id), {"positions": len(cleaned)})
        return next_id

    def request_search_depth(self, workspace_id: int, request_id: int) -> int | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COALESCE(c.search_depth, o.search_depth)
                   FROM requests r
                   LEFT JOIN request_search_config c ON c.request_id=r.id
                   LEFT JOIN request_search_options o ON o.request_id=r.id
                   WHERE r.id=? AND r.workspace_id=?""",
                (request_id, workspace_id),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

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
            connection.execute(
                """INSERT INTO request_search_jobs(
                    request_id, workspace_id, stage, position_index, enrich_hosts_json,
                    enrich_index, status, claim_token, locked_until, attempts,
                    last_error, created_at, updated_at
                ) VALUES (?, ?, 'serp', 0, '[]', 0, 'queued', NULL, NULL, 0, NULL, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    workspace_id=excluded.workspace_id,
                    stage='serp', position_index=0, enrich_hosts_json='[]',
                    enrich_index=0, status='queued', claim_token=NULL,
                    locked_until=NULL, attempts=0, last_error=NULL,
                    updated_at=excluded.updated_at""",
                (request_id, workspace_id, now, now),
            )
            self._audit_connection(connection, workspace_id, user_id, "request.search_started", "request", str(request_id), {})
        return {
            "request_id": request_id, "status": "searching", "search_total": total,
            "search_depth": self.request_search_depth(workspace_id, request_id) or 1,
        }

    def complete_request_search(self, workspace_id: int, request_id: int, *, error: str | None = None) -> None:
        now = iso_now()
        with self.connect() as connection:
            total = int(connection.execute("SELECT search_total FROM request_meta WHERE request_id=?", (request_id,)).fetchone()[0])
            connection.execute("UPDATE request_meta SET status=?, search_progress=?, last_error=?, updated_at=? WHERE request_id=? AND EXISTS (SELECT 1 FROM requests WHERE id=? AND workspace_id=?)", ("error" if error else "completed", 0 if error else total, error, now, request_id, request_id, workspace_id))
            connection.execute(
                "UPDATE request_search_jobs SET status=?, claim_token=NULL, locked_until=NULL, last_error=?, updated_at=? WHERE request_id=? AND workspace_id=?",
                ("failed" if error else "completed", error, now, request_id, workspace_id),
            )

    def claim_request_search_job(self, workspace_id: int, request_id: int) -> dict[str, Any] | None:
        """Claim one resumable search step with a short lease.

        The conditional UPDATE is the concurrency boundary: a recycled
        serverless invocation leaves the row claimable after the lease, while
        a second invocation cannot process the same cursor at the same time.
        """
        now = iso_now()
        locked_until = iso_after(120)
        claim_token = new_token(24)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = connection.execute(
                """SELECT request_id, workspace_id, stage, position_index,
                          enrich_hosts_json, enrich_index, status, claim_token,
                          locked_until, attempts, last_error
                   FROM request_search_jobs
                   WHERE workspace_id=? AND request_id=?
                     AND (status='queued' OR (status='processing' AND locked_until IS NOT NULL AND locked_until < ?))""",
                (workspace_id, request_id, now),
            ).fetchone()
            if not candidate:
                return None
            connection.execute(
                """UPDATE request_search_jobs
                   SET status='processing', claim_token=?, locked_until=?,
                       attempts=attempts+1, updated_at=?
                   WHERE workspace_id=? AND request_id=?
                     AND (status='queued' OR (status='processing' AND locked_until IS NOT NULL AND locked_until < ?))""",
                (claim_token, locked_until, now, workspace_id, request_id, now),
            )
            claimed = connection.execute(
                """SELECT request_id, workspace_id, stage, position_index,
                          enrich_hosts_json, enrich_index, status, claim_token,
                          locked_until, attempts, last_error
                   FROM request_search_jobs
                   WHERE workspace_id=? AND request_id=? AND claim_token=?""",
                (workspace_id, request_id, claim_token),
            ).fetchone()
        return dict(claimed) if claimed else None

    def advance_request_search_job(
        self,
        job: dict[str, Any],
        *,
        stage: str,
        position_index: int,
        hosts: list[str],
        enrich_index: int,
    ) -> bool:
        now = iso_now()
        hosts_json = json.dumps(hosts, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """UPDATE request_search_jobs
                   SET stage=?, position_index=?, enrich_hosts_json=?,
                       enrich_index=?, status='queued', claim_token=NULL,
                       locked_until=NULL, last_error=NULL, updated_at=?
                   WHERE request_id=? AND workspace_id=? AND status='processing'
                     AND claim_token=?""",
                (stage, position_index, hosts_json, enrich_index, now, job["request_id"], job["workspace_id"], job["claim_token"]),
            )
            row = connection.execute(
                "SELECT status FROM request_search_jobs WHERE request_id=? AND workspace_id=? AND status='queued' AND claim_token IS NULL",
                (job["request_id"], job["workspace_id"]),
            ).fetchone()
        return bool(row)

    def finish_request_search_job(self, job: dict[str, Any], *, enrich_index: int | None = None) -> bool:
        now = iso_now()
        final_enrich_index = int(job.get("enrich_index") or 0) if enrich_index is None else int(enrich_index)
        with self.connect() as connection:
            connection.execute(
                """UPDATE request_search_jobs
                   SET status='completed', claim_token=NULL, locked_until=NULL,
                       last_error=NULL, enrich_index=?, updated_at=?
                   WHERE request_id=? AND workspace_id=? AND status='processing'
                     AND claim_token=?""",
                (final_enrich_index, now, job["request_id"], job["workspace_id"], job["claim_token"]),
            )
            row = connection.execute(
                "SELECT request_id FROM request_search_jobs WHERE request_id=? AND workspace_id=? AND status='completed' AND claim_token IS NULL",
                (job["request_id"], job["workspace_id"]),
            ).fetchone()
            if not row:
                return False
            total = int(connection.execute("SELECT search_total FROM request_meta WHERE request_id=?", (job["request_id"],)).fetchone()[0])
            connection.execute(
                "UPDATE request_meta SET status='completed', search_progress=?, last_error=NULL, updated_at=? WHERE request_id=? AND EXISTS (SELECT 1 FROM requests WHERE id=? AND workspace_id=?)",
                (total, now, job["request_id"], job["request_id"], job["workspace_id"]),
            )
        return True

    def fail_request_search_job(self, job: dict[str, Any], error: str) -> bool:
        now = iso_now()
        message = error[:500]
        with self.connect() as connection:
            connection.execute(
                """UPDATE request_search_jobs
                   SET status='failed', claim_token=NULL, locked_until=NULL,
                       last_error=?, updated_at=?
                   WHERE request_id=? AND workspace_id=? AND status='processing'
                     AND claim_token=?""",
                (message, now, job["request_id"], job["workspace_id"], job["claim_token"]),
            )
            row = connection.execute(
                "SELECT request_id FROM request_search_jobs WHERE request_id=? AND workspace_id=? AND status='failed' AND claim_token IS NULL AND last_error=?",
                (job["request_id"], job["workspace_id"], message),
            ).fetchone()
            if not row:
                return False
            connection.execute(
                "UPDATE request_meta SET status='error', search_progress=0, last_error=?, updated_at=? WHERE request_id=? AND EXISTS (SELECT 1 FROM requests WHERE id=? AND workspace_id=?)",
                (message, now, job["request_id"], job["request_id"], job["workspace_id"]),
            )
        return True

    def dashboard_summary(self, workspace_id: int) -> dict[str, Any]:
        requests = self.list_requests(workspace_id)
        with self.connect() as connection:
            # Only inbound replies matched to a заявка/поставщик thread that the
            # buyer hasn't opened yet (see thread_messages(), which marks read
            # on open). Deliberately excludes mail_inbox_messages: those are
            # unmatched senders — newsletters, notifications — not supplier
            # replies, so they never counted as a "new reply" once fixed
            # (see Documents/28-8/PROJECT_DOCUMENTATION.md §18, 23 Aug audit finding: this KPI
            # used to count every inbound message ever, including those, and
            # never decreased).
            new_replies = int(connection.execute(
                "SELECT COUNT(*) FROM mail_messages m WHERE m.workspace_id=? AND m.direction='inbound' "
                "AND NOT EXISTS (SELECT 1 FROM mail_message_reads r WHERE r.message_id=m.id)",
                (workspace_id,),
            ).fetchone()[0])
            # The dashboard KPI is intentionally request-scoped: it must match
            # the error filter the user reaches by clicking the tile. Mail
            # delivery failures remain visible in correspondence and are not
            # mixed into the request error count.
            attention = sum(1 for item in requests if item["status"] == "error")
            active = sum(1 for item in requests if item["status"] in {"draft", "searching", "updating"})
            searching = sum(1 for item in requests if item["status"] == "searching")
            # Письма без привязки — отдельный счётчик, а не часть «новых ответов»:
            # это ответ, который система не смогла отнести к заявке, и он
            # требует действия человека. Без счётчика такое письмо тихо лежало
            # во вкладке «Без привязки», и его легко было не заметить.
            unmatched = connection.execute(
                "SELECT COUNT(*) FROM mail_inbox_messages WHERE workspace_id=? AND status='unmatched'",
                (workspace_id,),
            ).fetchone()[0]
        return {
            "kpis": {
                "active_requests": active, "searching_requests": searching,
                "new_replies": new_replies, "attention": attention,
                "unmatched_mail": int(unmatched or 0),
            },
            "requests": requests,
        }

    @staticmethod
    def _request_mail_facts(connection: sqlite3.Connection, request_id: int) -> dict[str, Any]:
        """Read transport and response facts for one request without mutating data.

        ``request_supplier_states`` is a compact pipeline cursor and cannot
        represent several email addresses on one company card.  The durable
        message history is therefore authoritative for contact-level facts;
        the cursor is used only as a compatibility fallback for old rows that
        have a state but no corresponding message.
        """
        outbound_rows = [dict(row) for row in connection.execute(
            """SELECT id, supplier_id, to_email, status, error, created_at
               FROM mail_messages m
               WHERE request_id=? AND direction='outbound'
                 AND NOT EXISTS (
                     SELECT 1
                     FROM mail_jobs j
                     JOIN mail_campaign_targets ct ON ct.job_id=j.id
                     WHERE j.message_id=m.id
                       AND ct.status='reconciled'
                       AND ct.exclusion_reason='accepted_history_reconciled'
                 )
               ORDER BY created_at, id""",
            (request_id,),
        ).fetchall()]
        # A canonical recovery may contain provider acceptance that was proven
        # from a signed/hashed backup without copying the old message row.  It
        # is still a real contact-level transport fact and must participate in
        # the request UI.  Keep one synthetic accepted event per recipient,
        # and only when canonical message history has no accepted row already.
        accepted_message_emails = {
            _normalized_mail_address(row["to_email"])
            for row in outbound_rows
            if str(row["status"] or "") == "sent" and _normalized_mail_address(row["to_email"])
        }
        reconciled_by_email: dict[str, dict[str, Any]] = {}
        for row in connection.execute(
            """SELECT id, supplier_id, normalized_recipient, accepted_at
               FROM mail_reconciled_outbound_events
               WHERE request_id=? AND outcome='accepted'
               ORDER BY accepted_at, id""",
            (request_id,),
        ).fetchall():
            email = _normalized_mail_address(row["normalized_recipient"])
            if email and email not in accepted_message_emails:
                reconciled_by_email[email] = {
                    "id": -int(row["id"]),
                    "supplier_id": int(row["supplier_id"]),
                    "to_email": email,
                    "status": "sent",
                    "error": None,
                    "created_at": row["accepted_at"] or "",
                }
        outbound_rows.extend(reconciled_by_email.values())
        outbound_rows.sort(key=lambda row: (str(row["created_at"] or ""), int(row["id"])))
        inbound_rows = connection.execute(
            """SELECT id, supplier_id, from_email, subject, body_text, body_html, created_at
               FROM mail_messages
               WHERE request_id=? AND direction='inbound'
               ORDER BY created_at, id""",
            (request_id,),
        ).fetchall()
        legacy_rows = connection.execute(
            "SELECT supplier_id, status, last_error FROM request_supplier_states WHERE request_id=?",
            (request_id,),
        ).fetchall()

        bounce_message_ids: set[int] = set()
        hard_bounce_addresses: dict[int, set[str]] = {}
        for row in inbound_rows:
            if classify_bounce(
                from_email=row["from_email"] or "",
                subject=row["subject"] or "",
                body_text=row["body_text"] or "",
            ) != "hard":
                continue
            addresses = {
                _normalized_mail_address(address)
                for address in failed_recipients(row["body_text"] or "", row["body_html"])
                if _normalized_mail_address(address)
            }
            if not addresses:
                # Some providers put the failed recipient only in a
                # ``mailto:`` HTML fragment that the conservative parser does
                # not accept.  The import path may still have matched this
                # hard bounce to a thread.  Use that thread's supplier only
                # when it has exactly one accepted outbound address; with
                # several addresses the contact remains unresolved rather
                # than guessing.
                supplier_id = int(row["supplier_id"])
                candidates = [
                    outbound for outbound in outbound_rows
                    if int(outbound["supplier_id"]) == supplier_id
                    and str(outbound["status"] or "") == "sent"
                ]
                if len(candidates) == 1:
                    bounce_message_ids.add(int(candidates[0]["id"]))
                continue
            supplier_id = int(row["supplier_id"])
            hard_bounce_addresses.setdefault(supplier_id, set()).update(addresses)
            for outbound in outbound_rows:
                if (
                    int(outbound["supplier_id"]) == supplier_id
                    and _normalized_mail_address(outbound["to_email"]) in addresses
                    and str(outbound["status"] or "") == "sent"
                ):
                    bounce_message_ids.add(int(outbound["id"]))

        by_contact: dict[tuple[int, str], dict[str, Any]] = {}
        for row in outbound_rows:
            supplier_id = int(row["supplier_id"])
            email = _normalized_mail_address(row["to_email"])
            if not email:
                continue
            status = _effective_delivery_status(
                row["status"], bounced=int(row["id"]) in bounce_message_ids,
            )
            key = (supplier_id, email)
            fact = by_contact.setdefault(key, {"events": [], "replied": False, "last_error": None})
            fact["events"].append({
                "id": int(row["id"]),
                "delivery_status": status,
                "created_at": row["created_at"] or "",
                "last_error": row["error"],
            })

        supplier_replies: set[int] = set()
        inbound_reply_count = 0
        for row in inbound_rows:
            bounce_kind = classify_bounce(
                from_email=row["from_email"] or "",
                subject=row["subject"] or "",
                body_text=row["body_text"] or "",
            )
            if bounce_kind is not None:
                continue
            sender = _normalized_mail_address(row["from_email"])
            if sender.startswith("mailer-daemon@") or sender.startswith("postmaster@"):
                continue
            inbound_reply_count += 1
            supplier_id = int(row["supplier_id"])
            supplier_replies.add(supplier_id)
            key = (supplier_id, sender)
            fact = by_contact.setdefault(key, {"events": [], "replied": False, "last_error": None})
            fact["replied"] = True

        for fact in by_contact.values():
            events = fact["events"]
            latest = events[-1] if events else None
            fact["latest_at"] = latest.get("created_at", "") if latest else ""
            fact["delivery_status"] = latest["delivery_status"] if latest else "not_sent"
            fact["response_status"] = "answered" if fact["replied"] else (
                "waiting" if fact["delivery_status"] == "accepted" else "none"
            )
            fact["last_error"] = latest.get("last_error") if latest else None

        legacy_by_supplier = {
            int(row["supplier_id"]): {
                "raw_status": str(row["status"] or "not_sent"),
                "last_error": row["last_error"],
            }
            for row in legacy_rows
        }
        return {
            "by_contact": by_contact,
            "supplier_replies": supplier_replies,
            "legacy_by_supplier": legacy_by_supplier,
            "outbound_rows": outbound_rows,
            "bounce_message_ids": bounce_message_ids,
            "inbound_reply_count": inbound_reply_count,
            "hard_bounce_addresses": hard_bounce_addresses,
        }

    @staticmethod
    def _request_mail_metrics(connection: sqlite3.Connection, request_id: int) -> dict[str, Any]:
        facts = MailRepository._request_mail_facts(connection, request_id)
        counts = _empty_delivery_counts()
        accepted_history = failed = queued = unknown = cancelled = 0
        for row in facts["outbound_rows"]:
            raw_status = str(row["status"] or "")
            if raw_status == "sent":
                accepted_history += 1
            elif raw_status == "failed":
                failed += 1
            elif raw_status in {"queued", "sending"}:
                queued += 1
            elif raw_status == "delivery_unknown":
                unknown += 1
            elif raw_status == "cancelled":
                cancelled += 1
            effective = _effective_delivery_status(
                raw_status, bounced=int(row["id"]) in facts["bounce_message_ids"],
            )
            counts[effective] += 1
        return {
            "outbound_total": len(facts["outbound_rows"]),
            "queued": queued,
            # This is the historical SMTP acceptance count.  It intentionally
            # remains additive with bounced: a bounce is a later outcome of an
            # earlier accepted SMTP transaction.
            "accepted": accepted_history,
            "accepted_effective": counts["accepted"],
            "failed": failed,
            "delivery_unknown": unknown,
            "bounced": counts["bounced"],
            "cancelled": cancelled,
            "replies": int(facts["inbound_reply_count"]),
        }

    @staticmethod
    def _accepted_supplier_provider(
        connection: sqlite3.Connection | PostgresConnection,
        request_id: int,
        supplier_id: int | None,
        normalized_recipient: str | None = None,
    ) -> str | None:
        """Return the provider of the latest accepted contact transport.

        A provider-switch continuation can create a new outbound message while
        the original campaign row remains queued.  The supplier-level outcome
        is therefore derived from durable message history, not from one
        campaign job or from ``request_supplier_states``.
        """

        if supplier_id is None:
            return None
        row = connection.execute(
            """SELECT provider FROM (
                   SELECT ma.provider AS provider,
                          COALESCE(m.sent_at, m.created_at) AS accepted_at,
                          m.id AS event_id
                   FROM mail_messages m
                   JOIN mail_accounts ma ON ma.id=m.mail_account_id
                   LEFT JOIN mail_jobs j ON j.message_id=m.id
                   WHERE m.request_id=? AND m.supplier_id=? AND m.direction='outbound'
                     AND (m.status='sent' OR j.status='sent'
                          OR EXISTS (
                              SELECT 1 FROM mail_send_attempts sa
                              WHERE sa.job_id=j.id AND sa.outcome='accepted'
                          ))
                   UNION ALL
                   SELECT re.provider_type AS provider,
                          re.accepted_at AS accepted_at,
                          re.id AS event_id
                   FROM mail_reconciled_outbound_events re
                   WHERE re.request_id=? AND re.supplier_id=?
                     AND re.outcome='accepted'
                     AND (? IS NULL OR re.normalized_recipient=?)
               ) accepted_events
               ORDER BY accepted_at DESC, event_id DESC
               LIMIT 1""",
            (request_id, int(supplier_id), request_id, int(supplier_id), normalized_recipient, normalized_recipient),
        ).fetchone()
        return str(row["provider"]) if row and row["provider"] else None

    def reconcile_outbound_event(
        self,
        *,
        request_id: int,
        supplier_id: int,
        normalized_recipient: str,
        provider_type: str,
        rfc_message_id: str,
        accepted_at: str,
        evidence_type: str,
        evidence_reference: str,
        evidence_sha256: str,
        created_by: str,
        operator_reason: str,
    ) -> dict[str, Any]:
        """Insert one verified historical acceptance without creating a send job.

        The source evidence hash is the idempotency key.  A second invocation
        with the same target but different evidence is rejected rather than
        silently adding a second provider-neutral acceptance.
        """

        normalized_recipient = _normalized_mail_address(normalized_recipient)
        provider_type = str(provider_type or "").strip().lower()
        rfc_message_id = str(rfc_message_id or "").strip()
        evidence_sha256 = str(evidence_sha256 or "").strip().lower()
        if not normalized_recipient or "@" not in normalized_recipient:
            raise ValueError("Reconciliation recipient is invalid.")
        if provider_type not in {"yandex", "mailru"}:
            raise ValueError("Reconciliation provider is invalid.")
        if not rfc_message_id or len(evidence_sha256) != 64 or any(char not in "0123456789abcdef" for char in evidence_sha256):
            raise ValueError("Reconciliation evidence identity is invalid.")
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT * FROM mail_reconciled_outbound_events
                   WHERE request_id=? AND supplier_id=? AND normalized_recipient=?
                     AND provider_type=? AND rfc_message_id=?""",
                (int(request_id), int(supplier_id), normalized_recipient, provider_type, rfc_message_id),
            ).fetchone()
            if existing:
                if str(existing["evidence_sha256"]).lower() == evidence_sha256:
                    return {**dict(existing), "already_reconciled": True}
                raise ValueError("A different reconciliation evidence already exists for this recipient.")
            now = iso_now()
            connection.execute(
                """INSERT INTO mail_reconciled_outbound_events(
                       request_id, supplier_id, normalized_recipient,
                       provider_type, outcome, rfc_message_id, accepted_at,
                       evidence_type, evidence_reference, evidence_sha256,
                       created_at, created_by, operator_reason
                   ) VALUES (?, ?, ?, ?, 'accepted', ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(evidence_sha256) DO NOTHING""",
                (
                    int(request_id), int(supplier_id), normalized_recipient,
                    provider_type, rfc_message_id, accepted_at,
                    str(evidence_type)[:100], str(evidence_reference)[:500],
                    evidence_sha256, now, str(created_by)[:100], str(operator_reason)[:500],
                ),
            )
            inserted = connection.execute(
                """SELECT * FROM mail_reconciled_outbound_events
                   WHERE request_id=? AND supplier_id=? AND normalized_recipient=?
                     AND provider_type=? AND rfc_message_id=?""",
                (int(request_id), int(supplier_id), normalized_recipient, provider_type, rfc_message_id),
            ).fetchone()
            connection.commit()
        if not inserted:
            raise ValueError("Reconciliation evidence conflicts with an existing event.")
        return {**dict(inserted), "already_reconciled": False}

    def list_reconciled_outbound_events(self, request_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if request_id is None:
                rows = connection.execute(
                    "SELECT * FROM mail_reconciled_outbound_events ORDER BY accepted_at, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM mail_reconciled_outbound_events WHERE request_id=? ORDER BY accepted_at, id",
                    (int(request_id),),
                ).fetchall()
        return [dict(row) for row in rows]

    def list_suppliers(self, workspace_id: int, request_id: int | None = None, *, query: str = "", region: str = "", kind: str = "", role: str = "", include_excluded: bool = False) -> list[dict[str, Any]]:
        clauses = ["s.workspace_id=?"]
        where_params: list[Any] = [workspace_id]
        if request_id is not None:
            clauses.append("rs.request_id=?")
            where_params.append(request_id)
            if not include_excluded:
                clauses.append("COALESCE(rs.is_irrelevant, 0)=0")
        # Request-scoped rows are collapsed by INN below.  Apply these
        # presentation filters after collapsing so a hidden hostless email
        # cannot make a company lose its other sites or contacts.
        if query and request_id is None:
            clauses.append("lower(s.name || ' ' || s.host || ' ' || s.email) LIKE ?")
            where_params.append(f"%{query.lower()}%")
        if region and request_id is None:
            clauses.append("p.region=?")
            where_params.append(region)
        if kind and request_id is None:
            clauses.append("p.kind=?")
            where_params.append(kind)
        if role and request_id is None:
            clauses.append("p.role=?")
            where_params.append(role)
        # LIKE-хвост, а не только точное совпадение: запись «ozon.com» должна
        # закрывать и am.ozon.com — по одному ИНН площадки бывают домены на
        # разных TLD и с разными поддоменами для товарных страниц.
        active_blacklist = (
            "NOT EXISTS (SELECT 1 FROM blacklist_entries b WHERE b.workspace_id=s.workspace_id "
            "AND b.restored_at IS NULL AND (s.external_key=b.external_key OR s.external_key LIKE '%.' || b.external_key))"
        )
        if not include_excluded:
            clauses.append(active_blacklist)
        join = "LEFT JOIN request_suppliers rs ON rs.supplier_id=s.id" if request_id is None else "LEFT JOIN request_suppliers rs ON rs.supplier_id=s.id AND rs.request_id=?"
        # Порядок здесь обязан совпадать с порядком «?» в тексте запроса ниже:
        # сначала подзапрос found_url в SELECT, затем join, затем состояние
        # переписки, затем условия WHERE.
        params: list[Any] = [request_id or 0, request_id or 0]
        if request_id is not None:
            params.append(request_id)
        params.append(request_id or 0)
        params.extend(where_params)
        delivery_unresolved: set[int] = set()
        delivery_resolved: set[int] = set()
        mail_facts: dict[str, Any] | None = None
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT s.id, s.external_key, s.name, s.email, s.host, s.created_at, s.updated_at,
                          COALESCE(p.inn, '') AS inn, COALESCE(sis.source_type, '') AS inn_source,
                          COALESCE(p.kind, '') AS kind, COALESCE(p.region, '') AS region,
                          COALESCE(p.role, '') AS role, COALESCE(p.phone, '') AS phone, COALESCE(p.reason, '') AS reason,
                          COALESCE(p.source, '') AS source, COALESCE(p.covers_json, '[]') AS covers_json,
                          COALESCE(p.site_unavailable, 0) AS site_unavailable,
                          COALESCE(rs.position_keys_json, '[]') AS position_keys_json,
                          COALESCE(st.status, 'not_sent') AS mail_status_raw, st.last_error,
                          gl.global_supplier_id, gr.ogrn AS registry_ogrn, gr.status AS registry_status,
                          gr.is_active AS registry_is_active, gr.registered_at AS registry_registered_at,
                          gf.report_year AS finance_report_year, gf.revenue AS finance_revenue, gf.profit AS finance_profit,
                          gk.risks_json,
                          -- Непрочитанные ответы поставщика по этой заявке: даёт
                          -- в списке разницу между «ответ пришёл» и «ответ уже
                          -- прочитан». Отбойники не считаются ответом.
                          (SELECT COUNT(*) FROM mail_messages um
                            WHERE um.request_id=COALESCE(rs.request_id, ?) AND um.supplier_id=s.id
                              AND um.direction='inbound'
                              AND lower(COALESCE(um.from_email,'')) NOT LIKE 'mailer-daemon@%'
                              AND lower(COALESCE(um.from_email,'')) NOT LIKE 'postmaster@%'
                              AND NOT EXISTS (SELECT 1 FROM mail_message_reads umr WHERE umr.message_id=um.id)) AS unread_count,
                          (SELECT src.url FROM search_result_sources src
                            WHERE src.request_id=COALESCE(rs.request_id, ?) AND src.supplier_id=s.id
                            ORDER BY src.position_key LIMIT 1) AS found_url
                   FROM suppliers s LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                   LEFT JOIN supplier_inn_sources sis ON sis.supplier_id=s.id
                   {join} LEFT JOIN request_supplier_states st ON st.supplier_id=s.id AND st.request_id=COALESCE(rs.request_id, ?)
                   LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                   LEFT JOIN global_supplier_registry gr ON gr.global_supplier_id=gl.global_supplier_id
                   LEFT JOIN global_supplier_finances gf ON gf.global_supplier_id=gl.global_supplier_id
                   LEFT JOIN global_supplier_risks gk ON gk.global_supplier_id=gl.global_supplier_id
                   WHERE {' AND '.join(clauses)} ORDER BY s.name""",
                params,
            ).fetchall()
            if request_id is not None:
                mail_facts = self._request_mail_facts(connection, request_id)
                delivery_rows = connection.execute(
                    """SELECT m.supplier_id,
                              MAX(CASE WHEN NOT EXISTS (
                                  SELECT 1 FROM mail_delivery_resolutions dr
                                  WHERE dr.message_id=m.id
                              ) THEN 1 ELSE 0 END) AS unresolved,
                              MAX(CASE WHEN EXISTS (
                                  SELECT 1 FROM mail_delivery_resolutions dr
                                  WHERE dr.message_id=m.id
                              ) THEN 1 ELSE 0 END) AS resolved
                       FROM mail_messages m
                       WHERE m.request_id=? AND m.status='delivery_unknown'
                       GROUP BY m.supplier_id""",
                    (request_id,),
                ).fetchall()
                delivery_unresolved = {
                    int(row["supplier_id"])
                    for row in delivery_rows
                    if int(row["unresolved"] or 0)
                }
                delivery_resolved = {
                    int(row["supplier_id"])
                    for row in delivery_rows
                    if int(row["resolved"] or 0) and not int(row["unresolved"] or 0)
                }
        result = []
        for row in rows:
            item = dict(row)
            item["covers"] = json.loads(item.pop("covers_json") or "[]")
            item["position_keys"] = json.loads(item.pop("position_keys_json") or "[]")
            raw_mail_status = item.pop("mail_status_raw", "not_sent")
            # Keep the raw cursor only inside the aggregation pipeline.  It is
            # needed for historical rows created before message history was
            # persisted, but is not exposed as a second competing UI status.
            item["mail_pipeline_status"] = raw_mail_status
            item["mail_status"] = _normalize_mail_status(raw_mail_status)
            item["delivery_issue_resolved"] = int(item["id"]) in delivery_resolved
            if int(item["id"]) in delivery_unresolved:
                item["delivery_issue_resolved"] = False
            global_supplier_id = item["global_supplier_id"]
            item["global_supplier_id"] = int(global_supplier_id) if global_supplier_id is not None else None
            has_registry = global_supplier_id is not None and (
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
            # None (риски не проверялись) отличается от [] (проверено, факторов
            # риска нет) — оба должны дойти до фронтенда как есть, не слиться в один "пусто".
            risks_json = item.pop("risks_json", None)
            item["risks"] = json.loads(risks_json) if risks_json is not None else None
            item["unread_count"] = int(item.get("unread_count") or 0)
            result.append(item)
        if request_id is not None:
            result = self._aggregate_request_suppliers(result, mail_facts=mail_facts)
            if query or region or kind or role:
                normalized_query = query.strip().lower()

                def matches(item: dict[str, Any]) -> bool:
                    if region and item.get("region") != region:
                        return False
                    if kind and item.get("kind") != kind:
                        return False
                    if role and item.get("role") != role:
                        return False
                    if not normalized_query:
                        return True
                    haystack = " ".join([
                        str(item.get("name") or ""), str(item.get("host") or ""),
                        str(item.get("email") or ""), str(item.get("inn") or ""),
                        *[str(value) for value in item.get("contact_sites", [])],
                        *[str(value) for value in item.get("contact_emails", [])],
                    ]).lower()
                    return normalized_query in haystack

                result = [item for item in result if matches(item)]
        return result

    @staticmethod
    def _aggregate_request_suppliers(
        items: list[dict[str, Any]],
        *,
        mail_facts: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return one request row per confirmed company without losing contacts.

        ``suppliers`` deliberately remains host-based for search/history.  The
        request screen is a company view: only a checked INN/global link can
        collapse host rows.  Hostless manual rows are attached only when their
        email identifies exactly one existing group; ambiguous addresses stay
        separate.
        """
        if not items:
            return []

        keys_by_item: dict[int, tuple[str, int]] = {}
        members: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for item in items:
            global_id = item.get("global_supplier_id")
            if global_id is not None and _is_valid_company_inn(item.get("inn")):
                key = ("global", int(global_id))
            else:
                key = ("supplier", int(item["id"]))
            keys_by_item[int(item["id"])] = key
            members.setdefault(key, []).append(item)

        email_keys: dict[str, set[tuple[str, int]]] = {}
        for key, group in members.items():
            for item in group:
                email = str(item.get("email") or "").strip().lower()
                if email:
                    email_keys.setdefault(email, set()).add(key)

        # Manual rows created without a website are often a second copy of a
        # discovered contact.  Attach only an unlinked/hostless row with one
        # unambiguous email target.  In particular, a free-form address such as
        # edwatikh@gmail.com remains its own unresolved contact.
        for key, group in list(members.items()):
            if key[0] != "supplier" or any(str(item.get("host") or "").strip() for item in group):
                continue
            candidate_keys: set[tuple[str, int]] = set()
            for item in group:
                email = str(item.get("email") or "").strip().lower()
                if email:
                    candidate_keys.update(email_keys.get(email, set()))
            candidate_keys.discard(key)
            if len(candidate_keys) != 1:
                continue
            target_key = next(iter(candidate_keys))
            for item in group:
                keys_by_item[int(item["id"])] = target_key
            members[target_key].extend(group)
            del members[key]

        def primary_score(item: dict[str, Any]) -> tuple[int, int, int, int, int]:
            return (
                int(bool(item.get("registry"))),
                int(bool(item.get("inn"))),
                int(bool(item.get("host"))),
                int(bool(item.get("email"))),
                -int(item["id"]),
            )

        def legacy_fact(item: dict[str, Any]) -> dict[str, Any]:
            raw = str(item.get("mail_pipeline_status") or "not_sent")
            delivery = _effective_delivery_status(raw)
            response = "answered" if raw == "replied" else ("waiting" if raw == "sent" else "none")
            if raw == "replied":
                delivery = "accepted"
            return {
                "delivery_status": delivery,
                "response_status": response,
                "last_error": item.get("last_error"),
                "latest_at": "",
            }

        def contact_fact(group: list[dict[str, Any]], email: str) -> dict[str, Any]:
            candidates: list[dict[str, Any]] = []
            for member in group:
                member_email = _normalized_mail_address(member.get("email"))
                if member_email != email:
                    continue
                supplier_id = int(member["id"])
                fact = (mail_facts or {}).get("by_contact", {}).get((supplier_id, email))
                candidates.append(fact or legacy_fact(member))
            candidates.sort(key=lambda fact: str(fact.get("latest_at") or ""))
            selected = dict(candidates[-1]) if candidates else {
                "delivery_status": "not_sent", "response_status": "none", "last_error": None,
            }
            # An answer is a company/contact fact even if a later retry was
            # queued.  It must never be downgraded to "waiting".
            if any(fact.get("response_status") == "answered" for fact in candidates):
                selected["response_status"] = "answered"
            return selected

        aggregated: list[dict[str, Any]] = []
        for key, group in members.items():
            primary = max(group, key=primary_score)
            combined = dict(primary)
            contacts_by_email: dict[str, dict[str, Any]] = {}
            sites: list[str] = []
            position_keys: list[str] = []
            covers: list[str] = []
            statuses: list[str] = []
            unresolved_delivery = False
            resolved_delivery = False
            last_error = ""
            for item in group:
                host = str(item.get("host") or "").strip().lower()
                if host and host not in sites:
                    sites.append(host)
                for field in ("position_keys", "covers"):
                    destination = position_keys if field == "position_keys" else covers
                    for value in item.get(field) or []:
                        if value not in destination:
                            destination.append(value)
                status = str(item.get("mail_status") or "not_sent")
                statuses.append(status)
                if item.get("delivery_issue_resolved") is False:
                    unresolved_delivery = True
                elif item.get("delivery_issue_resolved"):
                    resolved_delivery = True
                if not last_error and item.get("last_error"):
                    last_error = str(item["last_error"])
                email = str(item.get("email") or "").strip().lower()
                if email:
                    current = contacts_by_email.get(email)
                    if current is None or (not current.get("host") and host):
                        fact = contact_fact(group, email)
                        contacts_by_email[email] = {
                            "supplier_id": int(item["id"]),
                            "email": email,
                            "host": host,
                            "mail_status": status,
                            "delivery_status": fact["delivery_status"],
                            "response_status": fact["response_status"],
                            "last_error": fact.get("last_error"),
                        }
                    elif _REQUEST_STATUS_ORDER.get(status, 5) < _REQUEST_STATUS_ORDER.get(current["mail_status"], 5):
                        current["mail_status"] = status

            combined["id"] = int(primary["id"])
            combined["global_supplier_id"] = int(key[1]) if key[0] == "global" else primary.get("global_supplier_id")
            combined["related_supplier_ids"] = sorted({int(item["id"]) for item in group})
            combined["contact_sites"] = sites
            combined["contact_emails"] = list(contacts_by_email)
            combined["contacts"] = list(contacts_by_email.values())
            combined["site_count"] = len(sites)
            combined["email_count"] = len(contacts_by_email)
            if not combined.get("email") and contacts_by_email:
                combined["email"] = next(iter(contacts_by_email))
            if not combined.get("host") and sites:
                combined["host"] = sites[0]
            delivery_counts = _empty_delivery_counts()
            for contact in contacts_by_email.values():
                delivery_status = str(contact.get("delivery_status") or "not_sent")
                if delivery_status not in delivery_counts:
                    delivery_status = "not_sent"
                delivery_counts[delivery_status] += 1
            response_statuses = {
                str(contact.get("response_status") or "none")
                for contact in contacts_by_email.values()
            }
            card_response_status = (
                "answered" if "answered" in response_statuses
                else "waiting" if "waiting" in response_statuses
                else "none"
            )
            if card_response_status != "answered" and mail_facts:
                supplier_ids = {int(item["id"]) for item in group}
                if supplier_ids & set(mail_facts.get("supplier_replies", set())):
                    card_response_status = "answered"
            present_delivery = [status for status, count in delivery_counts.items() if count]
            if not present_delivery:
                card_delivery_status = "not_sent"
            elif len(present_delivery) == 1:
                card_delivery_status = present_delivery[0]
            else:
                card_delivery_status = "mixed"
            combined["delivery_counts"] = delivery_counts
            combined["delivery_status"] = card_delivery_status
            combined["response_status"] = card_response_status
            combined["unsent_contact_count"] = delivery_counts["not_sent"]
            combined["position_keys"] = position_keys
            combined["covers"] = covers
            combined["unread_count"] = sum(int(item.get("unread_count") or 0) for item in group)
            # Keep the old field for clients that have not migrated yet.  New
            # request UI code must use delivery_status/response_status above.
            if card_response_status == "answered":
                combined["mail_status"] = "answered"
            elif card_response_status == "waiting":
                combined["mail_status"] = "waiting"
            elif any(delivery_counts[key] for key in ("accepted", "queued")):
                combined["mail_status"] = "sent"
            elif any(delivery_counts[key] for key in ("failed", "bounced")):
                combined["mail_status"] = "error"
            elif delivery_counts["delivery_unknown"]:
                combined["mail_status"] = "delivery_unknown"
            else:
                combined["mail_status"] = "not_sent"
            combined["delivery_issue_resolved"] = False if unresolved_delivery else resolved_delivery
            combined["last_error"] = combined.get("last_error") or last_error
            combined["site_unavailable"] = int(any(int(item.get("site_unavailable") or 0) for item in group))
            aggregated.append(combined)

        return aggregated

    def list_blacklist(self, workspace_id: int, *, include_restored: bool = False) -> list[dict[str, Any]]:
        clause = "" if include_restored else "AND b.restored_at IS NULL"
        with self.connect() as connection:
            rows = connection.execute(f"SELECT b.id, b.external_key, b.company_name, b.level, b.reason, b.created_at, b.restored_at, s.host, s.email FROM blacklist_entries b LEFT JOIN suppliers s ON s.id=b.supplier_id WHERE b.workspace_id=? {clause} ORDER BY b.created_at DESC", (workspace_id,)).fetchall()
        return [dict(row) for row in rows]

    def add_blacklist(
        self,
        workspace_id: int,
        user_id: int,
        *,
        external_key: str,
        company_name: str,
        reason: str,
        supplier_id: int | None = None,
        level: str = "company",
    ) -> int:
        external_key = str(external_key or "").strip().lower()
        if not external_key:
            raise ValueError("Не указан поставщик для чёрного списка.")
        level = str(level or "company").strip().lower()[:40] or "company"
        now = iso_now()
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM blacklist_entries WHERE workspace_id=? AND external_key=? AND restored_at IS NULL ORDER BY id DESC LIMIT 1", (workspace_id, external_key)).fetchone()
            if row:
                return int(row[0])
            cursor = connection.execute("INSERT INTO blacklist_entries(workspace_id, supplier_id, external_key, company_name, level, reason, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (workspace_id, supplier_id, external_key, str(company_name or external_key)[:240], level, str(reason or "").strip()[:500], user_id, now))
            entry_id = int(cursor.lastrowid)
            self._audit_connection(
                connection, workspace_id, user_id,
                "supplier.email_suppressed" if level == "email" else "supplier.blacklisted",
                "email" if level == "email" else "supplier", external_key,
                {"reason": reason, "level": level},
            )
            return entry_id

    @staticmethod
    def _email_suppression_key(email: str) -> str:
        return f"email:{str(email or '').strip().lower()}"

    def add_email_suppression(
        self,
        workspace_id: int,
        user_id: int,
        *,
        email: str,
        reason: str = "do_not_contact",
        company_name: str = "",
        supplier_id: int | None = None,
    ) -> int:
        normalized = str(email or "").strip().lower()
        if "@" not in normalized:
            raise ValueError("Не указан корректный email для suppression.")
        return self.add_blacklist(
            workspace_id, user_id,
            external_key=self._email_suppression_key(normalized),
            company_name=company_name or normalized, reason=reason, supplier_id=supplier_id, level="email",
        )

    def restore_blacklist(self, workspace_id: int, user_id: int, entry_id: int) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE blacklist_entries SET restored_at=? WHERE id=? AND workspace_id=? AND restored_at IS NULL", (iso_now(), entry_id, workspace_id))
            self._audit_connection(connection, workspace_id, user_id, "supplier.blacklist_restored", "blacklist", str(entry_id), {})

    def set_irrelevant(self, workspace_id: int, user_id: int, request_id: int, supplier_id: int, value: bool) -> None:
        with self.connect() as connection:
            request_exists = connection.execute(
                "SELECT 1 FROM requests WHERE id=? AND workspace_id=?", (request_id, workspace_id),
            ).fetchone()
            target_ids = {supplier_id}
            if request_exists:
                # The request screen presents one company row for several
                # host-based identities.  Apply the row action to the same
                # display group so a reload cannot resurrect a hidden site.
                rows = connection.execute(
                    """SELECT s.id, s.email, s.host, COALESCE(p.inn, '') AS inn,
                              gl.global_supplier_id
                       FROM request_suppliers rs
                       JOIN suppliers s ON s.id=rs.supplier_id
                       LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                       LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                       WHERE rs.request_id=? AND s.workspace_id=?""",
                    (request_id, workspace_id),
                ).fetchall()
                synthetic_items = [
                    {
                        "id": int(row["id"]),
                        "email": row["email"],
                        "host": row["host"],
                        "inn": row["inn"],
                        "global_supplier_id": row["global_supplier_id"],
                        "registry": None,
                        "position_keys": [],
                        "covers": [],
                        "mail_status": "not_sent",
                    }
                    for row in rows
                ]
                group = next(
                    (
                        item for item in self._aggregate_request_suppliers(synthetic_items)
                        if supplier_id in item.get("related_supplier_ids", [])
                    ),
                    None,
                )
                if group:
                    target_ids = {int(item_id) for item_id in group["related_supplier_ids"]}
            placeholders = ",".join("?" for _ in target_ids)
            connection.execute(
                f"UPDATE request_suppliers SET is_irrelevant=?, updated_at=? "
                f"WHERE request_id=? AND supplier_id IN ({placeholders})",
                [int(value), iso_now(), request_id, *sorted(target_ids)],
            )
            self._audit_connection(
                connection, workspace_id, user_id,
                "supplier.irrelevant" if value else "supplier.relevant",
                "request_supplier", f"{request_id}:{supplier_id}",
                {"supplier_ids": sorted(target_ids)},
            )

    def list_threads(self, workspace_id: int, *, include_queue_only: bool = False) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM (
                     SELECT t.id, t.request_id, t.supplier_id, t.subject, t.last_message_at, t.created_at,
                            r.name AS request_name, s.name AS supplier_name, s.email AS supplier_email,
                            s.host AS supplier_host, s.external_key AS supplier_external_key,
                            (SELECT COUNT(*) FROM mail_messages m WHERE m.thread_id=t.id) AS messages_count,
                            (SELECT COUNT(*) FROM mail_messages m WHERE m.thread_id=t.id AND m.direction='inbound' AND lower(COALESCE(m.from_email,'')) NOT LIKE 'mailer-daemon@%' AND lower(COALESCE(m.from_email,'')) NOT LIKE 'postmaster@%') AS replies_count,
                            -- Непрочитанные ответы — отдельно от общего числа ответов.
                            (SELECT COUNT(*) FROM mail_messages m WHERE m.thread_id=t.id AND m.direction='inbound'
                               AND lower(COALESCE(m.from_email,'')) NOT LIKE 'mailer-daemon@%'
                               AND lower(COALESCE(m.from_email,'')) NOT LIKE 'postmaster@%'
                               AND NOT EXISTS (SELECT 1 FROM mail_message_reads mr WHERE mr.message_id=m.id)) AS unread_count,
                            (SELECT COUNT(*) FROM mail_messages m WHERE m.thread_id=t.id AND m.direction='outbound' AND m.status IN ('queued', 'sending')) AS pending_outbound_count,
                            (SELECT m.status FROM mail_messages m WHERE m.thread_id=t.id AND m.direction='outbound' ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS last_outbound_status,
                            (SELECT m.direction FROM mail_messages m WHERE m.thread_id=t.id ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS last_message_direction,
                            NULL AS manual_inbox_id
                     FROM mail_threads t JOIN requests r ON r.id=t.request_id JOIN suppliers s ON s.id=t.supplier_id
                     WHERE t.workspace_id=? AND (? = 1 OR EXISTS (
                         SELECT 1 FROM mail_messages visible_m
                         WHERE visible_m.thread_id=t.id AND (
                             visible_m.direction='inbound'
                             OR (visible_m.direction='outbound' AND visible_m.status IN ('sent', 'failed', 'delivery_unknown'))
                         )
                     ))
                     UNION ALL
                     SELECT -link.id AS id, link.request_id, COALESCE(link.supplier_id, 0) AS supplier_id,
                            inbox.subject, inbox.received_at AS last_message_at, link.created_at,
                            r.name AS request_name, COALESCE(s.name, '') AS supplier_name,
                            COALESCE(s.email, '') AS supplier_email, COALESCE(s.host, '') AS supplier_host,
                            COALESCE(s.external_key, '') AS supplier_external_key,
                            1 AS messages_count, 0 AS replies_count,
                            (SELECT COUNT(*) FROM mail_inbox_messages unread_inbox
                             WHERE unread_inbox.id=inbox.id
                               AND NOT EXISTS (SELECT 1 FROM mail_inbox_message_reads imr WHERE imr.message_id=unread_inbox.id)) AS unread_count,
                            0 AS pending_outbound_count, NULL AS last_outbound_status, 'inbound' AS last_message_direction,
                            link.inbox_message_id AS manual_inbox_id
                     FROM mail_inbox_request_links link
                     JOIN mail_inbox_messages inbox ON inbox.id=link.inbox_message_id
                     JOIN requests r ON r.id=link.request_id
                     LEFT JOIN suppliers s ON s.id=link.supplier_id
                     WHERE link.workspace_id=? AND link.active=1 AND inbox.status='matched'
                ) ORDER BY COALESCE(last_message_at, created_at) DESC""",
                (workspace_id, int(include_queue_only), workspace_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_outbox_threads(self, workspace_id: int) -> list[dict[str, Any]]:
        """Return request threads that still contain an outbound queue item.

        The correspondence view intentionally excludes queue-only threads, but
        operators still need a durable place to inspect them. Reusing the same
        summary contract keeps the outbox and correspondence views consistent.
        """
        return [
            item for item in self.list_threads(workspace_id, include_queue_only=True)
            if item.get("manual_inbox_id") is None and int(item.get("pending_outbound_count") or 0) > 0
        ]

    def list_manual_link_requests(self, workspace_id: int, query: str = "", *, limit: int = 40) -> list[dict[str, Any]]:
        """Return request options for an explicit inbox-link action.

        Search includes request metadata, positions, and known supplier fields,
        but selecting a request never chooses a supplier implicitly. The UI
        passes a supplier only when the user explicitly chooses an existing
        sender-based suggestion.
        """
        clean_query = str(query or "").strip().lower()[:200]
        limit = max(1, min(int(limit), 100))
        pattern = f"%{clean_query}%"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT r.id, r.name, r.description, r.sender_name, r.company_name,
                          COALESCE(m.status, 'draft') AS status,
                          s.name AS supplier_name, s.email AS supplier_email
                   FROM requests r
                   LEFT JOIN request_meta m ON m.request_id=r.id
                   LEFT JOIN request_suppliers rs ON rs.request_id=r.id AND COALESCE(rs.is_irrelevant, 0)=0
                   LEFT JOIN suppliers s ON s.id=rs.supplier_id
                   WHERE r.workspace_id=?
                     AND (
                       ? = ''
                       OR lower(CAST(r.id AS TEXT) || ' ' || COALESCE(r.name, '') || ' '
                               || COALESCE(r.description, '') || ' ' || COALESCE(r.sender_name, '') || ' '
                               || COALESCE(r.company_name, '') || ' ' || COALESCE(s.name, '') || ' '
                               || COALESCE(s.email, '')) LIKE ?
                       OR EXISTS (
                         SELECT 1 FROM request_positions p
                         WHERE p.request_id=r.id AND lower(COALESCE(p.name, '')) LIKE ?
                       )
                     )
                   ORDER BY r.created_at DESC, r.id DESC
                   LIMIT ?""",
                (workspace_id, clean_query, pattern, pattern, limit),
            ).fetchall()
        result: dict[int, dict[str, Any]] = {}
        for row in rows:
            request_id = int(row["id"])
            item = result.setdefault(request_id, {
                "id": request_id,
                "name": row["name"],
                "description": row["description"],
                "sender_name": row["sender_name"],
                "company_name": row["company_name"],
                "status": row["status"],
                "supplier_names": [],
                "supplier_emails": [],
            })
            if row["supplier_name"] and row["supplier_name"] not in item["supplier_names"]:
                item["supplier_names"].append(row["supplier_name"])
            if row["supplier_email"] and row["supplier_email"] not in item["supplier_emails"]:
                item["supplier_emails"].append(row["supplier_email"])
        return list(result.values())

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
                bounce = classify_bounce(
                    from_email=incoming.from_email,
                    subject=incoming.subject,
                    body_text=incoming.body_text,
                )
                bounce_addresses = failed_recipients(
                    incoming.body_text, getattr(incoming, "body_html", None),
                )
                thread = self._find_incoming_thread(connection, workspace_id, account_id, incoming)
                if not thread:
                    if bounce == "hard":
                        reported_at = incoming.received_at.astimezone(UTC).isoformat()
                        for address in bounce_addresses:
                            self._record_hard_bounce_suppression(
                                connection, workspace_id, user_id, address,
                                reported_at=reported_at,
                            )
                    # Отбойник приходит от mailer-daemon, а не от поставщика,
                    # поэтому поиск треда по адресу отправителя его никогда не
                    # находит. Без этой ветки недоставленное письмо навсегда
                    # оставалось в «Без привязки», а поставщик — со статусом
                    # «Отправлен»: закупщик считал, что письмо дошло. Адрес
                    # несостоявшегося получателя берём из тела отбойника.
                    thread = self._find_thread_for_bounce(connection, workspace_id, account_id, incoming)
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
                # A bounce isn't a reply — see Documents/28-8/suppliers-screen.md раздел 7. Only a
                # "hard" bounce (address doesn't exist) is a reliable enough signal to
                # record automatically; a "soft" one just means "try again later" and
                # is left as whatever state it already had.
                if bounce == "hard":
                    for address in bounce_addresses:
                        self._record_hard_bounce_suppression(
                            connection, workspace_id, user_id, address,
                            supplier_id=int(thread["supplier_id"]),
                            reported_at=created_at,
                        )
                    connection.execute(
                        """INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at)
                           VALUES (?, ?, ?, 'failed', ?, ?, ?)
                           ON CONFLICT(request_id, supplier_id) DO UPDATE SET mail_account_id=excluded.mail_account_id, status='failed', last_message_id=excluded.last_message_id, last_error=excluded.last_error, updated_at=excluded.updated_at""",
                        (thread["request_id"], thread["supplier_id"], account_id, message_id, "Письмо не доставлено (bounce).", created_at),
                    )
                    self._record_auto_bounce_issue(connection, thread["supplier_id"], incoming.subject, created_at)
                elif bounce is None:
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

    def list_unmatched_incoming_preview(self, workspace_id: int, *, limit: int = 5) -> list[dict[str, Any]]:
        """Лёгкая версия list_unmatched_incoming — для дашборда.

        Только id/отправитель/тема/время, без тела письма и без санитизации
        HTML: полная версия читает и очищает body_html/body_text для каждой
        строки, что оправдано на экране переписки, но не для превью из
        нескольких карточек на дашборде.
        """
        limit = max(1, min(int(limit), 20))
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, from_email, subject, received_at,
                          CASE WHEN EXISTS (
                              SELECT 1 FROM mail_inbox_message_reads r WHERE r.message_id=mail_inbox_messages.id
                          ) THEN 0 ELSE 1 END AS unread
                   FROM mail_inbox_messages
                   WHERE workspace_id=? AND status='unmatched'
                   ORDER BY received_at DESC, id DESC LIMIT ?""",
                (workspace_id, limit),
            ).fetchall()
        return [{**dict(row), "unread": bool(row["unread"])} for row in rows]

    def list_unmatched_incoming(self, workspace_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, from_email, to_email, subject, body_text, body_html, received_at, status, provider_message_id,
                          CASE WHEN EXISTS (
                              SELECT 1 FROM mail_inbox_message_reads r WHERE r.message_id=mail_inbox_messages.id
                          ) THEN 0 ELSE 1 END AS unread
                   FROM mail_inbox_messages
                   WHERE workspace_id=? AND status='unmatched'
                   ORDER BY received_at DESC, id DESC LIMIT ?""",
                (workspace_id, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = _readable_message(dict(row))
            item["unread"] = bool(item["unread"])
            result.append(item)
        return result

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

    def suggest_requests_for_inbox(self, workspace_id: int, inbox_message_id: int) -> list[dict[str, Any]]:
        """Куда, вероятно, относится неразобранное письмо.

        Автоматическая привязка (`_find_incoming_thread`) работает по
        заголовкам ответа и по паре «тема + адрес поставщика». Она не
        срабатывает, когда поставщик пишет новое письмо, а не отвечает на наше:
        нет `In-Reply-To`, а тема своя. Но адрес отправителя у нас, как
        правило, уже есть — по нему и предлагаем заявки.

        Возвращает кандидатов от сильного совпадения к слабому:
          exact  — тот же адрес, что у поставщика заявки;
          domain — адрес на домене поставщика (написал коллега с того же домена).
        Решение всё равно принимает человек: подсказка не привязывает сама.
        """
        with self.connect() as connection:
            message = connection.execute(
                "SELECT from_email FROM mail_inbox_messages WHERE id=? AND workspace_id=?",
                (inbox_message_id, workspace_id),
            ).fetchone()
            if not message:
                return []
            sender = str(message["from_email"] or "").strip().lower()
            if "@" not in sender:
                return []
            domain = sender.partition("@")[2]
            rows = connection.execute(
                """SELECT rs.request_id, rs.supplier_id, r.name AS request_name,
                          s.name AS supplier_name, s.email AS supplier_email, r.created_at
                   FROM request_suppliers rs
                   JOIN requests r ON r.id = rs.request_id
                   JOIN suppliers s ON s.id = rs.supplier_id
                   WHERE r.workspace_id=? AND s.email <> ''
                     AND (lower(s.email) = ? OR lower(s.email) LIKE ?)
                   ORDER BY r.created_at DESC""",
                (workspace_id, sender, f"%@{domain}"),
            ).fetchall()
        suggestions = []
        for row in rows:
            email = str(row["supplier_email"] or "").lower()
            suggestions.append({
                "request_id": int(row["request_id"]),
                "supplier_id": int(row["supplier_id"]),
                "request_name": row["request_name"],
                "supplier_name": row["supplier_name"],
                "supplier_email": row["supplier_email"],
                "match": "exact" if email == sender else "domain",
            })
        suggestions.sort(key=lambda item: 0 if item["match"] == "exact" else 1)
        return suggestions

    def attach_inbox_message(
        self, workspace_id: int, user_id: int, inbox_message_id: int, request_id: int, supplier_id: int,
    ) -> dict[str, int]:
        """Перенести неразобранное письмо в переписку по заявке.

        Ровно то же, что делает автоматическое сопоставление, но по решению
        человека: письмо становится входящим сообщением треда «заявка +
        поставщик», а исходная запись в «Без привязки» помечается разобранной,
        чтобы не висеть в списке дважды.

        Статус поставщика в заявке ставим «ответил» — для закупщика это и есть
        смысл действия: ответ найден и учтён.
        """
        now = iso_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            message = connection.execute(
                "SELECT * FROM mail_inbox_messages WHERE id=? AND workspace_id=? AND status='unmatched'",
                (inbox_message_id, workspace_id),
            ).fetchone()
            if not message:
                raise ValueError("Письмо не найдено или уже привязано к заявке.")
            owns = connection.execute(
                """SELECT 1 FROM request_suppliers rs JOIN requests r ON r.id=rs.request_id
                   WHERE rs.request_id=? AND rs.supplier_id=? AND r.workspace_id=?""",
                (request_id, supplier_id, workspace_id),
            ).fetchone()
            if not owns:
                raise ValueError("Такой заявки с этим поставщиком нет в рабочем пространстве.")

            account_id = message["mail_account_id"]
            subject = str(message["subject"] or "Без темы")
            thread = connection.execute(
                "SELECT id FROM mail_threads WHERE workspace_id=? AND request_id=? AND supplier_id=?",
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

            received_at = str(message["received_at"] or now)
            connection.execute(
                """INSERT INTO mail_messages(thread_id, workspace_id, user_id, request_id, supplier_id, mail_account_id,
                                             provider_message_id, message_id, in_reply_to, references_header, direction,
                                             from_email, to_email, subject, body_text, body_html, status, created_at, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'inbound', ?, ?, ?, ?, ?, 'received', ?, ?)""",
                (thread_id, workspace_id, user_id, request_id, supplier_id, account_id,
                 message["provider_message_id"], message["message_id"], message["in_reply_to"],
                 message["references_header"], message["from_email"], message["to_email"], subject,
                 message["body_text"], message["body_html"], received_at, received_at),
            )
            new_message_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            connection.execute(
                "UPDATE mail_threads SET last_message_at=CASE WHEN last_message_at IS NULL OR last_message_at < ? THEN ? ELSE last_message_at END WHERE id=?",
                (received_at, received_at, thread_id),
            )
            connection.execute(
                """INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at)
                   VALUES (?, ?, ?, 'replied', ?, NULL, ?)
                   ON CONFLICT(request_id, supplier_id) DO UPDATE SET status='replied', last_message_id=excluded.last_message_id, last_error=NULL, updated_at=excluded.updated_at""",
                (request_id, supplier_id, account_id, new_message_id, now),
            )
            connection.execute(
                "UPDATE mail_inbox_messages SET status='matched' WHERE id=?", (inbox_message_id,),
            )
            self._audit_connection(
                connection, workspace_id, user_id, "mail.inbox_attached", "mail_message", str(new_message_id),
                {"inbox_message_id": inbox_message_id, "request_id": request_id, "supplier_id": supplier_id},
            )
            connection.commit()
        return {"message_id": new_message_id, "thread_id": thread_id, "request_id": request_id, "supplier_id": supplier_id}

    def manually_link_inbox_message(
        self,
        workspace_id: int,
        user_id: int,
        inbox_message_id: int,
        request_id: int,
        supplier_id: int | None = None,
        *,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Associate one unmatched email with a request without changing mail history.

        A nullable supplier is intentional: a request association is not proof
        that the sender is a supplier. The separate link is also what makes
        changing or removing the manual decision reversible and idempotent.
        """
        if not confirmed:
            raise ValueError("Подтвердите привязку письма к заявке.")
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            message = connection.execute(
                "SELECT id, status FROM mail_inbox_messages WHERE id=? AND workspace_id=?",
                (inbox_message_id, workspace_id),
            ).fetchone()
            existing = connection.execute(
                "SELECT id, active FROM mail_inbox_request_links WHERE inbox_message_id=? AND workspace_id=?",
                (inbox_message_id, workspace_id),
            ).fetchone()
            if not message:
                raise ValueError("Письмо не найдено в текущем рабочем пространстве.")
            if message["status"] != "unmatched" and not (existing and int(existing["active"] or 0)):
                raise ValueError("Письмо уже обработано другим действием.")
            request = connection.execute(
                "SELECT id FROM requests WHERE id=? AND workspace_id=?",
                (request_id, workspace_id),
            ).fetchone()
            if not request:
                raise ValueError("Заявка не найдена в текущем рабочем пространстве.")
            if supplier_id is not None:
                supplier = connection.execute(
                    """SELECT 1 FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
                       JOIN requests r ON r.id=rs.request_id
                       WHERE rs.request_id=? AND rs.supplier_id=? AND r.workspace_id=? AND s.workspace_id=?""",
                    (request_id, supplier_id, workspace_id, workspace_id),
                ).fetchone()
                if not supplier:
                    raise ValueError("Выбранный поставщик не относится к этой заявке.")
            connection.execute(
                """INSERT INTO mail_inbox_request_links(
                       workspace_id, user_id, inbox_message_id, request_id, supplier_id,
                       source, active, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, 'manual', 1, ?, ?)
                   ON CONFLICT(inbox_message_id) DO UPDATE SET
                       workspace_id=excluded.workspace_id, user_id=excluded.user_id,
                       request_id=excluded.request_id, supplier_id=excluded.supplier_id,
                       source='manual', active=1, updated_at=excluded.updated_at""",
                (workspace_id, user_id, inbox_message_id, request_id, supplier_id, now, now),
            )
            connection.execute("UPDATE mail_inbox_messages SET status='matched' WHERE id=?", (inbox_message_id,))
            self._audit_connection(
                connection, workspace_id, user_id, "mail.inbox_manually_linked", "mail_inbox_message", str(inbox_message_id),
                {"request_id": request_id, "supplier_id": supplier_id, "source": "manual"},
            )
            connection.commit()
        return {
            "ok": True,
            "inbox_message_id": inbox_message_id,
            "request_id": request_id,
            "supplier_id": supplier_id,
            "source": "manual",
        }

    def unlink_manual_inbox_message(self, workspace_id: int, user_id: int, inbox_message_id: int) -> dict[str, Any]:
        """Remove only the manual association; the original email is preserved."""
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            link = connection.execute(
                "SELECT id, request_id, supplier_id, active FROM mail_inbox_request_links WHERE inbox_message_id=? AND workspace_id=?",
                (inbox_message_id, workspace_id),
            ).fetchone()
            if not link:
                message = connection.execute(
                    "SELECT id, status FROM mail_inbox_messages WHERE id=? AND workspace_id=?",
                    (inbox_message_id, workspace_id),
                ).fetchone()
                if not message:
                    raise ValueError("Письмо не найдено в текущем рабочем пространстве.")
                if not self.database_url:
                    connection.commit()
                return {"ok": True, "already_unlinked": True, "inbox_message_id": inbox_message_id}
            if int(link["active"] or 0):
                connection.execute(
                    "UPDATE mail_inbox_request_links SET active=0, updated_at=? WHERE id=?",
                    (now, int(link["id"])),
                )
                connection.execute(
                    "UPDATE mail_inbox_messages SET status='unmatched' WHERE id=? AND workspace_id=?",
                    (inbox_message_id, workspace_id),
                )
                self._audit_connection(
                    connection, workspace_id, user_id, "mail.inbox_manual_link_removed", "mail_inbox_message", str(inbox_message_id),
                    {"request_id": int(link["request_id"]), "supplier_id": link["supplier_id"]},
                )
            connection.commit()
        return {"ok": True, "already_unlinked": not bool(link["active"]), "inbox_message_id": inbox_message_id}

    def count_unmatched_incoming(self, workspace_id: int) -> int:
        """Сколько писем ждёт привязки — для счётчика в навигации."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM mail_inbox_messages WHERE workspace_id=? AND status='unmatched'",
                (workspace_id,),
            ).fetchone()
        return int(row[0] or 0)

    @classmethod
    def _find_thread_for_bounce(
        cls, connection: sqlite3.Connection, workspace_id: int, account_id: int, incoming: Any,
    ) -> dict[str, int] | None:
        """Тред по адресу из тела отбойника, а не по его отправителю.

        Срабатывает только если письмо действительно распознано как отбойник
        (classify_bounce) — иначе обычное письмо, где в тексте упомянут чужой
        адрес, могло бы подцепиться к чужому треду.

        Если разобрать адрес не удалось или он не соответствует ни одному
        поставщику, возвращает None: письмо останется в «Без привязки». Это
        сознательный выбор — пометить не того поставщика недоставленным хуже,
        чем оставить отбойник неразобранным.
        """
        if classify_bounce(
            from_email=incoming.from_email, subject=incoming.subject, body_text=incoming.body_text
        ) is None:
            return None
        addresses = failed_recipients(incoming.body_text, getattr(incoming, "body_html", None))
        if not addresses:
            return None
        placeholders = ",".join("?" for _ in addresses)
        row = connection.execute(
            f"""SELECT t.id AS thread_id, t.request_id, t.supplier_id
                FROM mail_threads t JOIN suppliers s ON s.id = t.supplier_id
                WHERE t.workspace_id=? AND t.mail_account_id=?
                  AND lower(s.email) IN ({placeholders})
                ORDER BY t.last_message_at DESC LIMIT 1""",
            (workspace_id, account_id, *addresses),
        ).fetchone()
        if not row:
            return None
        return {
            "thread_id": int(row["thread_id"]),
            "request_id": int(row["request_id"]),
            "supplier_id": int(row["supplier_id"]),
        }

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

    def is_suppressed(self, workspace_id: int, external_key: str | None = None, email: str | None = None) -> bool:
        """Final pre-send suppression check using the existing blacklist model."""

        key = str(external_key or "").strip().lower()
        normalized_email = str(email or "").strip().lower()
        with self.connect() as connection:
            if key and connection.execute(
                "SELECT 1 FROM blacklist_entries WHERE workspace_id=? AND external_key=? AND restored_at IS NULL LIMIT 1",
                (workspace_id, key),
            ).fetchone():
                return True
            if normalized_email and connection.execute(
                "SELECT 1 FROM blacklist_entries WHERE workspace_id=? AND level='email' AND external_key=? AND restored_at IS NULL LIMIT 1",
                (workspace_id, self._email_suppression_key(normalized_email)),
            ).fetchone():
                return True
            if normalized_email and connection.execute(
                """SELECT 1 FROM blacklist_entries b JOIN suppliers s ON s.external_key=b.external_key
                   WHERE b.workspace_id=? AND b.restored_at IS NULL AND LOWER(s.email)=? LIMIT 1""",
                (workspace_id, normalized_email),
                ).fetchone():
                return True
        return False

    def deliverability_flags(
        self,
        workspace_id: int,
        request_id: int,
        *,
        external_key: str | None = None,
        email: str | None = None,
        supplier_id: int | None = None,
    ) -> dict[str, Any]:
        """Read existing suppression, bounce and uncertainty evidence only."""

        key = str(external_key or "").strip().lower()
        normalized_email = str(email or "").strip().lower()
        with self.connect() as connection:
            supplier_query = """SELECT s.id, s.external_key, s.email, s.name, s.host,
                          COALESCE(rs.status, '') AS request_supplier_status,
                          COALESCE(rs.last_error, '') AS request_supplier_error,
                          lm.direction AS last_message_direction,
                          lm.from_email AS last_message_from,
                          lm.subject AS last_message_subject,
                          lm.body_text AS last_message_body
                   FROM suppliers s
                   LEFT JOIN request_suppliers rlink
                     ON rlink.supplier_id=s.id AND rlink.request_id=?
                   LEFT JOIN request_supplier_states rs
                     ON rs.supplier_id=s.id AND rs.request_id=?
                   LEFT JOIN mail_messages lm ON lm.id=rs.last_message_id
                   WHERE s.workspace_id=?
                     AND ((? IS NOT NULL AND s.id=?)
                          OR (? IS NULL AND ((? <> '' AND LOWER(s.external_key)=?)
                              OR (? <> '' AND LOWER(s.email)=?))))
                   ORDER BY s.id DESC LIMIT 1"""
            supplier = connection.execute(
                supplier_query,
                (request_id, request_id, workspace_id, supplier_id, supplier_id, supplier_id, key, key, normalized_email, normalized_email),
            ).fetchone()
            unresolved = False
            if supplier:
                unresolved = bool(connection.execute(
                    """SELECT 1 FROM mail_jobs j
                       JOIN mail_messages m ON m.id=j.message_id
                       WHERE m.workspace_id=? AND m.request_id=? AND m.supplier_id=?
                         AND j.status='delivery_unknown' AND m.status='delivery_unknown'
                       LIMIT 1""",
                    (workspace_id, request_id, supplier["id"]),
                ).fetchone())
        hard_bounce = False
        if supplier:
            hard_bounce = (
                supplier["request_supplier_status"] == "failed"
                and (
                    classify_bounce(
                        from_email=supplier["last_message_from"] or "",
                        subject=supplier["last_message_subject"] or "",
                        body_text=supplier["last_message_body"] or "",
                    ) == "hard"
                    or "bounce" in (supplier["request_supplier_error"] or "").lower()
                )
            )
        return {
            "supplier_id": int(supplier["id"]) if supplier else None,
            "suppressed": self.is_suppressed(workspace_id, key, normalized_email),
            "hard_bounce": hard_bounce,
            "unresolved_delivery_unknown": unresolved,
        }

    def email_identity_groups(self, workspace_id: int, email: str) -> dict[tuple[str, int], list[int]]:
        """Return exact-email identity groups without changing supplier data.

        A valid global/INN identity is one group even when it has several host
        rows.  An unlinked row remains its own group; this deliberately makes a
        shared email visible as a warning instead of silently merging companies.
        """

        normalized_email = _normalized_mail_address(email)
        if not normalized_email:
            return {}
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT s.id, COALESCE(p.inn, '') AS inn, gl.global_supplier_id
                   FROM suppliers s
                   LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                   LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                   WHERE s.workspace_id=? AND lower(trim(COALESCE(s.email, '')))=?
                   ORDER BY s.id""",
                (workspace_id, normalized_email),
            ).fetchall()
        groups: dict[tuple[str, int], list[int]] = {}
        for row in rows:
            key = (
                ("global", int(row["global_supplier_id"]))
                if row["global_supplier_id"] is not None and _is_valid_company_inn(row["inn"])
                else ("supplier", int(row["id"]))
            )
            groups.setdefault(key, []).append(int(row["id"]))
        return groups

    def request_email_was_contacted(self, workspace_id: int, request_id: int, email: str) -> bool:
        """Return whether this normalized email already has outbound history in a request."""

        normalized_email = _normalized_mail_address(email)
        if not normalized_email:
            return False
        with self.connect() as connection:
            row = connection.execute(
                """SELECT 1
                   FROM mail_messages
                   WHERE workspace_id=? AND request_id=? AND direction='outbound'
                     AND lower(trim(to_email))=?
                   LIMIT 1""",
                (workspace_id, request_id, normalized_email),
            ).fetchone()
        return row is not None

    def get_request(self, workspace_id: int, request_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                f"""SELECT {self._REQUEST_SELECT_COLUMNS}
                   FROM requests r {self._REQUEST_SELECT_JOIN}
                   WHERE r.workspace_id=? AND r.id=?""",
                (workspace_id, request_id),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["mail_metrics"] = self._request_mail_metrics(connection, request_id)
        return result

    def request_positions(self, workspace_id: int, request_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT p.id, p.position_key, p.name, p.quantity FROM request_positions p JOIN requests r ON r.id=p.request_id WHERE p.request_id=? AND r.workspace_id=? ORDER BY p.id",
                (request_id, workspace_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def request_supplier(self, workspace_id: int, request_id: int, supplier_id: int) -> dict[str, Any] | None:
        """Return the request-scoped supplier context after ownership checks."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT s.id, s.external_key, s.name, s.email, s.host,
                          COALESCE(p.phone, '') AS phone, COALESCE(p.inn, '') AS inn
                   FROM suppliers s
                   JOIN request_suppliers rs ON rs.supplier_id=s.id AND rs.request_id=?
                   LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                   WHERE s.id=? AND s.workspace_id=?""",
                (request_id, supplier_id, workspace_id),
            ).fetchone()
        return dict(row) if row else None

    def set_supplier_manual_inn(
        self, workspace_id: int, user_id: int, request_id: int, supplier_id: int, inn: str,
    ) -> dict[str, Any]:
        """Persist an explicitly entered ИНН and link the host to its global card.

        Checko enrichment is deliberately performed by SupplierApp after this
        method succeeds. That keeps the manual value durable even when Checko
        is unavailable, and leaves a clear source marker for later UI/API use.
        """
        inn = "".join(ch for ch in str(inn or "") if ch.isdigit())
        if not validate_inn_checksum(inn):
            raise ValueError("Проверьте ИНН: нужно корректное 10- или 12-значное число.")
        context = self.request_supplier(workspace_id, request_id, supplier_id)
        if not context:
            raise ValueError("Поставщик не найден в этой заявке.")
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO supplier_profiles(supplier_id, inn, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(supplier_id) DO UPDATE SET inn=excluded.inn, updated_at=excluded.updated_at""",
                (supplier_id, inn, now),
            )
            connection.execute(
                """INSERT INTO supplier_inn_sources(supplier_id, source_type, updated_by, updated_at)
                   VALUES (?, 'manual', ?, ?)
                   ON CONFLICT(supplier_id) DO UPDATE SET source_type='manual', updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (supplier_id, user_id, now),
            )
            global_id = self._get_or_create_global_supplier(
                connection, workspace_id, inn,
                name=str(context.get("name") or ""), site=str(context.get("host") or ""),
                email=str(context.get("email") or ""), phone=str(context.get("phone") or ""),
            )
            self._link_supplier_global(connection, supplier_id, global_id)
            self._audit_connection(
                connection, workspace_id, user_id, "supplier.inn_manual", "supplier", str(supplier_id),
                {"request_id": request_id, "inn": inn},
            )
        self.record_supplier_evidence(workspace_id, str(context.get("host") or ""), [{
            "field_name": "inn",
            "field_value": inn,
            "source_type": "manual",
            "source_url": "",
            "strength": "strong",
            "score": 100,
            "decision": "accepted",
            "details": {"entered_by": "user"},
        }])
        return {"supplier_id": supplier_id, "inn": inn, "global_supplier_id": global_id}

    def suppliers_with_email(self, workspace_id: int, hosts: list[str]) -> set[str]:
        """Hosts in this workspace that already have an email from a past search.

        Used to skip re-crawling/re-paying for a site whose contact we already
        found in an earlier заявка — see Documents/28-8/PROJECT_DOCUMENTATION.md §16.
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

    def blacklisted_hosts(self, workspace_id: int, hosts: list[str]) -> set[str]:
        """Какие из hosts подпадают под активную запись чёрного списка.

        Тот же LIKE-хвост, что и в list_suppliers: запись «ozon.com» должна
        закрывать и am.ozon.com. Используется до обхода/обогащения — чтобы
        не тратить Checko/LLM на сайт, который заведомо не поставщик
        (маркетплейс по умолчанию — см. _seed_default_blacklist), а не только
        прятать его в списке постфактум.
        """
        hosts = [h.strip().lower() for h in hosts if h and h.strip()]
        if not hosts:
            return set()
        with self.connect() as connection:
            entries = connection.execute(
                "SELECT external_key FROM blacklist_entries WHERE workspace_id=? AND restored_at IS NULL",
                (workspace_id,),
            ).fetchall()
        domains = [row[0] for row in entries]
        if not domains:
            return set()
        return {
            host for host in hosts
            if any(host == d or host.endswith("." + d) for d in domains)
        }

    def suppliers_missing_email(self, workspace_id: int, hosts: list[str]) -> list[tuple[str, str]]:
        """(host, ИНН) для поставщиков с известным ИНН, но без почты.

        Симметрично suppliers_missing_inn: тот чинит «есть почта, нет ИНН»,
        этот — обратный случай. Оба возникают по одной причине — обход нашёл
        что-то одно, но не всё сразу, — и Checko здесь идёт последним, а не
        первым источником (см. SupplierApp._resolve_missing_email): почта из
        реестра принимается, только если её домен совпадает с доменом сайта.
        """
        hosts = [h.strip().lower() for h in hosts if h and h.strip()]
        if not hosts:
            return []
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in hosts)
            rows = connection.execute(
                f"""SELECT s.external_key, p.inn FROM suppliers s
                    JOIN supplier_profiles p ON p.supplier_id = s.id
                    WHERE s.workspace_id=? AND p.inn <> '' AND s.email = ''
                      AND s.external_key IN ({placeholders})""",
                (workspace_id, *hosts),
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def suppliers_missing_inn(self, workspace_id: int, hosts: list[str]) -> list[tuple[str, str]]:
        """(host, email) для сайтов с почтой, но вообще без ИНН.

        Отдельная дыра рядом с suppliers_missing_registry: тот проход чинит
        только записи, у которых ИНН уже есть. Сайт, чью почту нашли раньше,
        а ИНН не нашли (не было на странице, или он ещё не искался в реестре),
        не попадал никуда: обход ему пропускают как «уже известному», а в
        догрузку реестра он не проходит по условию `p.inn <> ''`. Такой
        поставщик оставался без юрлица навсегда — ровно то, что владелец
        проекта увидел на заявке №1053.
        """
        hosts = [h.strip().lower() for h in hosts if h and h.strip()]
        if not hosts:
            return []
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in hosts)
            rows = connection.execute(
                f"""SELECT s.external_key, s.email FROM suppliers s
                    LEFT JOIN supplier_profiles p ON p.supplier_id = s.id
                    WHERE s.workspace_id=? AND COALESCE(p.inn, '') = ''
                      AND s.external_key IN ({placeholders})""",
                (workspace_id, *hosts),
            ).fetchall()
        return [(row[0], row[1] or "") for row in rows]

    def upsert_supplier(
        self, *, workspace_id: int, external_key: str, name: str, email: str, host: str,
        request_id: int | None = None,
    ) -> int:
        """Создать/обновить поставщика; при указанном request_id — привязать к заявке.

        Привязка нужна, потому что поставщик может появиться не только из
        поиска (upsert_search_result уже пишет request_suppliers), но и из
        отправки письма напрямую. Без неё письмо уходило, статус писался в
        request_supplier_states, а в списке поставщиков заявки строки не было
        вовсе — отправленное письмо становилось невидимым в интерфейсе.
        """
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO suppliers(workspace_id, external_key, name, email, host, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(workspace_id, external_key) DO UPDATE SET name=excluded.name, email=CASE WHEN excluded.email <> '' THEN excluded.email ELSE suppliers.email END, host=excluded.host, updated_at=excluded.updated_at""",
                (workspace_id, external_key, name, email, host, now, now),
            )
            supplier_id = int(connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id = ? AND external_key = ?", (workspace_id, external_key)
            ).fetchone()[0])
            if request_id is not None:
                connection.execute(
                    """INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at)
                       VALUES (?, ?, '[]', ?, 'manual', ?)
                       ON CONFLICT(request_id, supplier_id) DO NOTHING""",
                    (request_id, supplier_id, "Добавлен при отправке письма.", now),
                )
            return supplier_id

    def resolve_supplier_for_send(
        self,
        *,
        workspace_id: int,
        request_id: int,
        supplier_id: int | None,
        email: str,
        name: str,
        host: str,
        external_key: str,
    ) -> dict[str, Any]:
        """Resolve the durable supplier identity before assembling a send.

        A selected row is authoritative only after the workspace/request
        ownership check.  A manual address may reuse an existing supplier only
        when the exact email identifies one unambiguous workspace identity;
        otherwise it is rejected instead of silently creating or merging data.
        """
        normalized_email = str(email or "").strip().lower()
        normalized_host = str(host or "").strip().lower()
        normalized_key = str(external_key or normalized_host or normalized_email).strip().lower()
        clean_name = str(name or "").strip()[:240]
        now = iso_now()
        with self.connect() as connection:
            if not connection.execute(
                "SELECT 1 FROM requests WHERE id=? AND workspace_id=?",
                (request_id, workspace_id),
            ).fetchone():
                raise ValueError("Заявка не найдена в текущем рабочем пространстве.")

            row = None
            if supplier_id is not None:
                row = connection.execute(
                    """SELECT s.id, s.external_key, s.name, s.email, s.host,
                              COALESCE(p.inn, '') AS inn, gl.global_supplier_id
                       FROM suppliers s
                       JOIN request_suppliers rs ON rs.supplier_id=s.id AND rs.request_id=?
                       LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                       LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                       WHERE s.id=? AND s.workspace_id=?""",
                    (request_id, int(supplier_id), workspace_id),
                ).fetchone()
                if not row:
                    raise ValueError("Выбранный поставщик не найден в этой заявке.")
                stored_email = str(row["email"] or "").strip().lower()
                if stored_email and stored_email != normalized_email:
                    raise ValueError("Email не совпадает с выбранным поставщиком.")
            else:
                candidates = connection.execute(
                    """SELECT s.id, s.external_key, s.name, s.email, s.host,
                              COALESCE(p.inn, '') AS inn, gl.global_supplier_id
                       FROM suppliers s
                       LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                       LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                       WHERE s.workspace_id=? AND LOWER(s.email)=?
                       ORDER BY CASE WHEN gl.global_supplier_id IS NOT NULL THEN 0 ELSE 1 END,
                                CASE WHEN s.host<>'' THEN 0 ELSE 1 END, s.id""",
                    (workspace_id, normalized_email),
                ).fetchall()
                global_ids = {int(candidate["global_supplier_id"]) for candidate in candidates if candidate["global_supplier_id"] is not None}
                if len(global_ids) > 1 or (not global_ids and len(candidates) > 1):
                    raise ValueError("Этот email связан с несколькими поставщиками. Выберите конкретную строку компании.")
                if candidates:
                    row = candidates[0]

                # A host is a safe fallback only when its exact external key
                # points to one row and its stored email is empty or identical.
                if row is None and normalized_host:
                    host_candidates = connection.execute(
                        """SELECT s.id, s.external_key, s.name, s.email, s.host,
                                  COALESCE(p.inn, '') AS inn, gl.global_supplier_id
                           FROM suppliers s
                           LEFT JOIN supplier_profiles p ON p.supplier_id=s.id
                           LEFT JOIN global_supplier_links gl ON gl.supplier_id=s.id
                           WHERE s.workspace_id=? AND LOWER(s.external_key)=?
                           ORDER BY s.id""",
                        (workspace_id, normalized_key),
                    ).fetchall()
                    if len(host_candidates) > 1:
                        raise ValueError("Сайт связан с несколькими поставщиками. Выберите конкретную строку компании.")
                    if host_candidates:
                        candidate = host_candidates[0]
                        stored_email = str(candidate["email"] or "").strip().lower()
                        if stored_email and stored_email != normalized_email:
                            raise ValueError("Email не совпадает с найденным сайтом поставщика.")
                        row = candidate

            if row is not None:
                resolved_id = int(row["id"])
                stored_email = str(row["email"] or "").strip().lower()
                if not stored_email and normalized_email:
                    connection.execute(
                        "UPDATE suppliers SET email=?, updated_at=? WHERE id=?",
                        (normalized_email, now, resolved_id),
                    )
                connection.execute(
                    """INSERT INTO request_suppliers(request_id, supplier_id, position_keys_json, reason, source, updated_at)
                       VALUES (?, ?, '[]', ?, 'manual', ?)
                       ON CONFLICT(request_id, supplier_id) DO NOTHING""",
                    (request_id, resolved_id, "Добавлен при отправке письма.", now),
                )
                return {
                    "supplier_id": resolved_id,
                    "global_supplier_id": int(row["global_supplier_id"]) if row["global_supplier_id"] is not None else None,
                    "inn": str(row["inn"] or ""),
                    "external_key": str(row["external_key"] or normalized_key),
                    "name": str(row["name"] or clean_name),
                    "email": normalized_email or str(row["email"] or ""),
                    "host": str(row["host"] or normalized_host),
                    "existing_supplier": True,
                }

        resolved_id = self.upsert_supplier(
            workspace_id=workspace_id,
            external_key=normalized_key,
            name=clean_name,
            email=normalized_email,
            host=normalized_host,
            request_id=request_id,
        )
        return {
            "supplier_id": resolved_id,
            "global_supplier_id": None,
            "inn": "",
            "external_key": normalized_key,
            "name": clean_name,
            "email": normalized_email,
            "host": normalized_host,
            "existing_supplier": False,
        }

    def update_search_progress(self, workspace_id: int, request_id: int, progress: int) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE request_meta SET search_progress=?, updated_at=? WHERE request_id=? AND EXISTS (SELECT 1 FROM requests WHERE id=? AND workspace_id=?)", (progress, iso_now(), request_id, request_id, workspace_id))

    def upsert_search_result(self, workspace_id: int, request_id: int, position_key: str, *, host: str, title: str, snippet: str, source: str = "xmlriver", url: str = "") -> int:
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
            # Ссылка на саму страницу выдачи — чтобы «Почему найден» можно было
            # проверить, а не только прочитать. Одна строка на позицию: по
            # разным ключам поставщик находится разными страницами.
            if url:
                connection.execute(
                    """INSERT INTO search_result_sources(request_id, supplier_id, position_key, url, title, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(request_id, supplier_id, position_key)
                       DO UPDATE SET url=excluded.url, title=excluded.title, updated_at=excluded.updated_at""",
                    (request_id, supplier_id, position_key, str(url)[:500], str(title or "")[:240], now),
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
        finance_history: list[tuple[int, int | None, int | None]] | None = None,
        risks: list[str] | None = None,
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
            profile = connection.execute(
                "SELECT COALESCE(inn, '') AS inn FROM supplier_profiles WHERE supplier_id=?",
                (supplier_id,),
            ).fetchone()
            source = connection.execute(
                "SELECT source_type FROM supplier_inn_sources WHERE supplier_id=?",
                (supplier_id,),
            ).fetchone()
            # An explicit user value has higher priority than a later weak
            # crawler candidate. Checko may still enrich the same INN below,
            # but automatic discovery must not silently replace it.
            manual_inn = bool(source and source["source_type"] == "manual")
            current_inn = str(profile["inn"] or "") if profile else ""
            effective_inn = current_inn if manual_inn else str(inn or "")
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
                (effective_inn, effective_inn, phone, phone, region, region, role, role, now, supplier_id),
            )
            if effective_inn:
                global_id = self._get_or_create_global_supplier(
                    connection, workspace_id, effective_inn, name=company_name, site=host, email=email, phone=phone,
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
                if finance_history:
                    self._upsert_finance_history(connection, global_id, finance_history)
                # risks=[] (не None) значит «Checko проверил, факторов риска
                # нет» — это не то же самое, что «риски не проверялись», и
                # заслуживает своей зелёной пометки, а не пустого места.
                if risks is not None:
                    self._upsert_risk_facts(connection, global_id, risks)

    def record_supplier_evidence(
        self, workspace_id: int, host: str, items: list[dict[str, Any]],
    ) -> None:
        """Сохранить происхождение кандидатов и решений без потери истории."""
        if not items:
            return
        host = str(host or "").strip().lower()
        now = iso_now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM suppliers WHERE workspace_id=? AND external_key=?",
                (workspace_id, host),
            ).fetchone()
            if not row:
                return
            supplier_id = int(row[0])
            for item in items:
                field_name = str(item.get("field_name") or "").strip()[:40]
                field_value = str(item.get("field_value") or "").strip()[:500]
                if not field_name or not field_value:
                    continue
                source_type = str(item.get("source_type") or "")[:40]
                source_url = str(item.get("source_url") or "")[:1000]
                strength = str(item.get("strength") or "weak")[:20]
                decision = str(item.get("decision") or "observed")[:20]
                try:
                    score = max(0, min(100, int(item.get("score") or 0)))
                except (TypeError, ValueError):
                    score = 0
                details = item.get("details") or {}
                details_json = json.dumps(details, ensure_ascii=False, sort_keys=True)[:5000]
                connection.execute(
                    """INSERT INTO supplier_evidence(
                           workspace_id, supplier_id, field_name, field_value,
                           source_type, source_url, strength, score, decision,
                           details_json, first_seen_at, last_seen_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(supplier_id, field_name, field_value, source_type, source_url)
                       DO UPDATE SET strength=excluded.strength, score=excluded.score,
                           decision=excluded.decision, details_json=excluded.details_json,
                           last_seen_at=excluded.last_seen_at""",
                    (
                        workspace_id, supplier_id, field_name, field_value,
                        source_type, source_url, strength, score, decision,
                        details_json, now, now,
                    ),
                )

    def list_supplier_evidence(self, workspace_id: int, host: str) -> list[dict[str, Any]]:
        """Диагностический/API-ready вид графа доказательств."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT e.field_name, e.field_value, e.source_type, e.source_url,
                          e.strength, e.score, e.decision, e.details_json,
                          e.first_seen_at, e.last_seen_at
                   FROM supplier_evidence e
                   JOIN suppliers s ON s.id=e.supplier_id
                   WHERE e.workspace_id=? AND s.external_key=?
                   ORDER BY e.score DESC, e.last_seen_at DESC""",
                (workspace_id, str(host or "").strip().lower()),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.pop("details_json") or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                item["details"] = {}
                item.pop("details_json", None)
            result.append(item)
        return result

    # ---------------------------------------------------- enrichment retry queue

    def enqueue_enrichment_job(
        self, workspace_id: int, host: str, stage: str, *,
        context: dict[str, Any] | None = None, error: str = "",
        retry_after_seconds: int = 60,
    ) -> None:
        if stage not in {"crawl", "registry", "web", "finance"}:
            raise ValueError(f"Неизвестный этап обогащения: {stage}")
        host = str(host or "").strip().lower()
        if not host:
            return
        now = iso_now()
        next_attempt = iso_after(max(1, int(retry_after_seconds)))
        context_json = json.dumps(context or {}, ensure_ascii=False, sort_keys=True)[:20_000]
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO supplier_enrichment_jobs(
                       workspace_id, host, stage, context_json, status, attempts,
                       next_attempt_at, claim_token, locked_until, last_error,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, 'queued', 0, ?, NULL, NULL, ?, ?, ?)
                   ON CONFLICT(workspace_id, host, stage) DO UPDATE SET
                       context_json=excluded.context_json,
                       status=CASE WHEN supplier_enrichment_jobs.status='processing'
                                   THEN supplier_enrichment_jobs.status ELSE 'queued' END,
                       attempts=CASE WHEN supplier_enrichment_jobs.status IN ('completed','failed')
                                     THEN 0 ELSE supplier_enrichment_jobs.attempts END,
                       next_attempt_at=CASE WHEN supplier_enrichment_jobs.status='processing'
                                            THEN supplier_enrichment_jobs.next_attempt_at
                                            ELSE excluded.next_attempt_at END,
                       last_error=excluded.last_error,
                       updated_at=excluded.updated_at""",
                (
                    workspace_id, host, stage, context_json, next_attempt,
                    str(error or "")[:500], now, now,
                ),
            )

    def claim_enrichment_job(self, workspace_id: int) -> dict[str, Any] | None:
        now = iso_now()
        token = new_token(24)
        locked_until = iso_after(120)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = connection.execute(
                """SELECT id FROM supplier_enrichment_jobs
                   WHERE workspace_id=?
                     AND ((status='queued' AND next_attempt_at<=?)
                          OR (status='processing' AND locked_until IS NOT NULL AND locked_until<?))
                   ORDER BY next_attempt_at, updated_at LIMIT 1""",
                (workspace_id, now, now),
            ).fetchone()
            if not candidate:
                return None
            job_id = int(candidate[0])
            connection.execute(
                """UPDATE supplier_enrichment_jobs
                   SET status='processing', claim_token=?, locked_until=?,
                       attempts=attempts+1, updated_at=?
                   WHERE id=? AND ((status='queued' AND next_attempt_at<=?)
                       OR (status='processing' AND locked_until IS NOT NULL AND locked_until<?))""",
                (token, locked_until, now, job_id, now, now),
            )
            row = connection.execute(
                """SELECT id, workspace_id, host, stage, context_json, attempts,
                          claim_token, last_error
                   FROM supplier_enrichment_jobs WHERE id=? AND claim_token=?""",
                (job_id, token),
            ).fetchone()
        if not row:
            return None
        job = dict(row)
        try:
            job["context"] = json.loads(job.pop("context_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            job["context"] = {}
            job.pop("context_json", None)
        return job

    def retry_enrichment_job(
        self, job: dict[str, Any], error: str, *, retry_after_seconds: int,
        max_attempts: int = 12,
    ) -> bool:
        """Вернуть только неудавшийся этап в очередь; False — лимит исчерпан."""
        attempts = int(job.get("attempts") or 0)
        retry = attempts < max_attempts
        now = iso_now()
        next_attempt = iso_after(max(1, int(retry_after_seconds)))
        with self.connect() as connection:
            connection.execute(
                """UPDATE supplier_enrichment_jobs
                   SET status=?, next_attempt_at=?, claim_token=NULL,
                       locked_until=NULL, last_error=?, updated_at=?
                   WHERE id=? AND status='processing' AND claim_token=?""",
                (
                    "queued" if retry else "failed", next_attempt,
                    str(error or "")[:500], now, job["id"], job["claim_token"],
                ),
            )
        return retry

    def complete_enrichment_job(self, job: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """UPDATE supplier_enrichment_jobs
                   SET status='completed', claim_token=NULL, locked_until=NULL,
                       last_error='', updated_at=?
                   WHERE id=? AND status='processing' AND claim_token=?""",
                (iso_now(), job["id"], job["claim_token"]),
            )

    def list_enrichment_jobs(self, workspace_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, host, stage, status, attempts, next_attempt_at,
                          last_error, updated_at
                   FROM supplier_enrichment_jobs WHERE workspace_id=?
                   ORDER BY updated_at DESC""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def enrichment_workspace_ids(self) -> list[int]:
        """Workspaces that currently have a due or recoverable enrichment job."""
        now = iso_now()
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT DISTINCT workspace_id FROM supplier_enrichment_jobs
                   WHERE (status='queued' AND next_attempt_at<=?)
                      OR (status='processing' AND locked_until IS NOT NULL AND locked_until<?)
                   ORDER BY workspace_id""",
                (now, now),
            ).fetchall()
        return [int(row[0]) for row in rows]

    # --------------------------------------------------------- global suppliers
    #
    # See Documents/28-8/suppliers-screen.md. A "global supplier" is a workspace-wide
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
    def _upsert_finance_history(
        connection: sqlite3.Connection, global_supplier_id: int,
        history: list[tuple[int, int | None, int | None]],
    ) -> None:
        """Сохранить динамику по годам целиком (см. migrations/014).

        Перезапись, а не пропуск существующих: Росстат уточняет отчётность
        задним числом, и свежий ответ Checko вернее того, что мы записали
        месяц назад.
        """
        if not history:
            return
        now = iso_now()
        connection.executemany(
            "INSERT INTO global_supplier_finance_history(global_supplier_id, report_year, revenue, profit, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(global_supplier_id, report_year) DO UPDATE SET "
            "revenue=excluded.revenue, profit=excluded.profit, updated_at=excluded.updated_at",
            [(global_supplier_id, year, revenue, profit, now) for year, revenue, profit in history],
        )

    @staticmethod
    def _upsert_risk_facts(connection: sqlite3.Connection, global_supplier_id: int, risks: list[str]) -> None:
        """Сохранить факторы риска целиком (см. migrations/015).

        Полная перезапись, не слияние: Checko публикует данные ЕГРЮЛ/ЕГРИП
        ежедневно, и вчерашний список рисков (например, «дисквалифицированное
        лицо в руководстве») мог перестать быть верным — старое значение не
        копить, а заменять свежим.
        """
        connection.execute(
            "INSERT INTO global_supplier_risks(global_supplier_id, risks_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(global_supplier_id) DO UPDATE SET risks_json=excluded.risks_json, updated_at=excluded.updated_at",
            (global_supplier_id, json.dumps(risks, ensure_ascii=False), iso_now()),
        )

    @staticmethod
    def _record_hard_bounce_suppression(
        connection: sqlite3.Connection,
        workspace_id: int,
        user_id: int,
        email: str,
        *,
        reported_at: str,
        supplier_id: int | None = None,
    ) -> None:
        """Persist a confirmed hard-bounce address in existing blacklist storage.

        The email-level key prevents a later request using another external key
        from bypassing a confirmed address failure. Soft bounces never call
        this helper.
        """
        normalized = str(email or "").strip().lower()
        if "@" not in normalized:
            return
        suppression_key = MailRepository._email_suppression_key(normalized)
        existing = connection.execute(
            "SELECT id FROM blacklist_entries WHERE workspace_id=? AND level='email' AND external_key=? AND restored_at IS NULL LIMIT 1",
            (workspace_id, suppression_key),
        ).fetchone()
        if existing:
            return
        connection.execute(
            "INSERT INTO blacklist_entries(workspace_id, supplier_id, external_key, company_name, level, reason, created_by, created_at) VALUES (?, ?, ?, ?, 'email', 'hard_bounce', ?, ?)",
            (workspace_id, supplier_id, suppression_key, normalized, user_id, reported_at),
        )
        MailRepository._audit_connection(
            connection, workspace_id, user_id, "supplier.email_suppressed", "email", suppression_key,
            {"reason": "hard_bounce", "source": "incoming_bounce"},
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
            # Динамика по годам (migrations/014): для закупщика направление
            # важнее абсолютной цифры. Последние 6 лет — столько помещается в
            # карточку и столько имеет смысл: более старая отчётность о
            # сегодняшней надёжности поставщика уже мало что говорит.
            finance_history_rows = connection.execute(
                "SELECT report_year, revenue, profit FROM global_supplier_finance_history "
                "WHERE global_supplier_id=? ORDER BY report_year DESC LIMIT 6",
                (global_supplier_id,),
            ).fetchall()
            supplier["finance_history"] = [
                {"report_year": r["report_year"], "revenue": r["revenue"], "profit": r["profit"]}
                for r in reversed(finance_history_rows)
            ]
            risk_row = connection.execute(
                "SELECT risks_json FROM global_supplier_risks WHERE global_supplier_id=?",
                (global_supplier_id,),
            ).fetchone()
            supplier["risks"] = json.loads(risk_row["risks_json"]) if risk_row else None
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
            "registry": None, "finances": None, "risks": None,
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
        for row in connection.execute(
            f"SELECT global_supplier_id, risks_json FROM global_supplier_risks WHERE global_supplier_id IN ({gs_ph})",
            gs_ids,
        ).fetchall():
            summaries[int(row["global_supplier_id"])]["risks"] = json.loads(row["risks_json"])
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
                JOIN blacklist_entries b ON b.workspace_id=s.workspace_id AND b.restored_at IS NULL
                    AND (s.external_key=b.external_key OR s.external_key LIKE '%.' || b.external_key)
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
            "risks": summary.get("risks"),
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

    # ------------------------------------------------ workspace mail template

    def get_mail_template(self, workspace_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT subject, body_text, updated_at FROM workspace_mail_templates WHERE workspace_id=?",
                (workspace_id,),
            ).fetchone()
            if not row:
                return None
            attachments = connection.execute(
                """SELECT filename, mime_type, size_bytes, content
                   FROM workspace_mail_template_attachments
                   WHERE workspace_id=? ORDER BY id""",
                (workspace_id,),
            ).fetchall()
        return {**dict(row), "attachments": [dict(item) for item in attachments]}

    def save_mail_template(
        self, workspace_id: int, user_id: int, *, subject: str, body_text: str,
        attachments: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        """Atomically replace the workspace template and its attachment set."""
        now = iso_now()
        items = list(attachments)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO workspace_mail_templates(
                       workspace_id, subject, body_text, updated_by, updated_at
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(workspace_id) DO UPDATE SET
                       subject=excluded.subject, body_text=excluded.body_text,
                       updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (workspace_id, subject, body_text, user_id, now),
            )
            connection.execute(
                "DELETE FROM workspace_mail_template_attachments WHERE workspace_id=?",
                (workspace_id,),
            )
            for item in items:
                connection.execute(
                    """INSERT INTO workspace_mail_template_attachments(
                           workspace_id, filename, mime_type, size_bytes, content
                       ) VALUES (?, ?, ?, ?, ?)""",
                    (
                        workspace_id, item["filename"], item["mime_type"],
                        item["size_bytes"], item["content"],
                    ),
                )
            self._audit_connection(
                connection, workspace_id, user_id, "mail_template.updated",
                "workspace_mail_template", str(workspace_id),
                {
                    "subject_length": len(subject),
                    "body_length": len(body_text),
                    "attachments": [
                        {"filename": item["filename"], "size_bytes": item["size_bytes"]}
                        for item in items
                    ],
                },
            )
        return self.get_mail_template(workspace_id) or {}

    # --------------------------------------------- outgoing send operations

    def _ensure_request_email_guard_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        workspace_id: int,
        request_id: int,
        normalized_email: str,
        operation_id: int,
        allow_existing: bool = False,
        source_message_id: int | None = None,
    ) -> bool:
        """Claim the durable request/email guard for one logical outreach.

        Initial outreach must create a fresh guard.  A provider continuation
        or a proven cross-provider rejection may reuse the existing guard, but
        only when it names the exact source message being replaced.  The
        unique primary key remains the final race-safe barrier across workers,
        supplier rows and providers.
        """

        email = _normalized_mail_address(normalized_email)
        if not email or "@" not in email:
            raise ValueError("Нельзя создать guard для некорректного email.")
        existing = connection.execute(
            """SELECT operation_id FROM mail_request_email_guards
               WHERE workspace_id=? AND request_id=? AND normalized_email=?
               LIMIT 1""",
            (int(workspace_id), int(request_id), email),
        ).fetchone()
        if existing:
            if not allow_existing:
                raise ContactSendGuardConflictError(
                    "Для этой заявки письмо на данный email уже было поставлено в очередь. "
                    "Повтор требует явного разрешения."
                )
            if source_message_id is not None:
                source = connection.execute(
                    """SELECT id FROM mail_messages
                       WHERE id=? AND workspace_id=? AND request_id=?
                         AND direction='outbound' AND LOWER(TRIM(to_email))=?""",
                    (int(source_message_id), int(workspace_id), int(request_id), email),
                ).fetchone()
                if not source:
                    raise ContinuationPlanConflictError(
                        "Источник provider-switch не совпадает с recipient guard."
                    )
            return False

        if not allow_existing and connection.execute(
            """SELECT 1 FROM mail_messages
               WHERE workspace_id=? AND request_id=? AND direction='outbound'
                 AND LOWER(TRIM(to_email))=?""",
            (int(workspace_id), int(request_id), email),
        ).fetchone():
            raise ContactSendGuardConflictError(
                "Для этой заявки письмо на данный email уже было поставлено в очередь. "
                "Повтор требует явного разрешения."
            )
        if allow_existing:
            if source_message_id is None or not connection.execute(
                """SELECT 1 FROM mail_messages
                   WHERE id=? AND workspace_id=? AND request_id=?
                     AND direction='outbound' AND LOWER(TRIM(to_email))=?""",
                (int(source_message_id), int(workspace_id), int(request_id), email),
            ).fetchone():
                raise ContinuationPlanConflictError(
                    "Provider-switch guard требует существующий исходный message."
                )
        inserted = connection.execute(
            """INSERT INTO mail_request_email_guards(
                   workspace_id, request_id, normalized_email,
                   operation_id, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT DO NOTHING""",
            (int(workspace_id), int(request_id), email, int(operation_id), iso_now(), iso_now()),
        )
        if inserted.rowcount != 1:
            if allow_existing:
                return False
            raise ContactSendGuardConflictError(
                "Для этой заявки письмо на данный email уже было поставлено в очередь. "
                "Повтор требует явного разрешения."
            )
        return True

    def _supersede_untouched_provider_source_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        workspace_id: int,
        request_id: int,
        target_id: int,
        source_job_id: int,
        source_message_id: int,
        user_id: int,
        reason: str = "provider_continuation_superseded",
    ) -> None:
        """Cancel one untouched source job before creating its provider attempt."""

        row = connection.execute(
            """SELECT j.status AS job_status, j.attempts, m.status AS message_status,
                      ji.irreversible_at
               FROM mail_jobs j
               JOIN mail_messages m ON m.id=j.message_id
               LEFT JOIN mail_job_integrity ji ON ji.job_id=j.id
               WHERE j.id=? AND j.message_id=? AND m.id=?
                 AND m.workspace_id=? AND m.request_id=? AND m.direction='outbound'""",
            (
                int(source_job_id), int(source_message_id), int(source_message_id),
                int(workspace_id), int(request_id),
            ),
        ).fetchone()
        attempts = connection.execute(
            "SELECT 1 FROM mail_send_attempts WHERE job_id=? LIMIT 1",
            (int(source_job_id),),
        ).fetchone()
        if (
            not row
            or str(row["job_status"] or "") != "queued"
            or str(row["message_status"] or "") != "queued"
            or int(row["attempts"] or 0) != 0
            or row["irreversible_at"] is not None
            or attempts
        ):
            raise ContinuationPlanConflictError(
                "Исходное письмо уже изменилось или начало отправляться; provider-switch отменён."
            )
        now = iso_now()
        safe_reason = str(reason or "provider_continuation_superseded")[:500]
        connection.execute(
            """UPDATE mail_jobs
               SET status='cancelled', next_attempt_at=NULL, last_error=?, updated_at=?
               WHERE id=? AND status='queued' AND attempts=0""",
            (safe_reason, now, int(source_job_id)),
        )
        connection.execute(
            """UPDATE mail_messages
               SET status='cancelled', error=?, sent_at=NULL
               WHERE id=? AND status='queued'""",
            (safe_reason, int(source_message_id)),
        )
        connection.execute(
            """UPDATE mail_campaign_targets
               SET status='excluded', exclusion_reason=?, updated_at=?
               WHERE id=? AND job_id=? AND status IN ('eligible', 'waiting')""",
            (safe_reason, now, int(target_id), int(source_job_id)),
        )
        self._audit_connection(
            connection, int(workspace_id), int(user_id), "mail.provider_source_superseded",
            "mail_message", str(source_message_id),
            {
                "request_id": int(request_id),
                "source_job_id": int(source_job_id),
                "source_message_id": int(source_message_id),
                "target_id": int(target_id),
                "reason": safe_reason,
            },
        )

    def get_send_operation(self, workspace_id: int, idempotency_key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mail_send_operations WHERE workspace_id=? AND idempotency_key=?",
                (workspace_id, idempotency_key),
            ).fetchone()
        return dict(row) if row else None

    def _create_send_operation_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        account_id: int,
        idempotency_key: str,
        content_fingerprint: str,
        fingerprint_schema_version: int,
        target_rows: list[dict[str, Any]],
        guard_initial_contacts: bool,
    ) -> int:
        """Reserve an operation and its initial-contact guards in a caller transaction."""
        now = iso_now()
        cursor = connection.execute(
            """INSERT INTO mail_send_operations(
                workspace_id, user_id, request_id, mail_account_id,
                idempotency_key, content_fingerprint, fingerprint_schema_version,
                expected_recipient_count, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'assembling', ?, ?)""",
            (
                workspace_id, user_id, request_id, account_id, idempotency_key,
                content_fingerprint, fingerprint_schema_version, len(target_rows), now, now,
            ),
        )
        operation_id = int(cursor.lastrowid)
        if guard_initial_contacts:
            for target in target_rows:
                normalized_email = str(target["normalized_email"] or "").strip().lower()
                if connection.execute(
                    """SELECT 1 FROM mail_request_email_guards
                       WHERE workspace_id=? AND request_id=? AND normalized_email=?
                       LIMIT 1""",
                    (workspace_id, request_id, normalized_email),
                ).fetchone() or connection.execute(
                    """SELECT 1 FROM mail_messages
                       WHERE workspace_id=? AND request_id=? AND direction='outbound'
                         AND lower(trim(to_email))=?
                       LIMIT 1""",
                    (workspace_id, request_id, normalized_email),
                ).fetchone():
                    raise ContactSendGuardConflictError(
                        "Для этой заявки письмо на данный email уже было поставлено в очередь. "
                        "Повтор требует явного разрешения."
                    )
                guard_insert = connection.execute(
                    """INSERT INTO mail_request_email_guards(
                           workspace_id, request_id, normalized_email,
                           operation_id, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT DO NOTHING""",
                    (workspace_id, request_id, normalized_email, operation_id, now, now),
                )
                if guard_insert.rowcount != 1:
                    raise ContactSendGuardConflictError(
                        "Для этой заявки письмо на данный email уже было поставлено в очередь. "
                        "Повтор требует явного разрешения."
                    )
        for target in target_rows:
            connection.execute(
                """INSERT INTO mail_send_operation_targets(
                    operation_id, normalized_email, supplier_id, message_id_header,
                    subject, body_text, body_html, resend_of_message_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation_id, target["normalized_email"], target["supplier_id"],
                    target["message_id_header"], target["subject"], target["body_text"],
                    target["body_html"], target.get("resend_of_message_id"), now, now,
                ),
            )
        return operation_id

    def create_send_operation(
        self,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        account_id: int,
        idempotency_key: str,
        content_fingerprint: str,
        fingerprint_schema_version: int,
        targets: Iterable[dict[str, Any]],
        guard_initial_contacts: bool = True,
    ) -> int:
        target_rows = list(targets)
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            operation_id = self._create_send_operation_connection(
                connection,
                workspace_id=workspace_id, user_id=user_id, request_id=request_id,
                account_id=account_id, idempotency_key=idempotency_key,
                content_fingerprint=content_fingerprint,
                fingerprint_schema_version=fingerprint_schema_version,
                target_rows=target_rows, guard_initial_contacts=guard_initial_contacts,
            )
            if not self.database_url:
                connection.commit()
        return operation_id

    def create_send_operation_with_messages(
        self,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        account_id: int,
        idempotency_key: str,
        content_fingerprint: str,
        fingerprint_schema_version: int,
        targets: Iterable[dict[str, Any]],
        attachments: Iterable[dict[str, Any]],
        campaign: dict[str, Any] | None,
        guard_initial_contacts: bool = True,
    ) -> tuple[int, int | None, list[dict[str, int]]]:
        """Atomically assemble a new operation, guard, campaign and queued messages."""
        target_rows = list(targets)
        attachment_rows = list(attachments)
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            operation_id = self._create_send_operation_connection(
                connection,
                workspace_id=workspace_id, user_id=user_id, request_id=request_id,
                account_id=account_id, idempotency_key=idempotency_key,
                content_fingerprint=content_fingerprint,
                fingerprint_schema_version=fingerprint_schema_version,
                target_rows=target_rows, guard_initial_contacts=guard_initial_contacts,
            )
            campaign_id: int | None = None
            if campaign is not None:
                campaign_id = self._create_campaign_connection(
                    connection,
                    workspace_id=workspace_id, user_id=user_id, request_id=request_id,
                    account_id=account_id, operation_id=operation_id,
                    provider=str(campaign.get("provider") or "unknown"),
                    stage_limit=int(campaign["stage_limit"]),
                    manual_stage_approval=bool(campaign["manual_stage_approval"]),
                    preflight=dict(campaign.get("preflight") or {}),
                    provider_warning=campaign.get("provider_warning"),
                    now=now,
                )
            results: list[dict[str, int]] = []
            for ordinal, target in enumerate(target_rows, start=1):
                created = self._create_queued_message_connection(
                    connection,
                    user_id=user_id, workspace_id=workspace_id, request_id=request_id,
                    supplier_id=int(target["supplier_id"]), account_id=account_id,
                    from_email=str(campaign.get("from_email") if campaign else ""),
                    to_email=str(target["normalized_email"]),
                    subject=str(target["subject"]), body_text=str(target["body_text"]),
                    body_html=str(target["body_html"]),
                    message_id_header=str(target["message_id_header"]),
                    attachments=attachment_rows, operation_id=operation_id,
                    normalized_email=str(target["normalized_email"]),
                    resend_of_message_id=target.get("resend_of_message_id"),
                    campaign_id=campaign_id, campaign_ordinal=ordinal,
                    personalization_level=int(target.get("personalization_level") or 0),
                )
                results.append({
                    "job_id": int(created["job_id"]),
                    "message_id": int(created["message_id"]),
                    "thread_id": int(created["thread_id"]),
                })
            connection.execute(
                "UPDATE mail_send_operations SET status='ready', last_error=NULL, updated_at=? WHERE id=?",
                (now, operation_id),
            )
            if not self.database_url:
                connection.commit()
        return operation_id, campaign_id, results

    def get_send_operation_targets(self, operation_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM mail_send_operation_targets WHERE operation_id=? ORDER BY id",
                (operation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_send_operation_results(self, operation_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT t.normalized_email, t.supplier_id, t.message_id_header,
                          t.message_id, j.id AS job_id, m.thread_id,
                          o.status AS operation_status, o.idempotency_key
                   FROM mail_send_operation_targets t
                   JOIN mail_send_operations o ON o.id=t.operation_id
                   LEFT JOIN mail_messages m ON m.id=t.message_id
                   LEFT JOIN mail_jobs j ON j.message_id=m.id
                   WHERE t.operation_id=? ORDER BY t.id""",
                (operation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_send_operation_ready(self, operation_id: int) -> bool:
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """UPDATE mail_send_operations
                   SET status='ready', last_error=NULL, updated_at=?
                   WHERE id=? AND (
                     status='ready'
                     OR (status='assembling' AND expected_recipient_count=(
                       SELECT COUNT(*) FROM mail_send_operation_targets
                       WHERE operation_id=? AND message_id IS NOT NULL
                     ))
                   )""",
                (now, operation_id, operation_id),
            )
            if not self.database_url:
                connection.commit()
        return cursor.rowcount == 1

    def mark_send_operation_failed(self, operation_id: int, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_send_operations SET status='assembly_failed', last_error=?, updated_at=? WHERE id=? AND status='assembling'",
                (error[:500], iso_now(), operation_id),
            )

    # --------------------------------------------- deliverability campaigns

    def get_campaign_by_operation(self, operation_id: int, workspace_id: int | None = None) -> dict[str, Any] | None:
        clause = " AND workspace_id=?" if workspace_id is not None else ""
        params: tuple[Any, ...] = (operation_id, workspace_id) if workspace_id is not None else (operation_id,)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mail_campaigns WHERE operation_id=?" + clause,
                params,
            ).fetchone()
        return dict(row) if row else None

    def _create_campaign_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        account_id: int,
        operation_id: int,
        provider: str,
        stage_limit: int,
        manual_stage_approval: bool,
        preflight: dict[str, Any],
        provider_warning: str | None,
        now: str,
    ) -> int:
        connection.execute(
            """INSERT INTO mail_campaigns(
                   workspace_id, user_id, request_id, mail_account_id,
                   operation_id, provider, status, rollout_stage, stage_limit,
                   manual_stage_approval, preflight_status, preflight_json,
                   provider_warning, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(operation_id) DO NOTHING""",
            (
                workspace_id, user_id, request_id, account_id, operation_id,
                str(provider or "unknown"), max(1, int(stage_limit)), int(manual_stage_approval),
                str(preflight.get("status") or "PASS").lower(),
                json.dumps(preflight, ensure_ascii=False, sort_keys=True),
                provider_warning, now, now,
            ),
        )
        row = connection.execute("SELECT id FROM mail_campaigns WHERE operation_id=?", (operation_id,)).fetchone()
        if not row:
            raise ValueError("Не удалось создать campaign state.")
        return int(row[0])

    def create_campaign(
        self,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        account_id: int,
        operation_id: int,
        provider: str,
        stage_limit: int,
        manual_stage_approval: bool,
        preflight: dict[str, Any],
        provider_warning: str | None,
    ) -> int:
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            campaign_id = self._create_campaign_connection(
                connection,
                workspace_id=workspace_id, user_id=user_id, request_id=request_id,
                account_id=account_id, operation_id=operation_id, provider=provider,
                stage_limit=stage_limit, manual_stage_approval=manual_stage_approval,
                preflight=preflight, provider_warning=provider_warning, now=now,
            )
            if not self.database_url:
                connection.commit()
            return campaign_id

    def _insert_campaign_target_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        campaign_id: int,
        operation_target_id: int,
        job_id: int,
        ordinal: int,
        normalized_email: str,
        supplier_id: int,
        personalization_level: int,
        now: str,
    ) -> None:
        existing = connection.execute(
            "SELECT id FROM mail_campaign_targets WHERE campaign_id=? AND operation_target_id=?",
            (campaign_id, operation_target_id),
        ).fetchone()
        if existing:
            connection.execute(
                """UPDATE mail_campaign_targets
                   SET job_id=?, normalized_email=?, supplier_id=?,
                       personalization_level=?, updated_at=?
                   WHERE id=?""",
                (job_id, normalized_email, supplier_id, personalization_level, now, existing[0]),
            )
            return
        campaign = connection.execute(
            "SELECT stage_limit, status FROM mail_campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        if not campaign:
            raise ValueError("Campaign state не найден.")
        eligible = int(ordinal) <= int(campaign["stage_limit"]) and campaign["status"] == "active"
        connection.execute(
            """INSERT INTO mail_campaign_targets(
                   campaign_id, operation_target_id, job_id, ordinal,
                   normalized_email, supplier_id, status, personalization_level,
                   eligible_at, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                campaign_id, operation_target_id, job_id, ordinal, normalized_email,
                supplier_id, "eligible" if eligible else "waiting", personalization_level,
                now if eligible else None, now, now,
            ),
        )

    def _campaign_row_for_job(self, job_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT c.* FROM mail_campaigns c
                   JOIN mail_campaign_targets ct ON ct.campaign_id=c.id
                   WHERE ct.job_id=?""",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def campaign_job_allowed(self, job_id: int) -> bool:
        """Final race-safe campaign gate for a claim made before pause/stop."""

        with self.connect() as connection:
            row = connection.execute(
                """SELECT c.status AS campaign_status, ct.status AS target_status,
                          cp.status AS continuation_status
                   FROM mail_campaign_targets ct
                   JOIN mail_campaigns c ON c.id=ct.campaign_id
                   LEFT JOIN mail_job_integrity ji ON ji.job_id=ct.job_id
                   LEFT JOIN mail_continuation_plans cp ON cp.operation_id=ji.operation_id
                   WHERE ct.job_id=?""",
                (job_id,),
            ).fetchone()
        if row is None:
            return True
        # An explicitly applied continuation is a bounded operator-approved
        # provider switch. It must remain sendable when the source campaign is
        # paused for health; ordinary campaign jobs still require an active
        # campaign and an eligible target.
        return (
            row["campaign_status"] == "active" and row["target_status"] == "eligible"
        ) or row["continuation_status"] == "ready"

    def campaign_summary(self, workspace_id: int, campaign_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            campaign = connection.execute(
                "SELECT * FROM mail_campaigns WHERE id=? AND workspace_id=?",
                (campaign_id, workspace_id),
            ).fetchone()
            if not campaign:
                return None
            target_rows = connection.execute(
                """SELECT ct.*, s.name AS supplier_name,
                          j.status AS job_status, j.attempts, j.last_error,
                          m.status AS message_status
                   FROM mail_campaign_targets ct
                   LEFT JOIN suppliers s ON s.id=ct.supplier_id
                   LEFT JOIN mail_jobs j ON j.id=ct.job_id
                   LEFT JOIN mail_messages m ON m.id=j.message_id
                   WHERE ct.campaign_id=? ORDER BY ct.ordinal""",
                (campaign_id,),
            ).fetchall()
            result_rows: dict[int, list[dict[str, Any]]] = {}
            for row in target_rows:
                if row["job_id"] is None:
                    result_rows[int(row["id"])] = []
                    continue
                result_rows[int(row["id"])] = [dict(item) for item in connection.execute(
                    "SELECT outcome, provider_classification FROM mail_send_attempts WHERE job_id=?",
                    (row["job_id"],),
                ).fetchall()]
            campaign_attempts = [dict(row) for row in connection.execute(
                """SELECT a.outcome, a.started_at, a.ended_at, a.id
                   FROM mail_send_attempts a
                   JOIN mail_campaign_targets ct ON ct.job_id=a.job_id
                   WHERE ct.campaign_id=?
                     AND a.outcome IN ('accepted', 'transient_rejected', 'permanent_rejected', 'uncertain')
                   ORDER BY COALESCE(a.ended_at, a.started_at), a.id""",
                (campaign_id,),
            ).fetchall()]
            hard_bounce_suppliers: set[int] = set()
            accepted_provider_by_target: dict[int, str] = {}
            reconciled_target_ids: set[int] = set()
            for row in target_rows:
                if row["supplier_id"] is None:
                    continue
                if row["status"] != "excluded":
                    reconciled = connection.execute(
                        """SELECT id FROM mail_reconciled_outbound_events
                           WHERE request_id=? AND supplier_id=?
                             AND normalized_recipient=? AND outcome='accepted'
                           LIMIT 1""",
                        (int(campaign["request_id"]), int(row["supplier_id"]), str(row["normalized_email"] or "").lower()),
                    ).fetchone()
                    if reconciled:
                        reconciled_target_ids.add(int(row["id"]))
                    accepted_provider = self._accepted_supplier_provider(
                        connection,
                        int(campaign["request_id"]),
                        int(row["supplier_id"]),
                        str(row["normalized_email"] or "").lower(),
                    )
                    if accepted_provider:
                        accepted_provider_by_target[int(row["id"])] = accepted_provider
                bounce = connection.execute(
                    """SELECT rs.status, rs.last_error, m.direction, m.from_email,
                              m.subject, m.body_text
                       FROM request_supplier_states rs
                       LEFT JOIN mail_messages m ON m.id=rs.last_message_id
                       WHERE rs.request_id=? AND rs.supplier_id=?""",
                    (campaign["request_id"], row["supplier_id"]),
                ).fetchone()
                if bounce and bounce["status"] == "failed" and (
                    "bounce" in str(bounce["last_error"] or "").lower()
                    or classify_bounce(
                        from_email=bounce["from_email"] or "",
                        subject=bounce["subject"] or "",
                        body_text=bounce["body_text"] or "",
                    ) == "hard"
                ):
                    hard_bounce_suppliers.add(int(row["supplier_id"]))

        planned = len(target_rows)
        excluded = sum(1 for row in target_rows if row["status"] == "excluded")
        queued = waiting = attempted = accepted_in_campaign = failed_permanent = failed_transient = historical_disputed_transient = unknown = suppressed = cancelled = provider_rejections = 0
        accepted_target_ids: set[int] = set()
        accepted_by_provider: dict[str, int] = {}
        for row in target_rows:
            audit = result_rows.get(int(row["id"]), [])
            statuses = {str(item["outcome"] or "") for item in audit}
            classifications = {str(item["provider_classification"] or "").lower() for item in audit}
            job_status = str(row["job_status"] or "")
            if row["status"] == "excluded":
                if str(row["exclusion_reason"] or "").startswith("suppressed"):
                    suppressed += 1
                continue
            accepted_provider = accepted_provider_by_target.get(int(row["id"]))
            if row["status"] == "waiting" and job_status == "queued" and not accepted_provider:
                waiting += 1
            if job_status == "queued" and not accepted_provider:
                queued += 1
            if audit:
                attempted += 1
            if job_status == "sent":
                accepted_in_campaign += 1
            if accepted_provider:
                accepted_target_ids.add(int(row["id"]))
                accepted_by_provider[accepted_provider] = accepted_by_provider.get(accepted_provider, 0) + 1
            else:
                if job_status == "delivery_unknown":
                    unknown += 1
                if job_status == "cancelled":
                    cancelled += 1
                if "transient_rejected" in statuses and job_status != "sent":
                    failed_transient += 1
                if job_status == "queued" and "transient_rejected" in statuses and "accepted" not in statuses:
                    historical_disputed_transient += 1
                if job_status == "failed" and "transient_rejected" not in statuses:
                    failed_permanent += 1
            if any("spam" in item or "policy" in item for item in classifications):
                provider_rejections += 1
            if "supplier-suppressed" in classifications or "suppression" in classifications:
                suppressed += 1

        hard_bounces = len(hard_bounce_suppliers)
        failed_permanent = max(failed_permanent, hard_bounces)
        remaining = sum(
            1 for row in target_rows
            if int(row["id"]) not in accepted_target_ids
            and row["status"] in {"eligible", "waiting"}
            and str(row["job_status"] or "") in {"queued", "sending", ""}
        )
        accepted = len(accepted_target_ids)
        accepted_reconciled = len(reconciled_target_ids)
        # Accepted history takes precedence over a stale source job above, so
        # ``queued`` is already provider-neutral here.
        queued_provider_neutral = queued
        effective_attempted = max(attempted, accepted + failed_permanent + failed_transient + unknown)
        health = {
            "permanent_failure_rate": failed_permanent / effective_attempted if effective_attempted else 0.0,
            "transient_failure_rate": failed_transient / effective_attempted if effective_attempted else 0.0,
            "unknown_rate": unknown / effective_attempted if effective_attempted else 0.0,
            "provider_rejection_rate": provider_rejections / effective_attempted if effective_attempted else 0.0,
            "hard_bounces": hard_bounces,
        }
        transient_metrics = transient_health_metrics(
            [str(row["outcome"]) for row in campaign_attempts],
            window=10,
        )
        health.update(transient_metrics)
        excluded_targets = [
            {
                "email": str(row["normalized_email"] or ""),
                "supplier_id": int(row["supplier_id"]) if row["supplier_id"] is not None else None,
                "supplier_name": row["supplier_name"],
                "reason": str(row["exclusion_reason"] or "excluded"),
            }
            for row in target_rows
            if row["status"] == "excluded"
        ]
        return {
            "campaign_id": int(campaign["id"]),
            "operation_id": int(campaign["operation_id"]),
            "request_id": int(campaign["request_id"]),
            "mail_account_id": int(campaign["mail_account_id"]),
            "provider": campaign["provider"],
            "status": campaign["status"],
            "stage": int(campaign["rollout_stage"]),
            "stage_limit": int(campaign["stage_limit"]),
            "manual_stage_approval": bool(campaign["manual_stage_approval"]),
            "planned": planned,
            "eligible": max(0, planned - excluded),
            "excluded": excluded,
            "queued": queued,
            "waiting": waiting,
            "attempted": attempted,
            "accepted": accepted,
            "accepted_in_campaign": accepted_in_campaign,
            "accepted_reconciled": accepted_reconciled,
            "accepted_by_provider": accepted_by_provider,
            "failed_permanent": failed_permanent,
            "failed_transient": failed_transient,
            "historical_disputed_transient": historical_disputed_transient,
            "delivery_unknown": unknown,
            "suppressed": suppressed,
            "cancelled": cancelled,
            "remaining": remaining,
            "queued_provider_neutral": queued_provider_neutral,
            "provider_rejection_count": provider_rejections,
            "health": health,
            "pause_reason": campaign["pause_reason"],
            "provider_warning": campaign["provider_warning"],
            "excluded_targets": excluded_targets,
            "updated_at": campaign["updated_at"],
        }

    @staticmethod
    def _continuation_suppressed_connection(
        connection: sqlite3.Connection | PostgresConnection,
        workspace_id: int,
        external_key: str | None,
        normalized_email: str,
    ) -> bool:
        key = str(external_key or "").strip().lower()
        if key and connection.execute(
            "SELECT 1 FROM blacklist_entries WHERE workspace_id=? AND external_key=? AND restored_at IS NULL LIMIT 1",
            (workspace_id, key),
        ).fetchone():
            return True
        if normalized_email and connection.execute(
            """SELECT 1 FROM blacklist_entries
               WHERE workspace_id=? AND level='email' AND external_key=?
                 AND restored_at IS NULL LIMIT 1""",
            (workspace_id, MailRepository._email_suppression_key(normalized_email)),
        ).fetchone():
            return True
        return bool(normalized_email and connection.execute(
            """SELECT 1 FROM blacklist_entries b JOIN suppliers s ON s.external_key=b.external_key
               WHERE b.workspace_id=? AND b.restored_at IS NULL AND LOWER(s.email)=? LIMIT 1""",
            (workspace_id, normalized_email),
        ).fetchone())

    @staticmethod
    def _continuation_answered_connection(
        connection: sqlite3.Connection | PostgresConnection,
        request_id: int,
        supplier_id: int | None,
        normalized_email: str | None = None,
    ) -> bool:
        if supplier_id is not None and connection.execute(
            "SELECT 1 FROM request_supplier_states WHERE request_id=? AND supplier_id=? AND status IN ('replied','answered') LIMIT 1",
            (request_id, supplier_id),
        ).fetchone():
            return True
        email = _normalized_mail_address(normalized_email)
        if email and connection.execute(
            """SELECT 1
               FROM request_supplier_states rss
               JOIN suppliers s ON s.id=rss.supplier_id
               WHERE rss.request_id=? AND LOWER(TRIM(s.email))=?
                 AND rss.status IN ('replied','answered')
               LIMIT 1""",
            (request_id, email),
        ).fetchone():
            return True
        inbound_filter = "request_id=? AND direction='inbound'"
        inbound_params: tuple[Any, ...] = (request_id,)
        if supplier_id is not None:
            inbound_filter += " AND supplier_id=?"
            inbound_params += (supplier_id,)
        if email:
            inbound_filter += " AND LOWER(TRIM(from_email))=?"
            inbound_params += (email,)
        rows = connection.execute(
            f"""SELECT from_email, subject, body_text
               FROM mail_messages
               WHERE {inbound_filter}""",
            inbound_params,
        ).fetchall()
        for row in rows:
            sender = _normalized_mail_address(row["from_email"])
            if sender.startswith("mailer-daemon@") or sender.startswith("postmaster@"):
                continue
            if classify_bounce(
                from_email=row["from_email"] or "",
                subject=row["subject"] or "",
                body_text=row["body_text"] or "",
            ) is None:
                return True
        return False

    @staticmethod
    def _accepted_recipient_provider(
        connection: sqlite3.Connection | PostgresConnection,
        request_id: int,
        normalized_recipient: str,
    ) -> str | None:
        """Return the latest accepted provider for a request recipient.

        Continuation safety is recipient-scoped.  Supplier IDs are not a safe
        deduplication key because the same mailbox can exist on several legacy
        supplier rows with different external keys.
        """

        email = _normalized_mail_address(normalized_recipient)
        if not email:
            return None
        row = connection.execute(
            """SELECT provider FROM (
                   SELECT ma.provider AS provider,
                          COALESCE(m.sent_at, m.created_at) AS accepted_at,
                          m.id AS event_id
                   FROM mail_messages m
                   JOIN mail_accounts ma ON ma.id=m.mail_account_id
                   LEFT JOIN mail_jobs j ON j.message_id=m.id
                   WHERE m.request_id=? AND m.direction='outbound'
                     AND LOWER(TRIM(m.to_email))=?
                     AND (m.status='sent' OR j.status='sent'
                          OR EXISTS (
                              SELECT 1 FROM mail_send_attempts sa
                              WHERE sa.job_id=j.id AND sa.outcome='accepted'
                          ))
                   UNION ALL
                   SELECT re.provider_type AS provider,
                          re.accepted_at AS accepted_at,
                          re.id AS event_id
                   FROM mail_reconciled_outbound_events re
                   WHERE re.request_id=? AND LOWER(TRIM(re.normalized_recipient))=?
                     AND re.outcome='accepted'
               ) accepted_events
               ORDER BY accepted_at DESC, event_id DESC
               LIMIT 1""",
            (request_id, email, request_id, email),
        ).fetchone()
        return str(row["provider"]) if row and row["provider"] else None

    def _continuation_target_rows(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        campaign_id: int,
    ) -> list[Any]:
        return connection.execute(
            """SELECT ct.id AS target_id, ct.operation_target_id, ct.ordinal,
                      ct.normalized_email, ct.supplier_id, ct.status AS target_status,
                      ct.personalization_level, ct.exclusion_reason,
                      j.id AS job_id, j.message_id AS source_message_id,
                      j.status AS job_status, j.attempts,
                      m.status AS message_status, m.subject AS source_message_subject,
                      m.body_text AS source_body_text, m.body_html AS source_body_html,
                      mi.irreversible_at, s.external_key,
                      ot.subject AS frozen_subject, ot.body_text AS frozen_body_text,
                      ot.body_html AS frozen_body_html
               FROM mail_campaign_targets ct
               LEFT JOIN mail_jobs j ON j.id=ct.job_id
               LEFT JOIN mail_messages m ON m.id=j.message_id
               LEFT JOIN mail_job_integrity mi ON mi.job_id=j.id
               LEFT JOIN suppliers s ON s.id=ct.supplier_id
               LEFT JOIN mail_send_operation_targets ot ON ot.id=ct.operation_target_id
               WHERE ct.campaign_id=? ORDER BY ct.ordinal, ct.id""",
            (campaign_id,),
        ).fetchall()

    def _evaluate_continuation_targets(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        campaign: Any,
        rows: list[Any],
    ) -> list[dict[str, Any]]:
        evaluations: list[dict[str, Any]] = []
        request_id = int(campaign["request_id"])
        workspace_id = int(campaign["workspace_id"])
        seen_emails: set[str] = set()
        for row in rows:
            target_id = int(row["target_id"])
            email = _normalized_mail_address(row["normalized_email"])
            supplier_id = int(row["supplier_id"]) if row["supplier_id"] is not None else None
            reasons: list[str] = []
            duplicate_recipient_in_campaign = bool(email and email in seen_emails)
            if email:
                seen_emails.add(email)
            accepted_provider = self._accepted_recipient_provider(connection, request_id, email)
            reconciled = bool(connection.execute(
                """SELECT 1 FROM mail_reconciled_outbound_events
                   WHERE request_id=? AND LOWER(TRIM(normalized_recipient))=?
                     AND outcome='accepted' LIMIT 1""",
                (request_id, email),
            ).fetchone())
            disputed_transient = bool(connection.execute(
                """SELECT 1
                   FROM mail_send_attempts sa
                   JOIN mail_jobs sj ON sj.id=sa.job_id
                   JOIN mail_messages sm ON sm.id=sj.message_id
                   WHERE sm.request_id=?
                     AND LOWER(TRIM(sm.to_email))=?
                     AND sa.outcome='transient_rejected' LIMIT 1""",
                (request_id, email),
            ).fetchone())
            delivery_unknown = bool(connection.execute(
                """SELECT 1
                   FROM mail_jobs sj JOIN mail_messages sm ON sm.id=sj.message_id
                   WHERE sm.request_id=?
                     AND LOWER(TRIM(sm.to_email))=?
                     AND (sj.status='delivery_unknown' OR sm.status='delivery_unknown')
                   LIMIT 1""",
                (request_id, email),
            ).fetchone())
            continuation_prepared = bool(connection.execute(
                """SELECT 1
                   FROM mail_continuation_plans cp
                   JOIN mail_send_operations co ON co.id=cp.operation_id
                   JOIN mail_job_integrity cji ON cji.operation_id=co.id
                   JOIN mail_jobs cj ON cj.id=cji.job_id
                   JOIN mail_messages cm ON cm.id=cj.message_id
                   WHERE cp.request_id=? AND cm.request_id=?
                      AND LOWER(TRIM(cm.to_email))=?
                   LIMIT 1""",
                (request_id, request_id, email),
            ).fetchone())
            suppressed = self._continuation_suppressed_connection(
                connection, workspace_id, row["external_key"], email,
            )
            answered = self._continuation_answered_connection(connection, request_id, supplier_id, email)
            if duplicate_recipient_in_campaign:
                reasons.append("duplicate_recipient_in_campaign")
            if str(row["target_status"] or "") == "excluded":
                reasons.append(str(row["exclusion_reason"] or "excluded"))
            if accepted_provider:
                reasons.append("reconciled_accepted" if reconciled else "accepted_history")
            if disputed_transient:
                reasons.append("historical_disputed_transient")
            if delivery_unknown:
                reasons.append("delivery_unknown_history")
            if continuation_prepared:
                reasons.append("continuation_already_prepared")
            if suppressed:
                reasons.append("suppressed")
            if answered:
                reasons.append("answered")
            if str(campaign["provider"] or "") != "yandex":
                reasons.append("campaign_provider_not_yandex")
            if str(campaign["status"] or "") in {"stopped", "completed"}:
                reasons.append("campaign_terminal")
            if (
                str(row["target_status"] or "") not in {"eligible", "waiting"}
                or str(row["job_status"] or "") != "queued"
                or str(row["message_status"] or "") != "queued"
                or int(row["attempts"] or 0) != 0
                or bool(connection.execute(
                    "SELECT 1 FROM mail_send_attempts WHERE job_id=? LIMIT 1",
                    (row["job_id"],),
                ).fetchone())
                or row["irreversible_at"] is not None
            ):
                reasons.append("job_not_strictly_untouched")
            evaluations.append({
                "target_id": target_id,
                "operation_target_id": int(row["operation_target_id"]) if row["operation_target_id"] is not None else None,
                "ordinal": int(row["ordinal"]),
                "normalized_email": email,
                "supplier_id": supplier_id,
                "job_id": int(row["job_id"]) if row["job_id"] is not None else None,
                "source_message_id": int(row["source_message_id"]) if row["source_message_id"] is not None else None,
                "personalization_level": int(row["personalization_level"] or 0),
                "target_status": str(row["target_status"] or ""),
                "job_status": str(row["job_status"] or ""),
                "message_status": str(row["message_status"] or ""),
                "attempts": int(row["attempts"] or 0),
                "accepted_provider": accepted_provider,
                "reconciled": reconciled,
                "disputed_transient": disputed_transient,
                "delivery_unknown": delivery_unknown,
                "continuation_prepared": continuation_prepared,
                "duplicate_recipient_in_campaign": duplicate_recipient_in_campaign,
                "suppressed": suppressed,
                "answered": answered,
                "strictly_untouched": not reasons,
                "reasons": list(dict.fromkeys(reasons)),
                "frozen_subject": row["frozen_subject"] or row["source_message_subject"],
                "frozen_body_text": row["frozen_body_text"] or row["source_body_text"],
                "frozen_body_html": row["frozen_body_html"] or row["source_body_html"],
            })
        return evaluations

    @staticmethod
    def _continuation_selection_fingerprint(
        campaign_id: int,
        request_id: int,
        target_account_id: int,
        limit: int,
        target_ids: list[int],
    ) -> str:
        payload = {
            "schema": 1,
            "campaign_id": int(campaign_id),
            "request_id": int(request_id),
            "target_account_id": int(target_account_id),
            "limit": int(limit),
            "target_ids": [int(item) for item in target_ids],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _continuation_public_target(item: dict[str, Any]) -> dict[str, Any]:
        return {
            key: item[key]
            for key in (
                "target_id", "operation_target_id", "ordinal", "normalized_email",
                "supplier_id", "job_id", "source_message_id", "personalization_level",
            )
            if key in item
        }

    def campaign_continuation_dry_run(
        self,
        workspace_id: int,
        campaign_id: int,
        target_account_id: int,
        limit: int | None = None,
    ) -> dict[str, Any] | None:
        """Build the provider-neutral continuation plan without writing state."""

        if limit is not None and (int(limit) < 1 or int(limit) > 5):
            raise ValueError("Лимит continuation должен быть от 1 до 5.")
        with self.connect() as connection:
            campaign = connection.execute(
                """SELECT c.*, a.provider AS target_provider, a.email AS target_email,
                          a.status AS target_account_status
                   FROM mail_campaigns c
                   LEFT JOIN mail_accounts a ON a.id=?
                   WHERE c.id=? AND c.workspace_id=?""",
                (target_account_id, campaign_id, workspace_id),
            ).fetchone()
            if not campaign:
                return None
            rows = self._continuation_target_rows(connection, campaign_id)
            evaluations = self._evaluate_continuation_targets(connection, campaign, rows)
        eligible = [item for item in evaluations if item["strictly_untouched"]]
        selected = eligible[: int(limit)] if limit is not None else eligible
        selected_ids = [int(item["target_id"]) for item in selected]
        effective_limit = int(limit) if limit is not None else max(1, len(selected_ids))
        source_state = {
            "schema": 1,
            "request_id": int(campaign["request_id"]),
            "campaign_updated_at": campaign["updated_at"],
            "campaign_status": str(campaign["status"]),
            "campaign_provider": str(campaign["provider"]),
            "current_mail_account_id": int(campaign["mail_account_id"]),
            "target_mail_account_id": int(target_account_id),
            "selected_target_ids": selected_ids,
        }
        reconciled = {
            int(item["target_id"]) for item in evaluations if item["reconciled"]
        }
        accepted = failed = unknown = queued = cancelled = excluded = disputed = 0
        for item in evaluations:
            job_status = str(item["job_status"] or "")
            if item["target_status"] == "excluded":
                excluded += 1
            if item["accepted_provider"] or job_status == "sent":
                accepted += 1
            elif job_status == "failed":
                failed += 1
            elif job_status == "delivery_unknown":
                unknown += 1
            elif job_status == "queued":
                queued += 1
            elif job_status == "cancelled":
                cancelled += 1
            if item["disputed_transient"] and not item["accepted_provider"]:
                disputed += 1
        return {
            "dry_run": True,
            "campaign_id": int(campaign["id"]),
            "campaign_provider": str(campaign["provider"]),
            "campaign_status": str(campaign["status"]),
            "current_mail_account_id": int(campaign["mail_account_id"]),
            "target_mail_account_id": int(target_account_id),
            "target_provider": campaign["target_provider"],
            "target_account_status": campaign["target_account_status"],
            "target_email": campaign["target_email"],
            "limit": limit,
            "eligible_untouched": len(eligible),
            "would_create": len(selected),
            "would_send_now": 0,
            "accepted_not_repeated": accepted,
            "accepted_reconciled_not_repeated": len(reconciled),
            "failed_not_repeated": failed,
            "historical_disputed_transient_not_repeated": disputed,
            "delivery_unknown_not_repeated": unknown,
            "queued_in_current_campaign": queued,
            "cancelled_not_repeated": cancelled,
            "excluded_not_repeated": excluded,
            "selected_targets": [self._continuation_public_target(item) for item in selected],
            "source_state": source_state,
            "selection_fingerprint": self._continuation_selection_fingerprint(
                int(campaign["id"]), int(campaign["request_id"]), int(target_account_id),
                effective_limit, selected_ids,
            ),
            "safe": bool(
                str(campaign["provider"]) == "yandex"
                and str(campaign["status"]) not in {"stopped", "completed"}
                and str(campaign["target_provider"] or "") == "mailru"
                and str(campaign["target_account_status"] or "") == "connected"
            ),
            "no_live_send": True,
        }

    def _evaluate_cross_provider_retry_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        workspace_id: int,
        user_id: int | None,
        request_id: int,
        original_job_id: int,
        original_message_id: int,
        target_account_id: int,
        original_attempt_id: int | None = None,
    ) -> dict[str, Any]:
        """Evaluate one proven-rejection retry without changing any state.

        This evaluator is deliberately shared by preview and apply.  Apply
        calls it again inside its write transaction, so a preview cannot turn
        into a send plan after a concurrent acceptance, answer, or suppression.
        The private normalized recipient is consumed only by the repository;
        callers receive the masked form.
        """

        source = connection.execute(
            """SELECT j.id AS original_job_id, j.message_id AS original_message_id,
                      j.status AS job_status, j.attempts AS job_attempts,
                      m.workspace_id, m.user_id, m.request_id, m.supplier_id,
                      m.mail_account_id AS message_account_id, m.message_id AS rfc_message_id,
                      m.to_email, m.subject, m.body_text, m.body_html, m.status AS message_status,
                      ma.provider AS original_provider, ma.email AS original_account_email,
                      s.external_key,
                      mi.irreversible_at AS integrity_irreversible_at,
                      mmi.resend_of_message_id
               FROM mail_jobs j
               JOIN mail_messages m ON m.id=j.message_id
               LEFT JOIN mail_accounts ma ON ma.id=m.mail_account_id
               LEFT JOIN suppliers s ON s.id=m.supplier_id
               LEFT JOIN mail_job_integrity mi ON mi.job_id=j.id
               LEFT JOIN mail_message_integrity mmi ON mmi.message_id=m.id
               WHERE j.id=? AND j.message_id=? AND m.workspace_id=?
                 AND m.request_id=? AND m.direction='outbound'""",
            (int(original_job_id), int(original_message_id), int(workspace_id), int(request_id)),
        ).fetchone()
        target_params: list[Any] = [int(target_account_id), int(workspace_id)]
        target_owner_sql = ""
        if user_id is not None:
            target_owner_sql = " AND a.user_id=?"
            target_params.append(int(user_id))
        target = connection.execute(
            f"""SELECT a.id, a.user_id, a.workspace_id, a.email, a.provider, a.status,
                          p.auth_mode, p.credential_reference
                   FROM mail_accounts a
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   WHERE a.id=? AND a.workspace_id=?{target_owner_sql}""",
            target_params,
        ).fetchone()

        blocked: list[str] = []
        retry_schema_ready = bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mail_cross_provider_retries'"
        ).fetchone()) if isinstance(connection, sqlite3.Connection) else True
        if not retry_schema_ready:
            blocked.append("retry_schema_not_migrated")
        if source is None:
            blocked.append("original_not_found")
        if target is None:
            blocked.append("target_account_not_found")

        attempts: list[Any] = []
        if source is not None:
            attempts = connection.execute(
                """SELECT a.*, e.smtp_stage, e.smtp_code, e.smtp_enhanced_status,
                          e.provider_response_safe, e.exception_class
                   FROM mail_send_attempts a
                   LEFT JOIN mail_send_attempt_evidence e ON e.attempt_id=a.id
                   WHERE a.job_id=? AND a.message_id=? ORDER BY a.id""",
                (int(source["original_job_id"]), int(source["original_message_id"])),
            ).fetchall()
        attempt = None
        if original_attempt_id is not None:
            attempt = next((row for row in attempts if int(row["id"]) == int(original_attempt_id)), None)
            if attempt is None:
                blocked.append("original_attempt_not_found")
        elif attempts:
            attempt = attempts[-1]
        else:
            blocked.append("original_attempt_missing")

        recipient = _normalized_mail_address(source["to_email"] if source is not None else "")
        source_time = None
        if attempt is not None:
            source_time = attempt["ended_at"] or attempt["started_at"]
        if source_time is None and source is not None:
            source_time = connection.execute(
                "SELECT created_at FROM mail_messages WHERE id=?", (int(original_message_id),)
            ).fetchone()[0]

        if source is not None:
            if int(source["supplier_id"] or 0) <= 0:
                blocked.append("supplier_not_found")
            if str(source["original_provider"] or "") != "yandex":
                blocked.append("original_provider_not_yandex")
            if str(source["job_status"] or "") != "failed" or str(source["message_status"] or "") != "failed":
                blocked.append("original_not_terminal_failed")
            if source["resend_of_message_id"] is not None:
                blocked.append("original_is_retry")
        if target is not None:
            if str(target["provider"] or "") != "mailru":
                blocked.append("target_provider_not_mailru")
            if str(target["status"] or "") != "connected":
                blocked.append("target_account_not_connected")
            if source is not None and int(target["id"]) == int(source["message_account_id"] or 0):
                blocked.append("target_account_is_original")

        evidence = None
        if attempt is not None:
            outcome = str(attempt["outcome"] or "")
            if outcome == "accepted":
                blocked.append("original_accepted")
            elif outcome == "delivery_unknown":
                blocked.append("original_delivery_unknown")
            elif outcome != "permanent_rejected":
                blocked.append("original_outcome_not_proven_rejection")
            evidence = {
                "smtp_stage": attempt["smtp_stage"],
                "smtp_code": int(attempt["smtp_code"]) if attempt["smtp_code"] is not None else None,
                "smtp_enhanced_status": attempt["smtp_enhanced_status"],
                "provider_response_safe": attempt["provider_response_safe"],
                "exception_class": attempt["exception_class"],
            }
            if not evidence["smtp_stage"] or evidence["smtp_code"] is None or not evidence["provider_response_safe"]:
                blocked.append("missing_durable_smtp_evidence")
            if str(evidence["smtp_stage"] or "") not in _CROSS_PROVIDER_RETRY_FINAL_STAGES:
                blocked.append("final_server_response_stage_missing")
            if evidence["smtp_code"] is None or not 500 <= int(evidence["smtp_code"]) <= 599:
                blocked.append("final_response_not_5xx")
            if int(attempt["irreversible_reached"] or 0) != 1:
                blocked.append("non_irreversible_evidence")

        if len(attempts) > 1:
            blocked.append("original_disputed")

        accepted_later = False
        if source is not None and source_time is not None:
            accepted_later = bool(connection.execute(
                """SELECT 1
                   FROM mail_send_attempts a
                   JOIN mail_jobs j ON j.id=a.job_id
                   JOIN mail_messages m ON m.id=j.message_id
                   WHERE m.request_id=? AND LOWER(TRIM(m.to_email))=?
                     AND a.outcome='accepted'
                     AND a.id<>? AND COALESCE(a.ended_at, a.started_at)>?
                   LIMIT 1""",
                (int(source["request_id"]), recipient,
                 int(attempt["id"]) if attempt is not None else -1, source_time),
            ).fetchone()) or bool(connection.execute(
                """SELECT 1
                   FROM mail_messages m
                   LEFT JOIN mail_jobs j ON j.message_id=m.id
                   WHERE m.request_id=? AND LOWER(TRIM(m.to_email))=?
                     AND m.id<>?
                     AND (m.status='sent' OR j.status='sent')
                     AND COALESCE(m.sent_at, m.created_at)>?
                   LIMIT 1""",
                (int(source["request_id"]), recipient,
                 int(original_message_id), source_time),
            ).fetchone())
            if accepted_later:
                blocked.append("later_accepted_send")

        reconciled_accepted = False
        if source is not None:
            reconciled_accepted = bool(connection.execute(
                """SELECT 1 FROM mail_reconciled_outbound_events
                   WHERE request_id=? AND LOWER(TRIM(normalized_recipient))=?
                     AND outcome='accepted' LIMIT 1""",
                (int(source["request_id"]), recipient),
            ).fetchone())
            if reconciled_accepted:
                blocked.append("reconciled_accepted")

        delivery_unknown = False
        if source is not None:
            delivery_unknown = bool(connection.execute(
                """SELECT 1
                   FROM mail_messages m
                   LEFT JOIN mail_jobs j ON j.message_id=m.id
                   LEFT JOIN mail_send_attempts a ON a.job_id=j.id
                   WHERE m.request_id=?
                     AND LOWER(TRIM(m.to_email))=?
                     AND (m.status='delivery_unknown' OR j.status='delivery_unknown'
                          OR a.outcome='delivery_unknown')
                   LIMIT 1""",
                (int(source["request_id"]), recipient),
            ).fetchone())
            if delivery_unknown:
                blocked.append("delivery_unknown_history")

        active_delivery_for_recipient = False
        if source is not None:
            active_delivery_for_recipient = bool(connection.execute(
                """SELECT 1
                   FROM mail_messages m
                   LEFT JOIN mail_jobs j ON j.message_id=m.id
                   WHERE m.request_id=? AND LOWER(TRIM(m.to_email))=?
                     AND m.id<>?
                     AND (m.status IN ('queued', 'sending', 'delivery_unknown')
                          OR j.status IN ('queued', 'sending', 'delivery_unknown'))
                   LIMIT 1""",
                (int(source["request_id"]), recipient, int(original_message_id)),
            ).fetchone())
            if active_delivery_for_recipient:
                blocked.append("active_delivery_for_recipient")

        suppressed = False
        answered = False
        if source is not None:
            suppressed = self._continuation_suppressed_connection(
                connection, int(workspace_id), source["external_key"], recipient,
            )
            answered = self._continuation_answered_connection(
                connection, int(source["request_id"]), int(source["supplier_id"]), recipient,
            )
            if suppressed:
                blocked.append("suppressed")
            if answered:
                blocked.append("answered")

        existing_retry = False
        if source is not None and retry_schema_ready:
            existing_retry = bool(connection.execute(
                """SELECT 1 FROM mail_cross_provider_retries
                   WHERE workspace_id=? AND request_id=?
                     AND LOWER(TRIM(normalized_recipient))=?
                   LIMIT 1""",
                (int(workspace_id), int(source["request_id"]), recipient),
            ).fetchone())
            if existing_retry:
                blocked.append("retry_already_planned")

        blocked = list(dict.fromkeys(blocked))
        source_public = {
            "job_id": int(original_job_id),
            "message_id": int(original_message_id),
            "attempt_id": int(attempt["id"]) if attempt is not None else None,
            "provider": str(source["original_provider"]) if source is not None else None,
            "account_id": int(source["message_account_id"]) if source is not None and source["message_account_id"] is not None else None,
            "account_email": source["original_account_email"] if source is not None else None,
            "rfc_message_id": source["rfc_message_id"] if source is not None else None,
            "recipient_masked": _masked_mail_address(recipient),
            "supplier_id": int(source["supplier_id"]) if source is not None and source["supplier_id"] is not None else None,
            "job_status": source["job_status"] if source is not None else None,
            "message_status": source["message_status"] if source is not None else None,
            "outcome": str(attempt["outcome"]) if attempt is not None else None,
            "provider_classification": attempt["provider_classification"] if attempt is not None else None,
            "irreversible_reached": bool(attempt["irreversible_reached"]) if attempt is not None else False,
            "smtp_evidence": evidence,
        }
        target_public = {
            "account_id": int(target["id"]) if target is not None else int(target_account_id),
            "provider": str(target["provider"]) if target is not None else None,
            "email": target["email"] if target is not None else None,
            "status": target["status"] if target is not None else None,
            "auth_mode": target["auth_mode"] if target is not None else None,
            "credential_reference": target["credential_reference"] if target is not None else None,
        }
        fingerprint_payload = {
            "schema": 1,
            "request_id": int(request_id),
            "supplier_id": source_public["supplier_id"],
            "original_job_id": int(original_job_id),
            "original_message_id": int(original_message_id),
            "original_attempt_id": source_public["attempt_id"],
            "target_provider": "mailru",
            "target_mail_account_id": int(target_account_id),
            "recipient": recipient,
            "rfc_message_id": source_public["rfc_message_id"],
            "outcome": source_public["outcome"],
            "provider_classification": source_public["provider_classification"],
            "smtp_evidence": evidence,
            "retry_reason": "proven_provider_rejection",
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        source_state = {
            "schema": 1,
            **source_public,
            "request_id": int(request_id),
            "target_provider": "mailru",
            "target_mail_account_id": int(target_account_id),
            "recipient_masked": _masked_mail_address(recipient),
            "retry_reason": "proven_provider_rejection",
            "selection_fingerprint": fingerprint,
        }
        return {
            "eligible": not blocked,
            "blocked_reasons": blocked,
            "request_id": int(request_id),
            "supplier_id": source_public["supplier_id"],
            "recipient_masked": _masked_mail_address(recipient),
            "source": source_public,
            "target_account": target_public,
            "retry_reason": "proven_provider_rejection",
            "selection_fingerprint": fingerprint,
            "source_state": source_state,
            "accepted_later": accepted_later,
            "reconciled_accepted": reconciled_accepted,
            "delivery_unknown": delivery_unknown,
            "active_delivery_for_recipient": active_delivery_for_recipient,
            "suppressed": suppressed,
            "answered": answered,
            "would_create": 1 if not blocked else 0,
            "would_send_now": 0,
            "requires_operator_confirmation": True,
            "no_live_send": True,
            "smtp_data_calls": 0,
            "_normalized_recipient": recipient,
        }

    def cross_provider_retry_preview(
        self,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        original_job_id: int,
        original_message_id: int,
        target_account_id: int,
        original_attempt_id: int | None = None,
    ) -> dict[str, Any]:
        """Read-only preview for one explicitly selected cross-provider retry."""

        with self.connect() as connection:
            result = self._evaluate_cross_provider_retry_connection(
                connection, workspace_id=workspace_id, user_id=user_id,
                request_id=request_id, original_job_id=original_job_id,
                original_message_id=original_message_id,
                target_account_id=target_account_id,
                original_attempt_id=original_attempt_id,
            )
        result.pop("_normalized_recipient", None)
        return result

    def apply_cross_provider_retry(
        self,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        original_job_id: int,
        original_message_id: int,
        target_account_id: int,
        idempotency_key: str,
        selection_fingerprint: str,
        operator_confirmed: bool,
        confirmation: dict[str, Any] | None = None,
        original_attempt_id: int | None = None,
    ) -> dict[str, Any]:
        """Atomically queue one cross-provider retry; never calls SMTP."""

        if type(operator_confirmed) is not bool or not operator_confirmed:
            raise ValueError("Для cross-provider retry требуется явное подтверждение оператора.")
        clean_key = str(idempotency_key or "").strip()
        if not clean_key or len(clean_key) > 200:
            raise ValueError("Для cross-provider retry требуется корректный idempotency key.")
        fingerprint = str(selection_fingerprint or "").strip().lower()
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("Укажите корректный selection fingerprint из preview.")

        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM mail_cross_provider_retries WHERE workspace_id=? AND idempotency_key=?",
                (int(workspace_id), clean_key),
            ).fetchone()
            if existing:
                same_plan = (
                    int(existing["user_id"]) == int(user_id)
                    and int(existing["request_id"]) == int(request_id)
                    and int(existing["original_job_id"]) == int(original_job_id)
                    and int(existing["original_message_id"]) == int(original_message_id)
                    and int(existing["target_mail_account_id"]) == int(target_account_id)
                    and str(existing["selection_fingerprint"]) == fingerprint
                    and (original_attempt_id is None or int(existing["original_attempt_id"]) == int(original_attempt_id))
                )
                if not same_plan:
                    if not self.database_url:
                        connection.rollback()
                    raise ContinuationPlanConflictError("Этот idempotency key уже связан с другим cross-provider retry plan.")
                try:
                    replay = json.loads(existing["result_json"] or "{}")
                except (TypeError, ValueError):
                    replay = {}
                if not replay:
                    replay = {
                        "ok": True,
                        "retry_plan_id": int(existing["id"]),
                        "operation_id": int(existing["operation_id"]) if existing["operation_id"] is not None else None,
                        "status": existing["status"],
                    }
                if not self.database_url:
                    connection.rollback()
                return {**replay, "idempotent_replay": True}

            evaluation = self._evaluate_cross_provider_retry_connection(
                connection, workspace_id=workspace_id, user_id=user_id,
                request_id=request_id, original_job_id=original_job_id,
                original_message_id=original_message_id,
                target_account_id=target_account_id,
                original_attempt_id=original_attempt_id,
            )
            if not evaluation["eligible"]:
                if not self.database_url:
                    connection.rollback()
                raise CrossProviderRetryBlockedError(
                    "Cross-provider retry заблокирован: " + ", ".join(evaluation["blocked_reasons"])
                )
            if fingerprint != str(evaluation["selection_fingerprint"]):
                if not self.database_url:
                    connection.rollback()
                raise ContinuationPlanConflictError("Cross-provider retry preview устарел или имеет другой fingerprint.")

            expected_confirmation = {
                "recipient_masked": evaluation["recipient_masked"],
                "original_provider": "yandex",
                "original_smtp_code": evaluation["source"]["smtp_evidence"]["smtp_code"],
                "target_provider": "mailru",
                "reason": "proven_provider_rejection",
            }
            supplied_confirmation = confirmation if isinstance(confirmation, dict) else {}
            if any(supplied_confirmation.get(key) != value for key, value in expected_confirmation.items()):
                if not self.database_url:
                    connection.rollback()
                raise ValueError("Подтверждение не совпадает с preview: укажите recipient, исходный rejection и Mail.ru target из плана.")

            target = connection.execute(
                "SELECT id, email, provider, status FROM mail_accounts WHERE id=? AND user_id=? AND workspace_id=?",
                (int(target_account_id), int(user_id), int(workspace_id)),
            ).fetchone()
            source_content = connection.execute(
                "SELECT subject, body_text, body_html FROM mail_messages WHERE id=?",
                (int(original_message_id),),
            ).fetchone()
            if target is None or source_content is None:
                raise CrossProviderRetryBlockedError("Cross-provider retry source or target disappeared during apply.")

            plan_cursor = connection.execute(
                """INSERT INTO mail_cross_provider_retries(
                       workspace_id, user_id, request_id, supplier_id,
                       original_job_id, original_message_id, original_attempt_id,
                       target_provider, target_mail_account_id, normalized_recipient,
                       retry_reason, idempotency_key, selection_fingerprint,
                       source_state_json, status, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 'mailru', ?, ?, ?, ?, ?, ?, 'assembling', ?, ?)""",
                (
                    int(workspace_id), int(user_id), int(request_id), int(evaluation["supplier_id"]),
                    int(original_job_id), int(original_message_id), int(evaluation["source"]["attempt_id"]),
                    int(target_account_id), evaluation["_normalized_recipient"],
                    "proven_provider_rejection", clean_key, fingerprint,
                    json.dumps(evaluation["source_state"], ensure_ascii=False, sort_keys=True), now, now,
                ),
            )
            plan_id = int(plan_cursor.lastrowid)
            operation_key = f"cross-provider-retry:{plan_id}:{clean_key}"
            operation_cursor = connection.execute(
                """INSERT INTO mail_send_operations(
                       workspace_id, user_id, request_id, mail_account_id,
                       idempotency_key, content_fingerprint, fingerprint_schema_version,
                       expected_recipient_count, status, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 'assembling', ?, ?)""",
                (int(workspace_id), int(user_id), int(request_id), int(target_account_id), operation_key, fingerprint, now, now),
            )
            operation_id = int(operation_cursor.lastrowid)
            self._ensure_request_email_guard_connection(
                connection,
                workspace_id=workspace_id,
                request_id=request_id,
                normalized_email=evaluation["_normalized_recipient"],
                operation_id=operation_id,
                allow_existing=True,
                source_message_id=int(original_message_id),
            )
            message_id_header = make_msgid(domain=str(target["email"]).split("@", 1)[-1])
            body_text = str(source_content["body_text"] or "")
            body_html = source_content["body_html"] or f"<p>{escape(body_text).replace(chr(10), '<br>')}</p>"
            connection.execute(
                """INSERT INTO mail_send_operation_targets(
                       operation_id, normalized_email, supplier_id, message_id_header,
                       subject, body_text, body_html, resend_of_message_id,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation_id, evaluation["_normalized_recipient"], int(evaluation["supplier_id"]),
                    message_id_header, source_content["subject"], body_text, body_html,
                    int(original_message_id), now, now,
                ),
            )
            attachments = [
                dict(item) for item in connection.execute(
                    "SELECT filename, mime_type, size_bytes, content FROM mail_attachments WHERE message_id=? ORDER BY id",
                    (int(original_message_id),),
                ).fetchall()
            ]
            created = self._create_queued_message_connection(
                connection,
                user_id=int(user_id), workspace_id=int(workspace_id), request_id=int(request_id),
                supplier_id=int(evaluation["supplier_id"]), account_id=int(target_account_id),
                from_email=str(target["email"]), to_email=evaluation["_normalized_recipient"],
                subject=str(source_content["subject"] or ""), body_text=body_text, body_html=body_html,
                message_id_header=message_id_header, attachments=attachments,
                operation_id=operation_id, normalized_email=evaluation["_normalized_recipient"],
                resend_of_message_id=int(original_message_id),
            )
            connection.execute(
                "UPDATE mail_send_operations SET status='ready', updated_at=? WHERE id=?",
                (now, operation_id),
            )
            result = {
                "ok": True,
                "retry_plan_id": plan_id,
                "operation_id": operation_id,
                "request_id": int(request_id),
                "supplier_id": int(evaluation["supplier_id"]),
                "original_job_id": int(original_job_id),
                "original_message_id": int(original_message_id),
                "original_attempt_id": int(evaluation["source"]["attempt_id"]),
                "provider": "mailru",
                "target_mail_account_id": int(target_account_id),
                "recipient_masked": evaluation["recipient_masked"],
                "retry_reason": "proven_provider_rejection",
                "status": "queued",
                "job_id": int(created["job_id"]),
                "message_id": int(created["message_id"]),
                "message_id_header": message_id_header,
                "selection_fingerprint": fingerprint,
                "no_live_send": True,
                "smtp_data_calls": 0,
                "campaign_changed": False,
            }
            connection.execute(
                """UPDATE mail_cross_provider_retries
                   SET operation_id=?, status='queued', result_json=?, updated_at=? WHERE id=?""",
                (operation_id, json.dumps(result, ensure_ascii=False, sort_keys=True), now, plan_id),
            )
            self._audit_connection(
                connection, int(workspace_id), int(user_id), "mail.cross_provider_retry_applied",
                "mail_cross_provider_retry", str(plan_id),
                {
                    "request_id": int(request_id), "supplier_id": int(evaluation["supplier_id"]),
                    "original_job_id": int(original_job_id), "original_message_id": int(original_message_id),
                    "target_provider": "mailru", "target_mail_account_id": int(target_account_id),
                    "smtp_data_calls": 0,
                },
            )
            if not self.database_url:
                connection.commit()
            return result

    def get_continuation_plan(self, workspace_id: int, idempotency_key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mail_continuation_plans WHERE workspace_id=? AND idempotency_key=?",
                (workspace_id, idempotency_key),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        for key in ("source_state_json", "selected_targets_json", "effective_targets_json", "skipped_targets_json", "result_json"):
            try:
                result[key[:-5] if key.endswith("_json") else key] = json.loads(result[key])
            except (TypeError, ValueError):
                result[key[:-5] if key.endswith("_json") else key] = {}
        return result

    def apply_campaign_continuation(
        self,
        *,
        workspace_id: int,
        user_id: int,
        request_id: int,
        campaign_id: int,
        target_account_id: int,
        limit: int,
        idempotency_key: str,
        selection_fingerprint: str,
        selected_targets: list[dict[str, Any]],
        operator_confirmed: bool,
    ) -> dict[str, Any]:
        """Atomically prepare a bounded provider-switch operation for MailQueue."""

        if not operator_confirmed:
            raise ValueError("Для continuation требуется явное подтверждение оператора.")
        if int(limit) < 1 or int(limit) > 5:
            raise ValueError("Лимит continuation должен быть от 1 до 5.")
        target_ids = [int(item["target_id"]) for item in selected_targets]
        if len(target_ids) > int(limit) or len(set(target_ids)) != len(target_ids):
            raise ContinuationPlanConflictError("Continuation plan содержит некорректный набор targets.")
        expected_fingerprint = self._continuation_selection_fingerprint(
            campaign_id, request_id, target_account_id, int(limit), target_ids,
        )
        if str(selection_fingerprint or "") != expected_fingerprint:
            raise ContinuationPlanConflictError("Continuation plan устарел или имеет другой selection fingerprint.")

        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM mail_continuation_plans WHERE workspace_id=? AND idempotency_key=?",
                (workspace_id, idempotency_key),
            ).fetchone()
            if existing:
                if (
                    int(existing["campaign_id"]) != int(campaign_id)
                    or int(existing["mail_account_id"]) != int(target_account_id)
                    or int(existing["limit_count"]) != int(limit)
                    or str(existing["selection_fingerprint"]) != expected_fingerprint
                ):
                    if not self.database_url:
                        connection.rollback()
                    raise ContinuationPlanConflictError("Этот idempotency key уже связан с другим continuation plan.")
                try:
                    result = json.loads(existing["result_json"] or "{}")
                except (TypeError, ValueError):
                    result = {}
                if not self.database_url:
                    connection.rollback()
                return {**result, "idempotent_replay": True}

            campaign = connection.execute(
                "SELECT * FROM mail_campaigns WHERE id=? AND workspace_id=? AND request_id=?",
                (campaign_id, workspace_id, request_id),
            ).fetchone()
            account = connection.execute(
                "SELECT id, user_id, email, provider, status FROM mail_accounts WHERE id=? AND user_id=? AND workspace_id=?",
                (target_account_id, user_id, workspace_id),
            ).fetchone()
            if not campaign:
                raise ValueError("Campaign не найдена в текущем рабочем пространстве.")
            if not account or str(account["provider"]) != "mailru" or str(account["status"]) != "connected":
                raise ValueError("Выберите подключённый аккаунт Mail.ru для continuation.")
            if str(campaign["provider"]) != "yandex" or str(campaign["status"]) in {"stopped", "completed"}:
                raise ValueError("Continuation доступен только для незавершённой Yandex-кампании.")

            rows = self._continuation_target_rows(connection, campaign_id)
            evaluations = self._evaluate_continuation_targets(connection, campaign, rows)
            by_id = {int(item["target_id"]): item for item in evaluations}
            effective: list[dict[str, Any]] = []
            skipped: list[dict[str, Any]] = []
            for target_id in target_ids:
                item = by_id.get(target_id)
                if item is None:
                    skipped.append({"target_id": target_id, "reasons": ["target_not_found"]})
                elif item["strictly_untouched"] and item["frozen_subject"] is not None and item["frozen_body_text"] is not None:
                    effective.append(item)
                else:
                    skipped.append({
                        **self._continuation_public_target(item),
                        "reasons": list(item["reasons"]) or ["missing_frozen_personalization"],
                    })

            source_state = {
                "schema": 1,
                "request_id": int(campaign["request_id"]),
                "campaign_updated_at": campaign["updated_at"],
                "campaign_status": str(campaign["status"]),
                "campaign_provider": str(campaign["provider"]),
                "current_mail_account_id": int(campaign["mail_account_id"]),
                "target_mail_account_id": int(target_account_id),
                "selected_target_ids": target_ids,
            }
            plan_cursor = connection.execute(
                """INSERT INTO mail_continuation_plans(
                    workspace_id, user_id, request_id, campaign_id,
                    provider_type, mail_account_id, idempotency_key,
                    selection_fingerprint, source_state_json,
                    selected_targets_json, effective_targets_json,
                    skipped_targets_json, limit_count, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'mailru', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workspace_id, user_id, request_id, campaign_id, target_account_id,
                    idempotency_key, expected_fingerprint,
                    json.dumps(source_state, ensure_ascii=False, sort_keys=True),
                    json.dumps([self._continuation_public_target(item) for item in selected_targets], ensure_ascii=False, sort_keys=True),
                    json.dumps([], ensure_ascii=False), json.dumps(skipped, ensure_ascii=False, sort_keys=True),
                    int(limit), "empty" if not effective else "ready", now, now,
                ),
            )
            plan_id = int(plan_cursor.lastrowid)
            operation_key = f"continuation:{plan_id}:{idempotency_key}"
            operation_cursor = connection.execute(
                """INSERT INTO mail_send_operations(
                    workspace_id, user_id, request_id, mail_account_id,
                    idempotency_key, content_fingerprint, fingerprint_schema_version,
                    expected_recipient_count, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, 'assembling', ?, ?)""",
                (
                    workspace_id, user_id, request_id, target_account_id, operation_key,
                    expected_fingerprint, len(effective), now, now,
                ),
            )
            operation_id = int(operation_cursor.lastrowid)
            jobs: list[dict[str, Any]] = []
            for item in effective:
                self._ensure_request_email_guard_connection(
                    connection,
                    workspace_id=workspace_id,
                    request_id=request_id,
                    normalized_email=str(item["normalized_email"]),
                    operation_id=operation_id,
                    allow_existing=True,
                    source_message_id=int(item["source_message_id"]),
                )
                self._supersede_untouched_provider_source_connection(
                    connection,
                    workspace_id=workspace_id,
                    request_id=request_id,
                    target_id=int(item["target_id"]),
                    source_job_id=int(item["job_id"]),
                    source_message_id=int(item["source_message_id"]),
                    user_id=user_id,
                )
                message_id_header = make_msgid(domain=str(account["email"]).split("@", 1)[-1])
                connection.execute(
                    """INSERT INTO mail_send_operation_targets(
                        operation_id, normalized_email, supplier_id, message_id_header,
                        subject, body_text, body_html, resend_of_message_id,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        operation_id, item["normalized_email"], int(item["supplier_id"]),
                        message_id_header, item["frozen_subject"], item["frozen_body_text"],
                        item["frozen_body_html"] or f"<p>{escape(str(item['frozen_body_text'])).replace(chr(10), '<br>')}</p>",
                        int(item["source_message_id"]),
                        now, now,
                    ),
                )
                operation_target_id = int(connection.execute("SELECT LASTVAL()" if self.database_url else "SELECT last_insert_rowid()").fetchone()[0])
                attachments = []
                if item["source_message_id"] is not None:
                    attachments = [
                        dict(attachment) for attachment in connection.execute(
                            "SELECT filename, mime_type, size_bytes, content FROM mail_attachments WHERE message_id=? ORDER BY id",
                            (item["source_message_id"],),
                        ).fetchall()
                    ]
                created = self._create_queued_message_connection(
                    connection,
                    user_id=user_id, workspace_id=workspace_id, request_id=request_id,
                    supplier_id=int(item["supplier_id"]), account_id=target_account_id,
                    from_email=str(account["email"]), to_email=item["normalized_email"],
                    subject=item["frozen_subject"], body_text=item["frozen_body_text"],
                    body_html=item["frozen_body_html"] or f"<p>{escape(str(item['frozen_body_text'])).replace(chr(10), '<br>')}</p>",
                    message_id_header=message_id_header, attachments=attachments,
                    operation_id=operation_id, normalized_email=item["normalized_email"],
                    resend_of_message_id=int(item["source_message_id"]),
                    personalization_level=int(item["personalization_level"]),
                )
                connection.execute(
                    "UPDATE mail_send_operation_targets SET message_id=?, updated_at=? WHERE id=?",
                    (created["message_id"], now, operation_target_id),
                )
                jobs.append({
                    "target_id": int(item["target_id"]),
                    "normalized_email": item["normalized_email"],
                    "job_id": int(created["job_id"]),
                    "message_id": int(created["message_id"]),
                    "thread_id": int(created["thread_id"]),
                })
            connection.execute(
                "UPDATE mail_send_operations SET status='ready', updated_at=? WHERE id=?",
                (now, operation_id),
            )
            effective_public = [
                {**self._continuation_public_target(item), "job_id": job["job_id"], "message_id": job["message_id"]}
                for item, job in zip(effective, jobs)
            ]
            result = {
                "ok": True,
                "plan_id": plan_id,
                "operation_id": operation_id,
                "campaign_id": int(campaign_id),
                "provider": "mailru",
                "mail_account_id": int(target_account_id),
                "limit": int(limit),
                "selected_count": len(target_ids),
                "created_count": len(jobs),
                "skipped_count": len(skipped),
                "jobs": jobs,
                "skipped_targets": skipped,
                "selection_fingerprint": expected_fingerprint,
                "no_live_send": True,
                "smtp_data_calls": 0,
            }
            connection.execute(
                """UPDATE mail_continuation_plans
                   SET operation_id=?, effective_targets_json=?, result_json=?, updated_at=?
                   WHERE id=?""",
                (
                    operation_id, json.dumps(effective_public, ensure_ascii=False, sort_keys=True),
                    json.dumps(result, ensure_ascii=False, sort_keys=True), now, plan_id,
                ),
            )
            self._audit_connection(
                connection, workspace_id, user_id, "mail.continuation_applied",
                "mail_continuation_plan", str(plan_id),
                {"campaign_id": int(campaign_id), "mail_account_id": int(target_account_id), "limit": int(limit), "created_count": len(jobs)},
            )
            if not self.database_url:
                connection.commit()
            return result

    def _campaign_health_pause_reason(self, summary: dict[str, Any], rollout: Any) -> str | None:
        health = summary.get("health") or {}
        if int(summary.get("provider_rejection_count") or 0) >= int(getattr(rollout, "max_provider_rejections", 1)):
            return "provider_spam_or_policy_rejection"
        if int(health.get("hard_bounces") or 0) > 0:
            return "hard_bounce_detected"
        if float(health.get("permanent_failure_rate") or 0.0) > float(getattr(rollout, "max_permanent_failure_rate", 0.20)):
            return "abnormal_permanent_failure_rate"
        if float(health.get("unknown_rate") or 0.0) > float(getattr(rollout, "max_unknown_rate", 0.10)):
            return "delivery_unknown_rate"
        consecutive = int(health.get("consecutive_transient_failures") or 0)
        if consecutive >= int(getattr(rollout, "max_transient_failures", 3)):
            return "repeated_transient_failures"
        recent_count = int(health.get("recent_attempt_count") or 0)
        recent_transient = int(health.get("recent_transient_count") or 0)
        recent_ratio = float(health.get("recent_transient_ratio") or 0.0)
        min_sample = int(getattr(rollout, "recent_transient_min_sample", 10))
        pause_count = int(getattr(rollout, "recent_transient_pause_count", 5))
        pause_ratio = float(getattr(rollout, "recent_transient_pause_ratio", 0.50))
        if recent_count >= min_sample and recent_transient >= pause_count and recent_ratio >= pause_ratio:
            return "repeated_transient_failures"
        return None

    @staticmethod
    def _campaign_stage_complete(connection: sqlite3.Connection | PostgresConnection, campaign_id: int, stage_limit: int) -> bool:
        stage_targets = connection.execute(
            """SELECT ct.id, j.status FROM mail_campaign_targets ct
               LEFT JOIN mail_jobs j ON j.id=ct.job_id
               WHERE ct.campaign_id=? AND ct.ordinal<=?""",
            (campaign_id, stage_limit),
        ).fetchall()
        return bool(stage_targets) and all(
            str(row["status"] or "") in _CAMPAIGN_STAGE_TERMINAL_JOB_STATES
            for row in stage_targets
        )

    def refresh_campaign_after_job(self, job_id: int, *, rollout: Any, pause_reason: str | None = None) -> dict[str, Any] | None:
        campaign = self._campaign_row_for_job(job_id)
        if not campaign:
            return None
        summary = self.campaign_summary(int(campaign["workspace_id"]), int(campaign["id"]))
        if not summary:
            return None
        reason = pause_reason or self._campaign_health_pause_reason(summary, rollout)
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT * FROM mail_campaigns WHERE id=?", (campaign["id"],)).fetchone()
            if not current or current["status"] not in {"active"}:
                if not self.database_url:
                    connection.rollback()
                return self.campaign_summary(int(campaign["workspace_id"]), int(campaign["id"]))
            if reason:
                connection.execute(
                    "UPDATE mail_campaigns SET status='paused_for_health', pause_reason=?, paused_at=?, updated_at=? WHERE id=? AND status='active'",
                    (reason[:200], now, now, campaign["id"]),
                )
            else:
                current_limit = int(current["stage_limit"])
                planned = int(summary["planned"])
                stage_complete = self._campaign_stage_complete(connection, int(campaign["id"]), current_limit)
                next_stage: tuple[int, int] | None = None
                if stage_complete and current_limit < planned:
                    next_stage = rollout.next_stage(int(current["rollout_stage"]), planned)
                if stage_complete and next_stage:
                    next_number, next_limit = next_stage
                    if bool(getattr(rollout, "blocks_stage_advancement", lambda *_args: False)(int(campaign["id"]), next_number)):
                        connection.execute(
                            "UPDATE mail_campaigns SET status='paused_for_review', pause_reason=?, paused_at=?, updated_at=? WHERE id=?",
                            ("operator_stage_cap", now, now, campaign["id"]),
                        )
                    elif bool(current["manual_stage_approval"]):
                        connection.execute(
                            "UPDATE mail_campaigns SET status='paused_for_review', pause_reason=?, paused_at=?, updated_at=? WHERE id=?",
                            ("stage_review", now, now, campaign["id"]),
                        )
                    else:
                        connection.execute(
                            "UPDATE mail_campaigns SET rollout_stage=?, stage_limit=?, updated_at=? WHERE id=?",
                            (next_number, next_limit, now, campaign["id"]),
                        )
                        connection.execute(
                            """UPDATE mail_campaign_targets SET status='eligible', eligible_at=?, updated_at=?
                               WHERE campaign_id=? AND status='waiting' AND ordinal<=?""",
                            (now, now, campaign["id"], next_limit),
                        )
                elif stage_complete and current_limit >= planned:
                    connection.execute(
                        "UPDATE mail_campaigns SET status='completed', updated_at=? WHERE id=?",
                        (now, campaign["id"]),
                    )
            if not self.database_url:
                connection.commit()
        return self.campaign_summary(int(campaign["workspace_id"]), int(campaign["id"]))

    def pause_campaign(self, workspace_id: int, campaign_id: int, reason: str = "manual_pause") -> dict[str, Any] | None:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_campaigns SET status='paused_for_review', pause_reason=?, paused_at=?, updated_at=? WHERE id=? AND workspace_id=? AND status='active'",
                (str(reason or "manual_pause")[:200], now, now, campaign_id, workspace_id),
            )
        return self.campaign_summary(workspace_id, campaign_id)

    def resume_campaign(self, workspace_id: int, campaign_id: int, *, rollout: Any) -> dict[str, Any] | None:
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            campaign = connection.execute(
                "SELECT * FROM mail_campaigns WHERE id=? AND workspace_id=?", (campaign_id, workspace_id)
            ).fetchone()
            if not campaign:
                if not self.database_url:
                    connection.rollback()
                return None
            if campaign["status"] not in {"paused_for_review", "paused_for_health"}:
                if not self.database_url:
                    connection.rollback()
                return self.campaign_summary(workspace_id, campaign_id)
            stage = int(campaign["rollout_stage"])
            limit = int(campaign["stage_limit"])
            planned = int(connection.execute("SELECT COUNT(*) FROM mail_campaign_targets WHERE campaign_id=?", (campaign_id,)).fetchone()[0])
            is_stage_review = campaign["status"] == "paused_for_review" and campaign["pause_reason"] == "stage_review"
            is_operator_stage_hold = campaign["status"] == "paused_for_review" and campaign["pause_reason"] == "operator_stage_cap"
            if is_operator_stage_hold:
                next_stage = rollout.next_stage(stage, planned) if limit < planned and self._campaign_stage_complete(connection, campaign_id, limit) else None
                if next_stage and bool(getattr(rollout, "blocks_stage_advancement", lambda *_args: False)(campaign_id, next_stage[0])):
                    # A normal Resume must not bypass an active operator hold.
                    # Return the durable state unchanged; removing the process
                    # cap is an explicit operator action handled by a later
                    # Resume call.
                    if not self.database_url:
                        connection.rollback()
                    return self.campaign_summary(workspace_id, campaign_id)
            if (is_stage_review or is_operator_stage_hold) and limit < planned and self._campaign_stage_complete(connection, campaign_id, limit):
                next_stage = rollout.next_stage(stage, planned)
                if next_stage:
                    stage, limit = next_stage
            connection.execute(
                "UPDATE mail_campaigns SET status='active', rollout_stage=?, stage_limit=?, pause_reason=NULL, paused_at=NULL, updated_at=? WHERE id=?",
                (stage, limit, now, campaign_id),
            )
            connection.execute(
                "UPDATE mail_campaign_targets SET status='eligible', eligible_at=?, updated_at=? WHERE campaign_id=? AND status='waiting' AND ordinal<=?",
                (now, now, campaign_id, limit),
            )
            if not self.database_url:
                connection.commit()
        return self.campaign_summary(workspace_id, campaign_id)

    def stop_campaign(self, workspace_id: int, campaign_id: int) -> dict[str, Any] | None:
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            campaign = connection.execute(
                "SELECT id FROM mail_campaigns WHERE id=? AND workspace_id=?", (campaign_id, workspace_id)
            ).fetchone()
            if not campaign:
                if not self.database_url:
                    connection.rollback()
                return None
            connection.execute(
                "UPDATE mail_jobs SET status='cancelled', next_attempt_at=NULL, updated_at=? WHERE id IN (SELECT job_id FROM mail_campaign_targets WHERE campaign_id=? AND status IN ('eligible','waiting') AND job_id IS NOT NULL) AND status='queued'",
                (now, campaign_id),
            )
            connection.execute(
                "UPDATE mail_messages SET status='cancelled', error='Кампания остановлена пользователем.' WHERE id IN (SELECT j.message_id FROM mail_jobs j JOIN mail_campaign_targets ct ON ct.job_id=j.id WHERE ct.campaign_id=? AND j.status='cancelled')",
                (campaign_id,),
            )
            connection.execute(
                "UPDATE request_supplier_states SET status='cancelled', last_error='Кампания остановлена пользователем.', updated_at=? WHERE last_message_id IN (SELECT j.message_id FROM mail_jobs j JOIN mail_campaign_targets ct ON ct.job_id=j.id WHERE ct.campaign_id=? AND j.status='cancelled')",
                (now, campaign_id),
            )
            connection.execute(
                "UPDATE mail_campaign_targets SET status='cancelled', updated_at=? WHERE campaign_id=? AND status IN ('eligible','waiting') AND job_id IN (SELECT id FROM mail_jobs WHERE status='cancelled')",
                (now, campaign_id),
            )
            connection.execute(
                "UPDATE mail_campaigns SET status='stopped', pause_reason='stopped_by_user', stopped_at=?, updated_at=? WHERE id=?",
                (now, now, campaign_id),
            )
            if not self.database_url:
                connection.commit()
        return self.campaign_summary(workspace_id, campaign_id)

    def cancel_stopped_campaign_job(self, job_id: int, message_id: int) -> bool:
        """Finalize a claimed job that was released after campaign stop.

        ``stop_campaign`` can only cancel jobs that are queued at the instant
        its transaction runs.  A worker may already own a claim.  If the
        worker then observes the stopped campaign before the irreversible
        gate, it releases the claim; this second step makes that unsent job a
        durable cancellation without touching sent/unknown history.
        """

        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """UPDATE mail_jobs
                   SET status='cancelled', next_attempt_at=NULL, updated_at=?
                   WHERE id=? AND status='queued'
                     AND EXISTS (
                       SELECT 1 FROM mail_campaign_targets ct
                       JOIN mail_campaigns c ON c.id=ct.campaign_id
                       WHERE ct.job_id=? AND c.status='stopped'
                     )""",
                (now, job_id, job_id),
            )
            if cursor.rowcount != 1:
                if not self.database_url:
                    connection.rollback()
                return False
            connection.execute(
                "UPDATE mail_messages SET status='cancelled', error='Кампания остановлена пользователем.' WHERE id=? AND status='queued'",
                (message_id,),
            )
            connection.execute(
                "UPDATE request_supplier_states SET status='cancelled', last_error='Кампания остановлена пользователем.', updated_at=? WHERE last_message_id=?",
                (now, message_id),
            )
            connection.execute(
                "UPDATE mail_campaign_targets SET status='cancelled', updated_at=? WHERE job_id=? AND status IN ('eligible','waiting')",
                (now, job_id),
            )
            if not self.database_url:
                connection.commit()
        return True

    def mark_campaign_target_excluded(self, job_id: int, reason: str = "suppressed") -> bool:
        """Record late suppression without counting it as provider failure."""

        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE mail_campaign_targets
                   SET status='excluded', exclusion_reason=?, updated_at=?
                   WHERE job_id=? AND status IN ('eligible','waiting')""",
                (str(reason or "suppressed")[:200], iso_now(), job_id),
            )
        return cursor.rowcount == 1

    def get_operation_target(self, operation_id: int, normalized_email: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mail_send_operation_targets WHERE operation_id=? AND normalized_email=?",
                (operation_id, normalized_email),
            ).fetchone()
        return dict(row) if row else None

    def get_outbound_message(self, workspace_id: int, message_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT m.*, j.id AS job_id, j.status AS job_status, j.provider_message_id AS job_provider_message_id,
                          a.email AS account_email, a.provider, a.status AS account_status,
                          r.name AS request_name, s.name AS supplier_name, s.external_key
                   FROM mail_messages m
                   LEFT JOIN mail_jobs j ON j.message_id=m.id
                   JOIN mail_accounts a ON a.id=m.mail_account_id
                   JOIN requests r ON r.id=m.request_id
                   JOIN suppliers s ON s.id=m.supplier_id
                   WHERE m.workspace_id=? AND m.id=? AND m.direction='outbound'""",
                (workspace_id, message_id),
            ).fetchone()
            if not row:
                return None
            attachments = connection.execute(
                "SELECT filename, mime_type, size_bytes, content FROM mail_attachments WHERE message_id=? ORDER BY id",
                (message_id,),
            ).fetchall()
            result = dict(row)
            result["attachments"] = [dict(item) for item in attachments]
            resolution = connection.execute(
                "SELECT resolved_at, comment FROM mail_delivery_resolutions WHERE message_id=?",
                (message_id,),
            ).fetchone()
            result["delivery_resolved"] = bool(resolution)
            result["delivery_resolution"] = dict(resolution) if resolution else None
        return result

    def list_delivery_unknown_jobs(self, workspace_id: int | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        clause = ""
        if workspace_id is not None:
            clause = " AND m.workspace_id=?"
            params.append(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT j.id AS job_id, j.message_id, j.mail_account_id,
                          m.workspace_id, m.request_id, m.supplier_id, m.from_email,
                          m.to_email, m.subject, m.body_text, m.body_html, m.message_id AS message_id_header,
                          m.in_reply_to, m.references_header, m.sent_at, a.user_id,
                          a.email AS account_email, a.provider, a.status AS account_status,
                          a.access_token_encrypted, a.refresh_token_encrypted, a.token_expires_at
                   FROM mail_jobs j JOIN mail_messages m ON m.id=j.message_id
                   JOIN mail_accounts a ON a.id=j.mail_account_id
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   WHERE j.status='delivery_unknown' AND m.status='delivery_unknown'""" + clause,
                params,
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["attachments"] = [
                    dict(attachment) for attachment in connection.execute(
                        "SELECT filename, mime_type, content FROM mail_attachments WHERE message_id=? ORDER BY id",
                        (row["message_id"],),
                    ).fetchall()
                ]
                result.append(item)
        return result

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
        operation_id: int | None = None,
        normalized_email: str | None = None,
        resend_of_message_id: int | None = None,
        campaign_id: int | None = None,
        campaign_ordinal: int | None = None,
        personalization_level: int = 0,
    ) -> dict[str, int]:
        now = iso_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if operation_id is not None:
                target = connection.execute(
                    "SELECT id, message_id FROM mail_send_operation_targets WHERE operation_id=? AND normalized_email=?",
                    (operation_id, normalized_email or to_email.strip().lower()),
                ).fetchone()
                if not target:
                    raise ValueError("Получатель отсутствует в операции отправки.")
                if target["message_id"] is not None:
                    return {
                        "job_id": int(connection.execute("SELECT id FROM mail_jobs WHERE message_id=?", (target["message_id"],)).fetchone()[0]),
                        "message_id": int(target["message_id"]),
                        "thread_id": int(connection.execute("SELECT thread_id FROM mail_messages WHERE id=?", (target["message_id"],)).fetchone()[0]),
                    }
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
            connection.execute(
                "INSERT INTO mail_message_integrity(message_id, state_schema_version, resend_of_message_id, created_at) VALUES (?, ?, ?, ?)",
                (message_id, MAIL_INTEGRITY_SCHEMA_VERSION, resend_of_message_id, now),
            )
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
                """INSERT INTO mail_job_integrity(
                    job_id, operation_id, state_schema_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)""",
                (job_id, operation_id, MAIL_INTEGRITY_SCHEMA_VERSION, now, now),
            )
            if operation_id is not None:
                connection.execute(
                    "UPDATE mail_send_operation_targets SET message_id=?, updated_at=? WHERE operation_id=? AND normalized_email=? AND message_id IS NULL",
                    (message_id, now, operation_id, normalized_email or to_email.strip().lower()),
                )
                if campaign_id is not None and campaign_ordinal is not None:
                    operation_target = connection.execute(
                        "SELECT id FROM mail_send_operation_targets WHERE operation_id=? AND normalized_email=?",
                        (operation_id, normalized_email or to_email.strip().lower()),
                    ).fetchone()
                    if operation_target:
                        self._insert_campaign_target_connection(
                            connection,
                            campaign_id=campaign_id,
                            operation_target_id=int(operation_target[0]),
                            job_id=job_id,
                            ordinal=campaign_ordinal,
                            normalized_email=normalized_email or to_email.strip().lower(),
                            supplier_id=supplier_id,
                            personalization_level=personalization_level,
                            now=now,
                        )
            connection.execute(
                """INSERT INTO request_supplier_states(request_id, supplier_id, mail_account_id, status, last_message_id, last_error, updated_at)
                   VALUES (?, ?, ?, 'queued', ?, NULL, ?)
                   ON CONFLICT(request_id, supplier_id) DO UPDATE SET mail_account_id=excluded.mail_account_id, status='queued', last_message_id=excluded.last_message_id, last_error=NULL, updated_at=excluded.updated_at""",
                (request_id, supplier_id, account_id, message_id, now),
            )
            connection.execute("UPDATE mail_threads SET last_message_at = ? WHERE id = ?", (now, thread_id))
            connection.commit()
        result = {"job_id": job_id, "message_id": message_id, "thread_id": thread_id}
        if operation_id is not None:
            result["operation_id"] = operation_id
        return result

    def _create_queued_message_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
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
        operation_id: int | None = None,
        normalized_email: str | None = None,
        resend_of_message_id: int | None = None,
        campaign_id: int | None = None,
        campaign_ordinal: int | None = None,
        personalization_level: int = 0,
    ) -> dict[str, int]:
        """Create one queued message inside a caller-owned transaction."""

        now = iso_now()
        if operation_id is not None:
            target = connection.execute(
                "SELECT id, message_id FROM mail_send_operation_targets WHERE operation_id=? AND normalized_email=?",
                (operation_id, normalized_email or to_email.strip().lower()),
            ).fetchone()
            if not target:
                raise ValueError("Получатель отсутствует в операции отправки.")
            if target["message_id"] is not None:
                existing_job = connection.execute(
                    "SELECT id FROM mail_jobs WHERE message_id=?", (target["message_id"],)
                ).fetchone()
                existing_thread = connection.execute(
                    "SELECT thread_id FROM mail_messages WHERE id=?", (target["message_id"],)
                ).fetchone()
                if not existing_job or not existing_thread:
                    raise ValueError("Целостность операции отправки нарушена.")
                return {
                    "job_id": int(existing_job[0]),
                    "message_id": int(target["message_id"]),
                    "thread_id": int(existing_thread[0]),
                }
        thread = connection.execute(
            "SELECT id FROM mail_threads WHERE workspace_id=? AND request_id=? AND supplier_id=?",
            (workspace_id, request_id, supplier_id),
        ).fetchone()
        if thread is None:
            connection.execute(
                "INSERT INTO mail_threads(workspace_id, user_id, request_id, supplier_id, mail_account_id, subject, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (workspace_id, user_id, request_id, supplier_id, account_id, subject, now),
            )
            thread_id = int(connection.execute("SELECT LASTVAL()" if self.database_url else "SELECT last_insert_rowid()").fetchone()[0])
        else:
            thread_id = int(thread["id"])
            connection.execute(
                "UPDATE mail_threads SET subject=?, mail_account_id=? WHERE id=?",
                (subject, account_id, thread_id),
            )
        connection.execute(
            """INSERT INTO mail_messages(
                   thread_id, workspace_id, user_id, request_id, supplier_id,
                   mail_account_id, message_id, in_reply_to, references_header,
                   direction, from_email, to_email, subject, body_text, body_html,
                   status, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'outbound', ?, ?, ?, ?, ?, 'queued', ?)""",
            (
                thread_id, workspace_id, user_id, request_id, supplier_id,
                account_id, message_id_header, in_reply_to, references_header,
                from_email, to_email, subject, body_text, body_html, now,
            ),
        )
        message_id = int(connection.execute("SELECT LASTVAL()" if self.database_url else "SELECT last_insert_rowid()").fetchone()[0])
        connection.execute(
            "INSERT INTO mail_message_integrity(message_id, state_schema_version, resend_of_message_id, created_at) VALUES (?, ?, ?, ?)",
            (message_id, MAIL_INTEGRITY_SCHEMA_VERSION, resend_of_message_id, now),
        )
        for attachment in attachments:
            connection.execute(
                "INSERT INTO mail_attachments(message_id, filename, mime_type, size_bytes, content) VALUES (?, ?, ?, ?, ?)",
                (message_id, attachment["filename"], attachment["mime_type"], attachment["size_bytes"], attachment["content"]),
            )
        connection.execute(
            "INSERT INTO mail_jobs(message_id, mail_account_id, status, attempts, created_at, updated_at) VALUES (?, ?, 'queued', 0, ?, ?)",
            (message_id, account_id, now, now),
        )
        job_id = int(connection.execute("SELECT LASTVAL()" if self.database_url else "SELECT last_insert_rowid()").fetchone()[0])
        connection.execute(
            """INSERT INTO mail_job_integrity(
                   job_id, operation_id, state_schema_version, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?)""",
            (job_id, operation_id, MAIL_INTEGRITY_SCHEMA_VERSION, now, now),
        )
        if operation_id is not None:
            connection.execute(
                "UPDATE mail_send_operation_targets SET message_id=?, updated_at=? WHERE operation_id=? AND normalized_email=? AND message_id IS NULL",
                (message_id, now, operation_id, normalized_email or to_email.strip().lower()),
            )
            if campaign_id is not None and campaign_ordinal is not None:
                operation_target = connection.execute(
                    "SELECT id FROM mail_send_operation_targets WHERE operation_id=? AND normalized_email=?",
                    (operation_id, normalized_email or to_email.strip().lower()),
                ).fetchone()
                if operation_target:
                    self._insert_campaign_target_connection(
                        connection,
                        campaign_id=campaign_id,
                        operation_target_id=int(operation_target[0]),
                        job_id=job_id,
                        ordinal=campaign_ordinal,
                        normalized_email=normalized_email or to_email.strip().lower(),
                        supplier_id=supplier_id,
                        personalization_level=personalization_level,
                        now=now,
                    )
        connection.execute(
            """INSERT INTO request_supplier_states(
                   request_id, supplier_id, mail_account_id, status,
                   last_message_id, last_error, updated_at
               ) VALUES (?, ?, ?, 'queued', ?, NULL, ?)
               ON CONFLICT(request_id, supplier_id) DO UPDATE SET
                   mail_account_id=excluded.mail_account_id, status='queued',
                   last_message_id=excluded.last_message_id, last_error=NULL,
                   updated_at=excluded.updated_at""",
            (request_id, supplier_id, account_id, message_id, now),
        )
        connection.execute("UPDATE mail_threads SET last_message_at=? WHERE id=?", (now, thread_id))
        result = {"job_id": job_id, "message_id": message_id, "thread_id": thread_id}
        if operation_id is not None:
            result["operation_id"] = operation_id
        return result

    def claim_job(self, pacing: PacingSettings | None = None, *, only_job_id: int | None = None) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """SELECT j.*, m.thread_id, m.workspace_id, m.user_id, m.request_id, m.supplier_id,
                          m.from_email, m.to_email, m.subject, m.body_text, m.body_html, m.in_reply_to,
                          m.references_header, m.message_id AS message_id_header, m.status AS message_status,
                          ji.state_schema_version, ji.operation_id, ji.claim_token AS previous_claim_token,
                          ji.irreversible_at, ji.lease_expires_at,
                          a.email AS account_email, a.provider, a.access_token_encrypted, a.refresh_token_encrypted, a.token_expires_at, a.status AS account_status,
                          s.external_key AS supplier_external_key
                   FROM mail_jobs j JOIN mail_messages m ON m.id = j.message_id
                   LEFT JOIN mail_job_integrity ji ON ji.job_id=j.id
                   LEFT JOIN mail_send_operations op ON op.id=ji.operation_id
                   JOIN mail_accounts a ON a.id = j.mail_account_id
                   LEFT JOIN suppliers s ON s.id = m.supplier_id
                   WHERE j.status = 'queued'
                     AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= ?)
                     AND (
                       ji.irreversible_at IS NULL
                       OR EXISTS (
                         SELECT 1 FROM mail_send_attempts retry_attempt
                         WHERE retry_attempt.job_id=j.id
                           AND retry_attempt.outcome='transient_rejected'
                           AND retry_attempt.ended_at IS NOT NULL
                           AND retry_attempt.id = (
                             SELECT MAX(latest_attempt.id)
                             FROM mail_send_attempts latest_attempt
                             WHERE latest_attempt.job_id=j.id
                           )
                       )
                     )
                     AND (
                       ji.operation_id IS NULL
                       OR (
                         op.status='ready'
                         AND (
                           NOT EXISTS (SELECT 1 FROM mail_campaign_targets ct WHERE ct.job_id=j.id)
                           OR EXISTS (
                             SELECT 1 FROM mail_campaign_targets ct
                             JOIN mail_campaigns c ON c.id=ct.campaign_id
                             WHERE ct.job_id=j.id AND ct.status='eligible' AND c.status='active'
                           )
                           OR EXISTS (
                              SELECT 1 FROM mail_continuation_plans cp
                              WHERE cp.operation_id=ji.operation_id AND cp.status='ready'
                           )
                         )
                       )
                     )
                     AND (? IS NULL OR j.id=?)
                   ORDER BY COALESCE(j.next_attempt_at, j.created_at), j.created_at, j.id""",
                (iso_now(), only_job_id, only_job_id),
            ).fetchall()
            row = None
            reservation: dict[str, Any] | None = None
            if pacing is None:
                row = rows[0] if rows else None
            else:
                self._expire_pacing_reservations(connection)
                for candidate in rows:
                    if not self._account_send_eligible(connection, int(candidate["mail_account_id"]), pacing):
                        continue
                    reservation = self._reserve_send_slot(
                        connection,
                        account_id=int(candidate["mail_account_id"]),
                        owner_type="job",
                        owner_id=int(candidate["id"]),
                        operation_id=int(candidate["operation_id"]) if candidate["operation_id"] is not None else None,
                        pacing=pacing,
                    )
                    if reservation:
                        row = candidate
                        break
            if row is None:
                connection.rollback()
                return None
            job_id = row["id"]
            now = iso_now()
            claim_token = secrets.token_urlsafe(32)
            claim_owner = f"pid:{os.getpid()}"
            lease_expires_at = iso_after(MAIL_LEASE_SECONDS)
            claimed = connection.execute(
                "UPDATE mail_jobs SET status='sending', next_attempt_at=NULL, updated_at=? WHERE id=? AND status='queued'",
                (now, job_id),
            )
            if claimed.rowcount != 1:
                connection.rollback()
                return None
            connection.execute(
                """INSERT INTO mail_job_integrity(job_id, operation_id, state_schema_version, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(job_id) DO NOTHING""",
                (job_id, row["operation_id"], MAIL_INTEGRITY_SCHEMA_VERSION, now, now),
            )
            integrity_update = connection.execute(
                """UPDATE mail_job_integrity
                   SET claim_owner=?, claim_token=?, lease_expires_at=?, updated_at=?
                   WHERE job_id=? AND state_schema_version=?""",
                (claim_owner, claim_token, lease_expires_at, now, job_id, MAIL_INTEGRITY_SCHEMA_VERSION),
            )
            if integrity_update.rowcount != 1:
                connection.rollback()
                return None
            connection.execute("UPDATE mail_messages SET status='sending' WHERE id=? AND status='queued'", (row["message_id"],))
            connection.execute("UPDATE request_supplier_states SET status='sending', updated_at=? WHERE request_id=? AND supplier_id=?", (now, row["request_id"], row["supplier_id"]))
            connection.commit()
            payload = dict(row)
            # Claiming is a lease, not a transport attempt.  The durable
            # attempt counter is charged at the irreversible gate, after the
            # reservation wait and all late safety checks have passed.
            payload["attempts"] = int(row["attempts"])
            payload["claim_owner"] = claim_owner
            payload["claim_token"] = claim_token
            payload["lease_expires_at"] = lease_expires_at
            payload["state_schema_version"] = MAIL_INTEGRITY_SCHEMA_VERSION
            if reservation:
                payload.update({
                    "pacing_reservation_token": reservation["reservation_token"],
                    "pacing_scheduled_not_before": reservation["scheduled_not_before"],
                })
            payload["attachments"] = [dict(item) for item in connection.execute("SELECT filename, mime_type, content FROM mail_attachments WHERE message_id = ?", (row["message_id"],)).fetchall()]
            return payload

    @staticmethod
    def _timestamp_is_future(value: str | None, now: datetime) -> bool:
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC) > now

    @staticmethod
    def _timestamp_within_window(value: str | None, now: datetime, seconds: int) -> bool:
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        age = (now - parsed.astimezone(UTC)).total_seconds()
        return 0 <= age <= seconds

    def _expire_pacing_reservations(self, connection: sqlite3.Connection | PostgresConnection) -> None:
        connection.execute(
            "UPDATE mail_send_reservations SET status='expired', released_at=?, release_reason='lease-expired' WHERE status='reserved' AND expires_at <= ?",
            (iso_now(), iso_now()),
        )

    def reconcile_stale_started_reservations(
        self,
        account_id: int | None = None,
        *,
        limit: int = 100,
    ) -> dict[str, int]:
        """Close only stale reservations whose terminal outcome is proven.

        A ``started`` reservation crosses the irreversible boundary and must
        not be expired merely because its lease elapsed.  The only safe
        automatic cleanup here is a terminal, durable outcome that already
        proves what happened to the transport attempt.  An uncertain outcome
        remains untouched while its owner is still in progress or
        contradictory.  Once Iteration 1 has durably fixed the owner as
        delivery_unknown, the reservation is safe to consume: that closes
        the account slot without granting resend permission.
        """

        bounded_limit = max(1, min(int(limit), 1000))
        now = iso_now()
        counts = {"scanned": 0, "consumed": 0, "unresolved": 0}
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            params: list[Any] = [now]
            account_clause = ""
            if account_id is not None:
                account_clause = " AND r.mail_account_id=?"
                params.append(int(account_id))
            params.append(bounded_limit)
            lock_clause = " FOR UPDATE" if self.database_url else ""
            reservations = connection.execute(
                f"""SELECT r.id, r.reservation_token, r.owner_type, r.owner_id,
                                  j.status AS job_status,
                                  m.status AS message_status,
                                  rp.status AS reply_status
                           FROM mail_send_reservations r
                           LEFT JOIN mail_jobs j
                             ON r.owner_type='job' AND j.id=r.owner_id
                           LEFT JOIN mail_messages m
                             ON j.id IS NOT NULL AND m.id=j.message_id
                           LEFT JOIN mail_inbox_replies rp
                             ON r.owner_type='reply' AND rp.id=r.owner_id
                           WHERE r.status='started'
                             AND r.expires_at <= ?{account_clause}
                           ORDER BY r.id
                           LIMIT ?{lock_clause}""",
                params,
            ).fetchall()
            counts["scanned"] = len(reservations)
            for reservation in reservations:
                attempt = connection.execute(
                    """SELECT outcome, ended_at
                       FROM mail_send_attempts
                       WHERE reservation_token=?
                       ORDER BY id DESC
                       LIMIT 1""",
                    (reservation["reservation_token"],),
                ).fetchone()
                outcome = str(attempt["outcome"] if attempt else "")
                ended_at = attempt["ended_at"] if attempt else None
                job_status = reservation["job_status"]
                message_status = reservation["message_status"]
                reply_status = reservation["reply_status"]

                safe_terminal = bool(ended_at) and (
                    (
                        outcome == "transient_rejected"
                        and (
                            (job_status == "queued" and message_status == "queued")
                            or reply_status == "failed"
                        )
                    )
                    or (
                        outcome == "permanent_rejected"
                        and (
                            (job_status == "failed" and message_status == "failed")
                            or reply_status == "failed"
                        )
                    )
                    or (
                        outcome == "accepted"
                        and (
                            (job_status == "sent" and message_status == "sent")
                            or reply_status == "sent"
                        )
                    )
                    or (
                        outcome == "uncertain"
                        and (
                            (job_status == "delivery_unknown" and message_status == "delivery_unknown")
                            or reply_status == "delivery_unknown"
                        )
                    )
                )
                if not safe_terminal:
                    counts["unresolved"] += 1
                    continue
                updated = connection.execute(
                    """UPDATE mail_send_reservations
                       SET status='consumed', consumed_at=?, release_reason=?
                       WHERE id=? AND status='started'""",
                    (now, "stale-known-terminal-recovery", reservation["id"]),
                )
                counts["consumed"] += int(updated.rowcount == 1)
            if not self.database_url:
                connection.commit()
        return counts

    def _ensure_account_pacing_state(self, connection: sqlite3.Connection | PostgresConnection, account_id: int) -> dict[str, Any]:
        now = iso_now()
        connection.execute(
            """INSERT INTO mail_account_outbound_state(mail_account_id, updated_at)
               VALUES (?, ?) ON CONFLICT(mail_account_id) DO NOTHING""",
            (account_id, now),
        )
        lock = " FOR UPDATE" if self.database_url else ""
        row = connection.execute(
            "SELECT * FROM mail_account_outbound_state WHERE mail_account_id=?" + lock,
            (account_id,),
        ).fetchone()
        return dict(row)

    def _account_send_eligible(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        account_id: int,
        pacing: PacingSettings,
    ) -> bool:
        now = utc_now()
        state = self._ensure_account_pacing_state(connection, account_id)
        changed = False
        if state.get("cooldown_until") and not self._timestamp_is_future(state["cooldown_until"], now):
            state["cooldown_until"] = None
            state["cooldown_reason"] = None
            changed = True
        if state.get("breaker_state") == "open" and not self._timestamp_is_future(state.get("breaker_until"), now):
            state["breaker_state"] = "closed"
            state["breaker_until"] = None
            state["breaker_reason"] = None
            state["failure_count"] = 0
            state["failure_window_started_at"] = None
            changed = True
        if changed:
            connection.execute(
                """UPDATE mail_account_outbound_state
                   SET cooldown_until=?, cooldown_reason=?, breaker_state=?, breaker_until=?, breaker_reason=?,
                       failure_count=?, failure_window_started_at=?, updated_at=? WHERE mail_account_id=?""",
                (
                    state.get("cooldown_until"), state.get("cooldown_reason"), state.get("breaker_state"),
                    state.get("breaker_until"), state.get("breaker_reason"), state.get("failure_count", 0),
                    state.get("failure_window_started_at"), iso_now(), account_id,
                ),
            )
        if self._timestamp_is_future(state.get("next_send_not_before"), now):
            return False
        if self._timestamp_is_future(state.get("cooldown_until"), now):
            return False
        if state.get("breaker_state") == "open":
            return False
        active_reservation = connection.execute(
            "SELECT 1 FROM mail_send_reservations WHERE mail_account_id=? AND status IN ('reserved','started') LIMIT 1",
            (account_id,),
        ).fetchone()
        if active_reservation:
            return False
        hour_start = (now - timedelta(hours=1)).isoformat()
        day_start = (now - timedelta(days=1)).isoformat()
        hour_count = int(connection.execute(
            "SELECT COUNT(*) FROM mail_send_attempts WHERE mail_account_id=? AND started_at IS NOT NULL AND started_at >= ?",
            (account_id, hour_start),
        ).fetchone()[0])
        day_count = int(connection.execute(
            "SELECT COUNT(*) FROM mail_send_attempts WHERE mail_account_id=? AND started_at IS NOT NULL AND started_at >= ?",
            (account_id, day_start),
        ).fetchone()[0])
        return hour_count < pacing.max_per_hour and day_count < pacing.max_per_day

    def _reserve_send_slot(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        account_id: int,
        owner_type: str,
        owner_id: int,
        operation_id: int | None,
        pacing: PacingSettings,
    ) -> dict[str, Any] | None:
        if not self._account_send_eligible(connection, account_id, pacing):
            return None
        now_dt = utc_now()
        delay = pacing.next_delay()
        scheduled = now_dt + timedelta(seconds=delay)
        expires = now_dt + timedelta(seconds=pacing.reservation_lease_seconds)
        token = secrets.token_urlsafe(32)
        connection.execute(
            """INSERT INTO mail_send_reservations(
                   mail_account_id, owner_type, owner_id, reservation_token,
                   reserved_at, expires_at, scheduled_not_before, status
               ) VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved')""",
            (account_id, owner_type, owner_id, token, now_dt.isoformat(), expires.isoformat(), scheduled.isoformat()),
        )
        connection.execute(
            """UPDATE mail_account_outbound_state
               SET next_send_not_before=?, last_operation_id=?, updated_at=?
               WHERE mail_account_id=?""",
            (scheduled.isoformat(), operation_id, now_dt.isoformat(), account_id),
        )
        return {"reservation_token": token, "scheduled_not_before": scheduled.isoformat()}

    def reserve_send_slot(
        self,
        account_id: int,
        *,
        owner_type: str,
        owner_id: int,
        operation_id: int | None = None,
        pacing: PacingSettings | None = None,
    ) -> dict[str, Any] | None:
        """Atomically reserve the same account budget used by queue workers."""

        pacing = pacing or PacingSettings()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            self._expire_pacing_reservations(connection)
            reservation = self._reserve_send_slot(
                connection, account_id=account_id, owner_type=owner_type,
                owner_id=owner_id, operation_id=operation_id, pacing=pacing,
            )
            if not reservation:
                if not self.database_url:
                    connection.rollback()
                return None
            if not self.database_url:
                connection.commit()
            return reservation

    def release_send_reservation(self, token: str | None, reason: str, *, reset_pacing: bool = False) -> bool:
        if not token:
            return False
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT mail_account_id, scheduled_not_before FROM mail_send_reservations WHERE reservation_token=? AND status IN ('reserved','started')",
                (token,),
            ).fetchone()
            if not row:
                if not self.database_url:
                    connection.rollback()
                return False
            connection.execute(
                "UPDATE mail_send_reservations SET status='released', released_at=?, release_reason=? WHERE reservation_token=? AND status IN ('reserved','started')",
                (now, (reason or "released")[:200], token),
            )
            if reset_pacing:
                connection.execute(
                    "UPDATE mail_account_outbound_state SET next_send_not_before=NULL, updated_at=? WHERE mail_account_id=? AND next_send_not_before=?",
                    (now, row["mail_account_id"], row["scheduled_not_before"]),
                )
            if not self.database_url:
                connection.commit()
        return True

    def _insert_send_attempt(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        job_id: int | None,
        message_id: int | None,
        reply_id: int | None,
        account_id: int,
        reservation_token: str | None,
        attempt_number: int,
        started_at: str,
        ended_at: str | None,
        outcome: str,
        provider_classification: str | None,
        irreversible_reached: bool,
        cooldown_triggered: bool,
        next_retry_at: str | None,
        error: str | None,
        smtp_stage: str | None = None,
        smtp_code: int | None = None,
        smtp_enhanced_status: str | None = None,
        provider_response_safe: str | None = None,
        exception_class: str | None = None,
    ) -> int:
        cursor = connection.execute(
            """INSERT INTO mail_send_attempts(
                   job_id, message_id, reply_id, mail_account_id, reservation_token,
                   attempt_number, started_at, ended_at, outcome, provider_classification,
                   irreversible_reached, cooldown_triggered, next_retry_at, sanitized_error
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id, message_id, reply_id, account_id, reservation_token, attempt_number,
                started_at, ended_at, outcome, provider_classification, int(irreversible_reached),
                int(cooldown_triggered), next_retry_at, (error or "")[:500] if error else None,
            ),
        )
        attempt_id = int(cursor.lastrowid)
        self._upsert_send_attempt_evidence(
            connection,
            attempt_id=attempt_id,
            smtp_stage=smtp_stage,
            smtp_code=smtp_code,
            smtp_enhanced_status=smtp_enhanced_status,
            provider_response_safe=provider_response_safe,
            exception_class=exception_class,
        )
        return attempt_id

    def _upsert_send_attempt_evidence(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        attempt_id: int,
        smtp_stage: str | None = None,
        smtp_code: int | None = None,
        smtp_enhanced_status: str | None = None,
        provider_response_safe: str | None = None,
        exception_class: str | None = None,
    ) -> None:
        now = iso_now()
        connection.execute(
            """INSERT INTO mail_send_attempt_evidence(
                   attempt_id, smtp_stage, smtp_code, smtp_enhanced_status,
                   provider_response_safe, exception_class, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(attempt_id) DO UPDATE SET
                   smtp_stage=excluded.smtp_stage,
                   smtp_code=excluded.smtp_code,
                   smtp_enhanced_status=excluded.smtp_enhanced_status,
                   provider_response_safe=excluded.provider_response_safe,
                   exception_class=excluded.exception_class,
                   updated_at=excluded.updated_at""",
            (
                attempt_id,
                (smtp_stage or "")[:40] if smtp_stage else None,
                smtp_code,
                (smtp_enhanced_status or "")[:40] if smtp_enhanced_status else None,
                (provider_response_safe or "")[:500] if provider_response_safe else None,
                (exception_class or "")[:200] if exception_class else None,
                now,
                now,
            ),
        )

    def _reset_account_after_success(self, connection: sqlite3.Connection | PostgresConnection, account_id: int, now: str) -> None:
        connection.execute(
            """UPDATE mail_account_outbound_state
               SET cooldown_until=NULL, cooldown_reason=NULL, cooldown_level=0,
                   breaker_state='closed', breaker_reason=NULL, breaker_until=NULL,
                   failure_window_started_at=NULL, failure_count=0, last_failure_at=NULL,
                   last_error=NULL, updated_at=? WHERE mail_account_id=?""",
            (now, account_id),
        )

    def finish_send_attempt(
        self,
        *,
        reservation_token: str | None,
        outcome: str,
        provider_classification: str | None = None,
        error: str | None = None,
        cooldown_triggered: bool = False,
        next_retry_at: str | None = None,
        account_id: int | None = None,
        smtp_stage: str | None = None,
        smtp_code: int | None = None,
        smtp_enhanced_status: str | None = None,
        provider_response_safe: str | None = None,
        exception_class: str | None = None,
    ) -> bool:
        if not reservation_token:
            return False
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, mail_account_id FROM mail_send_attempts WHERE reservation_token=? AND outcome='in_progress' ORDER BY id DESC LIMIT 1",
                (reservation_token,),
            ).fetchone()
            reservation = connection.execute(
                "SELECT mail_account_id FROM mail_send_reservations WHERE reservation_token=?",
                (reservation_token,),
            ).fetchone()
            actual_account_id = int((row or reservation)["mail_account_id"]) if (row or reservation) else account_id
            if not actual_account_id:
                if not self.database_url:
                    connection.rollback()
                return False
            if row:
                connection.execute(
                    "UPDATE mail_send_attempts SET ended_at=?, outcome=?, provider_classification=?, cooldown_triggered=?, next_retry_at=?, sanitized_error=? WHERE id=?",
                    (now, outcome, provider_classification, int(cooldown_triggered), next_retry_at, (error or "")[:500] if error else None, row["id"]),
                )
                self._upsert_send_attempt_evidence(
                    connection,
                    attempt_id=int(row["id"]),
                    smtp_stage=smtp_stage,
                    smtp_code=smtp_code,
                    smtp_enhanced_status=smtp_enhanced_status,
                    provider_response_safe=provider_response_safe,
                    exception_class=exception_class,
                )
            connection.execute(
                "UPDATE mail_send_reservations SET status='consumed', consumed_at=? WHERE reservation_token=? AND status IN ('reserved','started')",
                (now, reservation_token),
            )
            if outcome == "accepted":
                self._reset_account_after_success(connection, actual_account_id, now)
            if not self.database_url:
                connection.commit()
        return True

    def record_pre_gate_attempt(
        self,
        *,
        job: dict[str, Any],
        reservation_token: str | None,
        outcome: str,
        provider_classification: str | None,
        error: str | None,
        next_retry_at: str | None,
        transient: bool = False,
        rate_limited: bool = False,
        revoked: bool = False,
        pacing: PacingSettings | None = None,
        smtp_stage: str | None = None,
        smtp_code: int | None = None,
        smtp_enhanced_status: str | None = None,
        provider_response_safe: str | None = None,
        exception_class: str | None = None,
    ) -> dict[str, Any]:
        """Record a known provider outcome for a retryable/terminal attempt."""

        pacing = pacing or PacingSettings()
        now_dt = utc_now()
        now = now_dt.isoformat()
        account_id = int(job["mail_account_id"])
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            self._ensure_account_pacing_state(connection, account_id)
            state = dict(connection.execute("SELECT * FROM mail_account_outbound_state WHERE mail_account_id=?", (account_id,)).fetchone())
            cooldown_until = state.get("cooldown_until")
            cooldown_reason = state.get("cooldown_reason")
            cooldown_level = int(state.get("cooldown_level") or 0)
            breaker_state = state.get("breaker_state") or "closed"
            breaker_until = state.get("breaker_until")
            breaker_reason = state.get("breaker_reason")
            failure_count = int(state.get("failure_count") or 0)
            window_started = state.get("failure_window_started_at")
            cooldown_triggered = False
            if transient or revoked:
                if not self._timestamp_within_window(window_started, now_dt, pacing.breaker_window_seconds):
                    window_started = now
                    failure_count = 0
                failure_count += 1
                if revoked or failure_count >= pacing.breaker_failure_threshold:
                    breaker_state = "open"
                    breaker_until = (now_dt + timedelta(seconds=pacing.breaker_open_seconds)).isoformat()
                    breaker_reason = "authentication/account failure" if revoked else "repeated provider failures"
                    cooldown_until = breaker_until
                    cooldown_reason = breaker_reason
                    cooldown_triggered = True
                elif rate_limited or transient:
                    cooldown_level += 1
                    delay = pacing.cooldown_delay(cooldown_level - 1)
                    cooldown_until = (now_dt + timedelta(seconds=delay)).isoformat()
                    cooldown_reason = provider_classification or "transient provider refusal"
                    cooldown_triggered = True
            existing_attempt = connection.execute(
                "SELECT id FROM mail_send_attempts WHERE reservation_token=? AND outcome='in_progress' ORDER BY id DESC LIMIT 1",
                (reservation_token,),
            ).fetchone() if reservation_token else None
            if existing_attempt:
                # Iteration 1 records the durable pre-DATA gate before the
                # provider is contacted. Complete that same row so the audit
                # remains one row per real transport attempt.
                connection.execute(
                    """UPDATE mail_send_attempts SET ended_at=?, outcome=?, provider_classification=?,
                           cooldown_triggered=?, next_retry_at=?, sanitized_error=? WHERE id=?""",
                    (now, outcome, provider_classification, int(cooldown_triggered), next_retry_at, (error or "")[:500] if error else None, existing_attempt["id"]),
                )
                self._upsert_send_attempt_evidence(
                    connection,
                    attempt_id=int(existing_attempt["id"]),
                    smtp_stage=smtp_stage,
                    smtp_code=smtp_code,
                    smtp_enhanced_status=smtp_enhanced_status,
                    provider_response_safe=provider_response_safe,
                    exception_class=exception_class,
                )
            else:
                integrity = connection.execute(
                    "SELECT irreversible_at FROM mail_job_integrity WHERE job_id=?",
                    (int(job["id"]),),
                ).fetchone()
                irreversible_reached = bool(integrity and integrity["irreversible_at"] is not None)
                no_transport_started = (
                    str(smtp_stage or "") == "pre_data"
                    and str(provider_classification or "") in {"message-encoding", "recipient-encoding"}
                )
                if not irreversible_reached and not no_transport_started:
                    charged = connection.execute(
                        """UPDATE mail_jobs SET attempts=attempts+1, updated_at=?
                           WHERE id=? AND status='sending'
                             AND NOT EXISTS (
                               SELECT 1 FROM mail_job_integrity
                               WHERE job_id=? AND irreversible_at IS NOT NULL
                             )""",
                        (now, int(job["id"]), int(job["id"])),
                    )
                    if charged.rowcount != 1:
                        if not self.database_url:
                            connection.rollback()
                        return {"cooldown_triggered": False, "cooldown_until": cooldown_until, "breaker_state": breaker_state}
                current_job = connection.execute(
                    "SELECT attempts FROM mail_jobs WHERE id=?",
                    (int(job["id"]),),
                ).fetchone()
                self._insert_send_attempt(
                    connection,
                    job_id=int(job["id"]), message_id=int(job["message_id"]), reply_id=None,
                    account_id=account_id, reservation_token=reservation_token,
                    attempt_number=int(current_job["attempts"] or 1) if current_job else int(job.get("attempts") or 1),
                    started_at=now, ended_at=now,
                    outcome=outcome, provider_classification=provider_classification,
                    irreversible_reached=irreversible_reached, cooldown_triggered=cooldown_triggered,
                    next_retry_at=next_retry_at, error=error,
                    smtp_stage=smtp_stage, smtp_code=smtp_code,
                    smtp_enhanced_status=smtp_enhanced_status,
                    provider_response_safe=provider_response_safe,
                    exception_class=exception_class,
                )
            connection.execute(
                """UPDATE mail_account_outbound_state SET next_send_not_before=COALESCE(next_send_not_before, ?),
                       cooldown_until=?, cooldown_reason=?, cooldown_level=?, breaker_state=?, breaker_reason=?,
                       breaker_until=?, failure_window_started_at=?, failure_count=?, last_failure_at=?, last_error=?, updated_at=?
                   WHERE mail_account_id=?""",
                (
                    cooldown_until or now, cooldown_until, cooldown_reason, cooldown_level, breaker_state, breaker_reason,
                    breaker_until, window_started, failure_count, now, (error or "")[:500] if error else None, now, account_id,
                ),
            )
            connection.execute(
                "UPDATE mail_send_reservations SET status='consumed', consumed_at=? WHERE reservation_token=? AND status IN ('reserved','started')",
                (now, reservation_token),
            )
            if not self.database_url:
                connection.commit()
        return {"cooldown_triggered": cooldown_triggered, "cooldown_until": cooldown_until, "breaker_state": breaker_state}

    def record_reply_pre_gate_attempt(
        self,
        *,
        reply_id: int,
        reservation_token: str | None,
        outcome: str,
        provider_classification: str | None,
        error: str | None,
        next_retry_at: str | None,
        transient: bool = False,
        rate_limited: bool = False,
        revoked: bool = False,
        pacing: PacingSettings | None = None,
        smtp_stage: str | None = None,
        smtp_code: int | None = None,
        smtp_enhanced_status: str | None = None,
        provider_response_safe: str | None = None,
        exception_class: str | None = None,
    ) -> dict[str, Any]:
        """Apply provider protection to the synchronous reply path as well."""

        pacing = pacing or PacingSettings()
        now_dt = utc_now()
        now = now_dt.isoformat()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            reply = connection.execute("SELECT mail_account_id FROM mail_inbox_replies WHERE id=?", (reply_id,)).fetchone()
            if not reply:
                if not self.database_url:
                    connection.rollback()
                return {"cooldown_triggered": False, "cooldown_until": None, "breaker_state": "closed"}
            account_id = int(reply["mail_account_id"])
            self._ensure_account_pacing_state(connection, account_id)
            state = dict(connection.execute("SELECT * FROM mail_account_outbound_state WHERE mail_account_id=?", (account_id,)).fetchone())
            cooldown_until = state.get("cooldown_until")
            cooldown_reason = state.get("cooldown_reason")
            cooldown_level = int(state.get("cooldown_level") or 0)
            breaker_state = state.get("breaker_state") or "closed"
            breaker_until = state.get("breaker_until")
            breaker_reason = state.get("breaker_reason")
            failure_count = int(state.get("failure_count") or 0)
            window_started = state.get("failure_window_started_at")
            cooldown_triggered = False
            if transient or revoked:
                if not self._timestamp_within_window(window_started, now_dt, pacing.breaker_window_seconds):
                    window_started = now
                    failure_count = 0
                failure_count += 1
                if revoked or failure_count >= pacing.breaker_failure_threshold:
                    breaker_state = "open"
                    breaker_until = (now_dt + timedelta(seconds=pacing.breaker_open_seconds)).isoformat()
                    breaker_reason = "authentication/account failure" if revoked else "repeated provider failures"
                    cooldown_until = breaker_until
                    cooldown_reason = breaker_reason
                    cooldown_triggered = True
                else:
                    cooldown_level += 1
                    cooldown_until = (now_dt + timedelta(seconds=pacing.cooldown_delay(cooldown_level - 1))).isoformat()
                    cooldown_reason = provider_classification or "transient provider refusal"
                    cooldown_triggered = True
            existing_attempt = connection.execute(
                "SELECT id FROM mail_send_attempts WHERE reservation_token=? AND outcome='in_progress' ORDER BY id DESC LIMIT 1",
                (reservation_token,),
            ).fetchone() if reservation_token else None
            if existing_attempt:
                connection.execute(
                    """UPDATE mail_send_attempts SET ended_at=?, outcome=?, provider_classification=?,
                           cooldown_triggered=?, next_retry_at=?, sanitized_error=? WHERE id=?""",
                    (now, outcome, provider_classification, int(cooldown_triggered), next_retry_at, (error or "")[:500] if error else None, existing_attempt["id"]),
                )
                self._upsert_send_attempt_evidence(
                    connection,
                    attempt_id=int(existing_attempt["id"]),
                    smtp_stage=smtp_stage,
                    smtp_code=smtp_code,
                    smtp_enhanced_status=smtp_enhanced_status,
                    provider_response_safe=provider_response_safe,
                    exception_class=exception_class,
                )
            else:
                self._insert_send_attempt(
                    connection,
                    job_id=None, message_id=None, reply_id=reply_id,
                    account_id=account_id, reservation_token=reservation_token,
                    attempt_number=1, started_at=now, ended_at=now,
                    outcome=outcome, provider_classification=provider_classification,
                    irreversible_reached=True, cooldown_triggered=cooldown_triggered,
                    next_retry_at=next_retry_at, error=error,
                    smtp_stage=smtp_stage, smtp_code=smtp_code,
                    smtp_enhanced_status=smtp_enhanced_status,
                    provider_response_safe=provider_response_safe,
                    exception_class=exception_class,
                )
            connection.execute(
                """UPDATE mail_account_outbound_state SET next_send_not_before=COALESCE(next_send_not_before, ?),
                       cooldown_until=?, cooldown_reason=?, cooldown_level=?, breaker_state=?, breaker_reason=?,
                       breaker_until=?, failure_window_started_at=?, failure_count=?, last_failure_at=?, last_error=?, updated_at=?
                   WHERE mail_account_id=?""",
                (
                    cooldown_until or now, cooldown_until, cooldown_reason, cooldown_level, breaker_state, breaker_reason,
                    breaker_until, window_started, failure_count, now, (error or "")[:500] if error else None, now, account_id,
                ),
            )
            connection.execute(
                "UPDATE mail_send_reservations SET status='consumed', consumed_at=? WHERE reservation_token=? AND status IN ('reserved','started')",
                (now, reservation_token),
            )
            if not self.database_url:
                connection.commit()
        return {"cooldown_triggered": cooldown_triggered, "cooldown_until": cooldown_until, "breaker_state": breaker_state}

    def next_pacing_wake_seconds(self, pacing: PacingSettings, default: float = 60.0) -> float:
        """Return a bounded sleep hint; wake_event can shorten it."""

        now = utc_now()
        waits: list[float] = []
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT DISTINCT j.mail_account_id FROM mail_jobs j
                   LEFT JOIN mail_job_integrity ji ON ji.job_id=j.id
                   LEFT JOIN mail_send_operations op ON op.id=ji.operation_id
                   WHERE j.status='queued' AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= ?)
                     AND (ji.operation_id IS NULL OR op.status='ready')""",
                (now.isoformat(),),
            ).fetchall()
            for row in rows:
                account_id = int(row["mail_account_id"])
                state = self._ensure_account_pacing_state(connection, account_id)
                for key in ("next_send_not_before", "cooldown_until", "breaker_until"):
                    value = state.get(key)
                    if value:
                        try:
                            parsed = datetime.fromisoformat(str(value))
                            if parsed.tzinfo is None:
                                parsed = parsed.replace(tzinfo=UTC)
                            waits.append(max(0.0, (parsed.astimezone(UTC) - now).total_seconds()))
                        except ValueError:
                            pass
                for window_seconds, limit in ((3600, pacing.max_per_hour), (86400, pacing.max_per_day)):
                    window_start = (now - timedelta(seconds=window_seconds)).isoformat()
                    count_row = connection.execute(
                        "SELECT COUNT(*) AS count, MIN(started_at) AS oldest FROM mail_send_attempts WHERE mail_account_id=? AND started_at IS NOT NULL AND started_at>=?",
                        (account_id, window_start),
                    ).fetchone()
                    if count_row and int(count_row["count"] or 0) >= limit and count_row["oldest"]:
                        try:
                            parsed = datetime.fromisoformat(str(count_row["oldest"]))
                            if parsed.tzinfo is None:
                                parsed = parsed.replace(tzinfo=UTC)
                            waits.append(max(0.0, (parsed.astimezone(UTC) + timedelta(seconds=window_seconds) - now).total_seconds()))
                        except ValueError:
                            pass
            next_job = connection.execute(
                "SELECT MIN(next_attempt_at) AS next_attempt_at FROM mail_jobs WHERE status='queued' AND next_attempt_at IS NOT NULL"
            ).fetchone()
            if next_job and next_job["next_attempt_at"]:
                try:
                    parsed = datetime.fromisoformat(str(next_job["next_attempt_at"]))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    waits.append(max(0.0, (parsed.astimezone(UTC) - now).total_seconds()))
                except ValueError:
                    pass
        return min([default, 60.0, *waits]) if waits else min(default, 60.0)

    def pacing_status(self, account_id: int, pacing: PacingSettings | None = None) -> dict[str, Any]:
        pacing = pacing or PacingSettings()
        with self.connect() as connection:
            state = self._ensure_account_pacing_state(connection, account_id)
            now = utc_now()
            hour_start = (now - timedelta(hours=1)).isoformat()
            day_start = (now - timedelta(days=1)).isoformat()
            hour_count = int(connection.execute("SELECT COUNT(*) FROM mail_send_attempts WHERE mail_account_id=? AND started_at>=?", (account_id, hour_start)).fetchone()[0])
            day_count = int(connection.execute("SELECT COUNT(*) FROM mail_send_attempts WHERE mail_account_id=? AND started_at>=?", (account_id, day_start)).fetchone()[0])
            reason = "eligible"
            next_eligible_at = None
            if state.get("breaker_state") == "open":
                reason = "account_breaker_open"
                next_eligible_at = state.get("breaker_until")
            elif state.get("cooldown_until") and self._timestamp_is_future(state.get("cooldown_until"), now):
                reason = "account_cooldown"
                next_eligible_at = state.get("cooldown_until")
            elif state.get("next_send_not_before") and self._timestamp_is_future(state.get("next_send_not_before"), now):
                reason = "pacing_wait"
                next_eligible_at = state.get("next_send_not_before")
            elif hour_count >= pacing.max_per_hour:
                reason = "hour_budget_wait"
            elif day_count >= pacing.max_per_day:
                reason = "day_budget_wait"
            active = connection.execute(
                "SELECT 1 FROM mail_send_reservations WHERE mail_account_id=? AND status IN ('reserved','started') LIMIT 1",
                (account_id,),
            ).fetchone()
            if active and reason == "eligible":
                reason = "reservation_in_progress"
            return {
                **state,
                "hour_count": hour_count,
                "day_count": day_count,
                "max_per_hour": pacing.max_per_hour,
                "max_per_day": pacing.max_per_day,
                "reason": reason,
                "next_eligible_at": next_eligible_at,
            }

    def _job_status_transition(
        self,
        *,
        job_id: int,
        message_id: int,
        target_status: str,
        error: str | None = None,
        next_attempt_at: str | None = None,
        claim_token: str | None = None,
        provider_message_id: str | None = None,
        generated_message_id: str | None = None,
        sent_at: str | None = None,
    ) -> bool:
        """Atomically move job, message, and supplier state together.

        The optional token keeps older callers source-compatible while every
        new queue path supplies the claim proof. A false result means the
        worker no longer owns the job; it must never send again.
        """

        now = sent_at or iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            params: list[Any] = [target_status, next_attempt_at, (error or "")[:500] if error else None, now, job_id]
            condition = "id=? AND status='sending'"
            if claim_token is not None:
                condition += " AND EXISTS (SELECT 1 FROM mail_job_integrity ji WHERE ji.job_id=mail_jobs.id AND ji.claim_token=?)"
                params.append(claim_token)
            cursor = connection.execute(
                f"UPDATE mail_jobs SET status=?, next_attempt_at=?, last_error=?, updated_at=? WHERE {condition}",
                params,
            )
            if cursor.rowcount != 1:
                if not self.database_url:
                    connection.rollback()
                return False
            if target_status == "sent":
                stored = connection.execute("SELECT message_id FROM mail_messages WHERE id=?", (message_id,)).fetchone()
                if stored and stored["message_id"] and stored["message_id"] != generated_message_id:
                    raise ValueError("Провайдер вернул другой идентификатор письма.")
                connection.execute(
                    "UPDATE mail_messages SET status='sent', provider_message_id=?, sent_at=?, error=NULL WHERE id=?",
                    (provider_message_id, now, message_id),
                )
                connection.execute(
                    "UPDATE request_supplier_states SET status='sent', last_error=NULL, updated_at=? WHERE last_message_id=?",
                    (now, message_id),
                )
            elif target_status == "delivery_unknown":
                connection.execute(
                    "UPDATE mail_messages SET status='delivery_unknown', error=? WHERE id=?",
                    ((error or "Не удалось подтвердить отправку.")[:500], message_id),
                )
                connection.execute(
                    "UPDATE request_supplier_states SET status='delivery_unknown', last_error=?, updated_at=? WHERE last_message_id=?",
                    ((error or "Не удалось подтвердить отправку.")[:500], now, message_id),
                )
            else:
                connection.execute(
                    "UPDATE mail_messages SET status=?, error=? WHERE id=?",
                    (target_status, (error or "")[:500] if error else None, message_id),
                )
                connection.execute(
                    "UPDATE request_supplier_states SET status=?, last_error=?, updated_at=? WHERE last_message_id=?",
                    (target_status, (error or "")[:500] if error else None, now, message_id),
                )
            connection.execute(
                "UPDATE mail_job_integrity SET claim_owner=NULL, claim_token=NULL, lease_expires_at=NULL, updated_at=? WHERE job_id=?",
                (now, job_id),
            )
            retry_status = {
                "sent": "accepted",
                "delivery_unknown": "delivery_unknown",
                "failed": "failed",
                "queued": "queued",
            }.get(target_status)
            if retry_status:
                connection.execute(
                    """UPDATE mail_cross_provider_retries
                       SET status=?, last_error=?, updated_at=?
                       WHERE operation_id=(SELECT operation_id FROM mail_job_integrity WHERE job_id=?)
                         AND status NOT IN ('accepted', 'delivery_unknown')""",
                    (retry_status, (error or "")[:500] if error else None, now, job_id),
                )
            if not self.database_url:
                connection.commit()
        return True

    def mark_job_sent(
        self,
        job_id: int,
        message_id: int,
        provider_message_id: str | None,
        generated_message_id: str,
        sent_at: str,
        claim_token: str | None = None,
    ) -> bool:
        return self._job_status_transition(
            job_id=job_id, message_id=message_id, target_status="sent",
            claim_token=claim_token, provider_message_id=provider_message_id,
            generated_message_id=generated_message_id, sent_at=sent_at,
        )

    def retry_job(self, job_id: int, message_id: int, error: str, next_attempt_at: str, claim_token: str | None = None) -> bool:
        return self._job_status_transition(
            job_id=job_id, message_id=message_id, target_status="queued",
            error=error, next_attempt_at=next_attempt_at, claim_token=claim_token,
        )

    def release_claim(self, job_id: int, message_id: int, error: str = "", claim_token: str | None = None) -> bool:
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            params: list[Any] = [None, (error or "")[:500] if error else None, iso_now(), job_id]
            condition = "id=? AND status='sending'"
            if claim_token is not None:
                condition += " AND EXISTS (SELECT 1 FROM mail_job_integrity ji WHERE ji.job_id=mail_jobs.id AND ji.claim_token=?)"
                params.append(claim_token)
            # A claim is not charged.  Only a claim that already crossed the
            # irreversible gate has to be neutralized when a later guard
            # releases it (for example, a kill-switch race after I1).
            decremented_attempts = "GREATEST(0, attempts-1)" if self.database_url else "MAX(0, attempts-1)"
            attempts_after_release = (
                f"CASE WHEN EXISTS (SELECT 1 FROM mail_job_integrity ji2 "
                f"WHERE ji2.job_id=mail_jobs.id AND ji2.irreversible_at IS NOT NULL) "
                f"THEN {decremented_attempts} ELSE attempts END"
            )
            cursor = connection.execute(
                f"UPDATE mail_jobs SET status='queued', next_attempt_at=?, last_error=?, attempts={attempts_after_release}, updated_at=? WHERE {condition}",
                params,
            )
            if cursor.rowcount != 1:
                if not self.database_url:
                    connection.rollback()
                return False
            connection.execute(
                "UPDATE mail_messages SET status='queued', error=NULL WHERE id=?",
                (message_id,),
            )
            connection.execute(
                "UPDATE request_supplier_states SET status='queued', last_error=NULL, updated_at=? WHERE last_message_id=?",
                (iso_now(), message_id),
            )
            connection.execute(
                "UPDATE mail_job_integrity SET claim_owner=NULL, claim_token=NULL, lease_expires_at=NULL, updated_at=? WHERE job_id=?",
                (iso_now(), job_id),
            )
            if not self.database_url:
                connection.commit()
        return True

    def fail_job(self, job_id: int, message_id: int, error: str, claim_token: str | None = None) -> bool:
        return self._job_status_transition(
            job_id=job_id, message_id=message_id, target_status="failed",
            error=error, claim_token=claim_token,
        )

    def fail_claim_without_attempt(self, job_id: int, message_id: int, error: str, claim_token: str | None = None) -> bool:
        """Terminally block a claimed job without charging a send attempt."""

        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            params: list[Any] = [(error or "")[:500], now, job_id]
            condition = "id=? AND status='sending' AND NOT EXISTS (SELECT 1 FROM mail_job_integrity ji WHERE ji.job_id=mail_jobs.id AND ji.irreversible_at IS NOT NULL)"
            if claim_token is not None:
                condition += " AND EXISTS (SELECT 1 FROM mail_job_integrity ji WHERE ji.job_id=mail_jobs.id AND ji.claim_token=?)"
                params.append(claim_token)
            cursor = connection.execute(
                f"UPDATE mail_jobs SET status='failed', next_attempt_at=NULL, last_error=?, updated_at=? WHERE {condition}",
                params,
            )
            if cursor.rowcount != 1:
                if not self.database_url:
                    connection.rollback()
                return False
            connection.execute("UPDATE mail_messages SET status='failed', error=? WHERE id=?", ((error or "")[:500], message_id))
            connection.execute(
                "UPDATE request_supplier_states SET status='failed', last_error=?, updated_at=? WHERE last_message_id=?",
                ((error or "")[:500], now, message_id),
            )
            connection.execute(
                "UPDATE mail_job_integrity SET claim_owner=NULL, claim_token=NULL, lease_expires_at=NULL, updated_at=? WHERE job_id=?",
                (now, job_id),
            )
            connection.execute(
                """UPDATE mail_cross_provider_retries
                   SET status='failed', last_error=?, updated_at=?
                   WHERE operation_id=(SELECT operation_id FROM mail_job_integrity WHERE job_id=?)
                     AND status NOT IN ('accepted', 'delivery_unknown')""",
                ((error or "")[:500], now, job_id),
            )
            if not self.database_url:
                connection.commit()
        return True

    def mark_job_delivery_unknown(self, job_id: int, message_id: int, error: str, claim_token: str | None = None) -> bool:
        return self._job_status_transition(
            job_id=job_id, message_id=message_id, target_status="delivery_unknown",
            error=error, claim_token=claim_token,
        )

    def get_job_integrity(self, job_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM mail_job_integrity WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def enter_irreversible_stage(
        self,
        job_id: int,
        claim_token: str,
        reservation_token: str | None = None,
        *,
        runtime_provenance: dict[str, Any] | None = None,
    ) -> bool:
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """UPDATE mail_job_integrity SET irreversible_at=?, updated_at=?
                   WHERE job_id=? AND state_schema_version=? AND claim_token=?
                     AND EXISTS (SELECT 1 FROM mail_jobs WHERE id=? AND status='sending')
                     AND (
                       NOT EXISTS (SELECT 1 FROM mail_campaign_targets ct WHERE ct.job_id=?)
                       OR EXISTS (
                         SELECT 1 FROM mail_campaign_targets ct
                         JOIN mail_campaigns c ON c.id=ct.campaign_id
                         WHERE ct.job_id=? AND ct.status='eligible' AND c.status='active'
                       )
                     )""",
                (now, now, job_id, MAIL_INTEGRITY_SCHEMA_VERSION, claim_token, job_id, job_id, job_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False

            # The irreversible gate is the first point at which this claimed
            # job becomes a real transport opportunity.  Charging attempts
            # here keeps future reservations and kill-switch/suppression
            # releases at zero while preserving retry numbering.
            attempts_update = connection.execute(
                "UPDATE mail_jobs SET attempts=attempts+1, updated_at=? WHERE id=? AND status='sending'",
                (now, job_id),
            )
            if attempts_update.rowcount != 1:
                connection.rollback()
                return False

            if reservation_token:
                job = connection.execute(
                    "SELECT message_id, mail_account_id, attempts FROM mail_jobs WHERE id=?",
                    (job_id,),
                ).fetchone()
                if not job:
                    connection.rollback()
                    return False
                attempt_id = self._insert_send_attempt(
                    connection,
                    job_id=job_id, message_id=int(job["message_id"]), reply_id=None,
                    account_id=int(job["mail_account_id"]), reservation_token=reservation_token,
                    attempt_number=int(job["attempts"] or 1), started_at=now, ended_at=None,
                    outcome="in_progress", provider_classification="irreversible-stage",
                    irreversible_reached=True, cooldown_triggered=False,
                    next_retry_at=None, error=None,
                )
                if runtime_provenance:
                    connection.execute(
                        """INSERT INTO mail_send_attempt_runtime(
                               attempt_id, runtime_id, db_identity,
                               canonical_check_passed, recorded_at
                           ) VALUES (?, ?, ?, ?, ?)""",
                        (
                            attempt_id,
                            runtime_provenance["runtime_id"],
                            runtime_provenance["db_identity"],
                            int(runtime_provenance["canonical_check_passed"]),
                            now,
                        ),
                    )
                reservation_update = connection.execute(
                    "UPDATE mail_send_reservations SET status='started', started_at=? WHERE reservation_token=? AND status='reserved'",
                    (now, reservation_token),
                )
                if reservation_update.rowcount != 1:
                    connection.rollback()
                    return False
            if not self.database_url:
                connection.commit()
        return True

    def mark_copy_status(self, job_id: int, status: str, error: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_job_integrity SET copy_status=?, copy_error=?, updated_at=? WHERE job_id=?",
                (status, (error or "")[:500] if error else None, iso_now(), job_id),
            )

    def mark_job_verified_sent(self, message_id: int, sent_at: str | None = None) -> bool:
        now = sent_at or iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM mail_jobs WHERE message_id=? AND status='delivery_unknown'",
                (message_id,),
            ).fetchone()
            if not row:
                if not self.database_url:
                    connection.rollback()
                return False
            job_id = int(row["id"])
            connection.execute("UPDATE mail_jobs SET status='sent', last_error=NULL, updated_at=? WHERE id=?", (now, job_id))
            connection.execute("UPDATE mail_messages SET status='sent', sent_at=?, error=NULL WHERE id=?", (now, message_id))
            connection.execute("UPDATE request_supplier_states SET status='sent', last_error=NULL, updated_at=? WHERE last_message_id=?", (now, message_id))
            connection.execute("UPDATE mail_job_integrity SET copy_status='verified', updated_at=? WHERE job_id=?", (now, job_id))
            if not self.database_url:
                connection.commit()
        return True

    def count_sent_today(self, account_id: int) -> int:
        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM mail_messages WHERE mail_account_id = ? AND status='sent' AND sent_at >= ?", (account_id, start)).fetchone()[0])

    def outgoing_enabled(self) -> bool:
        """Read the durable gate fail-closed, including on corrupt/missing DB state."""

        try:
            with self.connect() as connection:
                row = connection.execute("SELECT outgoing_enabled FROM mail_runtime_controls WHERE id=1").fetchone()
        except Exception:  # noqa: BLE001 — transport must be blocked on DB failure
            log.exception("Unable to read durable outgoing switch; treating it as disabled.")
            return False
        if not row:
            return False
        value = row[0]
        if type(value) is not int or value not in (0, 1):
            log.error("Invalid durable outgoing switch value %r; treating it as disabled.", value)
            return False
        return value == 1

    def set_outgoing_enabled(self, enabled: bool) -> bool:
        """Persist an already-authorized explicit outgoing-control decision."""

        if type(enabled) is not bool:
            raise ValueError("outgoing_enabled must be a boolean.")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_runtime_controls(id, outgoing_enabled, updated_at)
                   VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       outgoing_enabled=excluded.outgoing_enabled,
                       updated_at=excluded.updated_at""",
                (int(enabled), iso_now()),
            )
        return enabled

    def _historical_queued_reconciliation_preview_connection(
        self,
        connection: sqlite3.Connection | PostgresConnection,
        *,
        workspace_id: int,
        user_id: int,
        job_id: int,
        expected_resolution: str,
    ) -> dict[str, Any]:
        """Validate one stale queued job against durable evidence only."""

        resolution = str(expected_resolution or "").strip().lower()
        if resolution not in {"delivery_unknown", "accepted_history"}:
            raise ValueError("Unsupported historical queue resolution.")
        row = connection.execute(
            """SELECT j.id AS job_id, j.message_id, j.mail_account_id,
                      j.status AS job_status, j.attempts AS job_attempts,
                      j.provider_message_id AS job_provider_message_id,
                      m.workspace_id, m.user_id, m.request_id, m.supplier_id,
                      m.to_email, m.status AS message_status, m.sent_at,
                      ji.irreversible_at, ji.claim_owner, ji.claim_token,
                      ji.lease_expires_at, ma.provider,
                      ct.id AS campaign_target_id, ct.status AS target_status,
                      ct.exclusion_reason AS target_exclusion_reason,
                      c.status AS campaign_status,
                      COALESCE((SELECT outgoing_enabled FROM mail_runtime_controls WHERE id=1), 0) AS outgoing_enabled
               FROM mail_jobs j
               JOIN mail_messages m ON m.id=j.message_id
               JOIN mail_accounts ma ON ma.id=j.mail_account_id
               LEFT JOIN mail_job_integrity ji ON ji.job_id=j.id
               LEFT JOIN mail_campaign_targets ct ON ct.job_id=j.id
               LEFT JOIN mail_campaigns c ON c.id=ct.campaign_id
               WHERE j.id=? AND m.workspace_id=? AND m.user_id=?
                 AND m.direction='outbound'""",
            (int(job_id), int(workspace_id), int(user_id)),
        ).fetchone()
        if not row:
            raise ValueError("Historical queued job was not found for this owner.")
        email = _normalized_mail_address(row["to_email"])
        attempts = [dict(item) for item in connection.execute(
            """SELECT a.id, a.outcome, a.provider_classification,
                      a.irreversible_reached, e.smtp_stage, e.smtp_code,
                      e.provider_response_safe, e.exception_class
               FROM mail_send_attempts a
               LEFT JOIN mail_send_attempt_evidence e ON e.attempt_id=a.id
               WHERE a.job_id=? ORDER BY a.id""",
            (int(job_id),),
        ).fetchall()]
        accepted_event = connection.execute(
            """SELECT id, provider_type, accepted_at, evidence_sha256
               FROM mail_reconciled_outbound_events
               WHERE request_id=? AND supplier_id=?
                 AND LOWER(TRIM(normalized_recipient))=? AND outcome='accepted'
               ORDER BY accepted_at DESC, id DESC LIMIT 1""",
            (int(row["request_id"]), int(row["supplier_id"]), email),
        ).fetchone()
        active_reservation = bool(connection.execute(
            """SELECT 1 FROM mail_send_reservations
               WHERE owner_type='job' AND owner_id=?
                 AND status IN ('reserved', 'started') LIMIT 1""",
            (int(job_id),),
        ).fetchone())
        target_job_status = "delivery_unknown" if resolution == "delivery_unknown" else "cancelled"
        target_message_status = target_job_status
        target_marker_matches = row["campaign_target_id"] is None or (
            str(row["target_status"] or "") == (
                "delivery_unknown" if resolution == "delivery_unknown" else "reconciled"
            )
            and (
                resolution == "delivery_unknown"
                or str(row["target_exclusion_reason"] or "") == "accepted_history_reconciled"
            )
        )
        already_reconciled = (
            str(row["job_status"] or "") == target_job_status
            and str(row["message_status"] or "") == target_message_status
            and target_marker_matches
        )
        reasons: list[str] = []
        if int(row["outgoing_enabled"] or 0):
            reasons.append("durable_outgoing_enabled")
        if active_reservation:
            reasons.append("active_reservation")
        if row["claim_owner"] or row["claim_token"] or row["lease_expires_at"]:
            reasons.append("active_claim")
        if str(row["provider"] or "") != "yandex":
            reasons.append("source_provider_not_yandex")
        if str(row["campaign_status"] or "") == "active":
            reasons.append("campaign_active")
        if not already_reconciled and (
            str(row["job_status"] or "") != "queued"
            or str(row["message_status"] or "") != "queued"
        ):
            reasons.append("source_not_queued")
        if row["job_provider_message_id"] or row["sent_at"]:
            reasons.append("source_has_provider_acceptance_fields")

        if resolution == "accepted_history":
            if not accepted_event:
                reasons.append("accepted_reconciliation_event_missing")
            if attempts or int(row["job_attempts"] or 0) != 0:
                reasons.append("source_has_send_attempts")
            if row["irreversible_at"] is not None:
                reasons.append("source_crossed_irreversible_gate")
        else:
            accepted_provider = self._accepted_supplier_provider(
                connection,
                int(row["request_id"]),
                int(row["supplier_id"]),
                email,
            )
            outcomes = {str(item.get("outcome") or "") for item in attempts}
            if accepted_event or accepted_provider or "accepted" in outcomes:
                reasons.append("accepted_history_present")
            if not attempts or int(row["job_attempts"] or 0) <= 0:
                reasons.append("attempt_evidence_missing")
            if outcomes and outcomes != {"transient_rejected"}:
                reasons.append("unexpected_attempt_outcome")
            if attempts and not any(bool(item.get("irreversible_reached")) for item in attempts):
                reasons.append("irreversible_attempt_evidence_missing")
            if any(int(item.get("smtp_code") or 0) == 250 for item in attempts):
                reasons.append("smtp_acceptance_present")

        return {
            "safe": not reasons,
            "already_reconciled": already_reconciled and not reasons,
            "expected_resolution": resolution,
            "job_id": int(row["job_id"]),
            "message_id": int(row["message_id"]),
            "request_id": int(row["request_id"]),
            "supplier_id": int(row["supplier_id"]),
            "normalized_recipient": email,
            "campaign_target_id": int(row["campaign_target_id"]) if row["campaign_target_id"] is not None else None,
            "attempt_count": len(attempts),
            "accepted_event_id": int(accepted_event["id"]) if accepted_event else None,
            "reasons": list(dict.fromkeys(reasons)),
        }

    def preview_historical_queued_reconciliation(
        self,
        workspace_id: int,
        user_id: int,
        job_id: int,
        *,
        expected_resolution: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            return self._historical_queued_reconciliation_preview_connection(
                connection,
                workspace_id=workspace_id,
                user_id=user_id,
                job_id=job_id,
                expected_resolution=expected_resolution,
            )

    def reconcile_historical_queued_job(
        self,
        workspace_id: int,
        user_id: int,
        job_id: int,
        *,
        expected_resolution: str,
        comment: str = "",
    ) -> dict[str, Any]:
        """Make one stale queued record truthful without contacting a provider.

        The operation is deliberately evidence-gated and idempotent.  It can
        only classify a disputed irreversible transient as delivery-unknown,
        or cancel an untouched Yandex source whose exact recipient already has
        a durable reconciled acceptance event.
        """

        now = iso_now()
        resolution = str(expected_resolution or "").strip().lower()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            preview = self._historical_queued_reconciliation_preview_connection(
                connection,
                workspace_id=workspace_id,
                user_id=user_id,
                job_id=job_id,
                expected_resolution=resolution,
            )
            if not preview["safe"]:
                if not self.database_url:
                    connection.rollback()
                raise ValueError(
                    "Historical queue reconciliation blocked: "
                    + ", ".join(preview["reasons"])
                )
            if preview["already_reconciled"]:
                if not self.database_url:
                    connection.commit()
                return {**preview, "ok": True}

            safe_comment = str(comment or "").strip()[:500]
            if resolution == "delivery_unknown":
                safe_error = (
                    "Результат старой попытки неизвестен: передача могла начаться, "
                    "но подтверждения почтового сервера нет."
                )
                connection.execute(
                    """UPDATE mail_jobs SET status='delivery_unknown',
                              next_attempt_at=NULL, last_error=?, updated_at=?
                       WHERE id=? AND status='queued'""",
                    (safe_error, now, int(job_id)),
                )
                connection.execute(
                    """UPDATE mail_messages SET status='delivery_unknown', error=?
                       WHERE id=? AND status='queued'""",
                    (safe_error, int(preview["message_id"])),
                )
                connection.execute(
                    """UPDATE request_supplier_states
                       SET status='delivery_unknown', last_error=?, updated_at=?
                       WHERE request_id=? AND last_message_id=?""",
                    (
                        safe_error, now, int(preview["request_id"]),
                        int(preview["message_id"]),
                    ),
                )
                connection.execute(
                    """UPDATE mail_campaign_targets
                       SET status='delivery_unknown', exclusion_reason=NULL, updated_at=?
                       WHERE job_id=? AND status IN ('eligible', 'waiting')""",
                    (now, int(job_id)),
                )
                action = "mail.historical_queue.reconciled_unknown"
            else:
                safe_error = (
                    "Не отправлено повторно: точный адрес уже принят Mail.ru "
                    "по подтверждённому историческому событию."
                )
                connection.execute(
                    """UPDATE mail_jobs SET status='cancelled',
                              next_attempt_at=NULL, last_error=?, updated_at=?
                       WHERE id=? AND status='queued' AND attempts=0""",
                    (safe_error, now, int(job_id)),
                )
                connection.execute(
                    """UPDATE mail_messages SET status='cancelled', error=?, sent_at=NULL
                       WHERE id=? AND status='queued'""",
                    (safe_error, int(preview["message_id"])),
                )
                connection.execute(
                    """UPDATE request_supplier_states
                       SET status='cancelled', last_error=?, updated_at=?
                       WHERE request_id=? AND last_message_id=?""",
                    (
                        safe_error, now, int(preview["request_id"]),
                        int(preview["message_id"]),
                    ),
                )
                connection.execute(
                    """UPDATE mail_campaign_targets
                       SET status='reconciled', exclusion_reason='accepted_history_reconciled', updated_at=?
                       WHERE job_id=? AND status IN ('eligible', 'waiting')""",
                    (now, int(job_id)),
                )
                action = "mail.historical_queue.reconciled_accepted"

            connection.execute(
                """UPDATE mail_job_integrity
                   SET claim_owner=NULL, claim_token=NULL, lease_expires_at=NULL,
                       updated_at=? WHERE job_id=?""",
                (now, int(job_id)),
            )
            connection.execute(
                """UPDATE mail_cross_provider_retries
                   SET status=?, last_error=?, updated_at=?
                   WHERE operation_id=(SELECT operation_id FROM mail_job_integrity WHERE job_id=?)
                     AND status NOT IN ('accepted', 'delivery_unknown')""",
                (
                    "delivery_unknown" if resolution == "delivery_unknown" else "cancelled",
                    safe_error, now, int(job_id),
                ),
            )
            self._audit_connection(
                connection,
                int(workspace_id),
                int(user_id),
                action,
                "mail_message",
                str(preview["message_id"]),
                {
                    "job_id": int(job_id),
                    "request_id": int(preview["request_id"]),
                    "supplier_id": int(preview["supplier_id"]),
                    "expected_resolution": resolution,
                    "accepted_event_id": preview["accepted_event_id"],
                    "attempt_count": int(preview["attempt_count"]),
                    "comment": safe_comment or None,
                },
            )
            if not self.database_url:
                connection.commit()
        return {
            **preview,
            "ok": True,
            "already_reconciled": False,
            "resolved_at": now,
        }

    def reconcile_pre_data_delivery_unknown(
        self,
        workspace_id: int,
        user_id: int,
        message_id: int,
        *,
        expected_job_id: int,
        expected_account_id: int,
        expected_exception_class: str = "UnicodeEncodeError",
        comment: str = "",
    ) -> dict[str, Any]:
        """Reconcile one proven pre-DATA encoding failure without a resend.

        This is intentionally narrower than the manual delivery-unknown
        resolver.  It only changes an unknown job when the immutable evidence
        proves that no SMTP DATA response exists and the recorded exception is
        the known pre-DATA encoding defect.
        """

        now = iso_now()
        safe_error = "Письмо не было отправлено: ошибка кодирования адреса до SMTP DATA."
        safe_comment = str(comment or "").strip()[:500] or (
            "Пред-DATA ошибка UnicodeEncodeError: домен получателя должен передаваться в SMTP в IDNA-форме."
        )
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT j.id AS job_id, j.message_id, j.mail_account_id, j.status AS job_status,
                          j.provider_message_id AS job_provider_message_id,
                          m.workspace_id, m.user_id, m.request_id, m.supplier_id,
                          m.to_email, m.message_id AS message_id_header,
                          m.status AS message_status, m.sent_at, m.direction,
                          ji.irreversible_at, ji.copy_status,
                          a.outcome AS attempt_outcome, a.provider_classification,
                          a.irreversible_reached,
                          e.smtp_stage, e.smtp_code, e.provider_response_safe,
                          e.exception_class AS evidence_exception_class
                   FROM mail_jobs j
                   JOIN mail_messages m ON m.id=j.message_id
                   JOIN mail_job_integrity ji ON ji.job_id=j.id
                   JOIN mail_send_attempts a ON a.job_id=j.id
                   LEFT JOIN mail_send_attempt_evidence e ON e.attempt_id=a.id
                   WHERE j.id=? AND m.workspace_id=? AND m.user_id=? AND m.id=?
                     AND j.mail_account_id=? AND m.mail_account_id=?
                     AND m.direction='outbound'
                     AND a.id=(SELECT MAX(a2.id) FROM mail_send_attempts a2 WHERE a2.job_id=j.id)""",
                (expected_job_id, workspace_id, user_id, message_id, expected_account_id, expected_account_id),
            ).fetchone()
            if not row:
                raise ValueError("Пред-DATA evidence для указанного письма не найдена.")
            existing = connection.execute(
                "SELECT delivery_state, resolved_at FROM mail_delivery_resolutions WHERE message_id=?",
                (message_id,),
            ).fetchone()
            if existing:
                if existing["delivery_state"] != "not_sent" or row["job_status"] != "failed" or row["message_status"] != "failed":
                    raise ValueError("Для письма уже существует несовместимое delivery resolution.")
                if not self.database_url:
                    connection.commit()
                return {"ok": True, "already_reconciled": True, "job_id": expected_job_id, "message_id": message_id}
            if row["job_status"] != "delivery_unknown" or row["message_status"] != "delivery_unknown":
                raise ValueError("Письмо уже не находится в состоянии delivery_unknown.")
            if row["attempt_outcome"] != "uncertain" or not row["irreversible_reached"]:
                raise ValueError("Попытка не содержит требуемого evidence uncertain/irreversible.")
            if row["provider_classification"] != "internal-uncertain":
                raise ValueError("Классификация попытки не соответствует внутренней пред-DATA ошибке.")
            exception_class = row["evidence_exception_class"]
            if exception_class != expected_exception_class:
                raise ValueError("Класс исключения не соответствует известной ошибке кодирования.")
            if row["smtp_stage"] not in (None, "unknown", "pre_data") or row["smtp_code"] is not None or row["provider_response_safe"]:
                raise ValueError("Найдены признаки SMTP-ответа; автоматическая пред-DATA сверка запрещена.")
            if row["irreversible_at"] is None or row["sent_at"] is not None or row["job_provider_message_id"]:
                raise ValueError("В записи есть признаки подтверждённой передачи; сверка запрещена.")
            active_reservation = connection.execute(
                """SELECT 1 FROM mail_send_reservations
                   WHERE owner_type='job' AND owner_id=? AND status IN ('reserved', 'started') LIMIT 1""",
                (expected_job_id,),
            ).fetchone()
            if active_reservation:
                raise ValueError("У письма есть активная pacing reservation; сверка запрещена.")
            connection.execute(
                "UPDATE mail_jobs SET status='failed', next_attempt_at=NULL, last_error=?, updated_at=? WHERE id=? AND status='delivery_unknown'",
                (safe_error, now, expected_job_id),
            )
            connection.execute(
                "UPDATE mail_messages SET status='failed', error=?, sent_at=NULL WHERE id=? AND status='delivery_unknown'",
                (safe_error, message_id),
            )
            connection.execute(
                "UPDATE request_supplier_states SET status='failed', last_error=?, updated_at=? WHERE last_message_id=?",
                (safe_error, now, message_id),
            )
            connection.execute(
                """UPDATE mail_job_integrity
                   SET claim_owner=NULL, claim_token=NULL, lease_expires_at=NULL,
                       copy_status='not_applicable', copy_error=NULL, updated_at=?
                   WHERE job_id=?""",
                (now, expected_job_id),
            )
            connection.execute(
                """UPDATE mail_cross_provider_retries
                   SET status='failed', last_error=?, updated_at=?
                   WHERE operation_id=(SELECT operation_id FROM mail_job_integrity WHERE job_id=?)
                     AND status NOT IN ('accepted', 'delivery_unknown')""",
                (safe_error, now, expected_job_id),
            )
            snapshot = {
                "workspace_id": workspace_id,
                "request_id": row["request_id"],
                "supplier_id": row["supplier_id"],
                "message_id": message_id,
                "recipient_email": row["to_email"],
                "message_id_header": row["message_id_header"],
                "delivery_state": "not_sent",
                "resolved_by": user_id,
                "resolved_at": now,
                "comment": safe_comment,
            }
            connection.execute(
                """INSERT INTO mail_delivery_resolutions(
                    workspace_id, request_id, supplier_id, message_id,
                    recipient_email, message_id_header, delivery_state,
                    resolved_by, resolved_at, comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(snapshot.values()),
            )
            self._audit_connection(
                connection, workspace_id, user_id, "mail.delivery_unknown.reconciled_pre_data",
                "mail_message", str(message_id), snapshot,
            )
            if not self.database_url:
                connection.commit()
        return {"ok": True, "already_reconciled": False, "job_id": expected_job_id, "message_id": message_id, "resolved_at": now}

    def resolve_delivery_unknown(
        self,
        workspace_id: int,
        user_id: int,
        message_id: int,
        comment: str = "",
    ) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT m.id, m.request_id, m.supplier_id, m.to_email, m.message_id,
                          m.status, r.name AS request_name, s.name AS supplier_name
                   FROM mail_messages m JOIN requests r ON r.id=m.request_id
                   JOIN suppliers s ON s.id=m.supplier_id
                   WHERE m.workspace_id=? AND m.id=? AND m.direction='outbound'""",
                (workspace_id, message_id),
            ).fetchone()
            if not row:
                raise ValueError("Письмо не найдено в текущем рабочем пространстве.")
            if row["status"] != "delivery_unknown":
                raise ValueError("Это письмо не требует ручного разрешения.")
            existing = connection.execute(
                "SELECT resolved_at, comment FROM mail_delivery_resolutions WHERE message_id=?",
                (message_id,),
            ).fetchone()
            if existing:
                return {"ok": True, "already_resolved": True, **dict(existing)}
            snapshot = {
                "workspace_id": workspace_id,
                "request_id": row["request_id"],
                "supplier_id": row["supplier_id"],
                "message_id": message_id,
                "recipient_email": row["to_email"],
                "message_id_header": row["message_id"],
                "delivery_state": "delivery_unknown",
                "resolved_by": user_id,
                "resolved_at": now,
                "comment": str(comment or "").strip()[:500] or None,
            }
            connection.execute(
                """INSERT INTO mail_delivery_resolutions(
                    workspace_id, request_id, supplier_id, message_id,
                    recipient_email, message_id_header, delivery_state,
                    resolved_by, resolved_at, comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(snapshot.values()),
            )
            # Keep the existing audit trail as well. The companion snapshot is
            # required because audit_events.user_id is currently NOT NULL and
            # cascades on user deletion.
            self._audit_connection(
                connection, workspace_id, user_id, "mail.delivery_unknown.resolved",
                "mail_message", str(message_id), snapshot,
            )
            if not self.database_url:
                connection.commit()
        return {"ok": True, "already_resolved": False, "resolved_at": now}

    def request_statuses(self, workspace_id: int, request_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT s.id AS supplier_id, s.external_key, s.name, s.email, s.host,
                          COALESCE(r.status, 'not_sent') AS status,
                          r.last_error, r.updated_at,
                          EXISTS (SELECT 1 FROM mail_messages m
                                  WHERE m.request_id=? AND m.supplier_id=s.id
                                    AND m.status='delivery_unknown'
                                    AND NOT EXISTS (SELECT 1 FROM mail_delivery_resolutions dr WHERE dr.message_id=m.id)) AS delivery_attention,
                          EXISTS (SELECT 1 FROM mail_messages m
                                  WHERE m.request_id=? AND m.supplier_id=s.id
                                    AND m.status='delivery_unknown') AS has_delivery_unknown
                   FROM suppliers s LEFT JOIN request_supplier_states r ON r.supplier_id = s.id AND r.request_id = ?
                   WHERE s.workspace_id = ? ORDER BY s.id""",
                (request_id, request_id, request_id, workspace_id),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["mail_status"] = _normalize_mail_status(item["status"])
            item["delivery_issue_resolved"] = bool(item.pop("has_delivery_unknown", 0)) and not bool(item.pop("delivery_attention", 0))
            result.append(item)
        return result

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
            resolutions = {
                int(row["message_id"]): dict(row)
                for row in connection.execute(
                    "SELECT message_id, resolved_at, comment FROM mail_delivery_resolutions WHERE message_id IN (SELECT id FROM mail_messages WHERE workspace_id=? AND request_id=? AND supplier_id=?)",
                    (workspace_id, request_id, supplier_id),
                ).fetchall()
            }
        result = []
        for row in rows:
            item = _readable_message(dict(row))
            resolution = resolutions.get(int(row["id"]))
            item["delivery_resolved"] = resolution is not None
            item["delivery_resolution"] = resolution
            result.append(item)
        return result

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
            connection.execute(
                "INSERT INTO mail_reply_integrity(reply_id, state_schema_version, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (reply_id, MAIL_INTEGRITY_SCHEMA_VERSION, now, now),
            )
            connection.execute("UPDATE mail_inbox_threads SET last_message_at=? WHERE id=?", (now, inbox_thread_id))
            connection.commit()
        return reply_id

    def mark_inbox_reply_sent(self, reply_id: int, provider_message_id: str | None, generated_message_id: str, sent_at: str) -> None:
        with self.connect() as connection:
            stored = connection.execute("SELECT message_id FROM mail_inbox_replies WHERE id=?", (reply_id,)).fetchone()
            if stored and stored["message_id"] and stored["message_id"] != generated_message_id:
                raise ValueError("Провайдер вернул другой идентификатор письма.")
            connection.execute(
                "UPDATE mail_inbox_replies SET status='sent', provider_message_id=?, sent_at=?, error=NULL WHERE id=?",
                (provider_message_id, sent_at, reply_id),
            )
            connection.commit()

    def enter_reply_irreversible_stage(
        self,
        reply_id: int,
        reservation_token: str | None = None,
        *,
        runtime_provenance: dict[str, Any] | None = None,
    ) -> bool:
        now = iso_now()
        with self.connect() as connection:
            if not self.database_url:
                connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """UPDATE mail_reply_integrity SET irreversible_at=?, updated_at=?
                   WHERE reply_id=? AND state_schema_version=?
                     AND EXISTS (SELECT 1 FROM mail_inbox_replies WHERE id=? AND status='sending')""",
                (now, now, reply_id, MAIL_INTEGRITY_SCHEMA_VERSION, reply_id),
            )
            if cursor.rowcount == 1 and reservation_token:
                reply = connection.execute(
                    "SELECT mail_account_id FROM mail_inbox_replies WHERE id=?",
                    (reply_id,),
                ).fetchone()
                if reply:
                    attempt_id = self._insert_send_attempt(
                        connection,
                        job_id=None, message_id=None, reply_id=reply_id,
                        account_id=int(reply["mail_account_id"]), reservation_token=reservation_token,
                        attempt_number=1, started_at=now, ended_at=None,
                        outcome="in_progress", provider_classification="irreversible-stage",
                        irreversible_reached=True, cooldown_triggered=False,
                        next_retry_at=None, error=None,
                    )
                    if runtime_provenance:
                        connection.execute(
                            """INSERT INTO mail_send_attempt_runtime(
                                   attempt_id, runtime_id, db_identity,
                                   canonical_check_passed, recorded_at
                               ) VALUES (?, ?, ?, ?, ?)""",
                            (
                                attempt_id,
                                runtime_provenance["runtime_id"],
                                runtime_provenance["db_identity"],
                                int(runtime_provenance["canonical_check_passed"]),
                                now,
                            ),
                        )
                    connection.execute(
                        "UPDATE mail_send_reservations SET status='started', started_at=? WHERE reservation_token=? AND status='reserved'",
                        (now, reservation_token),
                    )
            if not self.database_url:
                connection.commit()
        return cursor.rowcount == 1

    def mark_inbox_reply_unknown(self, reply_id: int, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_inbox_replies SET status='delivery_unknown', error=? WHERE id=? AND status='sending'",
                (error[:500], reply_id),
            )

    def mark_inbox_reply_failed(self, reply_id: int, error: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE mail_inbox_replies SET status='failed', error=? WHERE id=?", (error[:500], reply_id))
            connection.commit()

    def inbox_conversation(self, workspace_id: int, message_id: int) -> dict[str, Any] | None:
        original = self.get_inbox_message(workspace_id, message_id)
        if not original:
            return None
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO mail_inbox_message_reads(message_id, read_at) VALUES (?, ?) ON CONFLICT(message_id) DO NOTHING",
                (message_id, iso_now()),
            )
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
            connection.commit()
        return {**original, "replies": replies}
