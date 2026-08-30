from __future__ import annotations

from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from .base import Connector
from ..contacts import BUYER_MARKERS
from ..http_client import ReadOnlyHttpClient
from ..matching import qualify_candidate
from ..models import OfferCandidate, PositionSpec, QueryVariant


class FlagmaConnector(Connector):
    name = "flagma"
    domain = "flagma.ru"

    def __init__(self, client: ReadOnlyHttpClient):
        self.client = client

    def _links(self, html: str, page_url: str, limit: int) -> list[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = urljoin(page_url, anchor.get("href", ""))
            path = urlparse(href).path.casefold()
            context = " ".join(anchor.parent.stripped_strings)[:500] if anchor.parent else anchor.get_text(" ", strip=True)
            if "flagma.ru" not in (urlparse(href).hostname or "").casefold() or "/products/" not in path:
                continue
            if any(marker in context.casefold() for marker in BUYER_MARKERS):
                continue
            if href not in links:
                links.append(href)
            if len(links) >= limit:
                break
        return links

    def discover(self, position: PositionSpec, query: QueryVariant, limit: int = 3) -> list[OfferCandidate]:
        search_url = f"https://flagma.ru/search/?q={quote_plus(query.query)}"
        search = self.client.get(search_url)
        if not search.html:
            return []
        offers: list[OfferCandidate] = []
        for url in self._links(search.html, search.final_url, limit):
            page = self.client.get(url)
            if not page.html:
                continue
            soup = BeautifulSoup(page.html, "html.parser")
            title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:240]
            snippet = " ".join(soup.stripped_strings)[:1000]
            offer = qualify_candidate(position, self.name, page.final_url, title, snippet, page.html, [search.final_url], self.domain)
            offer.metadata.update({"search_url": search_url, "http_status": page.status_code})
            offers.append(offer)
        return offers
