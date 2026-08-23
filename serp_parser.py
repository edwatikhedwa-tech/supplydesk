"""
Парсер поисковой выдачи для PoC сервиса поиска поставщиков.

Что делает: берёт ключ (например «кирпич»), добавляет к нему коммерческий
маркер («купить»), прогоняет получившийся запрос через XMLRiver на заданную
глубину страниц выдачи и отдаёт список сайтов.

Это шаг 1 конвейера PoC (Эпик 1, Test 1.1 из бэклога): собрать сырую выдачу,
чтобы затем считать долю мусора и проверять извлечение контактов. Никакой
фильтрации «поставщик / не поставщик» здесь нет — парсер отдаёт то, что
реально показал поисковик.

Примеры:
    python serp_parser.py "кирпич" --pages 3
    python serp_parser.py "кабель ВВГнг" "фланец стальной Ду 50" --pages 5 --engine google
    python serp_parser.py --file keywords.txt --pages 3 --lr 213 --out results/spb.csv
    python serp_parser.py "кирпич" --pages 2 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from xmlriver_client import XmlRiverClient, XmlRiverError

log = logging.getLogger("serp")

DEFAULT_SUFFIX = "купить"

# Составные доменные зоны: для них корневым доменом считаем три метки,
# иначе metall.com.ru схлопнулось бы в com.ru.
COMPOUND_TLDS = {
    "com.ru", "net.ru", "org.ru", "pp.ru", "msk.ru", "spb.ru",
    "com.ua", "co.ua", "in.ua", "org.ua", "net.ua",
    "com.by", "com.kz", "org.kz",
    "co.uk", "org.uk", "com.tr", "com.cn", "co.jp",
}


@dataclass
class SerpRow:
    """Строка итоговой выгрузки: один сайт по одному ключу."""

    keyword: str
    query: str
    engine: str
    page: int
    position: int
    url: str
    host: str
    root_domain: str
    title: str
    snippet: str
    found_total: int | None
    collected_at: str


# --------------------------------------------------------------------- утилиты


def build_query(keyword: str, suffix: str | None) -> str:
    """«кирпич» + «купить» -> «кирпич купить». Если маркер уже есть — не дублируем."""
    keyword = " ".join(keyword.split())
    if not suffix:
        return keyword
    suffix = " ".join(suffix.split())
    words = {w.strip(".,!?«»\"'").lower() for w in keyword.split()}
    if all(part.lower() in words for part in suffix.split()):
        return keyword
    return f"{keyword} {suffix}"


def host_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if "@" in host:
        host = host.split("@", 1)[1]
    host = host.split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def root_domain_of(host: str) -> str:
    """spb.metall.ru -> metall.ru. Нужно, чтобы не считать зеркала и филиальные
    поддомены разными компаниями (Test 2.1 бэклога PoC)."""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if ".".join(parts[-2:]) in COMPOUND_TLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def dedup_key(row: SerpRow, mode: str) -> str | None:
    if mode == "url":
        return row.url.rstrip("/").lower()
    if mode == "host":
        return row.host
    if mode == "root":
        return row.root_domain
    return None  # mode == "none"


def read_lines(path: Path) -> list[str]:
    """Список строк из файла: пустые строки и комментарии (#) пропускаем."""
    text = path.read_text(encoding="utf-8-sig")
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def parse_extra_params(pairs: list[str]) -> dict[str, str]:
    """--param filter=0 --param ads=1 -> {'filter': '0', 'ads': '1'}"""
    extra: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Параметр --param должен быть вида имя=значение, получено: {pair!r}")
        name, value = pair.split("=", 1)
        extra[name.strip()] = value.strip()
    return extra


# ------------------------------------------------------------------- сбор SERP


class SerpCollector:
    def __init__(
        self,
        client: XmlRiverClient,
        pages: int = 1,
        suffix: str | None = DEFAULT_SUFFIX,
        extra: dict[str, Any] | None = None,
        delay: float = 1.0,
        dedup: str = "host",
        exclude_domains: set[str] | None = None,
        stop_on_empty: bool = True,
    ):
        if pages < 1:
            raise ValueError("Глубина (--pages) должна быть не меньше 1")
        self.client = client
        self.pages = pages
        self.suffix = suffix
        self.extra = extra or {}
        self.delay = delay
        self.dedup = dedup
        self.exclude_domains = exclude_domains or set()
        self.stop_on_empty = stop_on_empty
        self.stats = {"queries": 0, "requests": 0, "rows": 0, "dropped": 0, "errors": 0}

    def collect(self, keywords: list[str]) -> list[SerpRow]:
        rows: list[SerpRow] = []
        for keyword in keywords:
            rows.extend(self.collect_one(keyword))
        return rows

    def collect_one(self, keyword: str) -> list[SerpRow]:
        query = build_query(keyword, self.suffix)
        self.stats["queries"] += 1
        log.info("Ключ «%s» -> запрос «%s», глубина %s стр.", keyword, query, self.pages)

        rows: list[SerpRow] = []
        seen: set[str] = set()
        position = 0

        for offset in range(self.pages):
            page = self.client.first_page + offset
            try:
                serp = self.client.search(query, page, self.extra)
                self.stats["requests"] += 1
            except XmlRiverError as exc:
                # Одна страница не должна ронять весь прогон: фиксируем и идём дальше.
                self.stats["errors"] += 1
                log.error("«%s» стр.%s пропущена: %s", query, page, exc)
                continue

            if not serp.docs:
                log.info("«%s» стр.%s: результатов нет", query, page)
                if self.stop_on_empty:
                    break
                continue

            for doc in serp.docs:
                position += 1
                host = host_of(doc.url)
                row = SerpRow(
                    keyword=keyword,
                    query=query,
                    engine=serp.engine,
                    page=page,
                    position=position,
                    url=doc.url,
                    host=host,
                    root_domain=root_domain_of(host),
                    title=doc.title,
                    snippet=doc.snippet,
                    found_total=serp.found,
                    collected_at=datetime.now().isoformat(timespec="seconds"),
                )

                if self._excluded(row):
                    self.stats["dropped"] += 1
                    continue

                key = dedup_key(row, self.dedup)
                if key is not None:
                    if key in seen:
                        self.stats["dropped"] += 1
                        continue
                    seen.add(key)

                rows.append(row)

            if self.delay and offset < self.pages - 1:
                time.sleep(self.delay)

        self.stats["rows"] += len(rows)
        log.info("«%s»: собрано %s сайтов", query, len(rows))
        return rows

    def _excluded(self, row: SerpRow) -> bool:
        return row.host in self.exclude_domains or row.root_domain in self.exclude_domains


# ------------------------------------------------------------------- выгрузка

CSV_FIELDS = [
    "keyword", "query", "engine", "page", "position",
    "url", "host", "root_domain", "title", "snippet",
    "found_total", "collected_at",
]


def write_csv(rows: list[SerpRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig — чтобы Excel открыл кириллицу без бубна.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(rows: list[SerpRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_table(rows: list[SerpRow], limit: int = 30) -> None:
    if not rows:
        print("Ничего не найдено.")
        return
    width = max(len(r.host) for r in rows[:limit])
    print(f"\n{'#':>3}  {'домен'.ljust(width)}  заголовок")
    print("-" * (width + 60))
    for row in rows[:limit]:
        title = row.title[:55] + ("…" if len(row.title) > 55 else "")
        print(f"{row.position:>3}  {row.host.ljust(width)}  {title}")
    if len(rows) > limit:
        print(f"... и ещё {len(rows) - limit} строк — смотрите файл выгрузки")


def default_out_path(keywords: list[str], engine: str) -> Path:
    stem = re.sub(r"[^\w\-]+", "_", keywords[0].lower())[:40] or "serp"
    if len(keywords) > 1:
        stem = f"{stem}_и_ещё_{len(keywords) - 1}"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"{stem}_{engine}_{stamp}.csv"


# ------------------------------------------------------------------------ CLI


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Парсер поисковой выдачи через XMLRiver: ключ + «купить» -> список сайтов.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("keywords", nargs="*", help="ключи, например: кирпич «кабель ВВГнг»")
    p.add_argument("--file", type=Path, help="файл со списком ключей, по одному на строку")

    p.add_argument("--pages", type=int, default=1, metavar="N",
                   help="глубина: сколько страниц выдачи забрать по каждому ключу (по умолчанию 1)")
    p.add_argument("--engine", choices=["yandex", "google"], default="yandex",
                   help="поисковик (по умолчанию yandex)")
    p.add_argument("--suffix", default=DEFAULT_SUFFIX, metavar="СЛОВО",
                   help=f"коммерческий маркер, добавляемый к ключу (по умолчанию «{DEFAULT_SUFFIX}»)")
    p.add_argument("--no-suffix", action="store_true", help="искать чистый ключ, без добавки")

    p.add_argument("--lr", metavar="ID", help="регион (Яндекс: 213 — Москва, 2 — СПб)")
    p.add_argument("--loc", metavar="ID", help="локация для Google")
    p.add_argument("--country", metavar="ID", help="страна для Google")
    p.add_argument("--domain", metavar="ID", help="домен поисковика")
    p.add_argument("--device", choices=["desktop", "tablet", "mobile"], help="тип устройства")
    p.add_argument("--param", action="append", default=[], metavar="ИМЯ=ЗНАЧЕНИЕ",
                   help="любой дополнительный параметр API (можно повторять)")

    p.add_argument("--dedup", choices=["root", "host", "url", "none"], default="host",
                   help="схлопывать дубли: root — до корневого домена, host — по хосту "
                        "(по умолчанию), url — по URL, none — не схлопывать")
    p.add_argument("--exclude-file", type=Path, metavar="ФАЙЛ",
                   help="файл со стоп-доменами (агрегаторы, справочники), по одному на строку")
    p.add_argument("--keep-going", action="store_true",
                   help="не прекращать обход глубины после первой пустой страницы")

    p.add_argument("--out", type=Path, metavar="ФАЙЛ", help="куда сохранить CSV")
    p.add_argument("--json", dest="json_out", type=Path, metavar="ФАЙЛ", help="дополнительно сохранить JSON")
    p.add_argument("--delay", type=float, default=1.0, metavar="СЕК",
                   help="пауза между страницами, сек (по умолчанию 1.0)")
    p.add_argument("--timeout", type=float, default=60.0, metavar="СЕК", help="таймаут запроса")
    p.add_argument("--retries", type=int, default=4, metavar="N", help="попыток при временных ошибках")

    p.add_argument("--user", help="XMLRiver user id (иначе берётся из XMLRIVER_USER)")
    p.add_argument("--key", help="XMLRiver key (иначе берётся из XMLRIVER_KEY)")

    p.add_argument("--dry-run", action="store_true", help="показать URL запросов, ничего не отправляя")
    p.add_argument("--balance", action="store_true", help="показать баланс и стоимость тысячи запросов")
    p.add_argument("-v", "--verbose", action="store_true", help="подробный лог")
    p.add_argument("-q", "--quiet", action="store_true", help="только ошибки")
    return p


def load_dotenv(path: Path) -> None:
    """Мини-.env: без зависимостей, уже заданные переменные окружения не трогаем."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def collect_keywords(args: argparse.Namespace) -> list[str]:
    keywords = list(args.keywords)
    if args.file:
        if not args.file.exists():
            raise SystemExit(f"Файл с ключами не найден: {args.file}")
        keywords.extend(read_lines(args.file))
    # порядок сохраняем, дубли убираем
    seen: set[str] = set()
    result = []
    for kw in keywords:
        norm = " ".join(kw.split()).lower()
        if norm and norm not in seen:
            seen.add(norm)
            result.append(" ".join(kw.split()))
    return result


def build_extra(args: argparse.Namespace) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "lr": args.lr,
        "loc": args.loc,
        "country": args.country,
        "domain": args.domain,
        "device": args.device,
    }
    extra.update(parse_extra_params(args.param))
    return {k: v for k, v in extra.items() if v not in (None, "")}


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    load_dotenv(Path(__file__).with_name(".env"))
    user = args.user or os.getenv("XMLRIVER_USER", "")
    key = args.key or os.getenv("XMLRIVER_KEY", "")
    if not user or not key:
        if args.dry_run:
            user, key = user or "USER_ID", key or "KEY"
        else:
            raise SystemExit(
                "Не заданы доступы к XMLRiver.\n"
                "Задайте XMLRIVER_USER и XMLRIVER_KEY в файле .env рядом со скриптом\n"
                "или передайте --user и --key. Взять их можно в личном кабинете:\n"
                "https://xmlriver.com/account/"
            )

    client = XmlRiverClient(
        user=user, key=key, engine=args.engine,
        timeout=args.timeout, max_retries=args.retries,
    )
    extra = build_extra(args)

    if args.balance:
        print(f"Баланс: {client.get_balance()}")
        print(f"Стоимость 1000 запросов ({args.engine}): {client.get_cost()}")
        if not args.keywords and not args.file:
            return 0

    keywords = collect_keywords(args)
    if not keywords:
        raise SystemExit("Не задано ни одного ключа. Передайте их аргументами или через --file.")

    suffix = None if args.no_suffix else args.suffix

    if args.dry_run:
        print(f"Поисковик: {args.engine}, глубина: {args.pages} стр., "
              f"страницы нумеруются с {client.first_page}")
        for kw in keywords:
            query = build_query(kw, suffix)
            print(f"\nКлюч «{kw}» -> запрос «{query}»")
            for offset in range(args.pages):
                print("  " + client.build_url(query, client.first_page + offset, extra))
        total = len(keywords) * args.pages
        print(f"\nИтого запросов к API: {total}")
        return 0

    exclude: set[str] = set()
    if args.exclude_file:
        if not args.exclude_file.exists():
            raise SystemExit(f"Файл стоп-доменов не найден: {args.exclude_file}")
        exclude = {host_of(d) if "//" in d else d.lower().lstrip(".") for d in read_lines(args.exclude_file)}
        log.info("Загружено стоп-доменов: %s", len(exclude))

    collector = SerpCollector(
        client=client, pages=args.pages, suffix=suffix, extra=extra,
        delay=args.delay, dedup=args.dedup, exclude_domains=exclude,
        stop_on_empty=not args.keep_going,
    )

    started = time.monotonic()
    try:
        rows = collector.collect(keywords)
    except KeyboardInterrupt:
        log.error("Прервано пользователем")
        return 130
    except XmlRiverError as exc:
        log.error("Сбор остановлен: %s", exc)
        return 1

    out_path = args.out or default_out_path(keywords, args.engine)
    write_csv(rows, out_path)
    if args.json_out:
        write_json(rows, args.json_out)

    if not args.quiet:
        print_table(rows)
        s = collector.stats
        print(
            f"\nКлючей: {s['queries']} | запросов к API: {s['requests']} | "
            f"сайтов: {s['rows']} | отброшено дублей и стоп-доменов: {s['dropped']} | "
            f"ошибок страниц: {s['errors']} | время: {time.monotonic() - started:.1f} c"
        )
        print(f"CSV: {out_path.resolve()}")
        if args.json_out:
            print(f"JSON: {args.json_out.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
