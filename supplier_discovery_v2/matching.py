from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .contacts import classify_role, extract_contacts, prioritize_contacts
from .models import ContactCandidate, OfferCandidate, PositionSpec, SellerCandidate
from .query_planner import normalize_text


def _tokens(text: str) -> set[str]:
    return {x.casefold() for x in re.findall(r"[a-zа-яё0-9][a-zа-яё0-9().,/_+-]*", normalize_text(text), re.I) if len(x) > 1}


def match_product(position: PositionSpec, title: str, snippet: str = "") -> tuple[str, float, list[str]]:
    target = _tokens(position.product)
    observed = _tokens(f"{title} {snippet}")
    if not target:
        return "unknown", 0.0, ["empty_target"]
    overlap = len(target & observed) / len(target)
    numbers = set(re.findall(r"\d+(?:[.,]\d+)?", normalize_text(position.product)))
    observed_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", normalize_text(f"{title} {snippet}")))
    number_match = bool(numbers and numbers <= observed_numbers)
    technical = {token for token in target if re.search(r"(ввг|аввг|пвс|сип|нг|fr|ls|гост|мкэ|кв)", token, re.I) or any(char.isdigit() for char in token)}
    missing_technical = [token for token in technical if not any(token in observed_token or observed_token in token for observed_token in observed)]
    if missing_technical:
        return "near_match", round(overlap, 3), ["critical_specification_missing:" + ",".join(sorted(missing_technical))]
    if overlap >= 0.8 and (not numbers or number_match):
        return "exact_match", min(1.0, 0.72 + overlap * 0.18 + (0.1 if number_match else 0)), ["token_overlap", "specification_numbers_match" if number_match else "no_numeric_spec"]
    if overlap >= 0.55:
        return "acceptable_analog", round(overlap, 3), ["partial_token_overlap"]
    if overlap >= 0.25:
        return "near_match", round(overlap, 3), ["weak_token_overlap"]
    return "unrelated", round(overlap, 3), ["insufficient_token_overlap"]


def _seller_name(text: str, fallback_url: str) -> str:
    soup = BeautifulSoup(text or "", "html.parser")
    meta = soup.find("meta", attrs={"property": "og:site_name"})
    if meta and meta.get("content"):
        return " ".join(str(meta["content"]).split())[:180]
    lines = [" ".join(line.split()) for line in soup.stripped_strings if line.strip()]
    for line in lines[:20]:
        if re.search(r"^(?:ооо|оао|зао|ао|ип\b|пао)\b", line.casefold()) or "название компании" in line.casefold():
            return line[:180]
    return urlparse(fallback_url).hostname or "unknown seller"


def qualify_candidate(position: PositionSpec, source: str, url: str, title: str, snippet: str, html: str, evidence_urls: list[str], platform_domain: str | None = None, contacts_override: list[ContactCandidate] | None = None) -> OfferCandidate:
    text = f"{title}\n{snippet}\n{html}"
    role, role_reasons = classify_role(f"{title}\n{snippet}", url)
    if role == "unknown":
        role, role_reasons = classify_role(text, url)
    match_class, score, match_reasons = match_product(position, title, snippet)
    contacts = contacts_override if contacts_override is not None else extract_contacts(html, url, platform_domain)
    valid_contacts = prioritize_contacts(contacts, position.region)
    reasons = role_reasons + match_reasons
    if role == "buyer_request":
        reasons.append("buyer_request")
    if not valid_contacts:
        reasons.append("no_public_seller_contact")
    if match_class in {"unrelated", "near_match"}:
        reasons.append("match_below_acceptable_threshold")
    status = "qualified" if role in {"seller_offer", "manufacturer"} and match_class in {"exact_match", "acceptable_analog"} and valid_contacts else "unqualified"
    seller = SellerCandidate(
        seller_key=urlparse(url).netloc.casefold(),
        name=_seller_name(html, url),
        source=source,
        source_url=url,
        role=role,
        match_class=match_class,
        match_score=score,
        contacts=valid_contacts,
        evidence_urls=list(dict.fromkeys([url, *evidence_urls])),
        status=status,
        reasons=list(dict.fromkeys(reasons)),
    )
    return OfferCandidate(position.position_key, source, url, title, snippet, role, match_class, score, seller, valid_contacts, seller.evidence_urls, status, seller.reasons)
