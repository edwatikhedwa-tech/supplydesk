from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import re
from datetime import timedelta
from email.utils import make_msgid
from email.utils import parseaddr
from html import escape
from typing import Any, Callable
from uuid import uuid4

from .crypto import decrypt, encrypt, load_key
from .deliverability import (
    DeliverabilityPreflightError,
    KNOWN_PLACEHOLDERS,
    RolloutSettings,
    body_quality,
    campaign_max_recipients_from_env,
    email_domain,
    estimate_duration_seconds,
    personalization_level,
    provider_policy_warning,
    similarity_ratio,
    subject_quality,
    unresolved_placeholders,
)
from .content import html_to_text, sanitize_email_html
from .pacing import PacingSettings
from .providers.base import MailProvider
from .repository import (
    ContactSendGuardConflictError,
    ContinuationPlanConflictError,
    MailRepository,
    iso_now,
    utc_now,
)
from .runtime import RuntimeSession
from .types import Attachment, DeliveryCheck, IncomingBatch, OutgoingMessage, ProviderError, SendAttempt, SendResult, TokenSet


FINGERPRINT_SCHEMA_VERSION = 3
LEGACY_FINGERPRINT_SCHEMA_VERSION = 2


logger = logging.getLogger(__name__)


EMAIL_RE = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
DEFAULT_SUBJECT = "Запрос коммерческого предложения"
DEFAULT_TEMPLATE = """Здравствуйте, {{supplier_name}}!

Наша компания ищет поставщика следующей продукции:

{{request_name}}

{{request_description}}

Просим сообщить:

— стоимость;
— наличие;
— минимальную партию;
— срок поставки;
— условия доставки.

Будем благодарны за коммерческое предложение.

{{sender_name}}
{{company_name}}"""


