from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import ContactCandidate


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+7|8)\s*[\-(]?\s*\d{3}\s*[)\-]?\s*\d{3}\s*[\-\s]?\d{2}\s*[\-\s]?\d{2}(?!\d)")
BUYER_MARKERS = ("купим", "ищу поставщика", "ищем поставщика", "требуется", "заявка на закупку", "заказчик", "нужен поставщик", "запрос цены")
SELLER_MARKERS = ("купить", "продажа", "поставщик", "производитель", "в наличии", "цена", "опт", "доставка", "каталог", "наша компания")
PLATFORM_EMAIL_DOMAINS = {"flagma.ru", "supl.biz", "all.biz", "productcenter.ru", "promportal.su", "postavshiki.com", "postavshikov.net"}


def clean_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return f"+{digits}" if digits else value.strip()


def _context(text: str, value: str, radius: int = 180) -> str:
    idx = text.casefold().find(value.casefold())
    if idx < 0:
        return text[:radius].strip()
    return " ".join(text[max(0, idx - radius // 2):idx + len(value) + radius // 2].split())


def is_platform_owned(value: str, page_url: str, platform_domain: str | None = None) -> bool:
    if "@" in value:
        domain = value.rsplit("@", 1)[1].casefold().strip()
        return domain in PLATFORM_EMAIL_DOMAINS or (platform_domain and domain == platform_domain.casefold())
    host = (urlparse(page_url).hostname or "").casefold()
    return any(domain in host for domain in PLATFORM_EMAIL_DOMAINS if domain != platform_domain)


def extract_contacts(html: str, source_url: str, platform_domain: str | None = None) -> list[ContactCandidate]:
    soup = BeautifulSoup(html or "", "html.parser")
    text = " ".join(soup.stripped_strings)
    found: list[ContactCandidate] = []
    seen: set[tuple[str, str]] = set()
    for raw in EMAIL_RE.findall(text):
        value = raw.strip().lower()
        key = ("email", value)
        if key in seen:
            continue
        seen.add(key)
        platform = is_platform_owned(value, source_url, platform_domain)
        context = _context(text, value)
        confidence = 0.25 if platform else 0.9
        if any(marker in context.casefold() for marker in SELLER_MARKERS):
            confidence = min(1.0, confidence + 0.08)
        found.append(ContactCandidate("email", value, confidence, source_url, context, not platform, platform, "rejected" if platform else "candidate", ["platform_owned"] if platform else []))
    for raw in PHONE_RE.findall(text):
        value = clean_phone(raw)
        key = ("phone", value)
        if key in seen:
            continue
        seen.add(key)
        context = _context(text, raw)
        platform = is_platform_owned(value, source_url, platform_domain)
        confidence = 0.82 if not platform else 0.2
        if any(marker in context.casefold() for marker in SELLER_MARKERS):
            confidence = min(1.0, confidence + 0.1)
        found.append(ContactCandidate("phone", value, confidence, source_url, context, not platform, platform, "rejected" if platform else "candidate", ["platform_owned"] if platform else []))
    return found


def prioritize_contacts(contacts: list[ContactCandidate], preferred_region: str | None = None, max_contacts: int = 5) -> list[ContactCandidate]:
    """Keep a small, application-ready contact set instead of a regional phone directory."""
    region = (preferred_region or "").casefold().strip()

    def rank(contact: ContactCandidate) -> tuple[float, float]:
        context = contact.context.casefold()
        contact_digits = re.sub(r"\D", "", contact.value)
        phone_tail = contact_digits[-4:] if len(contact_digits) >= 4 else contact_digits
        phone_tail_pattern = r"\D*".join(re.escape(char) for char in phone_tail)
        region_hit = 1.0 if region and phone_tail and re.search(rf"\b{re.escape(region)}\b.{{0,120}}{phone_tail_pattern}", context) else 0.0
        label_hit = 1.0 if any(marker in context for marker in ("отдел продаж", "заказать звонок", "контакт", "телефон", "email", "почта")) else 0.0
        branch_penalty = 0.35 if "бесплатно для регионов" in context and contact.kind == "phone" else 0.0
        freephone_bonus = 0.3 if contact.kind == "phone" and contact.value.startswith("+7800") else 0.0
        return (region_hit + label_hit + freephone_bonus - branch_penalty, contact.confidence)

    def has_region_phone(contact: ContactCandidate) -> bool:
        digits = re.sub(r"\D", "", contact.value)
        tail = digits[-4:] if len(digits) >= 4 else digits
        tail_pattern = r"\D*".join(re.escape(char) for char in tail)
        return bool(region and tail and re.search(rf"\b{re.escape(region)}\b.{{0,120}}{tail_pattern}", contact.context.casefold()))

    unique: dict[tuple[str, str], ContactCandidate] = {}
    for contact in contacts:
        if not contact.is_public or contact.is_platform_owned or contact.status == "rejected":
            continue
        key = (contact.kind, contact.value)
        if key not in unique or rank(contact) > rank(unique[key]):
            unique[key] = contact
    public = list(unique.values())
    emails = sorted((contact for contact in public if contact.kind == "email"), key=rank, reverse=True)[:2]
    all_phones = [contact for contact in public if contact.kind == "phone"]
    regional_phones = [contact for contact in all_phones if has_region_phone(contact)]
    if regional_phones:
        phone_pool = regional_phones + [contact for contact in all_phones if contact.value.startswith("+7800")]
    else:
        phone_pool = all_phones
    phones = sorted(phone_pool, key=rank, reverse=True)[:2]
    return (emails + phones)[:max_contacts]


def classify_role(text: str, url: str = "") -> tuple[str, list[str]]:
    haystack = f"{text} {url}".casefold()
    buyer_hits = [marker for marker in BUYER_MARKERS if marker in haystack]
    seller_hits = [marker for marker in SELLER_MARKERS if marker in haystack]
    strong_buyer = ("купим", "требуется", "заявка на закупку", "ищу поставщика", "ищем поставщика", "нужен поставщик")
    if any(marker in haystack[:900] for marker in strong_buyer) or buyer_hits and len(buyer_hits) >= max(1, len(seller_hits) // 2):
        return "buyer_request", buyer_hits
    if seller_hits:
        return "seller_offer", seller_hits
    return "unknown", []
