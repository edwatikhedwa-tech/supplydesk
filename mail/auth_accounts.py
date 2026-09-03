"""
Users/sessions/OAuth-state/mail-account CRUD, extracted from
mail/repository.py (TASK-BOUNDED-MAIL-REPOSITORY-AUTH-ACCOUNTS-EXTRACT-20260903)
as the second step (after the DB-compat shim) of splitting MailRepository by
responsibility, following a fresh read-only structural audit. This is the
one cluster confirmed to have zero private-helper coupling in either
direction with any other cluster in the file (its only shared touchpoint,
`_audit_connection`, is universal infrastructure called from ~15 sites
across 8+ clusters, not this cluster's property) -- the safest possible next
extraction after the DB-compat shim.

AuthAccountsMixin is composed into MailRepository via multiple inheritance,
so every method below still resolves `self.connect()` and `log` exactly as
before. No behavior changed: every method body below is moved
byte-for-byte. Four methods that were physically interleaved in the middle
of this line range in the source (get_request, request_positions,
request_supplier, set_supplier_manual_inn) belong to the Request/Supplier
domains instead -- confirmed by their private-helper dependencies on other
clusters -- and were deliberately left in mail/repository.py, not moved
here.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import timedelta
from typing import Any

from .auth import hash_password, new_token, token_hash
from .time_utils import DEFAULT_SESSION_LIFETIME_SECONDS, iso_after, iso_now, utc_now

log = logging.getLogger(__name__)


class AuthAccountsMixin:
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
            self._seed_default_blacklist(connection, workspace_id, row["id"])
            return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "workspace_id": workspace_id}

    # Маркетплейсы и агрегаторы, которые попадают в выдачу по товарным
    # запросам, но поставщиком быть не могут — их ИНН принадлежит площадке
    # (ozon.ru), а не продавцу со страницы товара (см. am.ozon.com в
    # Documents/28-8/enrichment-and-cache.md §2). В чёрный список по умолчанию, а не
    # жёстким фильтром в коде — пользователь может убрать конкретный домен,
    # если ему для его отрасли он всё же нужен.
    DEFAULT_MARKETPLACE_BLACKLIST: tuple[tuple[str, str], ...] = (
        # .ru, .com и .uz — площадка одна и та же, но домены разные (Ozon
        # обслуживает товарные страницы и с am.ozon.com, и с ozon.ru/ozon.uz).
        # ozon.uz замечен вживую с тем же ИНН 7704217370, что и am.ozon.com —
        # тот же класс проблемы.
        ("ozon.ru", "Ozon"), ("ozon.com", "Ozon"), ("ozon.uz", "Ozon"),
        ("wildberries.ru", "Wildberries"), ("avito.ru", "Avito"),
        ("market.yandex.ru", "Яндекс Маркет"),
        ("aliexpress.ru", "AliExpress"), ("aliexpress.com", "AliExpress"),
        ("sbermegamarket.ru", "СберМегаМаркет"), ("goods.ru", "goods.ru"),
    )
    # Сознательно НЕ включены сети вроде vseinstrumenti.ru и leroymerlin.ru:
    # это обычные продавцы со своим ИНН и отделом продаж, у которых закупщик
    # реально размещает заказы. Отсекаем только площадки-посредники, где ИНН на
    # странице товара принадлежит самой площадке, а не продавцу.

    @classmethod
    def _seed_default_blacklist(cls, connection: sqlite3.Connection, workspace_id: int, user_id: int) -> None:
        """Завести маркетплейсы в чёрный список нового workspace один раз.

        INSERT OR IGNORE на составной проверке через WHERE NOT EXISTS —
        идемпотентно, безопасно вызывать при каждом логине (тот же приём, что
        и _seed_request рядом). Не трогает запись, если пользователь её уже
        восстановил (сработает WHERE NOT EXISTS только по активным записям,
        значит после restore он не появится тут снова).
        """
        now = iso_now()
        for domain, label in cls.DEFAULT_MARKETPLACE_BLACKLIST:
            exists = connection.execute(
                "SELECT 1 FROM blacklist_entries WHERE workspace_id=? AND external_key=?",
                (workspace_id, domain),
            ).fetchone()
            if exists:
                continue
            connection.execute(
                "INSERT INTO blacklist_entries(workspace_id, supplier_id, external_key, company_name, reason, created_by, created_at) "
                "VALUES (?, NULL, ?, ?, ?, ?, ?)",
                (workspace_id, domain, label, "Маркетплейс/агрегатор — не поставщик (добавлено по умолчанию)", user_id, now),
            )

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

    def create_session(
        self,
        user_id: int,
        workspace_id: int,
        *,
        lifetime_seconds: int = DEFAULT_SESSION_LIFETIME_SECONDS,
    ) -> tuple[str, str]:
        session_token = new_token(32)
        # Derive the CSRF token from the opaque session secret so it can be recovered after a server restart.
        csrf_token = token_hash(session_token + ":csrf")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(token_hash, user_id, workspace_id, csrf_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (token_hash(session_token), user_id, workspace_id, token_hash(csrf_token), iso_after(lifetime_seconds), iso_now()),
            )
        return session_token, csrf_token

    def touch_session(self, session_token: str | None, *, lifetime_seconds: int = DEFAULT_SESSION_LIFETIME_SECONDS) -> str | None:
        """Refresh an active session without reviving an expired one.

        The session is only written when it is close to expiry. This keeps the
        authenticated polling path cheap while allowing an active browser to
        remain signed in until explicit logout. Expired sessions are never
        revived.
        """
        if not session_token:
            return None
        lifetime_seconds = max(15 * 60, int(lifetime_seconds))
        now = utc_now()
        now_iso = now.isoformat()
        refreshed_iso = (now + timedelta(seconds=lifetime_seconds)).isoformat()
        renewal_window = min(24 * 60 * 60, max(15 * 60, lifetime_seconds // 4))
        renewal_deadline = (now + timedelta(seconds=renewal_window)).isoformat()
        hashed_token = token_hash(session_token)
        with self.connect() as connection:
            connection.execute(
                """UPDATE sessions
                   SET expires_at=?
                   WHERE token_hash=? AND expires_at>? AND expires_at<=?""",
                (refreshed_iso, hashed_token, now_iso, renewal_deadline),
            )
            row = connection.execute(
                "SELECT expires_at FROM sessions WHERE token_hash=? AND expires_at>?",
                (hashed_token, now_iso),
            ).fetchone()
        return str(row[0]) if row else None

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
            self._seed_default_blacklist(connection, workspace_id, row["id"])
            return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "workspace_id": workspace_id}

    def get_mail_account(self, user_id: int, workspace_id: int, provider: str = "yandex") -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT a.*, p.display_name, p.auth_mode, p.credential_reference,
                          COALESCE(p.outgoing_enabled, 0) AS account_outgoing_enabled,
                          COALESCE(p.incoming_enabled, 1) AS account_incoming_enabled,
                          s.last_sync_at AS incoming_last_success_at,
                          s.last_error_at AS incoming_last_error_at,
                          s.last_error_message AS incoming_last_error
                   FROM mail_accounts a
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   LEFT JOIN mail_sync_states s ON s.mail_account_id=a.id
                   WHERE a.user_id = ? AND a.workspace_id = ? AND a.provider = ?""",
                (user_id, workspace_id, provider),
            ).fetchone()
        return dict(row) if row else None

    def is_workspace_owner(self, user_id: int, workspace_id: int) -> bool:
        """Return true only for the durable owner membership.

        Outgoing transport is a high-impact operation, so a missing or
        malformed membership record must not grant the control-plane action.
        """

        try:
            with self.connect() as connection:
                row = connection.execute(
                    """SELECT 1 FROM workspace_members
                       WHERE user_id=? AND workspace_id=? AND role='owner'""",
                    (int(user_id), int(workspace_id)),
                ).fetchone()
        except Exception:  # noqa: BLE001 — deny on database/role lookup failure
            log.exception("Unable to verify workspace owner; denying outgoing control action.")
            return False
        return bool(row)

    def list_mail_accounts(self, user_id: int, workspace_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.*, p.display_name, p.auth_mode, p.credential_reference,
                          COALESCE(p.outgoing_enabled, 0) AS account_outgoing_enabled,
                          COALESCE(p.incoming_enabled, 1) AS account_incoming_enabled,
                          s.last_sync_at AS incoming_last_success_at,
                          s.last_error_at AS incoming_last_error_at,
                          s.last_error_message AS incoming_last_error
                   FROM mail_accounts a
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   LEFT JOIN mail_sync_states s ON s.mail_account_id=a.id
                   WHERE a.user_id=? AND a.workspace_id=?
                   ORDER BY CASE a.provider WHEN 'yandex' THEN 0 WHEN 'mailru' THEN 1 ELSE 2 END, a.id""",
                (user_id, workspace_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_active_mail_accounts(self) -> list[dict[str, Any]]:
        """Подключённые ящики — для фоновой синхронизации входящих.

        Только id/user/workspace/email: токены фоновой задаче не нужны, их
        достаёт и расшифровывает сам MailService при обращении.
        """
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.id, a.user_id, a.workspace_id, a.provider, a.email,
                          COALESCE(p.incoming_enabled, 1) AS account_incoming_enabled
                   FROM mail_accounts a
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   WHERE a.status = 'connected' AND COALESCE(p.incoming_enabled, 1)=1"""
            ).fetchall()
        return [dict(row) for row in rows]

    def get_mail_account_by_id(self, account_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT a.*, p.display_name, p.auth_mode, p.credential_reference,
                          COALESCE(p.outgoing_enabled, 0) AS account_outgoing_enabled,
                          COALESCE(p.incoming_enabled, 1) AS account_incoming_enabled,
                          s.last_sync_at AS incoming_last_success_at,
                          s.last_error_at AS incoming_last_error_at,
                          s.last_error_message AS incoming_last_error
                   FROM mail_accounts a
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   LEFT JOIN mail_sync_states s ON s.mail_account_id=a.id
                   WHERE a.id = ?""",
                (account_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_mail_account_for_owner(self, account_id: int, user_id: int, workspace_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT a.*, p.display_name, p.auth_mode, p.credential_reference,
                          COALESCE(p.outgoing_enabled, 0) AS account_outgoing_enabled,
                          COALESCE(p.incoming_enabled, 1) AS account_incoming_enabled
                   FROM mail_accounts a
                   LEFT JOIN mail_account_profiles p ON p.account_id=a.id
                   WHERE a.id=? AND a.user_id=? AND a.workspace_id=?""",
                (account_id, user_id, workspace_id),
            ).fetchone()
        return dict(row) if row else None

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
            account_id = int(connection.execute(
                "SELECT id FROM mail_accounts WHERE user_id = ? AND workspace_id = ? AND provider = ?",
                (user_id, workspace_id, provider),
            ).fetchone()[0])
            # Connecting an account is an explicit user action.  It may make
            # this account eligible once the separate global outgoing control
            # is explicitly enabled; it never enables the global control.
            now = iso_now()
            connection.execute(
                """INSERT INTO mail_account_profiles(
                       account_id, display_name, auth_mode, credential_reference,
                       credential_encrypted, outgoing_enabled, incoming_enabled,
                       created_at, updated_at)
                   VALUES (?, 'Яндекс.Почта', 'oauth', ?, NULL, 1, 1, ?, ?)
                   ON CONFLICT(account_id) DO UPDATE SET
                       display_name=excluded.display_name,
                       auth_mode='oauth',
                       credential_reference=excluded.credential_reference,
                       credential_encrypted=NULL,
                       outgoing_enabled=1,
                       incoming_enabled=1,
                       updated_at=excluded.updated_at""",
                (account_id, f"oauth-account:{account_id}", now, now),
            )
            return account_id

    def save_app_password_mail_account(
        self,
        *,
        user_id: int,
        workspace_id: int,
        provider: str,
        email: str,
        display_name: str,
        credential_encrypted: str,
    ) -> int:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mail_accounts(user_id, workspace_id, provider, email,
                       access_token_encrypted, refresh_token_encrypted, token_expires_at,
                       status, created_at, updated_at, last_error_at, last_error_message)
                   VALUES (?, ?, ?, ?, NULL, NULL, NULL, 'connected', ?, ?, NULL, NULL)
                   ON CONFLICT(user_id, workspace_id, provider) DO UPDATE SET
                     email=excluded.email, access_token_encrypted=NULL,
                     refresh_token_encrypted=NULL, token_expires_at=NULL,
                     status='connected', updated_at=excluded.updated_at,
                     last_error_at=NULL, last_error_message=NULL""",
                (user_id, workspace_id, provider, email, now, now),
            )
            account_id = int(connection.execute(
                "SELECT id FROM mail_accounts WHERE user_id=? AND workspace_id=? AND provider=?",
                (user_id, workspace_id, provider),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO mail_account_profiles(
                       account_id, display_name, auth_mode, credential_reference,
                       credential_encrypted, outgoing_enabled, incoming_enabled,
                       created_at, updated_at)
                   VALUES (?, ?, 'app_password', ?, ?, 1, 1, ?, ?)
                   ON CONFLICT(account_id) DO UPDATE SET
                     display_name=excluded.display_name, auth_mode='app_password',
                     credential_reference=excluded.credential_reference,
                     credential_encrypted=excluded.credential_encrypted,
                     outgoing_enabled=1, incoming_enabled=1, updated_at=excluded.updated_at""",
                (account_id, display_name[:200], f"mailru-account:{account_id}", credential_encrypted, now, now),
            )
            return account_id

    def get_mail_account_secret(self, account_id: int) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT credential_encrypted FROM mail_account_profiles WHERE account_id=? AND auth_mode='app_password'",
                (account_id,),
            ).fetchone()
        return str(row[0]) if row and row[0] else None

    def update_mail_tokens(self, account_id: int, access_token_encrypted: str, refresh_token_encrypted: str, token_expires_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE mail_accounts SET access_token_encrypted = ?, refresh_token_encrypted = ?, token_expires_at = ?, status = 'connected', updated_at = ?, last_error_at = NULL, last_error_message = NULL WHERE id = ?",
                (access_token_encrypted, refresh_token_encrypted, token_expires_at, iso_now(), account_id),
            )

    def mark_mail_error(self, account_id: int, message: str, *, status: str | None = None) -> None:
        now = iso_now()
        with self.connect() as connection:
            if not message:
                if status:
                    connection.execute(
                        "UPDATE mail_accounts SET status = ?, last_error_at = NULL, last_error_message = NULL, updated_at = ? WHERE id = ?",
                        (status, now, account_id),
                    )
                else:
                    connection.execute(
                        "UPDATE mail_accounts SET last_error_at = NULL, last_error_message = NULL, updated_at = ? WHERE id = ?",
                        (now, account_id),
                    )
            elif status:
                connection.execute(
                    "UPDATE mail_accounts SET status = ?, last_error_at = ?, last_error_message = ?, updated_at = ? WHERE id = ?",
                    (status, now, message[:500], now, account_id),
                )
            else:
                connection.execute(
                    "UPDATE mail_accounts SET last_error_at = ?, last_error_message = ?, updated_at = ? WHERE id = ?",
                    (now, message[:500], now, account_id),
                )

    def disconnect_mail_account(
        self,
        user_id: int,
        workspace_id: int,
        provider: str = "yandex",
        account_id: int | None = None,
    ) -> None:
        with self.connect() as connection:
            if account_id is None:
                row = connection.execute(
                    "SELECT id FROM mail_accounts WHERE user_id=? AND workspace_id=? AND provider=?",
                    (user_id, workspace_id, provider),
                ).fetchone()
                account_id = int(row[0]) if row else None
            if account_id is None:
                return
            connection.execute(
                """UPDATE mail_accounts
                   SET access_token_encrypted=NULL, refresh_token_encrypted=NULL,
                       token_expires_at=NULL, status='disconnected', updated_at=?,
                       last_error_at=NULL, last_error_message=NULL
                   WHERE id=? AND user_id=? AND workspace_id=?""",
                (iso_now(), account_id, user_id, workspace_id),
            )
            connection.execute("DELETE FROM mail_account_profiles WHERE account_id=?", (account_id,))