class MailService:
    def __init__(
        self,
        repository: MailRepository,
        provider_factory: Callable[..., MailProvider],
        encryption_key: str | None,
        *,
        daily_limit: int = 250,
        pacing_settings: PacingSettings | None = None,
        rollout_settings: RolloutSettings | None = None,
        campaign_max_recipients: int | None = None,
        max_attachment_bytes: int = 10 * 1024 * 1024,
        max_total_attachment_bytes: int = 20 * 1024 * 1024,
        runtime: RuntimeSession | None = None,
    ) -> None:
        self.repository = repository
        self.provider_factory = provider_factory
        self._encryption_key_value = encryption_key
        self._encryption_key = load_key(encryption_key) if encryption_key else None
        self.daily_limit = daily_limit
        self.pacing_settings = pacing_settings or PacingSettings.from_env()
        self.rollout_settings = rollout_settings or RolloutSettings.from_env()
        self.campaign_max_recipients = campaign_max_recipients_from_env(campaign_max_recipients)
        self.max_attachment_bytes = max_attachment_bytes
        self.max_total_attachment_bytes = max_total_attachment_bytes
        self.runtime = runtime
        self._outgoing_disabled = (os.getenv("MAIL_OUTGOING_DISABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}

    def status(self, user_id: int, workspace_id: int) -> dict[str, Any]:
        accounts = self.repository.list_mail_accounts(user_id, workspace_id)
        safe_accounts = [
            self._public_account(
                account,
                outgoing_enabled=self.outgoing_enabled() and bool(account.get("account_outgoing_enabled", 0)),
            )
            for account in accounts
        ]
        account = next((item for item in accounts if item["status"] == "connected" and item["provider"] == "yandex"), None)
        if account is None:
            account = next((item for item in accounts if item["status"] == "connected"), None)
        if account is None:
            return {"connected": False, "provider": "yandex", "status": "disconnected", "accounts": safe_accounts}
        return {
            **self._public_account(
                account,
                outgoing_enabled=self.outgoing_enabled() and bool(account.get("account_outgoing_enabled", 0)),
            ),
            "outgoing_enabled": self.outgoing_enabled() and bool(account.get("account_outgoing_enabled", 0)),
            "pacing": self.repository.pacing_status(int(account["id"]), self.pacing_settings),
            "accounts": safe_accounts,
        }

    def accounts(self, user_id: int, workspace_id: int) -> list[dict[str, Any]]:
        return [
            self._public_account(
                account,
                outgoing_enabled=self.outgoing_enabled() and bool(account.get("account_outgoing_enabled", 0)),
            )
            for account in self.repository.list_mail_accounts(user_id, workspace_id)
        ]

    def set_outgoing_enabled(
        self,
        *,
        user_id: int,
        workspace_id: int,
        enabled: bool,
        confirmation: bool,
    ) -> dict[str, Any]:
        """Apply the global outgoing switch only after an owner confirmation."""

        if type(enabled) is not bool:
            raise ValueError("enabled должен быть логическим значением true или false.")
        if type(confirmation) is not bool or not confirmation:
            raise ValueError("Для изменения исходящей почты требуется явное подтверждение.")
        if not self.repository.is_workspace_owner(user_id, workspace_id):
            raise PermissionError("Только владелец рабочего пространства может менять исходящую почту.")
        self.repository.set_outgoing_enabled(enabled)
        if self.runtime is not None:
            self.runtime.refresh_durable_outgoing()
        return {
            "ok": True,
            "durable_outgoing_enabled": self.repository.outgoing_enabled(),
            "effective_outgoing_enabled": self.outgoing_enabled(),
        }

    def template(self, workspace_id: int) -> dict[str, Any]:
        stored = self.repository.get_mail_template(workspace_id)
        if not stored:
            return {
                "subject": DEFAULT_SUBJECT,
                "body": DEFAULT_TEMPLATE,
                "attachments": [],
                "updated_at": None,
            }
        return {
            "subject": stored["subject"],
            "body": stored["body_text"],
            "updated_at": stored.get("updated_at"),
            "attachments": [
                {
                    "filename": item["filename"],
                    "mime_type": item["mime_type"],
                    "size": int(item["size_bytes"]),
                    "content_base64": base64.b64encode(bytes(item["content"])).decode("ascii"),
                }
                for item in stored.get("attachments", [])
            ],
        }

    def save_template(
        self, *, user_id: int, workspace_id: int, subject: str, body: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        clean_subject = self._validate_subject(subject)
        clean_body = self._validate_body(body)
        parsed = self.validate_attachments(attachments or [])
        filenames = [item["filename"].casefold() for item in parsed]
        if len(set(filenames)) != len(filenames):
            raise ValueError("В шаблоне не должно быть вложений с одинаковыми именами.")
        self.repository.save_mail_template(
            workspace_id, user_id, subject=clean_subject,
            body_text=clean_body, attachments=parsed,
        )
        return self.template(workspace_id)

    def save_oauth_tokens(self, *, user_id: int, workspace_id: int, token_set: TokenSet, email: str) -> int:
        self._require_encryption()
        email = self.validate_email(email, "Email аккаунта")
        if not token_set.refresh_token:
            raise ProviderError("Яндекс не вернул refresh token. Подключите почту заново.", revoked=True)
        access_encrypted = encrypt(
            token_set.access_token,
            self._encryption_key,
            associated_data=self._aad(user_id, workspace_id, "access"),
        )
        refresh_encrypted = encrypt(
            token_set.refresh_token,
            self._encryption_key,
            associated_data=self._aad(user_id, workspace_id, "refresh"),
        )
        expires_at = (utc_now() + timedelta(seconds=max(60, token_set.expires_in))).isoformat()
        return self.repository.save_mail_account(
            user_id=user_id,
            workspace_id=workspace_id,
            provider="yandex",
            email=email,
            access_token_encrypted=access_encrypted,
            refresh_token_encrypted=refresh_encrypted,
            token_expires_at=expires_at,
        )

    def connect_mailru(self, *, user_id: int, workspace_id: int, email: str, app_password: str) -> dict[str, Any]:
        self._require_encryption()
        clean_email = self.validate_email(email, "Email аккаунта")
        clean_password = str(app_password or "")
        if not clean_password.strip() or len(clean_password) > 500:
            raise ValueError("Укажите пароль приложения Mail.ru.")
        provider = self.provider_factory("mailru", clean_password)
        try:
            # Connection verification intentionally performs SMTP+IMAP auth
            # and INBOX SELECT, never DATA or APPEND.
            provider.test_connection(clean_email, clean_password)
        except ProviderError:
            raise
        encrypted = encrypt(
            clean_password,
            self._encryption_key,
            associated_data=self._aad(user_id, workspace_id, "app_password"),
        )
        account_id = self.repository.save_app_password_mail_account(
            user_id=user_id,
            workspace_id=workspace_id,
            provider="mailru",
            email=clean_email,
            display_name="Mail.ru",
            credential_encrypted=encrypted,
        )
        return self._public_account(self.repository.get_mail_account_by_id(account_id) or {})

    def test_connection(self, user_id: int, workspace_id: int, *, mail_account_id: int | None = None) -> None:
        account, access_token = self._get_account_and_token(user_id, workspace_id, mail_account_id=mail_account_id)
        provider = self._provider_for_account(account, access_token)
        try:
            provider.test_connection(account["email"], access_token)
        except ProviderError as exc:
            self.repository.mark_mail_error(account["id"], exc.message, status="revoked" if exc.revoked else None)
            raise
        self.repository.mark_mail_error(account["id"], "", status="connected")

    def disconnect(self, user_id: int, workspace_id: int, *, mail_account_id: int | None = None) -> None:
        if mail_account_id is None:
            self.repository.disconnect_mail_account(user_id, workspace_id, provider="yandex")
            return
        account = self._get_account_for_queue(user_id, workspace_id, mail_account_id=mail_account_id, require_connected=False)
        self.repository.disconnect_mail_account(user_id, workspace_id, account_id=int(account["id"]))

    def sync_incoming(self, user_id: int, workspace_id: int, *, max_messages: int = 100, mail_account_id: int | None = None) -> dict[str, Any]:
        account, access_token = self._get_account_and_token(user_id, workspace_id, mail_account_id=mail_account_id)
        provider = self._provider_for_account(account, access_token)
        state = self.repository.get_mail_sync_state(account["id"]) or {}
        try:
            batch: IncomingBatch = provider.fetch_incoming(
                account["email"],
                access_token,
                uidvalidity=state.get("uidvalidity"),
                last_uid=int(state.get("last_uid") or 0),
                max_messages=max(1, min(int(max_messages), 500)),
            )
            result = self.repository.import_incoming_messages(
                workspace_id=workspace_id,
                user_id=user_id,
                account_id=account["id"],
                messages=batch.messages,
            )
            self.repository.save_mail_sync_state(
                account["id"],
                uidvalidity=batch.uidvalidity,
                last_uid=batch.last_uid,
                imported_count=result["imported"],
                unmatched_count=result["unmatched"],
            )
            self.repository.mark_mail_error(account["id"], "", status="connected")
            return {"ok": True, "scanned": batch.scanned_count, **result}
        except ProviderError as exc:
            self.repository.mark_mail_sync_error(account["id"], exc.message)
            # Keep SMTP sending available when the current grant is missing the new read-only IMAP scope.
            if exc.revoked:
                self.repository.mark_mail_error(account["id"], exc.message, status="revoked")
            else:
                self.repository.mark_mail_error(account["id"], exc.message)
            raise

    def sync_all_incoming(self, user_id: int, workspace_id: int, *, max_messages: int = 100) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for account in self.repository.list_mail_accounts(user_id, workspace_id):
            if account["status"] != "connected" or not bool(account.get("account_incoming_enabled", 1)):
                continue
            try:
                results.append(self.sync_incoming(user_id, workspace_id, max_messages=max_messages, mail_account_id=int(account["id"])))
            except ProviderError as exc:
                results.append({"ok": False, "account_id": int(account["id"]), "error": exc.message})
        return {
            "ok": all(item.get("ok", False) for item in results) if results else True,
            "accounts": results,
            "imported": sum(int(item.get("imported", 0)) for item in results),
            "unmatched": sum(int(item.get("unmatched", 0)) for item in results),
        }

    def _select_contact_for_request(
        self,
        *,
        workspace_id: int,
        request_id: int,
        item: dict[str, Any],
        request_cards: list[dict[str, Any]],
        allow_repeat: bool,
        force_requested_contact: bool = False,
    ) -> dict[str, Any]:
        """Choose at most one contact for one company card.

        Initial outreach is allowed only to a never-used contact in this
        request.  A used primary contact yields to the first stable
        never-used alternate.  ``allow_repeat`` is an explicit operator
        override and never changes the one-message-per-company-card rule.
        """

        requested_email = str(item.get("email") or "").strip().lower()
        requested_supplier_id = item.get("supplier_id")
        card = next(
            (
                candidate for candidate in request_cards
                if requested_supplier_id is not None
                and int(requested_supplier_id) in {
                    int(value) for value in candidate.get("related_supplier_ids", [candidate.get("id")])
                }
            ),
            None,
        )
        if card is None and requested_supplier_id is None:
            matching_cards = [
                candidate for candidate in request_cards
                if requested_email in {
                    str(value or "").strip().lower()
                    for value in candidate.get("contact_emails", [])
                }
            ]
            card = matching_cards[0] if len(matching_cards) == 1 else None

        identity_groups = self.repository.email_identity_groups(workspace_id, requested_email)
        selected_identity_group = None
        if requested_supplier_id is not None:
            selected_identity_group = next(
                (key for key, ids in identity_groups.items() if int(requested_supplier_id) in ids),
                None,
            )
        shared_email = len(identity_groups) > 1
        ambiguous_identity = requested_supplier_id is None and shared_email

        contacts: list[dict[str, Any]] = []
        if card is not None:
            seen_emails: set[str] = set()
            for contact in card.get("contacts") or []:
                email = str(contact.get("email") or "").strip().lower()
                if not email or email in seen_emails:
                    continue
                seen_emails.add(email)
                delivery = str(contact.get("delivery_status") or "not_sent")
                response = str(contact.get("response_status") or "none")
                state = "answered" if response == "answered" else delivery
                contacts.append({
                    "supplier_id": int(contact["supplier_id"]),
                    "email": email,
                    "host": str(contact.get("host") or card.get("host") or "").strip(),
                    "state": state,
                })

        if not contacts:
            contacts = [{
                "supplier_id": requested_supplier_id,
                "email": requested_email,
                "host": str(item.get("host") or "").strip(),
                "state": "not_sent",
            }]
        elif requested_email not in {contact["email"] for contact in contacts}:
            contacts.insert(0, {
                "supplier_id": requested_supplier_id,
                "email": requested_email,
                "host": str(item.get("host") or card.get("host") or "").strip(),
                "state": "not_sent",
            })

        requested = next((contact for contact in contacts if contact["email"] == requested_email), contacts[0])
        never_used = [contact for contact in contacts if contact["state"] == "not_sent"]
        # A card can be marked answered from a reply tied to a member row even
        # when that sender is no longer the member's current email.  Keep
        # preflight and queue aligned with the company-card safety rule.
        has_answered_contact = (
            str((card or {}).get("response_status") or "") == "answered"
            or any(contact["state"] == "answered" for contact in contacts)
        )
        chosen: dict[str, Any] | None = None
        decision = "skipped"
        if not ambiguous_identity and (force_requested_contact or allow_repeat):
            chosen = requested
            decision = "explicit_repeat"
        elif not ambiguous_identity and has_answered_contact:
            chosen = None
        elif not ambiguous_identity and never_used:
            chosen = requested if requested["state"] == "not_sent" else never_used[0]
            decision = "primary" if chosen["email"] == requested_email else "alternate"

        state = str(requested.get("state") or "not_sent")
        display_state = "answered" if has_answered_contact else state
        same_request_contacted = self.repository.request_email_was_contacted(
            workspace_id, request_id, requested_email,
        )
        reasons: list[str] = []
        if ambiguous_identity:
            reasons.append("ambiguous_supplier_identity")
        elif chosen is None:
            if not contacts:
                reasons.append("no_eligible_email")
            else:
                reasons.append("already_contacted")
                if same_request_contacted:
                    reasons.append("same_request_already_contacted")
                if has_answered_contact:
                    reasons.append("answered")
                elif state in {"queued", "accepted", "failed", "delivery_unknown", "bounced", "cancelled"}:
                    reasons.append(state)

        selected = dict(item)
        if chosen is not None:
            selected.update({
                "supplier_id": chosen.get("supplier_id"),
                "email": chosen["email"],
                "host": chosen.get("host") or item.get("host") or "",
            })
        else:
            selected = None
        result = {
            "requested_email": requested_email,
            "selected_supplier_id": chosen.get("supplier_id") if chosen else requested.get("supplier_id"),
            "contact_state": display_state,
            "decision": decision,
            "alternate_selected": bool(chosen and chosen["email"] != requested_email),
            "shared_email_across_companies": shared_email,
            "ambiguous_identity": ambiguous_identity,
            "reasons": reasons,
            "company_name": str((card or {}).get("name") or item.get("name") or "").strip(),
            "identity_group": selected_identity_group,
        }
        return {"item": selected, "result": result}

    def preflight_bulk(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        suppliers: list[dict[str, Any]],
        subject: str,
        body: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        manual_stage_approval: bool | None = None,
        allow_manual_resend: bool = False,
        allow_repeat: bool = False,
        mail_account_id: int | None = None,
    ) -> dict[str, Any]:
        """Analyze a bulk operation without writes, queueing, or provider calls."""

        if type(allow_repeat) is not bool:
            raise ValueError("allow_repeat должен быть логическим значением true или false.")
        effective_manual_stage_approval = self._resolve_manual_stage_approval(manual_stage_approval)
        planned = len(suppliers or [])
        result: dict[str, Any] = {
            "status": "PASS",
            "planned": planned,
            "eligible": 0,
            "excluded": 0,
            "unique_domains": 0,
            "recipient_results": [],
            "contact_selection": {
                "selected_companies": planned,
                "would_create": 0,
                "alternate_selected": 0,
                "already_contacted": 0,
                "answered": 0,
                "no_eligible_email": 0,
                "errors": 0,
                "ambiguous": 0,
            },
            "warnings": [],
            "blocks": [],
            "personalization_distribution": {},
            "similarity_ratio": 0.0,
            "attachment_total_bytes": 0,
            "provider": None,
            "provider_warning": None,
            "campaign_limits": {"max_recipients": self.campaign_max_recipients},
            "account_budget": {
                "max_per_hour": self.pacing_settings.max_per_hour,
                "max_per_day": self.pacing_settings.max_per_day,
            },
            "pacing": {
                "min_interval_seconds": self.pacing_settings.min_interval_seconds,
                "max_interval_seconds": self.pacing_settings.max_interval_seconds,
            },
            "budget_warning": None,
            "estimated_duration_seconds": estimate_duration_seconds(
                planned, self.pacing_settings.min_interval_seconds, self.pacing_settings.max_interval_seconds,
            ),
            "rollout": {
                "stage_1": self.rollout_settings.stage_1,
                "stage_2": self.rollout_settings.stage_2,
                "stage_3": self.rollout_settings.stage_3,
                "manual_stage_approval": effective_manual_stage_approval,
            },
        }

        try:
            account = self._get_account_for_queue(user_id, workspace_id, mail_account_id=mail_account_id)
            result["provider"] = account["provider"]
        except (ProviderError, ValueError) as exc:
            result["blocks"].append("provider_or_account_unavailable")
            result["error"] = str(exc)
            result["status"] = "BLOCK"
            return result
        request = self.repository.get_request(workspace_id, request_id)
        if not request:
            result["blocks"].append("request_not_found")
            result["status"] = "BLOCK"
            return result
        request_cards = self.repository.list_suppliers(workspace_id, request_id)
        if not suppliers or planned > self.campaign_max_recipients:
            result["blocks"].append("campaign_size_out_of_range")
        if planned > self.pacing_settings.max_per_day:
            result["budget_warning"] = (
                f"Кампания содержит {planned} получателей, а текущий rolling 24-часовой "
                f"бюджет аккаунта — {self.pacing_settings.max_per_day}. "
                "После исчерпания бюджета оставшиеся письма будут ждать открытия нового окна."
            )
            result["warnings"].append("campaign_exceeds_daily_budget")

        subject_value = str(subject or "")
        body_value, body_html_value = self._normalize_outbound_content(
            body=body, body_text=body_text, body_html=body_html,
        )
        try:
            self._validate_subject(subject_value)
        except ValueError:
            result["blocks"].append("invalid_subject")
        try:
            self._validate_body(body_value)
        except ValueError:
            result["blocks"].append("invalid_body")
        subject_blocks, subject_warnings = subject_quality(subject_value, recipient_count=planned)
        body_blocks, body_warnings = body_quality(body_value, request=request, allowed_placeholders=KNOWN_PLACEHOLDERS)
        result["blocks"].extend(subject_blocks)
        result["blocks"].extend(body_blocks)
        result["warnings"].extend(subject_warnings)
        result["warnings"].extend(body_warnings)
        unsupported_placeholders = [
            name for name in unresolved_placeholders(subject_value, "\n".join(filter(None, (body_value, body_html_value))))
            if name not in KNOWN_PLACEHOLDERS
        ]
        if unsupported_placeholders:
            result["blocks"].append("broken_placeholder")

        parsed_attachments: list[dict[str, Any]] = []
        try:
            parsed_attachments = self.validate_attachments(attachments or [])
            result["attachment_total_bytes"] = sum(int(item["size_bytes"]) for item in parsed_attachments)
        except ValueError as exc:
            result["blocks"].append("attachment_over_limit_or_invalid")
            result["attachment_error"] = str(exc)

        normalized: list[dict[str, Any]] = []
        for raw in suppliers or []:
            try:
                normalized.append(self._normalize_supplier(raw))
            except ValueError as exc:
                email = str((raw or {}).get("email") or "").strip().lower()
                result["recipient_results"].append({"email": email, "status": "excluded", "reasons": ["invalid_email", str(exc)]})
                result["blocks"].append("invalid_email")

        seen: set[str] = set()
        duplicate_emails: set[str] = set()
        for item in normalized:
            if item["email"] in seen:
                duplicate_emails.add(item["email"])
            seen.add(item["email"])
        if duplicate_emails:
            result["blocks"].append("duplicate_recipient")

        domains = {email_domain(item["email"]) for item in normalized if email_domain(item["email"])}
        result["unique_domains"] = len(domains)
        domain_counts: dict[str, int] = {}
        for item in normalized:
            domain = email_domain(item["email"])
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if planned >= 10 and domain_counts and max(domain_counts.values()) / max(1, len(normalized)) >= 0.5:
            result["warnings"].append("many_recipients_same_domain")
        if planned >= 50:
            result["warnings"].append("large_campaign_review")
        provider_warning = provider_policy_warning(str(account["provider"]), planned)
        if provider_warning:
            result["provider_warning"] = provider_warning
            result["warnings"].append("provider_policy_warning")

        rendered: list[dict[str, Any]] = []
        levels: dict[str, int] = {}
        for item in normalized:
            reasons: list[str] = []
            if item["email"] in duplicate_emails:
                reasons.append("duplicate")
            if not any(item.get(field) for field in ("name", "contact_name", "category", "website", "city")):
                result["warnings"].append("missing_supplier_context")
            selection = self._select_contact_for_request(
                workspace_id=workspace_id,
                request_id=request_id,
                item=item,
                request_cards=request_cards,
                allow_repeat=allow_repeat,
                force_requested_contact=allow_manual_resend,
            )
            selection_result = selection["result"]
            if selection_result.get("shared_email_across_companies"):
                result["warnings"].append("shared_email_across_companies")
            if selection_result.get("ambiguous_identity"):
                reasons.append("ambiguous_supplier_identity")
                result["blocks"].append("ambiguous_supplier_identity")
            selected_item = selection.get("item")
            contact_state = str(selection_result.get("contact_state") or "")
            if selection_result.get("alternate_selected"):
                result["contact_selection"]["alternate_selected"] += 1
            if selection_result.get("decision") == "explicit_repeat":
                result["warnings"].append("explicit_repeat_enabled")
            if selected_item is None:
                if "ambiguous_supplier_identity" not in reasons:
                    reasons.extend(selection_result.get("reasons") or ["no_eligible_email"])
                flags = self.repository.deliverability_flags(
                    workspace_id, request_id, external_key=item["external_key"], email=item["email"],
                    supplier_id=selection_result.get("selected_supplier_id") or item.get("supplier_id"),
                )
                if flags["suppressed"]:
                    reasons.append("suppressed")
                if flags["hard_bounce"]:
                    reasons.append("hard_bounce")
                result["contact_selection"]["already_contacted"] += int("already_contacted" in reasons)
                result["contact_selection"]["answered"] += int("answered" in reasons)
                result["contact_selection"]["no_eligible_email"] += int("no_eligible_email" in reasons)
                result["contact_selection"]["errors"] += int(any(
                    reason not in {
                        "already_contacted", "answered", "queued", "accepted", "failed",
                        "delivery_unknown", "bounced", "cancelled", "no_eligible_email",
                        "same_request_already_contacted",
                    }
                    for reason in reasons
                ))
                result["recipient_results"].append({
                    "email": item["email"],
                    "requested_email": item["email"],
                    "supplier_id": item.get("supplier_id"),
                    "selected_supplier_id": selection_result.get("selected_supplier_id"),
                    "contact_state": contact_state or None,
                    "alternate_selected": False,
                    "domain": email_domain(item["email"]),
                    "status": "excluded",
                    "reasons": reasons,
                    "personalization_level": 0,
                })
                result["blocks"].extend(
                    reason for reason in reasons
                    if reason in {"suppressed", "hard_bounce", "same_request_already_contacted"}
                )
                continue
            item = selected_item
            flags = self.repository.deliverability_flags(
                workspace_id, request_id, external_key=item["external_key"], email=item["email"],
                supplier_id=item.get("supplier_id"),
            )
            if flags["suppressed"]:
                reasons.append("suppressed")
            if flags["hard_bounce"]:
                reasons.append("hard_bounce")
            if flags["unresolved_delivery_unknown"] and not (allow_manual_resend or allow_repeat):
                reasons.append("unresolved_safety_state")
            elif flags["unresolved_delivery_unknown"]:
                result["warnings"].append("manual_resend_after_delivery_unknown")
            try:
                target = self._render_outbound_target(
                    account=account, request=request, supplier=item,
                    subject=subject_value, body=body_value, body_html=body_html_value,
                    supplier_id=flags.get("supplier_id"),
                )
            except ValueError:
                reasons.append("render_error")
                result["blocks"].append("render_error")
                target = None
            if target is not None:
                if unresolved_placeholders(target["subject"], target["body_text"]):
                    reasons.append("broken_placeholder")
                    result["blocks"].append("broken_placeholder")
                level = int(target["personalization_level"])
                levels[str(level)] = levels.get(str(level), 0) + 1
                rendered.append(target)
            status = "excluded" if reasons else "eligible"
            if reasons:
                result["blocks"].extend(reason for reason in reasons if reason in {"duplicate", "suppressed", "hard_bounce", "unresolved_safety_state"})
            result["recipient_results"].append({
                "email": item["email"],
                "requested_email": selection_result.get("requested_email"),
                "supplier_id": item.get("supplier_id"),
                "selected_supplier_id": item.get("supplier_id"),
                "contact_state": contact_state or "never_used",
                "alternate_selected": bool(selection_result.get("alternate_selected")),
                "domain": email_domain(item["email"]),
                "status": status,
                "reasons": reasons,
                "personalization_level": int(target["personalization_level"]) if target else 0,
            })
            if not reasons:
                result["contact_selection"]["would_create"] += 1
        if result["contact_selection"]["already_contacted"] or result["contact_selection"]["no_eligible_email"]:
            result["warnings"].append("some_recipients_skipped")

        result["personalization_distribution"] = levels
        result["excluded"] = sum(1 for item in result["recipient_results"] if item["status"] == "excluded")
        result["eligible"] = max(0, len(result["recipient_results"]) - result["excluded"])
        if result["eligible"] == 0 and not result["blocks"]:
            result["blocks"].append("no_eligible_recipients")
        if planned >= 10 and rendered and len({item["subject"] for item in rendered}) == 1:
            result["warnings"].append("subject_same_for_large_batch")
        result["similarity_ratio"] = similarity_ratio(
            [f"{item['subject']}\n{item['body_text']}" for item in rendered]
        )
        if planned >= 10 and result["similarity_ratio"] >= self.rollout_settings.similarity_warning_ratio:
            result["warnings"].append("high_content_similarity")
        result["previews"] = rendered[:5]
        result["blocks"] = list(dict.fromkeys(result["blocks"]))
        result["warnings"] = list(dict.fromkeys(result["warnings"]))
        if result["blocks"]:
            result["status"] = "BLOCK"
        elif result["warnings"]:
            result["status"] = "WARNING"
        return result

    def preview_bulk(self, **kwargs: Any) -> dict[str, Any]:
        """Return dry-run and exact rendered samples using the send renderer."""

        return self.preflight_bulk(**kwargs)

    def _render_outbound_target(
        self,
        *,
        account: dict[str, Any],
        request: dict[str, Any],
        supplier: dict[str, Any],
        subject: str,
        body: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        supplier_id: int | None = None,
        message_id_header: str | None = None,
        resend_of_message_id: int | None = None,
    ) -> dict[str, Any]:
        values = {
            "supplier_name": str(supplier.get("name") or "").strip(),
            "contact_name": str(supplier.get("contact_name") or "").strip(),
            "supplier_category": str(supplier.get("category") or supplier.get("supplier_category") or "").strip(),
            "supplier_website": str(supplier.get("website") or "").strip(),
            "supplier_city": str(supplier.get("city") or supplier.get("region") or "").strip(),
            "request_name": str(request.get("name") or "").strip(),
            "request_description": str(request.get("description") or "").strip(),
            "sender_name": str(request.get("sender_name") or "").strip(),
            "company_name": str(request.get("company_name") or "").strip(),
        }
        text_template = body_text if body_text is not None else body
        personalized_text = self.personalize(text_template or "", **values).strip()
        recipient_subject = self._validate_subject(self.personalize(subject, **values))
        if body_html and body_html.strip():
            personalized_html = self._personalize_html(body_html, values)
            rendered_html = sanitize_email_html(personalized_html)
            rendered_text = html_to_text(rendered_html) or personalized_text
            body_text_value = self._validate_body(rendered_text).strip()
            body_html_value = rendered_html or f"<p>{escape(body_text_value).replace(chr(10), '<br>')}</p>"
        else:
            body_text_value = self._validate_body(personalized_text).strip()
            body_html_value = f"<p>{escape(body_text_value).replace(chr(10), '<br>')}</p>"
        return {
            "normalized_email": supplier["email"],
            "supplier_id": supplier_id,
            "to_email": supplier["email"],
            "subject": recipient_subject,
            "body_text": body_text_value,
            "body_html": body_html_value,
            "message_id_header": message_id_header or make_msgid(domain=account["email"].split("@", 1)[-1]),
            "resend_of_message_id": resend_of_message_id,
            "personalization_level": personalization_level(supplier=supplier, request=request),
        }

    def queue_one(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        supplier: dict[str, Any],
        subject: str,
        body: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
        resend_of_message_id: int | None = None,
        allow_repeat: bool = False,
        mail_account_id: int | None = None,
    ) -> dict[str, int]:
        # Single-recipient sends keep their historical internal convenience:
        # callers that do not have a batch key get a fresh key for this one
        # user intent. Bulk-send calls enter queue_bulk directly, where the
        # key is mandatory.
        operation_key = str(idempotency_key or uuid4()).strip()
        results = self.queue_bulk(
            user_id=user_id,
            workspace_id=workspace_id,
            request_id=request_id,
            suppliers=[supplier],
            subject=subject,
            body=body,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            idempotency_key=operation_key,
            resend_of_message_id=resend_of_message_id,
        # A missing key creates a fresh operation key, but it does not grant
        # permission to repeat an initial contact. Repeats must stay explicit.
        allow_repeat=allow_repeat or resend_of_message_id is not None,
            mail_account_id=mail_account_id,
        )
        return results[0]

    def queue_bulk(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        suppliers: list[dict[str, Any]],
        subject: str,
        body: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
        resend_of_message_id: int | None = None,
        manual_stage_approval: bool | None = None,
        allow_repeat: bool = False,
        mail_account_id: int | None = None,
    ) -> list[dict[str, int]]:
        # Validate before any supplier upsert or operation assembly so a
        # malformed user bulk request is a true no-op.
        if type(allow_repeat) is not bool:
            raise ValueError("allow_repeat должен быть логическим значением true или false.")
        operation_key = self._normalize_idempotency_key(idempotency_key, required=True)
        effective_manual_stage_approval = self._resolve_manual_stage_approval(manual_stage_approval)
        if not suppliers or len(suppliers) > self.campaign_max_recipients:
            raise ValueError(
                f"За один раз можно поставить в очередь от 1 до {self.campaign_max_recipients} поставщиков."
            )
        clean_subject = self._validate_subject(subject)
        clean_body, clean_body_html = self._normalize_outbound_content(
            body=body, body_text=body_text, body_html=body_html,
        )
        account = self._get_account_for_queue(user_id, workspace_id, mail_account_id=mail_account_id)
        request = self.repository.get_request(workspace_id, request_id)
        if not request:
            raise ValueError("Заявка не найдена в текущем рабочем пространстве.")
        normalized = [self._normalize_supplier(supplier) for supplier in suppliers]
        keys = {supplier["email"] for supplier in normalized}
        if len(keys) != len(normalized):
            raise ValueError("В списке получателей есть дубликаты нормализованных адресов.")
        parsed_attachments = self.validate_attachments(attachments or [])
        operation = self.repository.get_send_operation(workspace_id, operation_key)
        preflight_result: dict[str, Any] | None = None
        atomic_results: list[dict[str, int]] | None = None
        atomic_campaign_id: int | None = None
        if operation is None:
            preflight_result = self.preflight_bulk(
                user_id=user_id, workspace_id=workspace_id, request_id=request_id,
                suppliers=suppliers, subject=clean_subject, body=clean_body, body_html=clean_body_html,
                attachments=attachments or [],
                manual_stage_approval=effective_manual_stage_approval,
                allow_manual_resend=resend_of_message_id is not None,
                allow_repeat=allow_repeat or resend_of_message_id is not None,
                mail_account_id=mail_account_id,
            )
            if preflight_result["status"] == "BLOCK":
                raise DeliverabilityPreflightError(preflight_result)
            request_cards = self.repository.list_suppliers(workspace_id, request_id)
            effective_normalized: list[dict[str, Any]] = []
            for item in normalized:
                selection = self._select_contact_for_request(
                    workspace_id=workspace_id,
                    request_id=request_id,
                    item=item,
                    request_cards=request_cards,
                    allow_repeat=allow_repeat or resend_of_message_id is not None,
                    force_requested_contact=resend_of_message_id is not None,
                )
                selected_item = selection.get("item")
                if selected_item is not None:
                    effective_normalized.append(selected_item)
            if not effective_normalized:
                raise DeliverabilityPreflightError(preflight_result)
        else:
            # Replays use the durable target snapshot captured by the first
            # assembly.  The original primary email may have yielded to an
            # alternate contact on that first request.
            effective_normalized = [
                {"email": target["normalized_email"]}
                for target in self.repository.get_send_operation_targets(int(operation["id"]))
            ]
            if not effective_normalized:
                raise ValueError("Операция не содержит snapshot получателя для безопасного продолжения.")
        fingerprint = self._send_fingerprint(
            account_id=account["id"],
            request=request,
            request_id=request_id,
            normalized_recipients=effective_normalized,
            subject_template=clean_subject,
            body_template=clean_body,
            body_html_template=clean_body_html,
            attachments=parsed_attachments,
            resend_of_message_id=resend_of_message_id,
            manual_stage_approval=effective_manual_stage_approval,
            fingerprint_schema_version=FINGERPRINT_SCHEMA_VERSION,
        )
        legacy_fingerprint = self._send_fingerprint(
            account_id=account["id"],
            request=request,
            request_id=request_id,
            normalized_recipients=effective_normalized,
            subject_template=clean_subject,
            body_template=clean_body,
            body_html_template=clean_body_html,
            attachments=parsed_attachments,
            resend_of_message_id=resend_of_message_id,
            fingerprint_schema_version=LEGACY_FINGERPRINT_SCHEMA_VERSION,
        )
        if operation:
            self._validate_existing_bulk_operation(
                operation,
                workspace_id=workspace_id,
                current_fingerprint=fingerprint,
                legacy_fingerprint=legacy_fingerprint,
                requested_manual_stage_approval=manual_stage_approval,
                fingerprint_args={
                    "account_id": account["id"],
                    "request": request,
                    "request_id": request_id,
                    "normalized_recipients": effective_normalized,
                    "subject_template": clean_subject,
                    "body_template": clean_body,
                    "body_html_template": clean_body_html,
                    "attachments": parsed_attachments,
                    "resend_of_message_id": resend_of_message_id,
                },
            )
            if operation["status"] == "assembly_failed":
                raise ValueError("Сборка этой операции завершилась ошибкой. Создайте новую операцию отправки.")
            operation_id = int(operation["id"])

        # Targets are the durable personalization snapshot. On an idempotent
        # retry do not re-read mutable supplier/enrichment data and do not
        # regenerate subject/body; use the values captured by the first
        # operation assembly instead.
        if operation:
            prepared = []
            prepared = self.repository.get_send_operation_targets(operation_id)
            if not prepared:
                raise ValueError("Операция не содержит snapshot получателя для безопасного продолжения.")
        else:
            prepared = []
            for item in effective_normalized:
                if self.repository.is_blacklisted(workspace_id, item["external_key"]):
                    raise ProviderError("Поставщик находится в чёрном списке рабочего пространства.")
                resolved = self.repository.resolve_supplier_for_send(
                    workspace_id=workspace_id,
                    request_id=request_id,
                    supplier_id=item.get("supplier_id"),
                    email=item["email"],
                    name=item["name"],
                    host=item["host"],
                    external_key=item["external_key"],
                )
                item.update(resolved)
                supplier_id = int(resolved["supplier_id"])
                logger.info(
                    "send supplier_id=%s global_supplier_id=%s email=%s existing_supplier=%s",
                    supplier_id,
                    resolved.get("global_supplier_id"),
                    item["email"],
                    bool(resolved.get("existing_supplier")),
                )
                prepared.append(self._render_outbound_target(
                    account=account, request=request, supplier=item,
                    subject=clean_subject, body=clean_body, body_html=clean_body_html, supplier_id=supplier_id,
                    resend_of_message_id=resend_of_message_id,
                ))
            try:
                operation_id, atomic_campaign_id, atomic_results = self.repository.create_send_operation_with_messages(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    request_id=request_id,
                    account_id=account["id"],
                    idempotency_key=operation_key,
                    content_fingerprint=fingerprint,
                    fingerprint_schema_version=FINGERPRINT_SCHEMA_VERSION,
                    targets=prepared,
                    attachments=parsed_attachments,
                    campaign={
                        "provider": account["provider"],
                        "stage_limit": self.rollout_settings.cumulative_limit(1, len(prepared)),
                        "manual_stage_approval": effective_manual_stage_approval,
                        "preflight": preflight_result or {"status": "PASS"},
                        "provider_warning": (preflight_result or {}).get("provider_warning"),
                        "from_email": account["email"],
                    },
                    guard_initial_contacts=not (allow_repeat or resend_of_message_id is not None),
                )
            except ContactSendGuardConflictError as exc:
                conflict = dict(preflight_result or {"status": "BLOCK", "planned": len(suppliers), "eligible": 0, "excluded": len(suppliers), "recipient_results": [], "warnings": [], "blocks": []})
                conflict["status"] = "BLOCK"
                conflict["blocks"] = list(dict.fromkeys([*(conflict.get("blocks") or []), "same_request_already_contacted"]))
                conflict["error"] = str(exc)
                raise DeliverabilityPreflightError(conflict) from exc
            except Exception:
                # The unique workspace/key constraint is the final arbiter
                # when two callers assemble the same operation concurrently.
                # Re-read the winner and apply the normal idempotency contract;
                # unrelated database failures are re-raised unchanged.
                operation = self.repository.get_send_operation(workspace_id, operation_key)
                if not operation:
                    raise
                self._validate_existing_bulk_operation(
                    operation,
                    workspace_id=workspace_id,
                    current_fingerprint=fingerprint,
                    legacy_fingerprint=legacy_fingerprint,
                    requested_manual_stage_approval=manual_stage_approval,
                    fingerprint_args={
                        "account_id": account["id"],
                        "request": request,
                        "request_id": request_id,
                        "normalized_recipients": effective_normalized,
                        "subject_template": clean_subject,
                        "body_template": clean_body,
                        "body_html_template": clean_body_html,
                        "attachments": parsed_attachments,
                        "resend_of_message_id": resend_of_message_id,
                    },
                )
                if operation["status"] == "assembly_failed":
                    raise ValueError("Сборка этой операции завершилась ошибкой. Создайте новую операцию отправки.")
                operation_id = int(operation["id"])
                prepared = self.repository.get_send_operation_targets(operation_id)
                if not prepared:
                    raise ValueError("Операция не содержит snapshot получателя для безопасного продолжения.")

        if atomic_results is not None:
            return [
                {**result, "operation_id": operation_id, **({"campaign_id": atomic_campaign_id} if atomic_campaign_id is not None else {})}
                for result in atomic_results
            ]

        campaign_id: int | None = None
        campaign = self.repository.get_campaign_by_operation(operation_id, workspace_id)
        if operation is None:
            campaign_id = self.repository.create_campaign(
                workspace_id=workspace_id,
                user_id=user_id,
                request_id=request_id,
                account_id=int(account["id"]),
                operation_id=operation_id,
                provider=str(account["provider"]),
                stage_limit=self.rollout_settings.cumulative_limit(1, len(prepared)),
                manual_stage_approval=effective_manual_stage_approval,
                preflight=preflight_result or {"status": "PASS"},
                provider_warning=(preflight_result or {}).get("provider_warning"),
            )
        elif campaign:
            campaign_id = int(campaign["id"])

        prepared_levels = {
            str(item.get("normalized_email") or ""): int(item.get("personalization_level") or 0)
            for item in prepared
        }
        results: list[dict[str, int]] = []
        try:
            for index, item in enumerate(prepared, start=1):
                target = self.repository.get_operation_target(operation_id, item["normalized_email"])
                if not target:
                    raise ValueError("Получатель отсутствует в операции отправки.")
                if target["message_id"] is not None:
                    existing = self.repository.get_send_operation_results(operation_id)
                    match = next((row for row in existing if row["normalized_email"] == item["normalized_email"]), None)
                    if match and match["job_id"] is not None:
                        results.append({"job_id": int(match["job_id"]), "message_id": int(match["message_id"]), "thread_id": int(match["thread_id"]), "operation_id": operation_id})
                    continue
                results.append(self.repository.create_queued_message(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    request_id=request_id,
                    supplier_id=int(target["supplier_id"]),
                    account_id=account["id"],
                    from_email=account["email"],
                    to_email=target["normalized_email"],
                    subject=target["subject"],
                    body_text=target["body_text"],
                    body_html=target["body_html"],
                    message_id_header=target["message_id_header"],
                    attachments=parsed_attachments,
                    operation_id=operation_id,
                    normalized_email=target["normalized_email"],
                    resend_of_message_id=target.get("resend_of_message_id"),
                    campaign_id=campaign_id,
                    campaign_ordinal=index,
                    personalization_level=int(target.get("personalization_level") or prepared_levels.get(target["normalized_email"], 0)),
                ))
            if not self.repository.mark_send_operation_ready(operation_id):
                raise ValueError("Операция отправки не собрана полностью.")
        except ValueError as exc:
            # A deterministic integrity/data error is terminal. Unexpected
            # exceptions intentionally leave `assembling` in place so a crash
            # can resume missing targets on the next request.
            self.repository.mark_send_operation_failed(operation_id, str(exc))
            raise
        return [
            {**result, "operation_id": operation_id, **({"campaign_id": campaign_id} if campaign_id is not None else {})}
            for result in results
        ]

    def reply_to_inbox(
        self,
        *,
        user_id: int,
        workspace_id: int,
        inbox_message_id: int,
        subject: str,
        body: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """Reply to an unmatched inbox message — no заявка/поставщик involved.

        Sent synchronously (unlike queue_one/queue_bulk's async job queue):
        this is always a single, user-initiated send, not bulk outreach, so
        there is no batch to protect with a retry queue — a failure surfaces
        immediately and the user can just try again.
        """
        original = self.repository.get_inbox_message(workspace_id, inbox_message_id)
        if not original:
            raise ValueError("Письмо не найдено.")
        peer_email = self.validate_email(original["from_email"], "Адрес отправителя")
        account, access_token = self._get_account_and_token(
            user_id, workspace_id, mail_account_id=original.get("mail_account_id")
        )
        if self.repository.count_sent_today(account["id"]) >= self.daily_limit:
            raise ProviderError(
                "Достигнут безопасный дневной предел отправки. Попробуйте завтра.",
                transient=True, rate_limited=True, provider_code="local-daily-limit",
            )
        body_text_template, body_html_template = self._normalize_outbound_content(
            body=body, body_text=body_text, body_html=body_html,
        )
        subject = self._validate_subject(subject or self._reply_subject(original["subject"]))
        values = {
            "supplier_name": "",
            "contact_name": "",
            "supplier_category": "",
            "supplier_website": "",
            "supplier_city": "",
            "request_name": "",
            "request_description": "",
            "sender_name": "",
            "company_name": "",
        }
        personalized_text = self.personalize(body_text_template, **values).strip()
        if body_html_template:
            rendered_html = sanitize_email_html(self._personalize_html(body_html_template, values))
            rendered_text = html_to_text(rendered_html) or personalized_text
            body_text_value = self._validate_body(rendered_text).strip()
            body_html_value = rendered_html or f"<p>{escape(body_text_value).replace(chr(10), '<br>')}</p>"
        else:
            body_text_value = self._validate_body(personalized_text).strip()
            body_html_value = f"<p>{escape(body_text_value).replace(chr(10), '<br>')}</p>"
        parsed_attachments = self.validate_attachments(attachments or [])
        message_id_header = make_msgid(domain=account["email"].split("@", 1)[-1])
        references = " ".join(token for token in (original.get("references_header"), original.get("message_id")) if token) or None
        thread_id = self.repository.get_or_create_inbox_thread(
            workspace_id=workspace_id, user_id=user_id, mail_account_id=account["id"],
            peer_email=peer_email, subject=subject,
        )
        reply_id = self.repository.record_inbox_reply(
            inbox_thread_id=thread_id, workspace_id=workspace_id, user_id=user_id, mail_account_id=account["id"],
            from_email=account["email"], to_email=peer_email, subject=subject, body_text=body_text_value, body_html=body_html_value,
            message_id_header=message_id_header, in_reply_to=original.get("message_id") or None, references_header=references,
        )
        provider = self._provider_for_account(account, access_token)
        outgoing = OutgoingMessage(
            from_email=account["email"], to_email=peer_email, subject=subject,
            body_text=body_text_value, body_html=body_html_value,
            message_id=message_id_header, in_reply_to=original.get("message_id") or None, references=references,
            attachments=[Attachment(filename=item["filename"], mime_type=item["mime_type"], content=item["content"]) for item in parsed_attachments],
        )
        if self.repository.is_suppressed(workspace_id, email=peer_email):
            self.repository.mark_inbox_reply_failed(reply_id, "Получатель находится в действующем suppression/blacklist.")
            raise ProviderError("Получатель находится в действующем списке подавления.", provider_code="supplier-suppressed")
        reservation = None
        try:
            self._assert_outgoing_allowed()
            reservation = self.repository.reserve_send_slot(
                account["id"], owner_type="reply", owner_id=reply_id,
                pacing=self.pacing_settings,
            )
            if not reservation:
                self.repository.mark_inbox_reply_failed(reply_id, "Письмо ожидает account-level pacing или budget.")
                raise ProviderError(
                    "Почтовый ящик временно ожидает pacing/cooldown/budget. Повторите позже.",
                    transient=True, rate_limited=True, provider_code="pacing-wait",
                )
            attempt = self._send_with_gate(
                provider,
                access_token,
                outgoing,
                lambda: self._enter_reply_irreversible_stage(reply_id, reservation["reservation_token"]),
            )
        except ProviderError as exc:
            if exc.revoked:
                self.mark_refresh_error(account["id"], exc)
            if exc.uncertain:
                self.repository.mark_inbox_reply_unknown(reply_id, exc.message)
                self.repository.finish_send_attempt(
                    reservation_token=(reservation or {}).get("reservation_token"),
                    outcome="uncertain", provider_classification=exc.provider_code or "transport-uncertain",
                    error=exc.message, account_id=account["id"],
                    smtp_stage=exc.smtp_stage,
                    smtp_code=exc.smtp_code,
                    smtp_enhanced_status=exc.smtp_enhanced_status,
                    provider_response_safe=exc.provider_response_safe,
                    exception_class=exc.exception_class,
                )
            else:
                self.repository.mark_inbox_reply_failed(reply_id, exc.message)
                token = (reservation or {}).get("reservation_token")
                if token:
                    if exc.provider_code in {"outgoing-disabled", "integrity-gate", "supplier-suppressed", "pacing-wait"}:
                        finished = False
                        if exc.provider_code == "outgoing-disabled":
                            finished = self.repository.finish_send_attempt(
                                reservation_token=token, outcome="blocked_global",
                                provider_classification="global-kill-switch", error=exc.message,
                                account_id=account["id"],
                                smtp_stage=exc.smtp_stage,
                                smtp_code=exc.smtp_code,
                                smtp_enhanced_status=exc.smtp_enhanced_status,
                                provider_response_safe=exc.provider_response_safe,
                                exception_class=exc.exception_class,
                            )
                        if not finished:
                            self.repository.release_send_reservation(token, exc.provider_code or "blocked", reset_pacing=True)
                    else:
                        status = self.repository.pacing_status(account["id"], self.pacing_settings)
                        delay = self.pacing_settings.cooldown_delay(int(status.get("cooldown_level") or 0)) if exc.rate_limited else self.pacing_settings.retry_delay(1)
                        next_retry = (utc_now() + timedelta(seconds=delay)).isoformat()
                        self.repository.record_reply_pre_gate_attempt(
                            reply_id=reply_id, reservation_token=token,
                            outcome="transient_rejected" if exc.transient else "permanent_rejected",
                            provider_classification=exc.provider_code or ("transient" if exc.transient else "permanent"),
                            error=exc.message, next_retry_at=next_retry,
                            transient=exc.transient, rate_limited=exc.rate_limited,
                            revoked=exc.revoked, pacing=self.pacing_settings,
                            smtp_stage=exc.smtp_stage,
                            smtp_code=exc.smtp_code,
                            smtp_enhanced_status=exc.smtp_enhanced_status,
                            provider_response_safe=exc.provider_response_safe,
                            exception_class=exc.exception_class,
                        )
            raise
        try:
            self.repository.mark_inbox_reply_sent(reply_id, attempt.provider_message_id, attempt.message_id, attempt.sent_at.isoformat())
        except Exception:
            # SMTP has already accepted the message. Try the external copy,
            # persist uncertainty when possible, and never convert this
            # persistence failure into a second send.
            try:
                self.repository.mark_inbox_reply_unknown(
                    reply_id,
                    "Провайдер принял письмо, но результат не удалось записать локально.",
                )
            except Exception:
                pass
            self._save_sent_copy_best_effort(attempt)
            self.repository.finish_send_attempt(
                reservation_token=(reservation or {}).get("reservation_token"),
                outcome="uncertain", provider_classification="db-persistence-failure",
                error="SMTP accepted but local result persistence failed.", account_id=account["id"],
                smtp_stage=attempt.result.smtp_stage,
                smtp_code=attempt.result.smtp_code,
                smtp_enhanced_status=attempt.result.smtp_enhanced_status,
                provider_response_safe=attempt.result.provider_response_safe,
                exception_class=attempt.result.exception_class,
            )
            raise
        self.repository.finish_send_attempt(
            reservation_token=(reservation or {}).get("reservation_token"),
            outcome="accepted", provider_classification="accepted", account_id=account["id"],
            smtp_stage=attempt.result.smtp_stage,
            smtp_code=attempt.result.smtp_code,
            smtp_enhanced_status=attempt.result.smtp_enhanced_status,
            provider_response_safe=attempt.result.provider_response_safe,
            exception_class=attempt.result.exception_class,
        )
        self._save_sent_copy_best_effort(attempt)
        return {"thread_id": thread_id, "reply_id": reply_id}

    @staticmethod
    def _reply_subject(original_subject: str) -> str:
        subject = str(original_subject or "").strip()
        if re.match(r"(?i)^re\s*:", subject):
            return subject
        return f"Re: {subject}" if subject else "Re:"

    def send_claimed_job(
        self,
        job: dict[str, Any],
        *,
        before_transport: Callable[[], None] | None = None,
    ) -> SendAttempt:
        account = self.repository.get_mail_account_by_id(job["mail_account_id"])
        if not account or account["status"] != "connected":
            raise ProviderError("Почтовый ящик отключён. Подключите его заново.", revoked=True)
        # Fail closed before decrypting credentials or constructing a provider
        # for a claimed job.  The same guard is repeated at the durable gate
        # and at the provider's final pre-DATA callback.
        self._assert_outgoing_allowed()
        access_token = self._access_token_for_account(account)
        provider = self._provider_for_account(account, access_token)
        outgoing = OutgoingMessage(
            from_email=job["from_email"],
            to_email=job["to_email"],
            subject=job["subject"],
            body_text=job["body_text"],
            body_html=job["body_html"],
            message_id=job.get("message_id_header"),
            in_reply_to=job.get("in_reply_to"),
            references=job.get("references_header"),
            attachments=[
                Attachment(filename=item["filename"], mime_type=item["mime_type"], content=item["content"])
                for item in job.get("attachments", [])
            ],
        )
        if self.repository.is_suppressed(int(job["workspace_id"]), job.get("supplier_external_key"), job.get("to_email")):
            raise ProviderError(
                "Получатель находится в действующем списке подавления.",
                provider_code="supplier-suppressed",
            )
        if not self.repository.campaign_job_allowed(int(job["id"])):
            raise ProviderError(
                "Campaign поставлена на паузу или остановлена. Письмо осталось без отправки.",
                provider_code="campaign-paused",
            )
        self._assert_outgoing_allowed()
        attempt = self._send_with_gate(
            provider,
            access_token,
            outgoing,
            lambda: self._enter_job_irreversible_stage(job),
            before_transport=before_transport,
        )
        return attempt

    def _enter_job_irreversible_stage(self, job: dict[str, Any]) -> None:
        self._assert_outgoing_allowed()
        if not self.repository.enter_irreversible_stage(
            int(job["id"]), str(job["claim_token"]), job.get("pacing_reservation_token"),
            runtime_provenance=self.runtime.provenance() if self.runtime else None,
        ):
            raise ProviderError("Не удалось зафиксировать начало отправки. Письмо оставлено без отправки.", provider_code="integrity-gate")

    def _enter_reply_irreversible_stage(self, reply_id: int, reservation_token: str | None = None) -> None:
        self._assert_outgoing_allowed()
        if not self.repository.enter_reply_irreversible_stage(
            reply_id,
            reservation_token,
            runtime_provenance=self.runtime.provenance() if self.runtime else None,
        ):
            raise ProviderError("Не удалось зафиксировать начало отправки. Письмо оставлено без отправки.", provider_code="integrity-gate")

    def _send_with_gate(
        self,
        provider: Any,
        access_token: str,
        outgoing: OutgoingMessage,
        before_irreversible: Callable[[], None],
        before_transport: Callable[[], None] | None = None,
    ) -> SendAttempt:
        # The durable gate must be committed before the provider is contacted;
        # this is what makes a failed gate a true no-network decision. The
        # provider callback is retained as a last-moment runtime-switch check
        # immediately before SMTP DATA (or the provider's equivalent).
        self._assert_outgoing_allowed()
        before_irreversible()
        # A runtime/lock loss after the durable gate must not even enter the
        # provider boundary.  The callback below is intentionally still kept
        # at the provider's final DATA edge as a second race-safe check.
        self._assert_outgoing_allowed()
        if before_transport is not None:
            before_transport()

        def guarded_before_irreversible() -> None:
            self._assert_outgoing_allowed()

        result = provider.send_message(access_token, outgoing, before_irreversible=guarded_before_irreversible)
        return SendAttempt(result=result, message=outgoing, access_token=access_token, provider=provider)

    def _save_sent_copy_best_effort(self, attempt: SendAttempt, *, job_id: int | None = None) -> None:
        try:
            attempt.provider.save_sent_copy(attempt.access_token, attempt.message, attempt.result)
        except Exception as exc:  # noqa: BLE001 — the provider copy never changes acceptance
            if job_id is not None:
                try:
                    self.repository.mark_copy_status(job_id, "failed", str(exc))
                except Exception:
                    pass
            return
        if job_id is not None:
            try:
                self.repository.mark_copy_status(job_id, "saved")
            except Exception:
                pass

    def save_sent_copy(self, attempt: SendAttempt, *, job_id: int | None = None) -> None:
        """Persist a provider copy after the acceptance state is committed."""

        self._save_sent_copy_best_effort(attempt, job_id=job_id)

    def verify_delivery(self, *, user_id: int, workspace_id: int, message_id: int) -> dict[str, Any]:
        message = self.repository.get_outbound_message(workspace_id, message_id)
        if not message:
            raise ValueError("Исходящее письмо не найдено.")
        if message.get("job_status") != "delivery_unknown" or message.get("status") != "delivery_unknown":
            return {"outcome": "not_applicable", "message_id": message_id, "status": message.get("status")}
        if not message.get("message_id"):
            return {"outcome": "unavailable", "message_id": message_id, "reason": "У письма нет сохранённого идентификатора."}
        try:
            account, access_token = self._get_account_and_token(
                user_id, workspace_id, mail_account_id=message.get("mail_account_id")
            )
            provider = self._provider_for_account(account, access_token)
            check: DeliveryCheck = provider.verify_sent_message(access_token, account["email"], message["message_id"])
        except ProviderError as exc:
            check = DeliveryCheck("unavailable", message.get("message_id"), exc.message)
        if check.outcome == "found":
            self.repository.mark_job_verified_sent(message_id, iso_now())
        return {
            "outcome": check.outcome,
            "message_id": message_id,
            "status": "sent" if check.outcome == "found" else "delivery_unknown",
            "reason": check.reason,
        }

    def recover_delivery_unknown(self, workspace_id: int | None = None) -> list[dict[str, Any]]:
        """Run the one minimal automatic recovery check at queue startup."""

        results: list[dict[str, Any]] = []
        for message in self.repository.list_delivery_unknown_jobs(workspace_id):
            message_id_header = message.get("message_id_header")
            if not message_id_header or message.get("account_status") != "connected":
                results.append({"message_id": message["message_id"], "outcome": "unavailable"})
                continue
            try:
                token = self._access_token_for_account(message)
                provider = self._provider_for_account(message, token)
                check = provider.verify_sent_message(token, message["account_email"], message_id_header)
            except ProviderError as exc:
                check = DeliveryCheck("unavailable", message_id_header, exc.message)
            if check.outcome == "found":
                self.repository.mark_job_verified_sent(int(message["message_id"]), message.get("sent_at") or iso_now())
            results.append({"message_id": message["message_id"], "outcome": check.outcome})
        return results

    def resend_delivery_unknown(
        self,
        *,
        user_id: int,
        workspace_id: int,
        message_id: int,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        original = self.repository.get_outbound_message(workspace_id, message_id)
        if not original:
            raise ValueError("Исходящее письмо не найдено.")
        if original.get("status") != "delivery_unknown":
            raise ValueError("Повторить можно только отправку без подтверждения.")
        check = self.verify_delivery(user_id=user_id, workspace_id=workspace_id, message_id=message_id)
        if check.get("outcome") == "found":
            return {"ok": True, "resent": False, "outcome": "found", "message_id": message_id}
        if not confirmed:
            return {
                "ok": True,
                "resent": False,
                "requires_confirmation": True,
                "outcome": check.get("outcome", "unavailable"),
                "message_id": message_id,
                "warning": "Оригинал не подтверждён. Повтор может создать дубликат у поставщика.",
            }
        supplier = {
            "name": original.get("supplier_name") or original.get("external_key") or original["to_email"],
            "email": original["to_email"],
            "external_key": original.get("external_key") or original["to_email"].split("@", 1)[-1],
        }
        queued = self.queue_one(
            user_id=user_id,
            workspace_id=workspace_id,
            request_id=int(original["request_id"]),
            supplier=supplier,
            subject=original["subject"],
            body_text=original["body_text"],
            body_html=original.get("body_html"),
            attachments=[
                {
                    "filename": item["filename"],
                    "mime_type": item["mime_type"],
                    "size": item.get("size_bytes", len(item["content"])),
                    "content_base64": base64.b64encode(bytes(item["content"])).decode("ascii"),
                }
                for item in original.get("attachments", [])
            ],
            idempotency_key=str(uuid4()),
            resend_of_message_id=message_id,
            allow_repeat=True,
            mail_account_id=original.get("mail_account_id"),
        )
        return {"ok": True, "resent": True, "outcome": check.get("outcome"), "original_message_id": message_id, "queued": queued}

    def mark_refresh_error(self, account_id: int, exc: ProviderError) -> None:
        self.repository.mark_mail_error(account_id, exc.message, status="revoked" if exc.revoked else None)

    def _get_account_for_queue(
        self,
        user_id: int,
        workspace_id: int,
        *,
        mail_account_id: int | None = None,
        require_connected: bool = True,
    ) -> dict[str, Any]:
        if mail_account_id is not None:
            account = self.repository.get_mail_account_for_owner(int(mail_account_id), user_id, workspace_id)
        else:
            account = self.repository.get_mail_account(user_id, workspace_id, "yandex")
            if not account or account["status"] != "connected":
                account = next(
                    (item for item in self.repository.list_mail_accounts(user_id, workspace_id) if item["status"] == "connected"),
                    None,
                )
        if not account or (require_connected and account["status"] != "connected"):
            raise ProviderError("Подключите рабочую почту, чтобы отправлять запросы поставщикам.")
        if require_connected and not bool(account.get("account_outgoing_enabled", 0)):
            raise ProviderError("Исходящая почта для этого аккаунта отключена.", provider_code="account-outgoing-disabled")
        return account

    def _resolve_manual_stage_approval(self, value: bool | None) -> bool:
        """Resolve the campaign mode once; a campaign stores the result durably."""
        if value is None:
            return bool(self.rollout_settings.manual_stage_approval)
        if type(value) is not bool:
            raise ValueError("manual_stage_approval должен быть логическим значением true или false.")
        return value

    def _validate_existing_bulk_operation(
        self,
        operation: dict[str, Any],
        *,
        workspace_id: int,
        current_fingerprint: str,
        legacy_fingerprint: str,
        requested_manual_stage_approval: bool | None,
        fingerprint_args: dict[str, Any],
    ) -> None:
        """Apply idempotency without changing an existing operation or campaign."""
        schema = int(operation.get("fingerprint_schema_version") or 0)
        campaign = self.repository.get_campaign_by_operation(int(operation["id"]), workspace_id)
        expected = current_fingerprint
        if schema == FINGERPRINT_SCHEMA_VERSION:
            # A replay without the optional field is still a replay of the
            # already-created intent, even if the process default changed.
            if requested_manual_stage_approval is None and campaign is not None:
                expected = self._send_fingerprint(
                    **fingerprint_args,
                    manual_stage_approval=bool(campaign["manual_stage_approval"]),
                    fingerprint_schema_version=FINGERPRINT_SCHEMA_VERSION,
                )
        elif schema == LEGACY_FINGERPRINT_SCHEMA_VERSION:
            expected = legacy_fingerprint
            # A legacy operation has no mode in its fingerprint. If a caller
            # now supplies a mode explicitly, only accept it when the durable
            # campaign snapshot proves the same intent.
            if requested_manual_stage_approval is not None and (
                campaign is None
                or bool(campaign["manual_stage_approval"]) != requested_manual_stage_approval
            ):
                raise ValueError("Ключ операции уже использован для другого содержимого или режима кампании.")
        else:
            raise ValueError("Ключ операции создан по несовместимой версии отпечатка. Создайте новую операцию отправки.")
        if operation["content_fingerprint"] != expected:
            raise ValueError("Ключ операции уже использован для другого содержимого или режима кампании.")

    @staticmethod
    def _normalize_idempotency_key(value: str | None, *, required: bool = False) -> str:
        key = str(value or "").strip()
        if not key:
            if required:
                raise ValueError("Для массовой отправки требуется idempotency key.")
            return str(uuid4())
        if len(key) > 200:
            raise ValueError("Ключ операции слишком длинный.")
        return key

    @staticmethod
    def _send_fingerprint(
        *,
        account_id: int,
        request: dict[str, Any],
        request_id: int,
        normalized_recipients: list[dict[str, Any]],
        subject_template: str,
        body_template: str,
        body_html_template: str | None = None,
        attachments: list[dict[str, Any]],
        resend_of_message_id: int | None,
        manual_stage_approval: bool | None = None,
        fingerprint_schema_version: int = FINGERPRINT_SCHEMA_VERSION,
    ) -> str:
        attachment_fingerprint = sorted(
            (
                {
                    "mime_type": item["mime_type"],
                    "sha256": hashlib.sha256(bytes(item["content"])).hexdigest(),
                }
                for item in attachments
            ),
            key=lambda item: (item["mime_type"], item["sha256"]),
        )
        payload = {
            "fingerprint_schema_version": fingerprint_schema_version,
            "mail_account_id": account_id,
            "request_id": request_id,
            "request_snapshot": {
                "name": request.get("name", ""),
                "description": request.get("description", ""),
                "sender_name": request.get("sender_name", ""),
                "company_name": request.get("company_name", ""),
            },
            "subject_template": subject_template,
            "body_template": body_template,
            "resend_of_message_id": resend_of_message_id,
            "recipients": [
                {
                    "email": item["email"],
                }
                for item in sorted(normalized_recipients, key=lambda item: item["email"])
            ],
            "attachments": attachment_fingerprint,
        }
        # Keep the schema version stable for legacy body-only operations. The
        # optional field makes rich HTML intents distinct without invalidating
        # already persisted fingerprints created before this contract existed.
        if body_html_template is not None:
            payload["body_html_template"] = body_html_template
        if fingerprint_schema_version >= FINGERPRINT_SCHEMA_VERSION:
            if type(manual_stage_approval) is not bool:
                raise ValueError("Для текущей версии отпечатка требуется режим подтверждения этапов.")
            payload["manual_stage_approval"] = manual_stage_approval
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _assert_outgoing_allowed(self) -> None:
        if self._outgoing_disabled_now():
            raise ProviderError("Исходящая почта временно отключена аварийным выключателем.", provider_code="outgoing-disabled")
        if self.runtime is not None:
            self.runtime.refresh_durable_outgoing()
        if not self.repository.outgoing_enabled():
            raise ProviderError("Исходящая почта временно отключена аварийным выключателем.", provider_code="outgoing-disabled")
        if self.runtime is not None:
            reason = self.runtime.transport_block_reason()
            if reason:
                raise ProviderError(
                    "Отправка заблокирована операционной защитой runtime. Письмо осталось в очереди.",
                    provider_code="operational_blocked_noncanonical_runtime",
                )
        elif (os.getenv("SUPPLYDESK_ENV", "") or "").strip().lower() in {"production", "development", "test"}:
            # A configured service must be constructed by SupplierApp so that
            # it owns the runtime policy and, in production, canonical
            # provenance. Direct construction is allowed only for legacy
            # provider-neutral unit tests with no configured environment.
            raise ProviderError(
                "Отправка заблокирована: runtime не инициализирован.",
                provider_code="operational_blocked_noncanonical_runtime",
            )

    def _outgoing_disabled_now(self) -> bool:
        """Read the process kill-switch again for long pacing waits.

        The constructor snapshot remains a safe fail-closed default, while a
        runtime environment change is also observed before a transport gate.
        """

        env_value = (os.getenv("MAIL_OUTGOING_DISABLED", "0") or "0").strip().lower()
        return self._outgoing_disabled or env_value in {"1", "true", "yes", "on"}

    def outgoing_enabled(self) -> bool:
        """Cheap worker pre-check; the provider boundary still has the final guard."""
        if self.runtime is not None:
            self.runtime.refresh_durable_outgoing()
            if not self.runtime.outgoing_allowed:
                return False
        if self.runtime is None and (os.getenv("SUPPLYDESK_ENV", "") or "").strip().lower() in {"production", "development", "test"}:
            return False
        return not self._outgoing_disabled_now() and self.repository.outgoing_enabled()

    def _get_account_and_token(
        self,
        user_id: int,
        workspace_id: int,
        *,
        mail_account_id: int | None = None,
    ) -> tuple[dict[str, Any], str]:
        account = self._get_account_for_queue(user_id, workspace_id, mail_account_id=mail_account_id)
        if account["status"] != "connected":
            raise ProviderError("Подключите рабочую почту, чтобы отправлять запросы поставщикам.")
        return account, self._access_token_for_account(account)

    def _access_token_for_account(self, account: dict[str, Any]) -> str:
        self._require_encryption()
        if account.get("auth_mode") == "app_password" or account.get("provider") == "mailru":
            encrypted = self.repository.get_mail_account_secret(int(account["id"]))
            if not encrypted:
                raise ProviderError("Пароль приложения не найден. Подключите Mail.ru заново.", revoked=True)
            try:
                return decrypt(
                    encrypted,
                    self._encryption_key,
                    associated_data=self._aad(account["user_id"], account["workspace_id"], "app_password"),
                )
            except Exception as exc:
                raise ProviderError("Не удалось расшифровать пароль приложения. Подключите Mail.ru заново.", revoked=True) from exc
        if not account.get("access_token_encrypted") or not account.get("refresh_token_encrypted"):
            raise ProviderError("Почтовый ящик нужно подключить заново.", revoked=True)
        access_token = decrypt(
            account["access_token_encrypted"], self._encryption_key,
            associated_data=self._aad(account["user_id"], account["workspace_id"], "access"),
        )
        expires_at = account.get("token_expires_at")
        if expires_at:
            from datetime import datetime, timezone

            try:
                expires = datetime.fromisoformat(expires_at)
            except ValueError:
                expires = utc_now()
            if expires <= utc_now() + timedelta(seconds=60):
                refresh_token = decrypt(
                    account["refresh_token_encrypted"], self._encryption_key,
                    associated_data=self._aad(account["user_id"], account["workspace_id"], "refresh"),
                )
                provider = self._provider_for_account(account, refresh_token)
                try:
                    token_set = provider.refresh_token(refresh_token)
                except ProviderError as exc:
                    self.mark_refresh_error(account["id"], exc)
                    raise
                new_refresh = token_set.refresh_token or refresh_token
                self.repository.update_mail_tokens(
                    account["id"],
                    encrypt(token_set.access_token, self._encryption_key, associated_data=self._aad(account["user_id"], account["workspace_id"], "access")),
                    encrypt(new_refresh, self._encryption_key, associated_data=self._aad(account["user_id"], account["workspace_id"], "refresh")),
                    (utc_now() + timedelta(seconds=max(60, token_set.expires_in))).isoformat(),
                )
                access_token = token_set.access_token
        return access_token

    def _provider_for_account(self, account: dict[str, Any], credential: str | None) -> MailProvider:
        if account.get("provider") == "mailru":
            return self.provider_factory("mailru", credential)
        return self.provider_factory(str(account["provider"]))

    @staticmethod
    def _public_account(account: dict[str, Any], *, outgoing_enabled: bool | None = None) -> dict[str, Any]:
        if not account:
            return {}
        provider = str(account.get("provider") or "")
        auth_mode = str(account.get("auth_mode") or ("oauth" if provider == "yandex" else "app_password"))
        connected = str(account.get("status") or "") == "connected" and (
            bool(account.get("access_token_encrypted")) if auth_mode == "oauth" else True
        )
        account_outgoing_enabled = bool(account.get("account_outgoing_enabled", 0))
        effective_outgoing_enabled = account_outgoing_enabled if outgoing_enabled is None else bool(outgoing_enabled)
        incoming_enabled = bool(account.get("account_incoming_enabled", 1))
        incoming_error = account.get("incoming_last_error") or None
        if not incoming_enabled:
            incoming_health = "disabled"
        elif incoming_error:
            incoming_health = "error"
        elif account.get("incoming_last_success_at"):
            incoming_health = "healthy"
        else:
            incoming_health = "pending"
        return {
            "id": int(account["id"]),
            "provider": provider,
            "provider_type": provider,
            "email": account.get("email"),
            "email_address": account.get("email"),
            "display_name": account.get("display_name") or ("Яндекс.Почта" if provider == "yandex" else "Mail.ru"),
            "auth_mode": auth_mode,
            "credential_reference": account.get("credential_reference"),
            "status": account.get("status"),
            "connected": connected,
            "outgoing_enabled": effective_outgoing_enabled,
            "outgoing_health": "ready" if effective_outgoing_enabled else "disabled",
            "incoming_enabled": incoming_enabled,
            "incoming_health": incoming_health,
            "incoming_last_success_at": account.get("incoming_last_success_at"),
            "incoming_last_error_at": account.get("incoming_last_error_at"),
            "incoming_last_error": incoming_error,
            "token_expires_at": account.get("token_expires_at"),
            "last_error": account.get("last_error_message"),
            "updated_at": account.get("updated_at"),
        }

    def continuation_dry_run(
        self,
        *,
        user_id: int,
        workspace_id: int,
        campaign_id: int,
        mail_account_id: int,
        limit: int | None = None,
    ) -> dict[str, Any]:
        account = self.repository.get_mail_account_for_owner(mail_account_id, user_id, workspace_id)
        if not account or account["provider"] != "mailru" or account["status"] != "connected":
            raise ProviderError("Выберите подключённый аккаунт Mail.ru для безопасной проверки продолжения.")
        result = self.repository.campaign_continuation_dry_run(
            workspace_id, campaign_id, mail_account_id, limit=limit,
        )
        if not result:
            raise ValueError("Campaign не найдена в текущем рабочем пространстве.")
        if not result["safe"]:
            raise ValueError("Проверка продолжения доступна только для незавершённой Yandex-кампании и подключённого Mail.ru.")
        result["target_account"] = self._public_account(account)
        return result

    def apply_campaign_continuation(
        self,
        *,
        user_id: int,
        workspace_id: int,
        campaign_id: int,
        mail_account_id: int,
        limit: int,
        idempotency_key: str,
        selection_fingerprint: str,
        operator_confirmed: bool,
        selected_targets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Prepare a bounded Mail.ru continuation; never calls SMTP.

        The caller may submit the immutable target snapshot returned by the
        dry-run.  This is important when a target becomes suppressed between
        dry-run and apply: the snapshot must be revalidated, not replaced by
        a newly selected target.
        """

        if type(operator_confirmed) is not bool or not operator_confirmed:
            raise ValueError("Для continuation требуется явное подтверждение оператора.")
        if int(limit) < 1 or int(limit) > 5:
            raise ValueError("Лимит continuation должен быть от 1 до 5.")
        clean_key = self._normalize_idempotency_key(idempotency_key, required=True)
        fingerprint = str(selection_fingerprint or "").strip().lower()
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("Укажите корректный selection fingerprint из dry-run.")
        account = self.repository.get_mail_account_for_owner(mail_account_id, user_id, workspace_id)
        if not account or account["provider"] != "mailru" or account["status"] != "connected":
            raise ProviderError("Выберите подключённый аккаунт Mail.ru для continuation.")
        existing = self.repository.get_continuation_plan(workspace_id, clean_key)
        if existing:
            if (
                int(existing.get("campaign_id") or 0) != int(campaign_id)
                or int(existing.get("mail_account_id") or 0) != int(mail_account_id)
                or int(existing.get("limit_count") or 0) != int(limit)
                or str(existing.get("selection_fingerprint") or "") != fingerprint
            ):
                raise ContinuationPlanConflictError("Этот idempotency key уже связан с другим continuation plan.")
            replay = dict(existing.get("result") or {})
            replay["idempotent_replay"] = True
            replay["target_account"] = self._public_account(account)
            return replay
        dry_run = self.repository.campaign_continuation_dry_run(
            workspace_id, campaign_id, mail_account_id, limit=int(limit),
        )
        if not dry_run:
            raise ValueError("Campaign не найдена в текущем рабочем пространстве.")
        if not dry_run["safe"]:
            raise ValueError("Continuation доступен только для незавершённой Yandex-кампании и подключённого Mail.ru.")
        immutable_targets = selected_targets if selected_targets is not None else list(dry_run.get("selected_targets") or [])
        if selected_targets is None and fingerprint != str(dry_run["selection_fingerprint"]):
            raise ContinuationPlanConflictError("Dry-run plan устарел. Повторите dry-run перед apply.")
        result = self.repository.apply_campaign_continuation(
            workspace_id=workspace_id,
            user_id=user_id,
            request_id=int(dry_run["source_state"]["request_id"]),
            campaign_id=campaign_id,
            target_account_id=mail_account_id,
            limit=int(limit),
            idempotency_key=clean_key,
            selection_fingerprint=fingerprint,
            selected_targets=immutable_targets,
            operator_confirmed=operator_confirmed,
        )
        result["target_account"] = self._public_account(account)
        return result

    def cross_provider_retry_preview(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        original_job_id: int,
        original_message_id: int,
        target_mail_account_id: int,
        original_attempt_id: int | None = None,
    ) -> dict[str, Any]:
        """Read-only preview for one proven Yandex rejection -> Mail.ru plan."""

        account = self.repository.get_mail_account_for_owner(
            target_mail_account_id, user_id, workspace_id,
        )
        if not account or account["provider"] != "mailru":
            raise ProviderError("Для cross-provider retry выберите аккаунт Mail.ru.")
        result = self.repository.cross_provider_retry_preview(
            workspace_id=workspace_id, user_id=user_id, request_id=request_id,
            original_job_id=original_job_id, original_message_id=original_message_id,
            target_account_id=target_mail_account_id, original_attempt_id=original_attempt_id,
        )
        result["target_account"] = self._public_account(account)
        result["no_live_send"] = True
        result["smtp_data_calls"] = 0
        return result

    def apply_cross_provider_retry(
        self,
        *,
        user_id: int,
        workspace_id: int,
        request_id: int,
        original_job_id: int,
        original_message_id: int,
        target_mail_account_id: int,
        idempotency_key: str,
        selection_fingerprint: str,
        operator_confirmed: bool,
        confirmation: dict[str, Any] | None = None,
        original_attempt_id: int | None = None,
    ) -> dict[str, Any]:
        """Queue one explicit retry plan; this method never invokes SMTP."""

        account = self.repository.get_mail_account_for_owner(
            target_mail_account_id, user_id, workspace_id,
        )
        if not account or account["provider"] != "mailru" or account["status"] != "connected":
            raise ProviderError("Для cross-provider retry выберите подключённый аккаунт Mail.ru.")
        result = self.repository.apply_cross_provider_retry(
            workspace_id=workspace_id, user_id=user_id, request_id=request_id,
            original_job_id=original_job_id, original_message_id=original_message_id,
            target_account_id=target_mail_account_id, idempotency_key=idempotency_key,
            selection_fingerprint=selection_fingerprint, operator_confirmed=operator_confirmed,
            confirmation=confirmation, original_attempt_id=original_attempt_id,
        )
        result["target_account"] = self._public_account(account)
        result["no_live_send"] = True
        result["smtp_data_calls"] = 0
        return result

    def validate_attachments(self, attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        allowed_prefixes = {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument", "text/plain", "image/"}
        total = 0
        result: list[dict[str, Any]] = []
        for item in attachments:
            filename = str(item.get("filename", "")).strip()
            mime_type = str(item.get("mime_type", "application/octet-stream")).lower().strip()
            encoded = item.get("content_base64")
            if not filename or len(filename) > 180 or "/" in filename or "\\" in filename:
                raise ValueError("Имя вложения некорректно.")
            if not isinstance(encoded, str):
                raise ValueError("Содержимое вложения не передано.")
            if not any(mime_type == prefix or mime_type.startswith(prefix) for prefix in allowed_prefixes):
                raise ValueError("Тип вложения не разрешён. Используйте PDF, DOCX, TXT или изображение.")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("Вложение повреждено.") from exc
            if len(content) > self.max_attachment_bytes:
                raise ValueError("Размер одного вложения превышает 10 МБ.")
            total += len(content)
            if total > self.max_total_attachment_bytes:
                raise ValueError("Общий размер вложений превышает 20 МБ.")
            result.append({"filename": filename, "mime_type": mime_type, "size_bytes": len(content), "content": content})
        return result

    @staticmethod
    def validate_email(value: str, label: str = "Email") -> str:
        value = str(value or "").strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError(f"{label} указан некорректно.")
        return value

    @staticmethod
    def _validate_subject(value: str) -> str:
        value = str(value).strip()
        if not value or len(value) > 240 or "\r" in value or "\n" in value:
            raise ValueError("Тема письма обязательна и не должна содержать переводы строки.")
        return value

    @staticmethod
    def _validate_html(value: str) -> str:
        if len(value) > 100_000:
            raise ValueError("HTML-текст письма превышает 100 000 символов.")
        return value

    def _normalize_outbound_content(
        self,
        *,
        body: str | None,
        body_text: str | None,
        body_html: str | None,
    ) -> tuple[str, str | None]:
        """Normalize legacy/plain and explicit HTML input into one send contract.

        ``body`` remains a compatibility alias. When HTML is supplied, its
        plain-text alternative is always derived from the sanitized fragment;
        explicit ``body_text`` is only a fallback for HTML with no visible text.
        """
        if body_text is not None and not isinstance(body_text, str):
            raise ValueError("body_text должен быть строкой.")
        if body_html is not None and not isinstance(body_html, str):
            raise ValueError("body_html должен быть строкой.")
        if body is not None and not isinstance(body, str):
            raise ValueError("body должен быть строкой.")

        explicit_html = body_html.strip() if body_html else ""
        explicit_text = body_text if body_text is not None else body
        if explicit_text is None:
            explicit_text = ""
        if explicit_html:
            self._validate_html(explicit_html)
            safe_html = sanitize_email_html(explicit_html)
            derived_text = html_to_text(safe_html)
            text = derived_text or explicit_text
            return self._validate_body(text), safe_html or None
        return self._validate_body(explicit_text), None

    @staticmethod
    def _validate_body(value: str) -> str:
        value = str(value)
        if not value.strip():
            raise ValueError("Текст письма не может быть пустым.")
        if len(value) > 20_000:
            raise ValueError("Текст письма превышает 20 000 символов.")
        return value

    @staticmethod
    def _normalize_supplier(supplier: dict[str, Any]) -> dict[str, Any]:
        email = MailService.validate_email(supplier.get("email", ""), "Email поставщика")
        name = str(supplier.get("name") or "").strip()[:240]
        host = str(supplier.get("host") or "").strip()[:240]
        external_key = str(supplier.get("external_key") or host or email).strip()[:240]
        if not external_key:
            external_key = email
        raw_supplier_id = supplier.get("id", supplier.get("supplier_id"))
        supplier_id: int | None = None
        if raw_supplier_id not in (None, ""):
            try:
                supplier_id = int(raw_supplier_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("Идентификатор поставщика указан некорректно.") from exc
            if supplier_id <= 0:
                raise ValueError("Идентификатор поставщика указан некорректно.")
        return {
            "supplier_id": supplier_id,
            "name": name,
            "email": email,
            "host": host,
            "external_key": external_key,
            "contact_name": str(supplier.get("contact_name") or "").strip()[:240],
            "category": str(supplier.get("category") or supplier.get("supplier_category") or "").strip()[:240],
            "website": str(supplier.get("website") or "").strip()[:500],
            "city": str(supplier.get("city") or supplier.get("region") or "").strip()[:240],
        }

    @staticmethod
    def personalize(template: str, **values: str) -> str:
        text = str(template or "")
        if not values.get("supplier_name"):
            text = re.sub(r"Здравствуйте,\s*\{\{supplier_name\}\}!", "Здравствуйте!", text, flags=re.IGNORECASE)
        for key in (
            "supplier_name", "contact_name", "supplier_category", "supplier_website",
            "supplier_city", "request_name", "request_description", "sender_name", "company_name",
        ):
            text = text.replace("{{" + key + "}}", values.get(key, "") or "")
        return text

    @classmethod
    def _personalize_html(cls, template: str, values: dict[str, str]) -> str:
        """Substitute dynamic values as escaped text before HTML sanitization."""
        escaped_values = {key: escape(value, quote=True) for key, value in values.items()}
        return cls.personalize(template, **escaped_values)

    def _require_encryption(self) -> None:
        if self._encryption_key is None:
            raise ProviderError("Сервер не настроен: задайте MAIL_TOKEN_ENCRYPTION_KEY.")

    @staticmethod
    def _aad(user_id: int, workspace_id: int, kind: str) -> str:
        return f"mail-account:{user_id}:{workspace_id}:{kind}"
