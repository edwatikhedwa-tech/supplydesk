"""
Шаг 2 PoC: собрать email с сайтов, найденных на шаге 1.

На вход — CSV от serp_parser.py (или просто список доменов), на выход две
выгрузки: по сайтам и по адресам, плюс сводка с измеренной полнотой сбора.

Canonical invocation (from the repository root):
    python -m scripts.collect_contacts --from-serp results/кирпич_yandex_20260820.csv
    python -m scripts.collect_contacts kirpich.ru braer.ru --max-pages 8
    python -m scripts.collect_contacts --from-serp results/serp.csv --workers 12 --no-mx

`python collect_contacts.py ...` at the repository root remains a supported
compatibility entrypoint that delegates here.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from contact_crawler import ContactCrawler, SiteResult
from email_extractor import root_domain, score_hit
from serp_parser import host_of, load_dotenv, read_lines

log = logging.getLogger("contacts")

SITE_FIELDS = [
    "host", "root_domain", "status", "pages_crawled",
    "emails_confirmed", "emails_possible", "best_email", "best_confidence",
    "best_method", "best_source_url", "best_evidence",
    "no_email_reason", "error", "elapsed_sec",
]

EMAIL_FIELDS = [
    "host", "email", "confidence", "score", "method", "source_url", "evidence",
    "mx_ok", "domain_matches_site", "is_free_mail", "is_role", "is_technical",
    "text_mismatch",
    "pages_seen", "reasons",
]


def hosts_from_serp(path: Path) -> list[str]:
    """Взять домены из выгрузки шага 1, сохранив порядок выдачи."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    if not rows:
        return []
    column = "host" if "host" in rows[0] else "url" if "url" in rows[0] else None
    if column is None:
        raise SystemExit(f"В {path} нет колонки host или url — это точно выгрузка шага 1?")

    hosts: list[str] = []
    seen: set[str] = set()
    for row in rows:
        value = (row.get(column) or "").strip()
        host = host_of(value) if "//" in value else value.lower()
        if host and host not in seen:
            seen.add(host)
            hosts.append(host)
    return hosts


