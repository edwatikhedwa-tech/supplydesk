"""Provider-neutral content preflight and staged-rollout primitives.

This module deliberately contains deterministic checks and internal rollout
policy only.  It does not contact SMTP/IMAP, alter message text to evade
filters, or claim anything about inbox placement.
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable


PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z][\w.-]*)\s*\}\}")
KNOWN_PLACEHOLDERS = {
    "supplier_name", "contact_name", "supplier_category", "supplier_website",
    "supplier_city", "request_name", "request_description", "sender_name", "company_name",
}
EMAIL_RE = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
DEFAULT_CAMPAIGN_MAX_RECIPIENTS = 300
MIN_CAMPAIGN_MAX_RECIPIENTS = 1
MAX_CAMPAIGN_MAX_RECIPIENTS = 500
_HEALTH_TERMINAL_OUTCOMES = frozenset({
    "accepted", "transient_rejected", "permanent_rejected", "uncertain",
})
UNSAFE_CLAIM_RE = re.compile(
    r"(?:видел[аи]?\s+у\s+вас|изучил[аи]?\s+ваш\s+ассортимент|знаем,?\s+что\s+у\s+вас|"
    r"we\s+(?:saw|reviewed)\s+your\s+(?:catalog|assortment))",
    re.IGNORECASE,
)


def campaign_max_recipients_from_env(value: Any | None = None) -> int:
    """Resolve the one provider-neutral campaign-size setting.

    Values outside the supported range are constrained safely; a malformed
    or non-positive value falls back to the product default instead of
    disabling the size guard.
    """

    raw = os.getenv("MAIL_CAMPAIGN_MAX_RECIPIENTS", str(DEFAULT_CAMPAIGN_MAX_RECIPIENTS)) if value is None else value
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CAMPAIGN_MAX_RECIPIENTS
    if parsed < MIN_CAMPAIGN_MAX_RECIPIENTS:
        return DEFAULT_CAMPAIGN_MAX_RECIPIENTS
    return min(parsed, MAX_CAMPAIGN_MAX_RECIPIENTS)


@dataclass(frozen=True, slots=True)
class RolloutSettings:
    """Internal staged-rollout defaults, changeable through environment."""

    stage_1: int = 10
    stage_2: int = 25
    stage_3: int = 50
    manual_stage_approval: bool = False
    max_permanent_failure_rate: float = 0.20
    max_unknown_rate: float = 0.10
    max_transient_failures: int = 3
    recent_transient_window: int = 10
    recent_transient_min_sample: int = 10
    recent_transient_pause_count: int = 5
    recent_transient_pause_ratio: float = 0.50
    max_provider_rejections: int = 1
    similarity_warning_ratio: float = 0.80
    # Test/operator-only runtime hold.  These values are deliberately not part
    # of campaign intent or the send idempotency fingerprint: they control
    # whether an already-created campaign may advance to a later stage in this
    # process.
    operator_stage_cap_campaign_id: int | None = None
    operator_stage_cap: int | None = None

    @classmethod
    def from_env(cls) -> "RolloutSettings":
        def integer(name: str, default: int, maximum: int = 100_000) -> int:
            try:
                value = int(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                value = default
            return max(1, min(value, maximum))

        def decimal(name: str, default: float) -> float:
            try:
                value = float(os.getenv(name, str(default)))
            except (TypeError, ValueError):
                value = default
            return max(0.0, min(value, 1.0))

        manual = (os.getenv("MAIL_CAMPAIGN_MANUAL_STAGE_APPROVAL", "0") or "0").strip().lower()

        def optional_positive_integer(name: str) -> int | None:
            raw = (os.getenv(name, "") or "").strip()
            if not raw:
                return None
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return None
            return value if value > 0 else None

        operator_stage_cap_campaign_id = optional_positive_integer("MAIL_CAMPAIGN_STAGE_CAP_ID")
        operator_stage_cap = optional_positive_integer("MAIL_CAMPAIGN_STAGE_CAP")
        if operator_stage_cap_campaign_id is None or operator_stage_cap is None:
            # A partial or malformed pair must not accidentally create a
            # global hold.  Without a complete pair production semantics are
            # unchanged.
            operator_stage_cap_campaign_id = None
            operator_stage_cap = None
        return cls(
            stage_1=integer("MAIL_ROLLOUT_STAGE_1", 10),
            stage_2=integer("MAIL_ROLLOUT_STAGE_2", 25),
            stage_3=integer("MAIL_ROLLOUT_STAGE_3", 50),
            manual_stage_approval=manual in {"1", "true", "yes", "on"},
            max_permanent_failure_rate=decimal("MAIL_CAMPAIGN_MAX_PERMANENT_FAILURE_RATE", 0.20),
            max_unknown_rate=decimal("MAIL_CAMPAIGN_MAX_UNKNOWN_RATE", 0.10),
            max_transient_failures=integer("MAIL_CAMPAIGN_MAX_TRANSIENT_FAILURES", 3),
            recent_transient_window=integer("MAIL_CAMPAIGN_TRANSIENT_WINDOW", 10, maximum=1000),
            recent_transient_min_sample=integer("MAIL_CAMPAIGN_TRANSIENT_MIN_SAMPLE", 10, maximum=1000),
            recent_transient_pause_count=integer("MAIL_CAMPAIGN_TRANSIENT_PAUSE_COUNT", 5, maximum=1000),
            recent_transient_pause_ratio=decimal("MAIL_CAMPAIGN_TRANSIENT_PAUSE_RATIO", 0.50),
            max_provider_rejections=integer("MAIL_CAMPAIGN_MAX_PROVIDER_REJECTIONS", 1),
            similarity_warning_ratio=decimal("MAIL_CAMPAIGN_SIMILARITY_WARNING_RATIO", 0.80),
            operator_stage_cap_campaign_id=operator_stage_cap_campaign_id,
            operator_stage_cap=operator_stage_cap,
        )

    def operator_stage_cap_for(self, campaign_id: int) -> int | None:
        """Return the process hold only for its explicitly named campaign."""

        if self.operator_stage_cap_campaign_id != int(campaign_id):
            return None
        return self.operator_stage_cap

    def blocks_stage_advancement(self, campaign_id: int, next_stage: int) -> bool:
        cap = self.operator_stage_cap_for(campaign_id)
        return cap is not None and int(next_stage) > cap

    def cumulative_limit(self, stage: int, total: int) -> int:
        limits = {1: self.stage_1, 2: self.stage_2, 3: self.stage_3}
        if stage >= 4:
            return total
        return min(total, limits.get(max(1, stage), total))

    def next_stage(self, stage: int, total: int) -> tuple[int, int] | None:
        next_stage = int(stage) + 1
        current_limit = self.cumulative_limit(stage, total)
        if current_limit >= total:
            return None
        if next_stage >= 4:
            return 4, total
        # Preserve the stage number even when the next cumulative ceiling
        # covers a small campaign in full (for example, stage 2 = 18).
        return next_stage, self.cumulative_limit(next_stage, total)


def transient_health_metrics(
    outcomes: Iterable[str],
    *,
    window: int = 10,
) -> dict[str, float | int]:
    """Calculate current transient health from durable outcomes in time order.

    ``outcomes`` must be ordered oldest to newest.  Only completed transport
    outcomes participate.  Lifetime audit rows remain untouched; this helper
    deliberately derives a bounded current signal instead of a cumulative
    incident counter.
    """

    terminal = [str(outcome) for outcome in outcomes if str(outcome) in _HEALTH_TERMINAL_OUTCOMES]
    consecutive = 0
    for outcome in reversed(terminal):
        if outcome != "transient_rejected":
            break
        consecutive += 1
    bounded_window = max(1, int(window))
    recent = terminal[-bounded_window:]
    recent_transient = sum(1 for outcome in recent if outcome == "transient_rejected")
    recent_count = len(recent)
    return {
        "consecutive_transient_failures": consecutive,
        "recent_attempt_count": recent_count,
        "recent_transient_count": recent_transient,
        "recent_transient_ratio": (recent_transient / recent_count) if recent_count else 0.0,
    }


class DeliverabilityPreflightError(ValueError):
    """A safe, structured refusal before operation/SMTP creation."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        blocks = ", ".join(str(item) for item in result.get("blocks", []))
        super().__init__("Preflight заблокировал кампанию" + (f": {blocks}" if blocks else "."))


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def is_valid_email(value: Any) -> bool:
    return bool(EMAIL_RE.match(normalize_email(value)))


