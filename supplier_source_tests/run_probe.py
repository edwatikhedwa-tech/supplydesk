"""Безопасный smoke-тест источников поставщиков.

Тест делает только GET к публичным страницам и один POST к публичному Tonzar
MCP, который по документации является поисковым JSON-RPC интерфейсом. Никаких
логинов, открытий контактов, отправок заявок или обхода ограничений нет.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from sources import SOURCE_BY_ROOT, SOURCES, Source


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"
TEST_KEYWORD = "кабель ВВГнг 3х2.5"
SERP_QUERY = f"{TEST_KEYWORD} купить оптом поставщик"
USER_AGENT = "SupplierSourceTest/1.0 (+read-only public catalog probe)"
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+7|8)\s*[\(\-]?\d{3}[\)\-\s]?\s*\d{3}[\-\s]?\d{2}[\-\s]?\d{2}")
SEARCH_NAMES = {"q", "s", "words", "query", "search", "keyword", "term", "text", "searchtext", "search_query"}
SKIP_ACTION_WORDS = ("login", "register", "signup", "upload", "feedback", "contact", "cart", "order")
SUPPLIER_MARKERS = ("поставщик", "производител", "оптов", "компани", "товар", "предлага", "завод", "заявка", "купим", "продам", "цена", "наличи")
BUYER_MARKERS = ("купим", "ищу", "ищем", "нужен", "нужна", "нужно", "требуется", "заявка", "заказчик")
SELLER_MARKERS = ("поставщик", "производител", "продавец", "продам", "прода", "склад", "предлага", "завод")
PRODUCT_TOKENS = ("ввгнг", "ввг нг", "ввг", "3х2", "3х25", "3х2.5")
DETAIL_SOURCE_SLUGS = {"productcenter", "promportal", "postavshikov", "optomtovar", "all-biz", "firstprice", "flagma"}
POST_SEARCH_ONLY_SLUGS = {"catalogvn"}
DETAIL_PATH_MARKERS = {
    "productcenter": ("/product", "/producer", "/proizvod"),
    "promportal": ("/product", "/tovar", "/goods"),
    "postavshikov": ("/product", "/tovar", "/goods", "/marketplace/"),
    "optomtovar": ("/product", "/tovar", "/goods", "/catalog/"),
    "all-biz": ("/g", "-g", "/product", "/goods"),
    "firstprice": ("/product/",),
    "flagma": ("/products/",),
}


@dataclass
class SourceProbe:
    slug: str
    name: str
    url: str
    expected_mode: str
    http_status: int | None = None
    final_url: str = ""
    title: str = ""
    robots: str = "unknown"
    analysis_scope: str = "none"
    search_form: str = "not_detected"
    search_url: str = ""
    search_status: int | None = None
    keyword_hits: int = 0
    supplier_marker_hits: int = 0
    internal_links: int = 0
    public_emails: int = 0
    public_phones: int = 0
    contact_candidates: list[dict[str, str]] | None = None
    detail_urls_checked: list[str] | None = None
    sample_labels: list[str] | None = None
    error: str = ""

    def __post_init__(self) -> None:
        if self.sample_labels is None:
            self.sample_labels = []
        if self.contact_candidates is None:
            self.contact_candidates = []
        if self.detail_urls_checked is None:
            self.detail_urls_checked = []


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def root_of(url: str) -> str:
    host = urlsplit(url).netloc.lower().split(":", 1)[0]
    return host.removeprefix("www.")


def safe_text(soup: BeautifulSoup) -> str:
    return " ".join(soup.get_text(" ", strip=True).split())


def check_robots(session: requests.Session, source: Source) -> tuple[str, RobotFileParser | None]:
    robots_url = urljoin(source.url, "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = session.get(robots_url, timeout=10)
        if response.status_code >= 400:
            return "unavailable", None
        parser.parse(response.text.splitlines())
        allowed = parser.can_fetch(USER_AGENT, source.url)
        return ("allowed" if allowed else "disallowed"), parser
    except requests.RequestException:
        return "unavailable", None


def pick_get_search_form(soup: BeautifulSoup, source: Source) -> tuple[str, str] | None:
    source_root = root_of(source.url)
    for form in soup.find_all("form"):
        method = (form.get("method") or "get").lower()
        if method != "get":
            continue
        action = urljoin(source.url, form.get("action") or source.url)
        if root_of(action) != source_root:
            continue
        if any(word in action.lower() for word in SKIP_ACTION_WORDS):
            continue
        candidate = None
        for control in form.find_all(["input", "textarea"]):
            name = (control.get("name") or "").strip().lower()
            input_type = (control.get("type") or "").lower()
            if input_type in {"hidden", "radio", "checkbox", "submit", "button", "file"}:
                continue
            placeholder = (control.get("placeholder") or "").lower()
            if input_type == "search" or name in SEARCH_NAMES or any(len(token) >= 3 and token in name for token in SEARCH_NAMES) or "поиск" in placeholder or "найти" in placeholder:
                candidate = name or "q"
                break
        if candidate:
            return action, candidate
    return None


def build_search_url(action: str, field: str) -> str:
    parts = urlsplit(action)
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != field.lower()]
    params.append((field, TEST_KEYWORD))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def is_buyer_only_context(context_lower: str) -> bool:
    return any(marker in context_lower for marker in BUYER_MARKERS) and not any(marker in context_lower for marker in SELLER_MARKERS)


def extract_contact_candidates(response: requests.Response, require_supplier_marker: bool) -> list[dict[str, str]]:
    soup = BeautifulSoup(response.text, "html.parser")
    plain = safe_text(soup)
    candidates: list[dict[str, str]] = []
    all_matches = list(EMAIL_RE.finditer(plain)) + list(PHONE_RE.finditer(plain))
    for match in sorted(all_matches, key=lambda item: item.start()):
        start = max(0, match.start() - 180)
        end = min(len(plain), match.end() + 180)
        context = " ".join(plain[start:end].split())
        context_lower = context.lower()
        if not any(token in context_lower for token in PRODUCT_TOKENS):
            continue
        if is_buyer_only_context(context_lower):
            continue
        if require_supplier_marker and not any(marker in context_lower for marker in SUPPLIER_MARKERS):
            continue
        value = match.group(0)
        if "@" in value:
            email_domain = value.rsplit("@", 1)[1].lower().removeprefix("www.")
            if email_domain == root_of(response.url):
                continue
        if any(item["value"] == value for item in candidates):
            continue
        candidates.append({"value": value, "context": context[:420], "source_url": response.url})
        if len(candidates) >= 20:
            break
    return candidates


def merge_contact_candidates(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            value = item.get("value", "")
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(item)
    return merged[:20]


def find_detail_urls(source: Source, response: requests.Response) -> list[str]:
    if source.slug not in DETAIL_SOURCE_SLUGS:
        return []
    source_root = root_of(source.url)
    path_markers = DETAIL_PATH_MARKERS.get(source.slug, ())
    urls: list[str] = []
    seen: set[str] = set()
    for link in BeautifulSoup(response.text, "html.parser").find_all("a", href=True):
        href = urljoin(response.url, link["href"])
        parts = urlsplit(href)
        if parts.scheme not in {"http", "https"} or root_of(href) != source_root:
            continue
        path = parts.path.lower()
        label = " ".join(link.get_text(" ", strip=True).split()).lower()
        searchable = f"{path} {label}"
        if not any(marker in path for marker in path_markers):
            continue
        if not any(token in searchable for token in PRODUCT_TOKENS):
            continue
        if any(marker in searchable for marker in BUYER_MARKERS) and not any(marker in searchable for marker in SELLER_MARKERS):
            continue
        clean = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
        if clean in seen:
            continue
        seen.add(clean)
        urls.append(clean)
        if len(urls) >= 3:
            break
    return urls


def enrich_from_detail_pages(session: requests.Session, source: Source, result: requests.Response, probe: SourceProbe, robots: RobotFileParser | None) -> None:
    detail_urls = find_detail_urls(source, result)
    probe.detail_urls_checked = detail_urls
    detail_candidates: list[dict[str, str]] = []
    for detail_url in detail_urls:
        if robots is not None and not robots.can_fetch(USER_AGENT, detail_url):
            continue
        try:
            detail = session.get(detail_url, timeout=15, allow_redirects=True)
            if detail.status_code < 400 and "text/html" in detail.headers.get("content-type", "text/html"):
                detail_candidates.extend(extract_contact_candidates(detail, require_supplier_marker=False))
        except requests.RequestException:
            continue
    probe.contact_candidates = merge_contact_candidates(probe.contact_candidates or [], detail_candidates)
    probe.public_emails = sum(1 for item in probe.contact_candidates if "@" in item["value"])
    probe.public_phones = sum(1 for item in probe.contact_candidates if "@" not in item["value"])


def analyze_result(source: Source, probe: SourceProbe, response: requests.Response, scope: str) -> None:
    probe.analysis_scope = scope
    soup = BeautifulSoup(response.text, "html.parser")
    text = safe_text(soup).lower()
    keyword_tokens = [token for token in re.findall(r"[\wА-Яа-яЁё]+", TEST_KEYWORD.lower()) if len(token) > 2]
    probe.keyword_hits = sum(text.count(token) for token in keyword_tokens)
    probe.supplier_marker_hits = sum(text.count(marker) for marker in SUPPLIER_MARKERS)
    source_root = root_of(source.url)
    probe.internal_links = sum(1 for link in soup.find_all("a", href=True) if root_of(urljoin(response.url, link["href"])) == source_root)
    if scope == "search":
        # Flagma mixes seller offers and buyer requests in one search page;
        # use product-card pages for contacts so a buyer's phone is not routed
        # to a supplier lead.
        candidates = [] if source.slug == "flagma" else extract_contact_candidates(response, require_supplier_marker=True)
        probe.contact_candidates = candidates
        probe.public_emails = sum(1 for item in candidates if "@" in item["value"])
        probe.public_phones = sum(1 for item in candidates if "@" not in item["value"])
    labels: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "title"]):
        label = " ".join(element.get_text(" ", strip=True).split())
        if label and label not in labels:
            labels.append(label[:160])
        if len(labels) >= 8:
            break
    probe.sample_labels = labels


def probe_source(session: requests.Session, source: Source, dry_run: bool) -> SourceProbe:
    probe = SourceProbe(source.slug, source.name, source.url, source.expected_mode)
    if dry_run:
        probe.error = "dry-run: network request skipped"
        return probe
    try:
        probe.robots, robots = check_robots(session, source)
        response = session.get(source.url, timeout=20, allow_redirects=True)
        probe.http_status = response.status_code
        probe.final_url = response.url
        soup = BeautifulSoup(response.text, "html.parser")
        probe.title = " ".join((soup.title.get_text(" ", strip=True) if soup.title else "").split())[:200]
        if response.status_code >= 400:
            probe.error = f"homepage HTTP {response.status_code}"
            return probe
        if source.slug in POST_SEARCH_ONLY_SLUGS:
            probe.search_form = "POST:not_tested"
            analyze_result(source, probe, response, "homepage")
            return probe
        form = pick_get_search_form(soup, source)
        if not form:
            probe.search_form = "not_detected"
            analyze_result(source, probe, response, "homepage")
            return probe
        action, field = form
        probe.search_form = f"GET:{field}"
        probe.search_url = build_search_url(action, field)
        if robots is not None and not robots.can_fetch(USER_AGENT, probe.search_url):
            probe.search_form = "GET:blocked_by_robots"
            analyze_result(source, probe, response, "homepage")
            return probe
        result = session.get(probe.search_url, timeout=20, allow_redirects=True)
        probe.search_status = result.status_code
        if result.status_code < 400 and "text/html" in result.headers.get("content-type", "text/html"):
            analyze_result(source, probe, result, "search")
            enrich_from_detail_pages(session, source, result, probe, robots)
        else:
            probe.error = f"search HTTP {result.status_code}"
        return probe
    except requests.RequestException as exc:
        probe.error = f"network: {type(exc).__name__}"
        return probe
    except Exception as exc:  # pragma: no cover - defensive boundary for one external site
        probe.error = f"probe: {type(exc).__name__}"
        return probe


def xmlriver_probe(dry_run: bool) -> dict[str, object]:
    result: dict[str, object] = {"status": "not_run", "query": SERP_QUERY, "docs": 0, "matched_sources": []}
    if dry_run:
        result["status"] = "dry_run"
        return result
    load_dotenv(ROOT / ".env")
    user = os.getenv("XMLRIVER_USER", "")
    key = os.getenv("XMLRIVER_KEY", "")
    if not user or not key:
        result["status"] = "missing_credentials"
        return result
    try:
        sys.path.insert(0, str(ROOT))
        from xmlriver_client import XmlRiverClient

        client = XmlRiverClient(user=user, key=key, engine="yandex", timeout=30, max_retries=2)
        page = client.search(SERP_QUERY, client.first_page)
        matched: dict[str, dict[str, object]] = {}
        docs: list[dict[str, str]] = []
        for doc in page.docs:
            host = root_of(doc.url)
            source = SOURCE_BY_ROOT.get(host)
            docs.append({"url": doc.url, "host": host, "title": doc.title, "snippet": doc.snippet})
            if source:
                item = matched.setdefault(source.slug, {"name": source.name, "count": 0, "positions": []})
                item["count"] = int(item["count"]) + 1
                positions = item["positions"]
                assert isinstance(positions, list)
                positions.append(len(docs))
        result.update({"status": "ok", "found_total": page.found, "docs": docs, "matched_sources": list(matched.values()), "matched_count": len(matched)})
    except Exception as exc:
        result.update({"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
    return result


def tonzar_probe(dry_run: bool) -> dict[str, object]:
    result: dict[str, object] = {"status": "not_run", "query": TEST_KEYWORD, "items": []}
    if dry_run:
        result["status"] = "dry_run"
        return result
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "searchProducts", "arguments": {"query": TEST_KEYWORD, "maxResults": 10}},
    }
    try:
        response = requests.post(
            "https://tonzar.com/mcp",
            json=payload,
            headers={"Accept": "application/json, text/event-stream", "User-Agent": USER_AGENT},
            timeout=30,
        )
        result["http_status"] = response.status_code
        if response.status_code >= 400:
            result.update({"status": "http_error", "error": f"HTTP {response.status_code}"})
            return result
        raw = response.text.strip()
        body = raw
        if raw.startswith("data:"):
            body = next((line[5:].strip() for line in raw.splitlines() if line.startswith("data:")), "")
        parsed = json.loads(body)
        if "result" not in parsed and isinstance(parsed.get("tools"), list):
            result.update({"status": "manifest_only", "tool_count": len(parsed["tools"]), "error": "endpoint returned manifest instead of JSON-RPC result"})
            return result
        if "error" in parsed:
            result.update({"status": "rpc_error", "error": str(parsed["error"])[:240]})
            return result
        structured = parsed.get("result", {}).get("structuredContent", {})
        content = parsed.get("result", {}).get("content", [])
        result.update({"status": "ok", "structured_keys": sorted(structured) if isinstance(structured, dict) else [], "content_preview": str(content)[:1200]})
    except requests.RequestException as exc:
        result.update({"status": "network_error", "error": type(exc).__name__})
    except json.JSONDecodeError:
        result.update({"status": "parse_error", "error": "response is not JSON/SSE JSON"})
    except Exception as exc:
        result.update({"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="не выполнять сетевые запросы")
    parser.add_argument("--skip-xmlriver", action="store_true", help="не повторять платный SERP-запрос")
    args = parser.parse_args(argv)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    started = time.monotonic()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "keyword": TEST_KEYWORD,
        "serp_query": SERP_QUERY,
        "network_mode": "dry-run" if args.dry_run else "read-only",
        "xmlriver": {"status": "skipped"} if args.skip_xmlriver else xmlriver_probe(args.dry_run),
        "tonzar_mcp": tonzar_probe(args.dry_run),
        "sources": [asdict(probe_source(session, source, args.dry_run)) for source in SOURCES],
    }
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "latest_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path = OUT / "latest_summary.md"
    summary_lines = [
        f"# Отчёт теста источников ({report['generated_at']})",
        "",
        f"Ключ: `{TEST_KEYWORD}`",
        f"Режим: `{report['network_mode']}`",
        "",
        "## XMLRiver",
        "",
        f"```json\n{json.dumps(report['xmlriver'], ensure_ascii=False, indent=2)[:6000]}\n```",
        "",
        "## Tonzar MCP",
        "",
        f"```json\n{json.dumps(report['tonzar_mcp'], ensure_ascii=False, indent=2)[:4000]}\n```",
        "",
        "## Сайты",
        "",
        "| Источник | HTTP | Поиск | Результат | Контакты | Ошибка |",
        "|---|---:|---|---:|---:|---|",
    ]
    for item in report["sources"]:
        assert isinstance(item, dict)
        contacts = int(item.get("public_emails", 0)) + int(item.get("public_phones", 0)) if item.get("analysis_scope") == "search" else 0
        result_hits = int(item.get("keyword_hits", 0))
        summary_lines.append(
            f"| {item['name']} | {item.get('http_status') or '—'} | {item.get('search_form', '—')} | {result_hits} | {contacts} | {item.get('error', '') or '—'} |"
        )
    summary_lines.extend(["", f"JSON: `{out_path}`", ""])
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Отчёт: {out_path.resolve()}")
    print(f"Сводка: {summary_path.resolve()}")
    print(f"Время: {report['elapsed_seconds']} c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
