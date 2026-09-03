"""
Шаг 3 PoC: собрать ИНН с сайтов поставщиков (Test 1.3).

Порядок ступеней — от дешёвых к дорогим, каждая следующая включается только
там, где предыдущая вернула пусто:

  1. Разметка schema.org и подписанный «ИНН 7701234567» — бесплатно.
  2. Числа без подписи, отсеянные контрольной суммой — бесплатно.
  3. Языковая модель по сохранённому тексту страницы — платно, ключом --llm.
  4. Подтверждение в реестре DaData — бесплатно до 10 000 запросов в день.

Примеры:
    python collect_inn.py --from-serp results/кирпич_yandex_20260820.csv
    python collect_inn.py zavod.ru --llm
    python collect_inn.py --from-serp results/serp.csv --llm --llm-model claude-haiku-4-5
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

from backend.domain.supplier_enrichment.contact_crawler import ContactCrawler, SiteResult
from backend.domain.supplier_identity.inn_extractor import (
    InnHit,
    LegalIdHit,
    extract_inn_from_html,
    extract_inn_from_text,
    extract_legal_ids_from_html,
    extract_legal_ids_from_text,
    is_requisites_url,
    score_inn,
    visible_text_from_html,
)
from serp_parser import host_of, load_dotenv, read_lines

log = logging.getLogger("inn-cli")

# Где реквизиты обязаны быть по закону: оферта и политика обработки данных
# содержат ИНН почти всегда, даже если на «Контактах» его нет.
INN_URL_HINTS = (
    "oferta", "offer", "dogovor", "usloviya", "policy", "politika", "privacy",
    "personal", "soglashenie", "оферт", "политик", "соглашен", "реквизит",
    "oplata", "payment",
)
INN_PATHS = (
    "/oferta/", "/publichnaya-oferta/", "/dogovor-oferty/", "/policy/",
    "/politika-konfidencialnosti/", "/privacy/", "/rekvizity/", "/oplata/",
)

FIELDS = [
    "host", "inn", "kind", "confidence", "score", "method",
    "company_name", "dadata_ok", "checksum_ok", "source_url", "evidence",
    "status", "reasons",
]


def page_text(html: str) -> str:
    # LLM получает тот же quorum-текст, что и регулярки. Иначе regex уже
    # восстановил бы повреждённую страницу через html.parser, а платная
    # резервная ступень снова увидела бы обрезанный lxml-результат.
    return visible_text_from_html(html)


def extract_for_site(site: SiteResult) -> list[InnHit]:
    """Детерминированный разбор всех сохранённых страниц сайта."""
    found: dict[str, InnHit] = {}
    for url, html in site.html_pages.items():
        for hit in extract_inn_from_html(html, url):
            current = found.get(hit.inn)
            if current is None:
                found[hit.inn] = hit
    for url, text in site.text_pages.items():
        for hit in extract_inn_from_text(text, url):
            current = found.get(hit.inn)
            if current is None:
                found[hit.inn] = hit
    for hit in found.values():
        score_inn(hit, on_requisites_page=is_requisites_url(hit.source_url))
    return sorted(found.values(), key=lambda h: h.score, reverse=True)


def extract_legal_ids_for_site(site: SiteResult) -> list[LegalIdHit]:
    """ОГРН/ОГРНИП со всех HTML-страниц и ограниченных PDF сайта."""
    found: dict[tuple[str, str], LegalIdHit] = {}
    for url, html in site.html_pages.items():
        for hit in extract_legal_ids_from_html(html, url):
            found.setdefault((hit.kind, hit.value), hit)
    for url, text in site.text_pages.items():
        for hit in extract_legal_ids_from_text(text, url):
            found.setdefault((hit.kind, hit.value), hit)
    return sorted(found.values(), key=lambda hit: hit.score, reverse=True)


def write_csv(rows: list[tuple[SiteResult, InnHit | None]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        for site, hit in rows:
            writer.writerow({
                "host": site.host,
                "inn": hit.inn if hit else "",
                "kind": hit.kind if hit else "",
                "confidence": hit.confidence if hit else "",
                "score": hit.score if hit else "",
                "method": hit.method if hit else "",
                "company_name": hit.company_name if hit else "",
                "dadata_ok": "" if not hit or hit.dadata_ok is None else int(hit.dadata_ok),
                "checksum_ok": int(hit.checksum_ok) if hit else "",
                "source_url": hit.source_url if hit else "",
                "evidence": (hit.evidence[:300] if hit else ""),
                "status": site.status,
                "reasons": "; ".join(hit.reasons) if hit else "",
            })


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Сбор ИНН с сайтов поставщиков (шаг 3 PoC).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("hosts", nargs="*", help="домены")
    p.add_argument("--from-serp", type=Path, metavar="CSV", help="домены из выгрузки шага 1")
    p.add_argument("--file", type=Path, help="файл со списком доменов")
    p.add_argument("--limit", type=int, metavar="N")

    p.add_argument("--max-pages", type=int, default=6, metavar="N")
    p.add_argument("--workers", type=int, default=8, metavar="N")
    p.add_argument("--timeout", type=float, default=15.0, metavar="СЕК")
    p.add_argument("--ignore-robots", action="store_true")

    p.add_argument("--llm", action="store_true",
                   help="подключить языковую модель там, где разбор не справился")
    p.add_argument("--llm-model", default=None, metavar="МОДЕЛЬ",
                   help="модель RouterAI для ступени 3 (по умолчанию выбранная замером)")
    p.add_argument("--web", action="store_true",
                   help="искать в интернете через XMLRiver там, где сайт недоступен")
    p.add_argument("--llm-limit", type=int, default=50, metavar="N",
                   help="потолок вызовов модели за прогон — защита от неожиданного счёта")

    p.add_argument("--out-dir", type=Path, default=Path("results"), metavar="ПАПКА")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def collect_hosts(args: argparse.Namespace) -> list[str]:
    hosts = list(args.hosts)
    if args.from_serp:
        if not args.from_serp.exists():
            raise SystemExit(f"Файл не найден: {args.from_serp}")
        with args.from_serp.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                value = (row.get("host") or row.get("url") or "").strip()
                if value:
                    hosts.append(host_of(value) if "//" in value else value)
    if args.file:
        hosts.extend(read_lines(args.file))

    seen: set[str] = set()
    unique = []
    for h in hosts:
        h = (host_of(h) if "//" in h else h).lower().lstrip(".")
        if h and h not in seen:
            seen.add(h)
            unique.append(h)
    return unique[: args.limit] if args.limit else unique


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s", stream=sys.stderr,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(Path(__file__).with_name(".env"))

    hosts = collect_hosts(args)
    if not hosts:
        raise SystemExit("Не задано ни одного домена.")

    crawler = ContactCrawler(
        max_pages=args.max_pages, timeout=args.timeout,
        respect_robots=not args.ignore_robots, check_mx=False, keep_html=True,
        extra_url_hints=INN_URL_HINTS, extra_paths=INN_PATHS,
    )

    started = time.monotonic()
    sites = crawler.crawl_many(hosts, workers=args.workers)
    order = {h: i for i, h in enumerate(hosts)}
    sites.sort(key=lambda s: order.get(s.host, 10**6))

    # Ступени 1–2: детерминированный разбор.
    results: list[tuple[SiteResult, InnHit | None]] = []
    for site in sites:
        hits = extract_for_site(site)
        results.append((site, hits[0] if hits else None))

    deterministic_found = sum(1 for _s, h in results if h)
    crawled = [s for s, _h in results if s.html_pages]
    log.info("Детерминированный разбор: ИНН найден на %s из %s открывшихся сайтов",
             deterministic_found, len(crawled))

    # Ступень 3: модель — только там, где страница получена, а ИНН не найден.
    llm_used = 0
    llm_cost = 0.0
    if args.llm:
        from backend.integrations.llm.llm_fallback import DEFAULT_MODEL, LlmExtractor, api_key_present

        if not api_key_present():
            raise SystemExit(
                "Для --llm нужен ключ RouterAI.\n"
                "Задайте ROUTERAI_KEY в .env рядом со скриптом или в окружении."
            )
        extractor = LlmExtractor(model=args.llm_model or DEFAULT_MODEL)
        candidates = [(s, i) for i, (s, h) in enumerate(results) if not h and s.html_pages]
        log.info("Кандидатов для модели: %s (потолок %s)", len(candidates), args.llm_limit)

        for site, index in candidates[: args.llm_limit]:
            # Берём страницу, где реквизиты вероятнее всего.
            url, html = max(
                site.html_pages.items(),
                key=lambda kv: (is_requisites_url(kv[0]), len(kv[1])),
            )
            try:
                hit = extractor.extract_inn(site.host, page_text(html), url)
            except Exception as exc:  # noqa: BLE001 — сбой модели не роняет прогон
                log.error("%s: модель не ответила: %s", site.host, exc)
                continue
            llm_used += 1
            if hit:
                score_inn(hit, on_requisites_page=is_requisites_url(url))
                results[index] = (site, hit)
                log.info("%s: модель нашла ИНН %s (%s)", site.host, hit.inn, hit.company_name)
        llm_cost = extractor.cost_rub()

    # Ступень 3б: поиск в интернете. Единственный путь к сайтам, которые
    # не открылись или закрыты robots.txt — показать модели нечего, но
    # сведения о компании есть в каталогах и поисковой выдаче.
    web_found = 0
    if args.web:
        from backend.integrations.search.xmlriver_client import XmlRiverClient
        from backend.integrations.search.web_lookup import WebLookup

        user, key = os.getenv("XMLRIVER_USER", ""), os.getenv("XMLRIVER_KEY", "")
        if not user or not key:
            log.warning("--web пропущен: не заданы XMLRIVER_USER и XMLRIVER_KEY")
        else:
            lookup = WebLookup(XmlRiverClient(user=user, key=key, engine="yandex"))
            for index, (site, hit) in enumerate(results):
                if hit:
                    continue
                found = lookup.find_inn(site.host)
                if found:
                    score_inn(found)
                    results[index] = (site, found)
                    web_found += 1
                    log.info("%s: ИНН %s найден в выдаче", site.host, found.inn)

    # Ступень 4: подтверждение в реестре.
    if os.getenv("DADATA_TOKEN"):
        from backend.integrations.registry.dadata_client import DadataClient

        dadata = DadataClient(os.getenv("DADATA_TOKEN", ""))
        for site, hit in results:
            if hit:
                dadata.confirm(hit)
                score_inn(hit, on_requisites_page=is_requisites_url(hit.source_url))
    else:
        log.warning("DADATA_TOKEN не задан — ИНН не подтверждаются в реестре, "
                    "выше «вероятен» они не поднимутся")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = args.out_dir / f"inn_{stamp}.csv"
    write_csv(results, out)

    # ---------------------------------------------------------------- отчёт
    found = [(s, h) for s, h in results if h]
    print("\n" + "=" * 78)
    print("СБОР ИНН — ИТОГИ")
    print("=" * 78)
    print(f"Сайтов обработано:        {len(results)}")
    print(f"Страницы получены:        {len(crawled)}")
    print(f"ИНН найден:               {len(found)}"
          + (f"  ({len(found) / len(crawled) * 100:.0f}% от открывшихся)" if crawled else ""))
    print(f"  детерминированно:       {deterministic_found}")
    if args.web:
        print(f"  нашёл поиск:            {web_found}")
    if args.llm:
        print(f"  добавила модель:        {len(found) - deterministic_found}"
              f"  (вызовов: {llm_used}, {llm_cost:.3f} ₽)")

    if found:
        print("\nПо способу:")
        for method, count in Counter(h.method for _s, h in found).most_common():
            print(f"  {method:10} {count}")
        print("\nПо достоверности:")
        for level in ("high", "medium", "low"):
            label = {"high": "подтверждён", "medium": "вероятен", "low": "проверить"}[level]
            print(f"  {label:14} {sum(1 for _s, h in found if h.confidence == level)}")

        width = max(len(s.host) for s, _h in found)
        print(f"\n{'сайт'.ljust(width)}  {'ИНН'.ljust(13)} способ    компания")
        print("-" * (width + 50))
        for site, hit in found:
            print(f"{site.host.ljust(width)}  {hit.inn.ljust(13)} "
                  f"{hit.method:9} {hit.company_name[:32]}")

    missing = [(s, h) for s, h in results if not h]
    if missing:
        print(f"\nБез ИНН — {len(missing)}:")
        for reason, count in Counter(
            "страница не получена" if not s.html_pages else "ИНН на страницах нет"
            for s, _h in missing
        ).most_common():
            print(f"  {count:3}  {reason}")

    print(f"\nВремя: {time.monotonic() - started:.1f} c")
    print(f"CSV: {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
