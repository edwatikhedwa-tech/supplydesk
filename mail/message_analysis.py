"""Mail Intelligence Core (Iteration 2 / EDW-7): analyse one incoming message ONCE and reuse the result.

    incoming message
      -> idempotency lookup (workspace, message, content hash, analysis version)   -> hit: 0 model calls
      -> exact rules first: bounce / bulk sender / nothing to extract / thread or [SD-N] match / candidates
      -> only if something extractable remains: budget check -> cheap model -> validate
      -> invalid or unsupported -> ONE strong model -> validate -> otherwise manual review
      -> facts with provenance (verbatim quote + offsets), a ledger row per stage, downstream event
      -> event handler acts WITHOUT any model call

Principles (Documentation Pack V1.2): exact rules before AI; the model never invents critical facts (a fact
is kept only if its quote and SKU are literally in the message); facts are proposals and never change the
request by themselves; every model call is measured (reason, model, tokens, cost, version, hash); an
unchanged message under the same version is never analysed twice; reprocessing is explicit and versioned.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from .bounce import classify_bounce
from .request_references import parse_request_reference_from_subject
from .time_utils import iso_now

ANALYSIS_VERSION = "mail-extract/v3"
STALE_IN_PROGRESS_MINUTES = 15
MAX_ATTEMPTS = 3                      # provider errors per (message, hash, version) before manual review
MAX_TEXT_CHARS = 6000                 # what may be sent to a model
FOLLOWUP_TASK_TITLE = "Связаться с поставщиком"   # the fixed default of the "remind" action
# issues that say the LETTER lacks the information: a stronger model cannot supply it -> manual review, no escalation
UNFIXABLE_ISSUES = ("currency_not_in_message", "price_is_range")
MESSAGE_TYPES = {"quote", "question", "decline", "invoice", "other"}
CURRENCIES = {"RUB", "USD", "EUR", "CNY", "KZT", "BYN"}
_CURRENCY_ALIASES = {"₽": "RUB", "РУБ": "RUB", "РУБ.": "RUB", "Р.": "RUB", "RUR": "RUB", "$": "USD", "€": "EUR",
                     "ЮАНЬ": "CNY", "ЮАНЕЙ": "CNY"}

_QUOTED_LINE = re.compile(r"^\s*>")
_REPLY_MARKER = re.compile(r"^\s*(-{2,}\s*(original message|исходное сообщение|пересылаемое сообщение)|"
                           r"от:\s.+|from:\s.+|on .+ wrote:|.+ написал\(а\):)\s*$", re.IGNORECASE)
# something worth extracting: a price-like number, a currency word or a quote-related term
_PRICE_PATTERN = re.compile(r"\d[\d\s.,]*\s*(₽|руб|р\.|rub|usd|eur|cny|юан|\$|€)", re.IGNORECASE)
_QUOTE_TERMS = re.compile(r"(цен[аыуой]|стоимост|прайс|кп\b|коммерческ|предложен|счёт|счет|срок|наличи|отгруз|поставк|скидк)",
                          re.IGNORECASE)
_ATTACHMENT = re.compile(r"(во\s+вложени|вложени[еяю]|приложенн|прикреплен|прикрепил|attached|attachment|excel-файл)", re.IGNORECASE)
_UNSUBSCRIBE = re.compile(r"(отписат|отписк|unsubscribe|рассылк)", re.IGNORECASE)

_ITEM_KEYS = ["name", "brand", "sku", "quantity", "unit", "price", "currency", "vat_included", "lead_time_days", "source_quote"]
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "message_type": {"type": "string", "enum": sorted(MESSAGE_TYPES)},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "brand": {"type": ["string", "null"]},
                    "sku": {"type": ["string", "null"]},
                    "quantity": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "price": {"type": ["number", "null"]},
                    "currency": {"type": ["string", "null"], "enum": ["RUB", "USD", "EUR", "CNY", "KZT", "BYN", None]},
                    "vat_included": {"type": ["boolean", "null"]},
                    "lead_time_days": {"type": ["integer", "null"]},
                    "source_quote": {"type": "string"},
                },
                "required": _ITEM_KEYS,
            },
        },
    },
    "required": ["message_type", "items"],
}

SYSTEM_PROMPT = (
    "Ты извлекаешь факты из ответа поставщика на запрос цены. Верни ТОЛЬКО JSON строго по схеме, без пояснений.\n"
    "message_type: quote — в письме названа цена хотя бы одной позиции; question — поставщик просит уточнений или обещает "
    "цену позже; decline — отказ; invoice — счёт на оплату; other — всё остальное.\n"
    "items: по одному элементу на КАЖДУЮ названную в письме цену (ступени цены по количеству — отдельные элементы). "
    "Если цен в письме нет, items пустой. Не включай номер счёта, телефон, ИНН, артикул, дату и общую сумму счёта как цену.\n"
    "price — число за единицу товара (без валюты и пробелов). currency — код: RUB (руб., ₽, р.), USD ($), EUR (€), CNY, KZT, "
    "BYN; если валюта не названа — null. sku — артикул/модель/обозначение позиции, если оно явно написано в письме рядом с ценой (примеры: 6205-2RS1, NU 2210 E, LGMT 2/1, R901025, AB-7654/12), иначе null. Ничего не выдумывай: "
    "нет в тексте — null. source_quote — ДОСЛОВНАЯ цитата из письма (одна строка), содержащая позицию и цену. "
    "Не оценивай массу, габариты и наличие, если их нет в тексте."
)


# --------------------------------------------------------------------------- pure helpers
def normalize_text(subject: str, body: str) -> str:
    """Subject + own text of the message: quoted reply lines and everything after a reply marker removed,
    whitespace collapsed. This is BOTH the model input and the content that is hashed."""
    kept: list[str] = []
    for line in str(body or "").replace("\r", "").split("\n"):
        if _REPLY_MARKER.match(line):
            break
        if _QUOTED_LINE.match(line):
            continue
        kept.append(line)
    text = " ".join(" ".join(kept).split())
    return f"{' '.join(str(subject or '').split())}\n{text}".strip()


def _stale_before() -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(minutes=STALE_IN_PROGRESS_MINUTES)).isoformat()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def needs_extraction(text: str) -> bool:
    """False when the message contains nothing an extractor could use: no price-like number, and either no quote
    term at all or only an "it is in the attachment" note (attachments are a later iteration)."""
    if _PRICE_PATTERN.search(text):
        return True
    # Quote terms count only in the message's own text: the subject of a reply carries OUR request ("Запрос цены ..."),
    # which is not a signal that the supplier named a price (found by the real-mailbox E2E run).
    own_text = text.partition("\n")[2]
    return bool(_QUOTE_TERMS.search(own_text)) and not _ATTACHMENT.search(text)


def looks_like_newsletter(text: str) -> bool:
    """Unmatched mail that carries an unsubscribe / mass-mailing marker (used only for messages without a thread)."""
    return bool(_UNSUBSCRIBE.search(text))


def _loose(value: str) -> str:
    return re.sub(r"[\s\-_./]+", "", value.casefold())


_NUMBER = re.compile(r"\d[\d\s]*(?:[.,]\d+)?")
_CURRENCY_MARKERS = {
    "RUB": re.compile(r"₽|руб|\brub\b|\bр\.|\bр\b|\brur\b", re.IGNORECASE),
    "USD": re.compile(r"\$|usd|доллар", re.IGNORECASE),
    "EUR": re.compile(r"€|eur\b|евро", re.IGNORECASE),
    "CNY": re.compile(r"cny|юан|¥|rmb", re.IGNORECASE),
    "KZT": re.compile(r"kzt|тенге|₸", re.IGNORECASE),
    "BYN": re.compile(r"byn|бел\.?\s*руб", re.IGNORECASE),
}


# a range is a tight hyphen/en dash between two amounts ("1 200–1 350 руб.") or "от X до Y"; an em dash with spaces
# ("6205-2RS1 — 1 850 руб.") is only a separator between the item and its price
_CUR = r"(?:₽|руб|р\.|rub|usd|eur|cny|юан|\$|€)"
_RANGE = re.compile(rf"(\d[\d\s]*(?:[.,]\d+)?)[–-](\d[\d\s]*(?:[.,]\d+)?)\s*{_CUR}|"
                    rf"от\s+(\d[\d\s]*(?:[.,]\d+)?)\s+до\s+(\d[\d\s]*(?:[.,]\d+)?)\s*{_CUR}", re.IGNORECASE)
_PRICE_MENTION = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(?:₽|руб|р\.|rub|usd|eur|cny|юан|\$|€)", re.IGNORECASE)


def price_mentions(text: str) -> set[Decimal]:
    """Amounts the letter writes next to a currency ("1 850 руб.", "120 USD"): what an extraction should cover."""
    out: set[Decimal] = set()
    for raw in _PRICE_MENTION.findall(text):
        value = _to_decimal(raw.replace(" ", "").replace(" ", ""))
        if value is not None and value > 0:
            out.add(value.normalize())
    return out


def _numbers_in(text: str) -> set[Decimal]:
    found: set[Decimal] = set()
    for raw in _NUMBER.findall(text):
        value = _to_decimal(raw.replace(" ", "").replace("\u00a0", ""))
        if value is not None:
            found.add(value.normalize())
    return found


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


def validate_extraction(data: Any, text: str) -> dict[str, Any]:
    """Deterministic checks of a model answer. Returns
    {"ok", "message_type", "facts": [...], "issues": [...]}. `ok` means the answer can be used as is."""
    issues: list[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "message_type": "", "facts": [], "issues": ["not_an_object"]}
    message_type = str(data.get("message_type") or "")
    if message_type not in MESSAGE_TYPES:
        return {"ok": False, "message_type": "", "facts": [], "issues": ["bad_message_type"]}
    items = data.get("items")
    if not isinstance(items, list) or len(items) > 50:
        return {"ok": False, "message_type": message_type, "facts": [], "issues": ["bad_items"]}
    haystack = text.casefold()
    facts: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append(f"item{index}:not_an_object")
            continue
        quote = " ".join(str(item.get("source_quote") or "").split())
        start = haystack.find(quote.casefold()) if quote else -1
        if start < 0:
            issues.append(f"item{index}:source_quote_not_in_message")     # provenance is mandatory
            continue
        if item.get("price") is None or str(item.get("price")).strip() == "":
            continue            # an item that states no price is not a quote item (nothing to verify, nothing to keep)
        price = _to_decimal(item.get("price"))
        if price is None and isinstance(item.get("price"), str):       # "34 руб." -> 34, but only if it holds ONE number
            numbers = _numbers_in(str(item.get("price")))
            price = next(iter(numbers)) if len(numbers) == 1 else None
        if price is None or price <= 0:
            issues.append(f"item{index}:price_invalid")
            continue
        if price.normalize() not in _numbers_in(quote):
            issues.append(f"item{index}:price_not_in_quote")             # a price the quote does not contain is invented
            continue
        range_pairs = [(m[0] or m[2], m[1] or m[3]) for m in _RANGE.findall(quote)]
        if any(price.normalize() in {_to_decimal(a.replace(" ", "")).normalize(), _to_decimal(b.replace(" ", "")).normalize()}
               for a, b in range_pairs if _to_decimal(a.replace(" ", "")) and _to_decimal(b.replace(" ", ""))):
            issues.append(f"item{index}:price_is_range")                 # "1 200-1 350 руб." is not a price
            continue
        currency = str(item.get("currency") or "").strip().upper()
        currency = _CURRENCY_ALIASES.get(currency, currency)
        if not currency:      # the model left it out: take it from the quote only when the quote shows exactly one currency
            shown = [code for code, marker in _CURRENCY_MARKERS.items() if marker.search(quote)]
            currency = shown[0] if len(shown) == 1 else ""
        if currency not in CURRENCIES:
            issues.append(f"item{index}:currency_invalid")
            continue
        if not _CURRENCY_MARKERS[currency].search(text):
            issues.append(f"item{index}:currency_not_in_message")        # the letter does not show this currency
            continue
        quantity = _to_decimal(item.get("quantity"))
        if item.get("quantity") is not None and (quantity is None or quantity <= 0):
            issues.append(f"item{index}:quantity_invalid")
            quantity = None
        sku = str(item.get("sku") or "").strip() or None
        if sku and _loose(sku) not in _loose(text):
            issues.append(f"item{index}:sku_not_in_message")              # a SKU the text does not contain is dropped
            sku = None
        lead = item.get("lead_time_days")
        lead = int(lead) if isinstance(lead, int) and not isinstance(lead, bool) and 0 <= lead <= 365 else None
        vat = item.get("vat_included") if isinstance(item.get("vat_included"), bool) else None
        facts.append({
            "data": {"name": str(item.get("name") or "").strip()[:240], "brand": (item.get("brand") or None),
                     "sku": sku, "quantity": float(quantity) if quantity is not None else None,
                     "unit": (str(item.get("unit") or "").strip() or None), "price": float(price),
                     "currency": currency, "vat_included": vat, "lead_time_days": lead},
            "source_quote": quote, "source_start": start, "source_end": start + len(quote), "position": index,
        })
    if message_type == "quote" and facts:
        # completeness: an amount written next to a currency that no fact carries may be a missed item (or an invoice
        # total): not provable either way, so the answer is not "clean" -> the cascade decides (strong / review)
        covered = {Decimal(str(f["data"]["price"])).normalize() for f in facts}
        if price_mentions(text) - covered:
            issues.append("price_mentioned_not_extracted")
    if message_type == "quote" and not facts and not items:
        # "a quote" that states no price (the offer is in an attachment, a range, "later"): not an error, not a quote
        return {"ok": True, "message_type": "other", "facts": [], "issues": ["quote_without_price"]}
    if message_type == "quote" and not facts:
        issues.append("quote_without_valid_item")
    ok = not issues
    return {"ok": ok, "message_type": message_type, "facts": facts, "issues": issues}


# --------------------------------------------------------------------------- model adapter
@dataclass
class ModelReply:
    data: dict[str, Any] | None
    model: str
    provider: str = "routerai"
    input_tokens: int = 0
    output_tokens: int = 0
    cost_rub: float | None = None
    cost_source: str = "none"
    latency_ms: int = 0
    error: str = ""
    cached_tokens: int = 0
    retries: int = 0          # extra PAID attempts inside one call (response-format fallbacks, empty answers)
    endpoint: str = ""        # the upstream provider that really served the request, as reported by the gateway


class AnalysisModels(Protocol):
    def model_for(self, stage: str) -> str | None: ...
    def call(self, stage: str, system: str, user: str, schema: dict[str, Any]) -> ModelReply: ...


class RouterAiAnalysisModels:
    """Production adapter over backend.integrations.llm.routerai_client.RouterAiClient (unchanged). The
    client only keeps per-model totals, so one call's usage is the difference of the totals."""

    def __init__(self, client: Any, cheap_model: str | None = None, strong_model: str | None = None) -> None:
        from backend.integrations.llm.llm_fallback import DEFAULT_MODEL

        self.client = client
        self.models = {"cheap": cheap_model or os.getenv("MAIL_ANALYSIS_CHEAP_MODEL") or DEFAULT_MODEL,
                       "strong": strong_model or os.getenv("MAIL_ANALYSIS_STRONG_MODEL") or None}
        self._attempts: list[dict[str, Any]] = []
        self._install_recorder()

    def _install_recorder(self) -> None:
        """Record the RAW usage of every completed attempt (the gateway returns the real cost, cached tokens and the
        serving provider) without changing the client class: the SDK's `create` is wrapped on this instance only."""
        completions = getattr(getattr(getattr(self.client, "_client", None), "chat", None), "completions", None)
        if completions is None or getattr(completions.create, "_sd_recorder", False):
            return
        original, attempts = completions.create, self._attempts

        def recording_create(*args: Any, **kwargs: Any) -> Any:
            completion = original(*args, **kwargs)
            usage = getattr(completion, "usage", None)
            attempts.append({
                "usage": usage.model_dump() if hasattr(usage, "model_dump") else {},
                "endpoint": str(getattr(completion, "provider", "") or ""),
            })
            return completion

        recording_create._sd_recorder = True  # type: ignore[attr-defined]
        completions.create = recording_create

    def model_for(self, stage: str) -> str | None:
        return self.models.get(stage)

    def call(self, stage: str, system: str, user: str, schema: dict[str, Any]) -> ModelReply:
        model = self.models[stage]
        before = self.client.usage.get(model)
        b_in, b_out = (before.input_tokens, before.output_tokens) if before else (0, 0)
        self._attempts.clear()
        started = time.monotonic()
        try:
            data = self.client.complete_json(model, system, user, schema=schema, max_tokens=1024)
        except Exception as exc:  # noqa: BLE001 - provider failure is recorded, never raised into mail handling
            return ModelReply(None, model, error=f"{type(exc).__name__}: {exc}"[:300],
                              latency_ms=int((time.monotonic() - started) * 1000))
        latency_ms = int((time.monotonic() - started) * 1000)
        error = "" if data is not None else "no_valid_json"
        if self._attempts:                       # measured: every paid attempt, real cost when the gateway reports it
            usages = [a["usage"] for a in self._attempts]
            costs = [u.get("cost") for u in usages]
            provider_cost = sum(float(c) for c in costs) if all(isinstance(c, (int, float)) for c in costs) else None
            tin = sum(int(u.get("prompt_tokens") or 0) for u in usages)
            tout = sum(int(u.get("completion_tokens") or 0) for u in usages)
            cached = sum(int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0) for u in usages)
            if provider_cost is not None:
                cost, source = provider_cost, "provider_reported"
            else:
                prices = self.client.catalog.prices(model)
                cost, source = tin * prices[0] + tout * prices[1], "catalog_estimate"
            return ModelReply(data, model, input_tokens=tin, output_tokens=tout, cost_rub=cost, cost_source=source,
                              latency_ms=latency_ms, error=error, cached_tokens=cached, retries=len(self._attempts) - 1,
                              endpoint=self._attempts[-1]["endpoint"])
        after = self.client.usage.get(model)     # fallback: difference of the client's per-model totals
        d_in = (after.input_tokens - b_in) if after else 0
        d_out = (after.output_tokens - b_out) if after else 0
        prices = self.client.catalog.prices(model)
        cost = d_in * prices[0] + d_out * prices[1]
        return ModelReply(data, model, input_tokens=d_in, output_tokens=d_out, cost_rub=cost,
                          cost_source="catalog_estimate" if prices != (0.0, 0.0) else "none",
                          latency_ms=latency_ms, error=error)