def write_sites_csv(results: list[SiteResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SITE_FIELDS, delimiter=";")
        writer.writeheader()
        for site in results:
            best = site.best
            writer.writerow({
                "host": site.host,
                "root_domain": site.root,
                "status": site.status,
                "pages_crawled": site.pages_crawled,
                "emails_confirmed": ", ".join(h.email for h in site.confirmed),
                "emails_possible": ", ".join(h.email for h in site.possible),
                "best_email": best.email if best else "",
                "best_confidence": best.confidence if best else "",
                "best_method": best.method if best else "",
                "best_source_url": best.source_url if best else "",
                "best_evidence": (best.evidence[:300] if best else ""),
                "no_email_reason": site.no_email_reason,
                "error": site.error,
                "elapsed_sec": f"{site.elapsed:.1f}",
            })


def write_emails_csv(results: list[SiteResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EMAIL_FIELDS, delimiter=";")
        writer.writeheader()
        for site in results:
            for hit in site.hits:
                writer.writerow({
                    "host": site.host,
                    "email": hit.email,
                    "confidence": hit.confidence,
                    "score": hit.score,
                    "method": hit.method,
                    "source_url": hit.source_url,
                    "evidence": hit.evidence[:300],
                    "mx_ok": "" if hit.mx_ok is None else int(hit.mx_ok),
                    "domain_matches_site": int(hit.domain_matches_site),
                    "is_free_mail": int(hit.is_free_mail),
                    "is_role": int(hit.is_role),
                    "is_technical": int(hit.is_technical),
                    "text_mismatch": int(hit.text_mismatch),
                    "pages_seen": hit.pages_seen,
                    "reasons": "; ".join(hit.reasons),
                })


def print_report(results: list[SiteResult], elapsed: float) -> None:
    total = len(results)
    reachable = [r for r in results if r.status in ("ok", "no_email")]
    with_email = [r for r in results if r.hits]
    confirmed = [r for r in results if r.confirmed]
    all_emails = [h for r in results for h in r.hits]

    print("\n" + "=" * 78)
    print("СБОР EMAIL — ИТОГИ")
    print("=" * 78)
    print(f"Сайтов обработано:            {total}")
    print(f"Открылись:                    {len(reachable)}")
    if reachable:
        share = len(with_email) / len(reachable) * 100
        print(f"Email найден:                 {len(with_email)}  ({share:.0f}% от открывшихся)")
    print(f"  из них подтверждённых:      {len(confirmed)}")
    print(f"Всего адресов:                {len(all_emails)}")

    if all_emails:
        print("\nПо способу извлечения:")
        for method, count in Counter(h.method for h in all_emails).most_common():
            print(f"  {method:12} {count}")
        print("\nПо достоверности:")
        for level in ("high", "medium", "low"):
            count = sum(1 for h in all_emails if h.confidence == level)
            label = {"high": "подтверждён", "medium": "вероятен", "low": "требует проверки"}[level]
            print(f"  {label:18} {count}")

    problems = [r for r in results if not r.hits]
    if problems:
        print(f"\nБез email — {len(problems)} сайтов (это и есть предел полноты):")
        for reason, count in Counter(
            r.no_email_reason or r.error or r.status for r in problems
        ).most_common():
            print(f"  {count:3}  {reason}")

    print(f"\nВремя: {elapsed:.1f} c")


def print_table(results: list[SiteResult], limit: int = 40) -> None:
    shown = [r for r in results if r.best][:limit]
    if not shown:
        return
    width = max(len(r.host) for r in shown)
    print(f"\n{'сайт'.ljust(width)}  {'email'.ljust(34)} достоверность  способ")
    print("-" * (width + 62))
    label = {"high": "подтверждён", "medium": "вероятен", "low": "проверить"}
    for site in shown:
        best = site.best
        print(f"{site.host.ljust(width)}  {best.email[:34].ljust(34)} "
              f"{label[best.confidence]:14} {best.method}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Сбор email с сайтов поставщиков (шаг 2 PoC).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("hosts", nargs="*", help="домены, например: kirpich.ru braer.ru")
    p.add_argument("--from-serp", type=Path, metavar="CSV",
                   help="взять домены из выгрузки шага 1")
    p.add_argument("--file", type=Path, help="файл со списком доменов")
    p.add_argument("--limit", type=int, metavar="N", help="взять только первые N доменов")

    p.add_argument("--max-pages", type=int, default=6, metavar="N",
                   help="сколько страниц смотреть на сайте (по умолчанию 6)")
    p.add_argument("--workers", type=int, default=8, metavar="N",
                   help="сколько сайтов обходить параллельно (по умолчанию 8)")
    p.add_argument("--timeout", type=float, default=15.0, metavar="СЕК")
    p.add_argument("--delay", type=float, default=0.5, metavar="СЕК",
                   help="пауза между страницами одного сайта")
    p.add_argument("--no-mx", action="store_true",
                   help="не проверять MX-записи (быстрее, но точность ниже)")
    p.add_argument("--ignore-robots", action="store_true",
                   help="игнорировать robots.txt (по умолчанию соблюдается)")

    p.add_argument("--web", action="store_true",
                   help="искать в интернете через XMLRiver там, где обход ничего не дал")
    p.add_argument("--llm", action="store_true",
                   help="разбирать поисковую выдачу моделью, если регулярка не справилась")
    p.add_argument("--llm-model", default=None, metavar="МОДЕЛЬ")
    p.add_argument("--verify", action="store_true",
                   help="свести проверки в вердикт «подтверждён / требует проверки»")

    p.add_argument("--out-dir", type=Path, default=Path("results"), metavar="ПАПКА")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(REPO_ROOT / ".env")

    hosts: list[str] = [h.strip().lower() for h in args.hosts if h.strip()]
    if args.from_serp:
        if not args.from_serp.exists():
            raise SystemExit(f"Файл не найден: {args.from_serp}")
        hosts.extend(hosts_from_serp(args.from_serp))
    if args.file:
        if not args.file.exists():
            raise SystemExit(f"Файл не найден: {args.file}")
        hosts.extend(read_lines(args.file))

    seen: set[str] = set()
    unique = []
    for h in hosts:
        h = host_of(h) if "//" in h else h.lower().lstrip(".")
        if h and h not in seen:
            seen.add(h)
            unique.append(h)
    hosts = unique[: args.limit] if args.limit else unique

    if not hosts:
        raise SystemExit(
            "Не задано ни одного домена.\n"
            "Передайте их аргументами, через --file или возьмите из шага 1: --from-serp results/....csv"
        )

    log.info("Сайтов к обходу: %s, потоков: %s, страниц на сайт: %s",
             len(hosts), args.workers, args.max_pages)

    crawler = ContactCrawler(
        max_pages=args.max_pages,
        timeout=args.timeout,
        delay=args.delay,
        respect_robots=not args.ignore_robots,
        check_mx=not args.no_mx,
    )

    started = time.monotonic()
    try:
        results = crawler.crawl_many(hosts, workers=args.workers)
    except KeyboardInterrupt:
        log.error("Прервано пользователем")
        return 130
    elapsed = time.monotonic() - started

    # Ступень поиска: единственный путь к сайтам, которые не открылись или
    # закрыты robots.txt. Обходить их нельзя, но сведения о компании есть
    # в каталогах и поисковой выдаче.
    web_found = 0
    if args.web:
        import os

        from xmlriver_client import XmlRiverClient
        from web_lookup import WebLookup

        user, key = os.getenv("XMLRIVER_USER", ""), os.getenv("XMLRIVER_KEY", "")
        if not user or not key:
            raise SystemExit(
                "--web требует доступов XMLRiver: задайте XMLRIVER_USER и "
                "XMLRIVER_KEY в .env в корне репозитория."
            )
        else:
            llm = None
            if args.llm:
                from llm_fallback import DEFAULT_MODEL, LlmExtractor

                llm = LlmExtractor(model=args.llm_model or DEFAULT_MODEL)
            lookup = WebLookup(XmlRiverClient(user=user, key=key, engine="yandex"), llm=llm)
            for site in results:
                if site.hits:
                    continue
                finding = lookup.find_contacts(site.host)
                if not finding.emails:
                    continue
                for hit in finding.emails:
                    hit.mx_ok = crawler.mx.check(hit.email.partition("@")[2])
                    score_hit(hit, site_root=site.root)
                site.hits = sorted(finding.emails, key=lambda h: h.score, reverse=True)
                site.status = "ok"
                site.no_email_reason = f"найдено поиском: {finding.queries[0]}"
                web_found += 1
                log.info("%s: поиск дал %s", site.host, site.best.email)

    if args.verify:
        from verify import verify_email

        for site in results:
            for hit in site.hits:
                verdict = verify_email(
                    hit, site.host,
                    also_found_in_web=(hit.method in ("web", "web_llm")),
                )
                hit.reasons.append(
                    ("ВЕРИФИЦИРОВАН" if verdict.verified else "требует проверки")
                    + " — " + verdict.explain()
                )
                if not verdict.verified and hit.confidence == "high":
                    hit.confidence = "medium"

    # Порядок выдачи важен: он отражает позиции из шага 1.
    order = {h: i for i, h in enumerate(hosts)}
    results.sort(key=lambda r: order.get(r.host, 10**6))

    stamp = time.strftime("%Y%m%d_%H%M%S")
    sites_path = args.out_dir / f"contacts_sites_{stamp}.csv"
    emails_path = args.out_dir / f"contacts_emails_{stamp}.csv"
    write_sites_csv(results, sites_path)
    write_emails_csv(results, emails_path)

    if not args.quiet:
        print_table(results)
        print_report(results, elapsed)
        if args.web:
            print(f"Добавил поиск в интернете:    {web_found} сайтов")
        print(f"\nПо сайтам: {sites_path.resolve()}")
        print(f"По адресам: {emails_path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
