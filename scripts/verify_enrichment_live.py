"""Bounded live smoke-test for the supplier enrichment funnel.

No files or database rows are changed. Registry calls are opt-in because they
consume the configured Checko quota.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.integrations.registry.checko_client import CheckoClient  # noqa: E402
from collect_inn import (  # noqa: E402
    INN_PATHS,
    INN_URL_HINTS,
    extract_for_site,
    extract_legal_ids_for_site,
)
from backend.domain.supplier_enrichment.contact_crawler import ContactCrawler  # noqa: E402
from backend.domain.supplier_identity.inn_resolver import collect_name_hints_from_pages, resolve_inn_by_legal_ids  # noqa: E402
from supplier_app import load_dotenv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("hosts", nargs="+", help="Domains to crawl")
    parser.add_argument("--registry", action="store_true", help="Use existing CHECKO_KEY for exact legal-ID lookup")
    parser.add_argument("--max-elapsed", type=float, default=35.0)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")

    crawler = ContactCrawler(
        max_pages=6, timeout=8.0, delay=0, respect_robots=True,
        check_mx=False, keep_html=True,
        extra_url_hints=INN_URL_HINTS, extra_paths=INN_PATHS,
        max_pdfs=0 if args.no_pdf else 2,
        pdf_parse_timeout=6.0, max_elapsed=args.max_elapsed,
    )
    checko = CheckoClient() if args.registry and os.getenv("CHECKO_KEY") else None
    if args.registry and checko is None:
        print("CHECKO_KEY is not configured; registry step skipped", file=sys.stderr)

    for host in args.hosts:
        site = crawler.crawl(host)
        inns = extract_for_site(site)
        legal_ids = extract_legal_ids_for_site(site)
        print(f"HOST {host}")
        print(f"  status={site.status} elapsed={site.elapsed:.1f}s")
        print(f"  pages={site.pages}")
        print(f"  pdfs={list(site.text_pages)} errors={site.document_errors}")
        print(f"  emails={[hit.email for hit in site.hits[:3]]}")
        print(f"  inns={[(hit.inn, hit.source_url) for hit in inns]}")
        print(f"  legal_ids={[(hit.kind, hit.value, hit.source_url) for hit in legal_ids]}")
        print(f"  name_hints={collect_name_hints_from_pages(site.html_pages)[:5]}")
        if checko is not None and legal_ids:
            resolved = resolve_inn_by_legal_ids(legal_ids, checko)
            print(f"  registry_inn={resolved.inn if resolved else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
