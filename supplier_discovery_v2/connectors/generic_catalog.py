from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup

from ..connectors.base import Connector
from ..http_client import ReadOnlyHttpClient
from ..matching import qualify_candidate
from ..models import OfferCandidate, PositionSpec, QueryVariant


@dataclass(frozen=True)
class CatalogConfig:
    name: str
    base_url: str
    search_template: str


CATALOGS = [
    CatalogConfig("productcenter", "https://productcenter.ru", "/search/?q={query}"),
    CatalogConfig("promportal", "https://promportal.su", "/?s={query}"),
    CatalogConfig("optomtovar", "https://www.optomtovar.ru", "/search?q={query}"),
    CatalogConfig("all-biz", "https://all.biz", "/search/goods?q={query}"),
    CatalogConfig("postavshikov", "https://postavshikov.net", "/marketplace?s={query}"),
]


def _same_origin(url: str, base: str) -> bool:
    return (urlparse(url).hostname or "").casefold().lstrip("www.") == (urlparse(base).hostname or "").casefold().lstrip("www.")


class GenericCatalogConnector(Connector):
    def __init__(self, config: CatalogConfig, client: ReadOnlyHttpClient):
        self.config = config
        self.name = config.name
        self.domain = urlparse(config.base_url).hostname or ""
        self.client = client

    def _product_links(self, html: str, page_url: str, limit: int) -> list[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = urljoin(page_url, anchor.get("href", ""))
            path = urlparse(href).path.casefold()
            if not _same_origin(href, self.config.base_url):
                continue
            if not any(marker in path for marker in ("product", "tovar", "catalog", "goods", "item", "offer")):
                continue
            if href not in links:
                links.append(href)
            if len(links) >= limit:
                break
        return links

    def discover(self, position: PositionSpec, query: QueryVariant, limit: int = 3) -> list[OfferCandidate]:
        search_url = self.config.base_url.rstrip("/") + self.config.search_template.format(query=quote_plus(query.query))
        search = self.client.get(search_url)
        if not search.html:
            return []
        soup = BeautifulSoup(search.html, "html.parser")
        search_text = " ".join(soup.stripped_strings)
        links = self._product_links(search.html, search.final_url, limit)
        offers: list[OfferCandidate] = []
        for url in links:
            page = self.client.get(url)
            if not page.html:
                continue
            detail = BeautifulSoup(page.html, "html.parser")
            title = (detail.title.get_text(" ", strip=True) if detail.title else "")[:240]
            snippet = " ".join(detail.stripped_strings)[:800]
            offer = qualify_candidate(position, self.name, page.final_url, title, snippet or search_text[:800], page.html, [search.final_url], self.domain)
            offer.metadata.update({"search_url": search_url, "http_status": page.status_code})
            offers.append(offer)
        return offers