# --------------------------------------------------------------------------- repository mixin
class MessageAnalysisMixin:
    def _load_message(self, connection: Any, workspace_id: int, kind: str, message_id: int) -> dict[str, Any]:
        if kind == "mail_message":
            row = connection.execute(
                """SELECT id, request_id, supplier_id, from_email, subject, body_text,
                          (SELECT COUNT(*) FROM mail_attachments a WHERE a.message_id = mail_messages.id) AS attachment_count
                   FROM mail_messages WHERE id=? AND workspace_id=? AND direction='inbound'""", (message_id, workspace_id)).fetchone()
        elif kind == "inbox_message":
            row = connection.execute(
                """SELECT id, NULL AS request_id, NULL AS supplier_id, from_email, subject, body_text
                   FROM mail_inbox_messages WHERE id=? AND workspace_id=?""", (message_id, workspace_id)).fetchone()
        else:
            raise ValueError("Неизвестный тип сообщения.")
        if not row:
            raise ValueError("Входящее письмо не найдено в текущем рабочем пространстве.")
        return dict(row)

    def _log_run(self, connection: Any, *, workspace_id: int, analysis_id: int, reason: str, stage: str,
                 provider: str, status: str, chash: str, version: str, reply: ModelReply | None = None,
                 detail: str = "", error: str = "") -> None:
        repeat = 0
        if provider != "rules":
            repeat = 1 if connection.execute(
                """SELECT 1 FROM mail_ai_runs r JOIN mail_analyses a ON a.id=r.analysis_id
                   WHERE r.workspace_id=? AND r.content_hash=? AND r.provider<>'rules' AND r.status IN ('ok','invalid_output')
                     AND a.message_kind=(SELECT message_kind FROM mail_analyses WHERE id=?)
                     AND a.message_id=(SELECT message_id FROM mail_analyses WHERE id=?) AND r.analysis_version=? LIMIT 1""",
                (workspace_id, chash, analysis_id, analysis_id, version)).fetchone() else 0
        connection.execute(
            """INSERT INTO mail_ai_runs(workspace_id, analysis_id, reason, stage, provider, model, input_tokens,
                   output_tokens, cached_tokens, retries, endpoint, cost_rub, cost_source, latency_ms, status, error,
                   detail, content_hash, analysis_version, repeat_of_same_content, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (workspace_id, analysis_id, reason, stage, provider, reply.model if reply else "",
             reply.input_tokens if reply else 0, reply.output_tokens if reply else 0,
             reply.cached_tokens if reply else 0, reply.retries if reply else 0, reply.endpoint if reply else "",
             reply.cost_rub if reply else 0.0, reply.cost_source if reply else "none",
             reply.latency_ms if reply else 0, status, (error or (reply.error if reply else ""))[:300],
             detail[:300], chash, version, repeat, iso_now()))

    def _ai_spent_today(self, connection: Any, workspace_id: int) -> float:
        row = connection.execute(
            "SELECT COALESCE(SUM(cost_rub), 0) AS s FROM mail_ai_runs WHERE workspace_id=? AND created_at>=?",
            (workspace_id, iso_now()[:10])).fetchone()
        return float(row["s"] or 0.0)

    def mail_analysis_budget_rub(self) -> float:
        try:
            return float(os.getenv("MAIL_ANALYSIS_DAILY_BUDGET_RUB", "20") or 0)
        except ValueError:
            return 20.0

    def _analysis_view(self, connection: Any, analysis_id: int, *, cached: bool, ai_calls: int) -> dict[str, Any]:
        row = dict(connection.execute("SELECT * FROM mail_analyses WHERE id=?", (analysis_id,)).fetchone())
        facts = [dict(f) for f in connection.execute(
            "SELECT id, kind, position, data_json, source_quote, source_start, source_end, state FROM mail_facts "
            "WHERE analysis_id=? ORDER BY position", (analysis_id,)).fetchall()]
        for f in facts:
            f["data"] = json.loads(f.pop("data_json"))
        row.update(facts=facts, cached=cached, ai_calls=ai_calls,
                   candidates=json.loads(row.pop("candidates_json")), result=json.loads(row.pop("result_json")))
        return row

    def analyze_message(self, workspace_id: int, message_id: int, *, kind: str = "mail_message",
                        models: AnalysisModels | None = None, reprocess: bool = False) -> dict[str, Any]:
        """Analyse one incoming message; see the module docstring. Returns the stored analysis (with facts)
        plus `cached` and `ai_calls` (model calls made by THIS invocation)."""
        from .repository import _is_bulk_sender

        with self.connect() as connection:
            message = self._load_message(connection, workspace_id, kind, message_id)
            text = normalize_text(message["subject"], message["body_text"])
            chash, version = content_hash(text), ANALYSIS_VERSION

            existing = connection.execute(
                """SELECT * FROM mail_analyses WHERE workspace_id=? AND message_kind=? AND message_id=? AND content_hash=?
                   ORDER BY id DESC""", (workspace_id, kind, message_id, chash)).fetchall()
            same = next((dict(r) for r in existing if r["analysis_version"] == version), None)
            if same and same["status"] == "in_progress" and same["updated_at"] < _stale_before():
                # a worker died mid-analysis: make it claimable again (its model calls stay in the ledger)
                connection.execute("UPDATE mail_analyses SET status='pending_retry' WHERE id=? AND status='in_progress'", (same["id"],))
                same["status"] = "pending_retry"
            if same and same["status"] in ("final", "needs_review", "in_progress"):
                connection.execute("UPDATE mail_analyses SET reuse_count=reuse_count+1 WHERE id=?", (same["id"],))
                return self._analysis_view(connection, int(same["id"]), cached=True, ai_calls=0)
            if existing and not reprocess and not same:
                # analysed under another version: reuse it, a new version only runs on explicit reprocess
                old = existing[0]
                connection.execute("UPDATE mail_analyses SET reuse_count=reuse_count+1 WHERE id=?", (old["id"],))
                return self._analysis_view(connection, int(old["id"]), cached=True, ai_calls=0)

            # claim: the unique key makes two concurrent analyses of one message impossible
            now = iso_now()
            if same:  # pending_retry
                claimed = connection.execute(
                    "UPDATE mail_analyses SET status='in_progress', updated_at=? WHERE id=? AND status='pending_retry'",
                    (now, same["id"])).rowcount
                analysis_id = int(same["id"])
                if not claimed:
                    return self._analysis_view(connection, analysis_id, cached=True, ai_calls=0)
                attempts = int(same["attempts"])
            else:
                inserted = connection.execute(
                    """INSERT INTO mail_analyses(workspace_id, message_kind, message_id, content_hash, analysis_version,
                           status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'in_progress', ?, ?)
                       ON CONFLICT(workspace_id, message_kind, message_id, content_hash, analysis_version) DO NOTHING""",
                    (workspace_id, kind, message_id, chash, version, now, now)).rowcount
                row = connection.execute(
                    """SELECT id FROM mail_analyses WHERE workspace_id=? AND message_kind=? AND message_id=?
                       AND content_hash=? AND analysis_version=?""", (workspace_id, kind, message_id, chash, version)).fetchone()
                analysis_id, attempts = int(row["id"]), 0
                if not inserted:      # somebody else claimed it between our lookup and our insert
                    return self._analysis_view(connection, analysis_id, cached=True, ai_calls=0)
            connection.commit()

        outcome = {"status": "final", "stage": "rules", "message_type": "other", "is_relevant": 1, "review_reason": "",
                   "match_method": "", "request_id": None, "supplier_id": None, "candidates": [], "result": {}}
        facts: list[dict[str, Any]] = []
        ai_calls = 0
        reason = "reprocess" if reprocess and existing else "extract"

        with self.connect() as connection:
            # ---- exact rules first ------------------------------------------------------------------
            if classify_bounce(from_email=message["from_email"], subject=message["subject"], body_text=message["body_text"]) is not None:
                outcome.update(message_type="bounce", is_relevant=0, result={"rule": "bounce"})
                self._log_run(connection, workspace_id=workspace_id, analysis_id=analysis_id, reason="classify", stage="rules",
                              provider="rules", status="not_needed", chash=chash, version=version, detail="bounce")
            elif _is_bulk_sender(message["from_email"]) or (kind == "inbox_message" and looks_like_newsletter(text)):
                outcome.update(message_type="newsletter", is_relevant=0, result={"rule": "bulk_sender"})
                self._log_run(connection, workspace_id=workspace_id, analysis_id=analysis_id, reason="classify", stage="rules",
                              provider="rules", status="not_needed", chash=chash, version=version, detail="bulk_sender_or_unsubscribe")
            else:
                self._match_deterministically(connection, workspace_id, kind, message, outcome)
                # A letter that carries attachments and names no price in its own text: the offer is in the attachments (read by the
                # attachment pipeline), the body has nothing for a model to extract. Found by the real-mailbox E2E run.
                body_only_note = kind == "mail_message" and bool(message.get("attachment_count")) and not _PRICE_PATTERN.search(text)
                if body_only_note or not needs_extraction(text):
                    outcome["result"] = {"rule": "no_extractable_signal"}
                    self._log_run(connection, workspace_id=workspace_id, analysis_id=analysis_id, reason="classify", stage="rules",
                                  provider="rules", status="not_needed", chash=chash, version=version, detail="no_extractable_signal")
                else:
                    self._log_run(connection, workspace_id=workspace_id, analysis_id=analysis_id, reason="classify", stage="rules",
                                  provider="rules", status="ok", chash=chash, version=version, detail="extractable_signal")
            connection.commit()

        extract = outcome["message_type"] == "other" and not outcome["result"].get("rule")
        if extract:
            models = models or self._default_analysis_models()
            user_prompt = text[:MAX_TEXT_CHARS]
            validated: dict[str, Any] | None = None
            for stage in ("cheap", "strong"):
                if models is None or models.model_for(stage) is None:
                    if stage == "cheap":
                        outcome["review_reason"] = "no_model_configured"
                    break
                with self.connect() as connection:
                    if self._ai_spent_today(connection, workspace_id) >= self.mail_analysis_budget_rub():
                        self._log_run(connection, workspace_id=workspace_id, analysis_id=analysis_id, reason=reason, stage=stage,
                                      provider="rules", status="skipped_budget", chash=chash, version=version, detail="daily budget")
                        connection.commit()
                        outcome["review_reason"] = "budget_exhausted"
                        break
                reply = models.call(stage, SYSTEM_PROMPT, user_prompt, EXTRACTION_SCHEMA)
                ai_calls += 1
                verdict = validate_extraction(reply.data, text) if reply.data is not None else None
                run_reason = reason if stage == "cheap" else "extract_escalation"
                with self.connect() as connection:
                    if reply.error and reply.data is None and not reply.input_tokens and reply.error != "no_valid_json":
                        self._log_run(connection, workspace_id=workspace_id, analysis_id=analysis_id, reason=run_reason, stage=stage,
                                      provider=reply.provider, status="error", chash=chash, version=version, reply=reply)
                        connection.commit()
                        outcome["status"], outcome["stage"] = "pending_retry", stage
                        break
                    ok = bool(verdict and (verdict["ok"] or (stage == "strong" and verdict["facts"])))
                    self._log_run(connection, workspace_id=workspace_id, analysis_id=analysis_id, reason=run_reason, stage=stage,
                                  provider=reply.provider, status="ok" if ok else "invalid_output", chash=chash, version=version,
                                  reply=reply, detail=",".join(verdict["issues"]) if verdict else "invalid_json")
                    connection.commit()
                if ok:
                    validated = verdict
                    outcome["stage"] = stage
                    break
                outcome["stage"] = stage
                real_issues = [i for i in (verdict["issues"] if verdict else []) if i != "quote_without_valid_item"]
                if stage == "cheap" and real_issues and all(any(u in i for u in UNFIXABLE_ISSUES) for i in real_issues):
                    outcome["review_reason"] = "letter_lacks_information"     # do not pay a strong model for it
                    break
            if outcome["status"] == "pending_retry":
                pass
            elif validated is not None:
                outcome.update(message_type=validated["message_type"],
                               result={"issues": validated["issues"], "validated": True})
                facts = validated["facts"]
            else:
                outcome.update(status="needs_review", review_reason=outcome["review_reason"] or "extraction_failed_validation")

        if not outcome["is_relevant"]:
            pass                                    # bounce / newsletter: nothing to link, nothing to review
        elif outcome["status"] == "final" and outcome["match_method"] == "" and outcome["request_id"] is None:
            outcome["status"], outcome["review_reason"] = "needs_review", outcome["review_reason"] or "request_link_unknown"
        elif outcome["status"] == "final" and outcome["match_method"] == "candidates":
            outcome["status"], outcome["review_reason"] = "needs_review", "ambiguous_request_link"
        elif outcome["status"] == "final" and "price_mentioned_not_extracted" in (outcome["result"].get("issues") or []):
            outcome["status"], outcome["review_reason"] = "needs_review", "incomplete_extraction"
        elif outcome["status"] == "final" and outcome["match_method"] == "sd_label" and outcome["supplier_id"] is None:
            outcome["status"], outcome["review_reason"] = "needs_review", "supplier_unconfirmed"

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE") if not self.database_url else None
            attempts += 1 if outcome["status"] == "pending_retry" else 0
            if outcome["status"] == "pending_retry" and attempts >= MAX_ATTEMPTS:
                outcome.update(status="needs_review", review_reason="provider_errors_exhausted")
            # facts of an older version of the same message become superseded (kept for audit)
            if facts and reprocess:
                connection.execute(
                    """UPDATE mail_facts SET state='superseded' WHERE workspace_id=? AND message_kind=? AND message_id=?
                       AND analysis_id<>? AND state='proposed'""", (workspace_id, kind, message_id, analysis_id))
            now = iso_now()
            for f in facts:
                connection.execute(
                    """INSERT INTO mail_facts(workspace_id, analysis_id, message_kind, message_id, request_id, supplier_id, kind,
                           position, data_json, source_quote, source_start, source_end, state, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'quote_item', ?, ?, ?, ?, ?, 'proposed', ?)""",
                    (workspace_id, analysis_id, kind, message_id, outcome["request_id"], outcome["supplier_id"], f["position"],
                     json.dumps(f["data"], ensure_ascii=False), f["source_quote"], f["source_start"], f["source_end"], now))
            connection.execute(
                """UPDATE mail_analyses SET status=?, stage=?, message_type=?, is_relevant=?, match_method=?, request_id=?,
                       supplier_id=?, candidates_json=?, result_json=?, review_reason=?, attempts=?, updated_at=? WHERE id=?""",
                (outcome["status"], outcome["stage"], outcome["message_type"], outcome["is_relevant"], outcome["match_method"],
                 outcome["request_id"], outcome["supplier_id"], json.dumps(outcome["candidates"], ensure_ascii=False),
                 json.dumps(outcome["result"], ensure_ascii=False), outcome["review_reason"], attempts, now, analysis_id))
            if (outcome["status"] == "final" and outcome["message_type"] == "quote" and facts
                    and outcome["request_id"] and outcome["supplier_id"]):
                connection.execute(
                    """INSERT INTO mail_analysis_events(workspace_id, analysis_id, event_type, payload_json, created_at)
                       VALUES (?, ?, 'quote_received', ?, ?)
                       ON CONFLICT(analysis_id, event_type) DO NOTHING""",
                    (workspace_id, analysis_id, json.dumps({"request_id": outcome["request_id"], "supplier_id": outcome["supplier_id"],
                                                            "facts": len(facts)}), now))
            connection.commit()
            return self._analysis_view(connection, analysis_id, cached=False, ai_calls=ai_calls)

    def _default_analysis_models(self) -> AnalysisModels | None:
        if not os.getenv("ROUTERAI_KEY"):
            return None
        from backend.integrations.llm.routerai_client import RouterAiClient
        return RouterAiAnalysisModels(RouterAiClient())

    def _match_deterministically(self, connection: Any, workspace_id: int, kind: str, message: dict[str, Any],
                                 outcome: dict[str, Any]) -> None:
        """Existing exact rules only. A confirmed thread link is used as is; an unmatched inbox message is linked
        only by an explicit [SD-N] marker plus a sender that is a known supplier of that request; anything weaker is
        recorded as candidates for a human (never linked silently)."""
        if kind == "mail_message":
            outcome.update(match_method="thread", request_id=message["request_id"], supplier_id=message["supplier_id"])
            return
        sender = str(message["from_email"] or "").strip().lower()
        parsed = parse_request_reference_from_subject(message["subject"] or "")
        if parsed.status == "valid" and parsed.email_reference:
            request = connection.execute(
                """SELECT r.id FROM requests r JOIN request_email_references er ON er.request_id=r.id
                   WHERE r.workspace_id=? AND er.email_reference=?""", (workspace_id, parsed.email_reference)).fetchone()
            if request:
                supplier = connection.execute(
                    """SELECT rs.supplier_id FROM request_suppliers rs JOIN suppliers s ON s.id=rs.supplier_id
                       WHERE rs.request_id=? AND s.workspace_id=? AND LOWER(s.email)=?""",
                    (request["id"], workspace_id, sender)).fetchall()
                if len(supplier) == 1:
                    outcome.update(match_method="sd_label", request_id=int(request["id"]), supplier_id=int(supplier[0]["supplier_id"]))
                    return
                # the marker names the request exactly, but the sender is not a known supplier of it: the REQUEST is
                # known, linking the SUPPLIER needs a human (evidence), so no downstream action fires
                outcome.update(match_method="sd_label", request_id=int(request["id"]), supplier_id=None)
                return
        candidates = self.suggest_requests_for_inbox(workspace_id, int(message["id"]))
        outcome["candidates"] = candidates[:5]
        outcome["match_method"] = "candidates" if candidates else ""
        outcome["review_reason"] = "" if candidates else "unknown_sender"

    # ------------------------------------------------------------------ downstream (no model calls)
    def process_analysis_events(self, workspace_id: int) -> dict[str, int]:
        """Act on analysis events. quote_received -> close the open default follow-up task(s) of that supplier in
        that request (the awaited quote has arrived). Each event is handled at most once."""
        handled = closed = 0
        with self.connect() as connection:
            events = connection.execute(
                """SELECT id, analysis_id, payload_json FROM mail_analysis_events
                   WHERE workspace_id=? AND handled_at IS NULL AND event_type='quote_received' ORDER BY id""",
                (workspace_id,)).fetchall()
            for ev in events:
                payload = json.loads(ev["payload_json"])
                link = connection.execute(
                    """SELECT gl.global_supplier_id FROM global_supplier_links gl JOIN suppliers s ON s.id=gl.supplier_id
                       WHERE s.id=? AND s.workspace_id=?""", (payload["supplier_id"], workspace_id)).fetchone()
                task_ids: list[int] = []
                if link:
                    rows = connection.execute(
                        """SELECT id FROM tasks WHERE workspace_id=? AND request_id=? AND supplier_id=? AND title=? AND done=0""",
                        (workspace_id, payload["request_id"], link["global_supplier_id"], FOLLOWUP_TASK_TITLE)).fetchall()
                    task_ids = [int(r["id"]) for r in rows]
                now = iso_now()
                for tid in task_ids:
                    connection.execute("UPDATE tasks SET done=1, completed_at=?, updated_at=? WHERE id=? AND done=0", (now, now, tid))
                connection.execute(
                    "UPDATE mail_analysis_events SET handled_at=?, handler_result=? WHERE id=? AND handled_at IS NULL",
                    (now, json.dumps({"tasks_completed": task_ids}), ev["id"]))
                handled += 1
                closed += len(task_ids)
            connection.commit()
        return {"events_handled": handled, "tasks_closed": closed}

    # ------------------------------------------------------------------ measurement
    def mail_ai_cost_report(self, workspace_id: int) -> dict[str, Any]:
        """Cost KPIs straight from the ledger (Cost plan section 5)."""
        with self.connect() as connection:
            analyses = int(connection.execute("SELECT COUNT(*) AS n FROM mail_analyses WHERE workspace_id=?", (workspace_id,)).fetchone()["n"])
            ai = connection.execute(
                """SELECT COUNT(*) AS calls, COALESCE(SUM(cost_rub),0) AS cost, COALESCE(SUM(input_tokens),0) AS tin,
                          COALESCE(SUM(output_tokens),0) AS tout, COALESCE(SUM(repeat_of_same_content),0) AS repeats,
                          COALESCE(SUM(CASE WHEN stage='strong' THEN 1 ELSE 0 END),0) AS strong
                   FROM mail_ai_runs WHERE workspace_id=? AND provider<>'rules'""", (workspace_id,)).fetchone()
            analysed_by_ai = int(connection.execute(
                """SELECT COUNT(DISTINCT analysis_id) AS n FROM mail_ai_runs WHERE workspace_id=? AND provider<>'rules'""",
                (workspace_id,)).fetchone()["n"])
        return {"messages_analysed": analyses, "ai_calls": int(ai["calls"]), "ai_analysed_messages": analysed_by_ai,
                "ai_call_ratio": (analysed_by_ai / analyses) if analyses else 0.0, "cost_rub": float(ai["cost"]),
                "input_tokens": int(ai["tin"]), "output_tokens": int(ai["tout"]),
                "cost_per_received_email": (float(ai["cost"]) / analyses) if analyses else 0.0,
                "cost_per_ai_analysed_email": (float(ai["cost"]) / analysed_by_ai) if analysed_by_ai else 0.0,
                "strong_escalations": int(ai["strong"]), "duplicate_reprocessing_calls": int(ai["repeats"])}
