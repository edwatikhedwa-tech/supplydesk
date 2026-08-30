from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import DiscoveryResult, OfferCandidate, QueryVariant


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, run_key TEXT NOT NULL UNIQUE, mode TEXT NOT NULL, created_at TEXT NOT NULL, request_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS search_tasks (run_id TEXT NOT NULL, position_key TEXT NOT NULL, source TEXT NOT NULL, query TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL, PRIMARY KEY(run_id, position_key, source, query));
CREATE TABLE IF NOT EXISTS discovery_results (run_id TEXT NOT NULL, source TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL, snippet TEXT NOT NULL, query TEXT NOT NULL, rank INTEGER, metadata_json TEXT NOT NULL, PRIMARY KEY(run_id, source, url));
CREATE TABLE IF NOT EXISTS offer_candidates (run_id TEXT NOT NULL, position_key TEXT NOT NULL, source TEXT NOT NULL, url TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(run_id, position_key, source, url));
CREATE TABLE IF NOT EXISTS candidate_contacts (run_id TEXT NOT NULL, position_key TEXT NOT NULL, source_url TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(run_id, position_key, source_url, kind, value));
CREATE TABLE IF NOT EXISTS candidate_evidence (run_id TEXT NOT NULL, position_key TEXT NOT NULL, candidate_url TEXT NOT NULL, evidence_url TEXT NOT NULL, PRIMARY KEY(run_id, position_key, candidate_url, evidence_url));
CREATE TABLE IF NOT EXISTS source_health (run_id TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL, PRIMARY KEY(run_id, source));
CREATE TABLE IF NOT EXISTS usage_events (run_id TEXT NOT NULL, source TEXT NOT NULL, event TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(run_id, source, event));
"""


class DiscoveryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def create_run(self, run_id: str, run_key: str, mode: str, request: object) -> None:
        self.connection.execute("INSERT OR IGNORE INTO runs(run_id, run_key, mode, created_at, request_json) VALUES (?, ?, ?, ?, ?)", (run_id, run_key, mode, datetime.now(timezone.utc).isoformat(), json.dumps(request, ensure_ascii=False, default=str)))
        self.connection.commit()

    def record_task(self, run_id: str, position_key: str, source: str, query: QueryVariant, status: str, details: dict[str, object]) -> None:
        self.connection.execute("INSERT OR REPLACE INTO search_tasks VALUES (?, ?, ?, ?, ?, ?, ?)", (run_id, position_key, source, query.query, query.kind, status, json.dumps(details, ensure_ascii=False, default=str)))

    def add_results(self, run_id: str, results: Iterable[DiscoveryResult]) -> None:
        self.connection.executemany("INSERT OR REPLACE INTO discovery_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [(run_id, item.source, item.url, item.title, item.snippet, item.query, item.rank, json.dumps(item.metadata, ensure_ascii=False, default=str)) for item in results])

    def add_offers(self, run_id: str, offers: Iterable[OfferCandidate]) -> None:
        rows = []
        contact_rows = []
        evidence_rows = []
        for offer in offers:
            rows.append((run_id, offer.position_key, offer.source, offer.url, json.dumps(offer.to_dict(), ensure_ascii=False, default=str), offer.status))
            for contact in offer.contacts:
                contact_rows.append((run_id, offer.position_key, offer.url, contact.kind, contact.value, json.dumps(contact.to_dict(), ensure_ascii=False, default=str)))
            for evidence in offer.evidence_urls:
                evidence_rows.append((run_id, offer.position_key, offer.url, evidence))
        self.connection.executemany("INSERT OR REPLACE INTO offer_candidates VALUES (?, ?, ?, ?, ?, ?)", rows)
        self.connection.executemany("INSERT OR REPLACE INTO candidate_contacts VALUES (?, ?, ?, ?, ?, ?)", contact_rows)
        self.connection.executemany("INSERT OR REPLACE INTO candidate_evidence VALUES (?, ?, ?, ?)", evidence_rows)

    def add_health(self, run_id: str, source: str, status: str, details: dict[str, object]) -> None:
        self.connection.execute("INSERT OR REPLACE INTO source_health VALUES (?, ?, ?, ?)", (run_id, source, status, json.dumps(details, ensure_ascii=False, default=str)))

    def add_usage(self, run_id: str, source: str, event: str, count: int = 1) -> None:
        self.connection.execute("INSERT OR REPLACE INTO usage_events VALUES (?, ?, ?, ?)", (run_id, source, event, count))

    def commit(self) -> None:
        self.connection.commit()
