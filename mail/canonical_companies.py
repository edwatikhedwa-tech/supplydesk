"""
Cross-tenant company directory (DECISION-022, docs/domain/SUPPLIER_MODEL.md
§6) -- the one table cluster in this project with no workspace_id, extracted
as its own mixin per the same zero-coupling pattern as mail/mail_templates.py
and mail/logistics_quotes.py.

CanonicalCompaniesMixin is composed into MailRepository via multiple
inheritance, so self.connect()/iso_now() resolve exactly as elsewhere.

Scope, deliberately narrow: `canonical_companies` holds only the general,
public facts about a legal entity (ИНН/ОГРН/name/site/public contact/
registry status/finances) -- never a supplier's relationship to any one
workspace, never communication, notes, prices, or anything else scoped to a
tenant. See migrations/038_canonical_companies.sql for the exact column
list and the boundary comment.
"""

from __future__ import annotations

from typing import Any

from mail.time_utils import iso_now


class CanonicalCompaniesMixin:
    def lookup_canonical_company(self, inn: str) -> dict[str, Any] | None:
        """Read-only cross-tenant lookup -- any workspace may call this for
        any ИНН; it carries no tenant-specific data to leak."""
        inn = str(inn or "").strip()
        if not inn:
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM canonical_companies WHERE inn=?", (inn,),
            ).fetchone()
            if not row:
                return None
            company = dict(row)
            finance_rows = connection.execute(
                """SELECT report_year, revenue, profit FROM canonical_company_finance_history
                   WHERE canonical_company_id=? ORDER BY report_year DESC""",
                (company["id"],),
            ).fetchall()
            risk_rows = connection.execute(
                "SELECT risk FROM canonical_company_risks WHERE canonical_company_id=?",
                (company["id"],),
            ).fetchall()
        company["finance_history"] = [dict(r) for r in finance_rows]
        company["risks"] = [str(r["risk"]) for r in risk_rows]
        return company

    def upsert_canonical_company(
        self, inn: str, *,
        ogrn: str = "", legal_name: str = "", display_name: str = "",
        site: str = "", email: str = "", phone: str = "", region: str = "", role: str = "",
        status: str = "", is_active: bool | None = None, registered_at: str = "",
        source: str = "", finance_history: list[tuple[int, int | None, int | None]] | None = None,
        risks: list[str] | None = None,
    ) -> int:
        """Write-through from a real registry/Checko resolution only -- every
        caller of this method is, by construction, a workspace that just
        resolved this ИНН with an authoritative source, so every non-empty
        field always wins (same trusted-write pattern as
        apply_supplier_enrichment / _get_or_create_global_supplier's
        trusted_name=True). Never called with a placeholder-quality guess.
        """
        inn = str(inn or "").strip()
        if not inn:
            raise ValueError("ИНН обязателен для canonical_companies.")
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO canonical_companies(
                       inn, ogrn, legal_name, display_name, site, email, phone, region, role,
                       status, is_active, registered_at, source, first_seen_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(inn) DO UPDATE SET
                       ogrn=CASE WHEN excluded.ogrn<>'' THEN excluded.ogrn ELSE canonical_companies.ogrn END,
                       legal_name=CASE WHEN excluded.legal_name<>'' THEN excluded.legal_name ELSE canonical_companies.legal_name END,
                       display_name=CASE WHEN excluded.display_name<>'' THEN excluded.display_name ELSE canonical_companies.display_name END,
                       site=CASE WHEN excluded.site<>'' THEN excluded.site ELSE canonical_companies.site END,
                       email=CASE WHEN excluded.email<>'' THEN excluded.email ELSE canonical_companies.email END,
                       phone=CASE WHEN excluded.phone<>'' THEN excluded.phone ELSE canonical_companies.phone END,
                       region=CASE WHEN excluded.region<>'' THEN excluded.region ELSE canonical_companies.region END,
                       role=CASE WHEN excluded.role<>'' THEN excluded.role ELSE canonical_companies.role END,
                       status=CASE WHEN excluded.status<>'' THEN excluded.status ELSE canonical_companies.status END,
                       is_active=COALESCE(excluded.is_active, canonical_companies.is_active),
                       registered_at=CASE WHEN excluded.registered_at<>'' THEN excluded.registered_at ELSE canonical_companies.registered_at END,
                       source=CASE WHEN excluded.source<>'' THEN excluded.source ELSE canonical_companies.source END,
                       updated_at=excluded.updated_at""",
                (
                    inn, ogrn, legal_name, display_name, site, email, phone, region, role,
                    status, (None if is_active is None else int(is_active)), registered_at, source, now, now,
                ),
            )
            company_id = int(connection.execute(
                "SELECT id FROM canonical_companies WHERE inn=?", (inn,),
            ).fetchone()[0])
            for report_year, revenue, profit in (finance_history or []):
                connection.execute(
                    """INSERT INTO canonical_company_finance_history(canonical_company_id, report_year, revenue, profit, updated_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(canonical_company_id, report_year) DO UPDATE SET
                           revenue=excluded.revenue, profit=excluded.profit, updated_at=excluded.updated_at""",
                    (company_id, report_year, revenue, profit, now),
                )
            for risk in (risks or []):
                risk = str(risk or "").strip()
                if not risk:
                    continue
                connection.execute(
                    """INSERT INTO canonical_company_risks(canonical_company_id, risk, updated_at)
                       VALUES (?, ?, ?) ON CONFLICT(canonical_company_id, risk) DO UPDATE SET updated_at=excluded.updated_at""",
                    (company_id, risk, now),
                )
        return company_id
