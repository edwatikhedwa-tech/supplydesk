from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .connectors import CATALOGS, FlagmaConnector, GenericCatalogConnector
from .direct_site import DirectSiteAdapter
from .http_client import ReadOnlyHttpClient
from .matching import match_product
from .models import DiscoveryResult, OfferCandidate, PositionSpec, QueryVariant
from .query_planner import QueryPlanner
from .storage import DiscoveryStore
from .xmlriver_subprocess import XmlRiverSubprocess


def _dedupe_results(items: list[DiscoveryResult]) -> list[DiscoveryResult]:
    result: list[DiscoveryResult] = []
    seen: set[str] = set()
    for item in items:
        key = item.url.split("#", 1)[0].rstrip("/")
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _dedupe_offers(items: list[OfferCandidate]) -> list[OfferCandidate]:
    result: list[OfferCandidate] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.source, item.url.split("#", 1)[0].rstrip("/"))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def plan_only(positions: list[PositionSpec], max_queries: int) -> dict[str, object]:
    planner = QueryPlanner(max_queries)
    plans = [{"position": position.to_dict(), "queries": [item.to_dict() for item in planner.plan(position)]} for position in positions]
    return {"mode": "plan", "generated_at": datetime.now(timezone.utc).isoformat(), "positions": plans, "network_requests": 0, "writes_to_current_system": 0}


def run_pipeline(positions: list[PositionSpec], mode: str, out_dir: str | Path, db_path: str | Path, max_queries: int = 3, max_direct_sites: int = 8, catalog_limit: int = 2) -> dict[str, object]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if mode in {"plan", "dry-run"}:
        report = plan_only(positions, max_queries)
        report["mode"] = mode
        _write_report(out, report)
        return report
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    request_payload = [position.to_dict() for position in positions]
    store = DiscoveryStore(db_path)
    store.create_run(run_id, run_id, mode, request_payload)
    planner = QueryPlanner(max_queries)
    serp = XmlRiverSubprocess(out / "serp")
    all_results: list[DiscoveryResult] = []
    serp_details: list[dict[str, object]] = []
    plans: list[dict[str, object]] = []
    for position in positions:
        queries = planner.plan(position)
        plans.append({"position": position.to_dict(), "queries": [query.to_dict() for query in queries]})
        for query in queries:
            results, details = serp.search(query)
            for result in results:
                result.metadata["position_key"] = position.position_key
            all_results.extend(results)
            serp_details.append(details)
            store.record_task(run_id, position.position_key, "xmlriver_serp", query, str(details.get("status")), details)
    all_results = _dedupe_results(all_results)
    store.add_results(run_id, all_results)
    store.add_usage(run_id, "xmlriver", "serp_queries", len(serp_details))
    offers: list[OfferCandidate] = []
    health: dict[str, dict[str, object]] = {"xmlriver_serp": {"status": "ok" if any(d.get("status") == "ok" for d in serp_details) else "error", "queries": serp_details}}
    direct = DirectSiteAdapter(ReadOnlyHttpClient(timeout=15, delay=0.1))
    direct_count = 0
    for position in positions:
        position_results = [item for item in all_results if item.query and item.source == "xmlriver_serp" and item.metadata.get("position_key") == position.position_key]
        position_results.sort(key=lambda item: match_product(position, item.title, item.snippet)[1], reverse=True)
        position_results = position_results[:max_direct_sites]
        for result in position_results:
            candidate = direct.enrich(position, result)
            if candidate:
                offers.append(candidate)
                direct_count += 1
    health["direct_site"] = {"status": "ok" if direct_count else "empty", "landing_pages_checked": direct_count}
    connectors = [FlagmaConnector(ReadOnlyHttpClient(timeout=15, delay=0.2))]
    connectors.extend(GenericCatalogConnector(config, ReadOnlyHttpClient(timeout=15, delay=0.2)) for config in CATALOGS[:catalog_limit])
    for connector in connectors:
        connector_count = 0
        statuses: list[str] = []
        for position in positions:
            for query in planner.plan(position):
                try:
                    found = connector.discover(position, query, 2)
                    offers.extend(found)
                    connector_count += len(found)
                    statuses.append("ok")
                except Exception as exc:
                    statuses.append(type(exc).__name__)
        health[connector.name] = {"status": "ok" if connector_count else ("error" if statuses and all(status != "ok" for status in statuses) else "empty"), "offers": connector_count, "attempts": len(statuses)}
    offers = _dedupe_offers(offers)
    store.add_offers(run_id, offers)
    for source, details in health.items():
        store.add_health(run_id, source, str(details.get("status")), details)
    store.commit()
    store.close()
    qualified = [offer for offer in offers if offer.status == "qualified"]
    contacts: list[dict[str, object]] = []
    seen_contacts: set[tuple[str, str, str]] = set()
    for offer in qualified:
        supplier_key = offer.seller.seller_key if offer.seller else offer.url
        for contact in offer.contacts:
            dedupe_key = (supplier_key, contact.kind, contact.value)
            if dedupe_key in seen_contacts:
                continue
            seen_contacts.add(dedupe_key)
            contacts.append(contact.to_dict() | {"supplier": offer.seller.name if offer.seller else "", "supplier_url": offer.url, "source": offer.source, "position_key": offer.position_key, "match_class": offer.match_class, "match_score": offer.match_score})
    report: dict[str, object] = {"mode": mode, "run_id": run_id, "generated_at": datetime.now(timezone.utc).isoformat(), "positions": [position.to_dict() for position in positions], "plans": plans, "xmlriver": serp_details, "discovery_results": [item.to_dict() for item in all_results], "candidates": [offer.to_dict() for offer in offers], "qualified_contacts": contacts, "source_health": health, "stats": {"serp_results": len(all_results), "offers": len(offers), "qualified_offers": len(qualified), "qualified_contacts": len(contacts)}, "writes_to_current_system": 0}
    _write_report(out, report)
    return report


def _write_report(out: Path, report: dict[str, object]) -> None:
    (out / "latest_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    contacts = report.get("qualified_contacts", [])
    with (out / "qualified_contacts.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        rows = contacts if isinstance(contacts, list) else []
        fieldnames = ["position_key", "supplier", "source", "supplier_url", "kind", "value", "match_class", "match_score"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    summary = report.get("stats", {})
    lines = [f"# Supplier discovery v2", "", f"Режим: `{report.get('mode')}`", f"Поставщики-кандидаты: {summary.get('offers', 0)}", f"Квалифицированные предложения: {summary.get('qualified_offers', 0)}", f"Релевантные публичные контакты: {summary.get('qualified_contacts', 0)}", "", "## Гарантии", "", "- Кодовая база текущего парсера не изменяется и не импортируется.", "- В текущую БД и production-конфигурацию записей нет.", "- Buyer-запросы и platform-owned контакты не квалифицируются."]
    (out / "latest_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
