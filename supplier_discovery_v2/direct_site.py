from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .contacts import classify_role, extract_contacts, prioritize_contacts
from .http_client import ReadOnlyHttpClient
from .matching import qualify_candidate
from .models import DiscoveryResult, OfferCandidate, PositionSpec


CONTACT_PATH_MARKERS = ("contact", "kontak", "rekviz", "about", "o-komp", "company")


def _same_origin(left: str, right: str) -> bool:
    return (urlparse(left).hostname or "").casefold().lstrip("www.") == (urlparse(right).hostname or "").casefold().lstrip("www.")


class DirectSiteAdapter:
    name = "direct_site"

    def __init__(self, client: ReadOnlyHttpClient):
        self.client = client

    def _contact_links(self, html: str, base_url: str, limit: int = 4) -> list[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = urljoin(base_url, anchor.get("href", ""))
            label = f"{anchor.get_text(' ', strip=True)} {urlparse(href).path}".casefold()
            if _same_origin(href, base_url) and any(marker in label for marker in CONTACT_PATH_MARKERS) and href not in links:
                links.append(href)
            if len(links) >= limit:
                break
        return links

    def enrich(self, position: PositionSpec, result: DiscoveryResult) -> OfferCandidate | None:
        landing = self.client.get(result.url)
        if not landing.html:
            return None
        soup = BeautifulSoup(landing.html, "html.parser")
        title = result.title or (soup.title.get_text(" ", strip=True) if soup.title else "")[:240]
        snippet = result.snippet or " ".join(soup.stripped_strings)[:800]
        role, _ = classify_role(f"{title} {snippet}", result.url)
        pages = [landing]
        for link in self._contact_links(landing.html, landing.final_url):
            page = self.client.get(link)
            if page.html:
                pages.append(page)
        combined_html = "\n".join(page.html for page in pages)
        contacts = prioritize_contacts([contact for page in pages for contact in extract_contacts(page.html, page.final_url)], position.region)
        offer = qualify_candidate(position, self.name, landing.final_url, title, snippet, combined_html, [page.final_url for page in pages], contacts_override=contacts)
        offer.metadata.update({"landing_url": result.url, "contact_pages_checked": [page.final_url for page in pages[1:]], "initial_role": role})
        return offer
