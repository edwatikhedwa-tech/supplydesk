from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from urllib.robotparser import RobotFileParser


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    html: str
    error: str = ""


class ReadOnlyHttpClient:
    def __init__(self, timeout: float = 15.0, delay: float = 0.15, user_agent: str = "SupplyDeskSupplierDiscovery/0.1 (+read-only)"):
        self.timeout = timeout
        self.delay = max(0.0, delay)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "ru,en;q=0.7"})
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last_request = 0.0

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            try:
                response = self.session.get(origin + "/robots.txt", timeout=min(self.timeout, 5.0), allow_redirects=True)
                if response.ok:
                    parser.set_url(origin + "/robots.txt")
                    parser.parse(response.text.splitlines())
                else:
                    parser = None
                self._robots[origin] = parser
            except requests.RequestException:
                self._robots[origin] = None
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(self.session.headers["User-Agent"], url)

    def get(self, url: str) -> FetchResult:
        if not self.allowed(url):
            return FetchResult(url, url, 0, "", "blocked_by_robots_or_scheme")
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            self._last_request = time.monotonic()
            return FetchResult(url, response.url, response.status_code, response.text if response.ok else "", "" if response.ok else f"http_{response.status_code}")
        except requests.RequestException as exc:
            self._last_request = time.monotonic()
            return FetchResult(url, url, 0, "", type(exc).__name__)