def email_domain(value: str) -> str:
    return normalize_email(value).rsplit("@", 1)[-1] if "@" in normalize_email(value) else ""


def unresolved_placeholders(*values: str) -> list[str]:
    found: list[str] = []
    for value in values:
        for name in PLACEHOLDER_RE.findall(str(value or "")):
            if name not in found:
                found.append(name)
    return found


def personalization_level(*, supplier: dict[str, Any], request: dict[str, Any], verified_context: bool = False) -> int:
    """Score only known data; the score never changes the rendered text."""

    company = str(supplier.get("name") or "").strip()
    if not company:
        return 0
    if verified_context:
        return 3
    request_context = str(request.get("name") or "").strip() or str(request.get("description") or "").strip()
    category = str(supplier.get("category") or supplier.get("supplier_category") or "").strip()
    return 2 if request_context or category else 1


def normalized_similarity_text(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[^\w@.+-]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def similarity_ratio(values: Iterable[str]) -> float:
    items = [normalized_similarity_text(value) for value in values if str(value or "").strip()]
    if len(items) < 2:
        return 1.0 if items else 0.0
    baseline = items[0]
    similar = sum(difflib.SequenceMatcher(None, baseline, item).ratio() >= 0.92 for item in items)
    return similar / len(items)


def subject_quality(subject: str, *, recipient_count: int) -> tuple[list[str], list[str]]:
    blocks: list[str] = []
    warnings: list[str] = []
    value = str(subject or "").strip()
    if not value:
        blocks.append("empty_subject")
        return blocks, warnings
    if len(value) > 160:
        warnings.append("subject_too_long")
    letters = [char for char in value if char.isalpha()]
    if letters and sum(char.isupper() for char in letters) / len(letters) > 0.85:
        warnings.append("subject_all_caps")
    if value.count("!") >= 3:
        warnings.append("subject_excessive_exclamation")
    if re.match(r"(?i)^(?:re|fw|fwd)\s*:", value):
        blocks.append("misleading_reply_subject_without_thread")
    return blocks, warnings


def body_quality(
    body: str,
    *,
    request: dict[str, Any],
    verified_context: bool = False,
    allowed_placeholders: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    blocks: list[str] = []
    warnings: list[str] = []
    value = str(body or "")
    if not value.strip():
        blocks.append("empty_body")
        return blocks, warnings
    allowed = KNOWN_PLACEHOLDERS if allowed_placeholders is None else allowed_placeholders
    placeholders = [name for name in unresolved_placeholders(value) if name not in allowed]
    if placeholders:
        blocks.append("broken_placeholder:" + ",".join(placeholders))
    if len(re.findall(r"https?://", value, flags=re.IGNORECASE)) > 5:
        warnings.append("too_many_links")
    if len(value) > 12_000:
        warnings.append("large_body")
    if not str(request.get("name") or "").strip() and not str(request.get("description") or "").strip():
        warnings.append("missing_clear_request")
    if UNSAFE_CLAIM_RE.search(value) and not verified_context:
        blocks.append("unverified_personalization_claim")
    return blocks, warnings


def provider_policy_warning(provider: str, recipient_count: int) -> str | None:
    if str(provider or "").lower() == "yandex" and recipient_count >= 10:
        return (
            "Яндекс может ограничить однотипные коммерческие письма с обычного "
            "ящика раньше технического ceiling. Внутренний pacing SupplyDesk "
            "снижает нагрузку, но не отменяет правила провайдера."
        )
    return None


def classify_provider_error(error: Any) -> str:
    """Map explicit provider evidence to the campaign health taxonomy."""

    code = str(getattr(error, "provider_code", "") or "").lower()
    message = str(getattr(error, "message", "") or "").lower()
    if getattr(error, "uncertain", False):
        return "transport-uncertain"
    if getattr(error, "revoked", False) or code in {"535", "auth", "authentication", "imap-auth"}:
        return "authentication"
    if any(token in code for token in ("spam", "policy")) or any(
        token in message for token in ("spam", "спам", "policy", "политик")
    ):
        return "provider-spam-policy"
    if getattr(error, "rate_limited", False) or any(
        token in code for token in ("throttl", "rate", "421", "450", "451", "452")
    ):
        return "provider-throttling"
    if any(token in code for token in ("recipient", "invalid-recipient", "550", "551", "553")):
        return "recipient-invalid"
    return code or ("transient" if getattr(error, "transient", False) else "permanent")


def estimate_duration_seconds(recipient_count: int, min_interval: float, max_interval: float) -> dict[str, int]:
    count = max(0, int(recipient_count))
    intervals = max(0, count - 1)
    average = (float(min_interval) + float(max_interval)) / 2.0
    return {
        "minimum": int(round(intervals * float(min_interval))),
        "average": int(round(intervals * average)),
        "maximum": int(round(intervals * float(max_interval))),
    }
