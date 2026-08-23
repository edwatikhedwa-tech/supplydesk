"""
Стенд для выбора модели: какая справляется и сколько это стоит.

Вопрос «какая модель нужна» решается замером, а не мнением. У нас есть
16 сайтов, где ИНН найден детерминированно и подтверждён контрольной суммой —
это готовый эталон. Прогоняем по нему кандидатов и смотрим, кто сколько
угадал и почём.

Страницы кэшируются на диск: модели сравниваются на одних и тех же данных,
и повторный прогон не ходит в сеть.

Порядок работы:
    python benchmark_models.py --prepare --from-serp results/serp.csv   # собрать кэш и эталон
    python benchmark_models.py --run                                    # прогнать модели
    python benchmark_models.py --run --models a,b,c                     # свой список
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

from contact_crawler import ContactCrawler
from inn_extractor import extract_inn_from_html, is_requisites_url, validate_inn_checksum
from serp_parser import host_of, load_dotenv

log = logging.getLogger("bench")

MAX_OUTPUT_TOKENS = 4000

CACHE_DIR = Path("cache/pages")
TRUTH_PATH = Path("cache/ground_truth.json")

# Кандидаты от самых дешёвых к дорогим. Дорогие здесь как точка отсчёта:
# если дешёвая берёт столько же, переплачивать не за что.
DEFAULT_MODELS = [
    "inclusionai/ling-2.6-flash",
    "openai/gpt-oss-120b",
    "qwen/qwen3-30b-a3b-instruct-2507",
    "google/gemini-2.5-flash-lite",
    "openai/gpt-5-nano",
    "deepseek/deepseek-chat-v3.1",
    "anthropic/claude-haiku-4.5",
]


@dataclass
class ModelScore:
    model: str
    correct: int = 0          # ИНН совпал с эталоном
    wrong: int = 0            # выдала другой номер
    missed: int = 0           # вернула пусто
    invalid: int = 0          # не прошло контрольную сумму — отсечено защитой
    failed: int = 0           # модель не ответила
    cost_rub: float = 0.0
    seconds: float = 0.0
    details: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.correct + self.wrong + self.missed + self.invalid + self.failed

    @property
    def accuracy(self) -> float:
        return self.correct / self.total * 100 if self.total else 0.0


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


def safe_name(host: str, url: str) -> str:
    import hashlib

    return f"{host}__{hashlib.md5(url.encode()).hexdigest()[:10]}.html"


def prepare(hosts: list[str], workers: int, max_pages: int) -> None:
    """Обойти сайты один раз, сложить страницы в кэш и составить эталон."""
    from collect_inn import INN_PATHS, INN_URL_HINTS

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    crawler = ContactCrawler(
        max_pages=max_pages, check_mx=False, keep_html=True,
        extra_url_hints=INN_URL_HINTS, extra_paths=INN_PATHS,
    )
    truth: dict[str, dict] = {}

    for site in crawler.crawl_many(hosts, workers=workers):
        if not site.html_pages:
            continue
        saved: list[str] = []
        for url, html in site.html_pages.items():
            path = CACHE_DIR / safe_name(site.host, url)
            path.write_text(html, encoding="utf-8")
            saved.append(path.name)

        # Эталон: ИНН, найденный детерминированно и прошедший контрольную сумму.
        found = None
        for url, html in site.html_pages.items():
            for hit in extract_inn_from_html(html, url):
                if hit.method == "labeled" and hit.checksum_ok:
                    found = {"inn": hit.inn, "url": url, "evidence": hit.evidence[:200]}
                    break
            if found:
                break

        truth[site.host] = {"pages": saved, "inn": found["inn"] if found else None,
                            "source": found["url"] if found else ""}

    TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRUTH_PATH.write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")

    with_inn = sum(1 for v in truth.values() if v["inn"])
    print(f"Кэш собран: {len(truth)} сайтов, страниц {sum(len(v['pages']) for v in truth.values())}")
    print(f"Эталон: ИНН известен для {with_inn} сайтов")
    print(f"Файлы: {CACHE_DIR.resolve()}")


def load_truth() -> dict[str, dict]:
    if not TRUTH_PATH.exists():
        raise SystemExit(
            f"Эталон не найден: {TRUTH_PATH}\n"
            "Сначала соберите кэш: python benchmark_models.py --prepare --from-serp <csv>"
        )
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))


def best_page(host: str, entry: dict) -> tuple[str, str]:
    """Страница, на которой эталонный ИНН реально стоит.

    Сравнение честное только так: модели дают ровно тот текст, из которого
    регулярка достала эталон. Иначе меряется не умение модели читать, а
    везение с выбором страницы — на этом первая версия стенда и ошиблась,
    показав ноль у всех моделей разом.
    """
    source = entry.get("source") or ""
    if source:
        path = CACHE_DIR / safe_name(host, source)
        if path.exists():
            return path.name, path.read_text(encoding="utf-8")

    best_name, best_html, best_key = "", "", (-1, -1)
    for name in entry["pages"]:
        path = CACHE_DIR / name
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        key = (int(is_requisites_url(name)), len(html))
        if key > best_key:
            best_name, best_html, best_key = name, html, key
    return best_name, best_html


def run(models: list[str], limit: int | None) -> None:
    from llm_fallback import INN_SCHEMA, INN_SYSTEM_PROMPT, build_inn_user_message
    from routerai_client import RouterAiClient

    truth = load_truth()
    cases = [(host, entry) for host, entry in truth.items() if entry["inn"]]
    if limit:
        cases = cases[:limit]
    if not cases:
        raise SystemExit("В эталоне нет сайтов с известным ИНН.")

    print(f"Эталонных сайтов: {len(cases)}, моделей: {len(models)}\n")
    client = RouterAiClient()
    scores: list[ModelScore] = []

    for model in models:
        score = ModelScore(model=model)
        started = time.monotonic()
        print(f"--- {model}")

        for host, entry in cases:
            _name, html = best_page(host, entry)
            if not html:
                continue
            expected = entry["inn"]
            data = client.complete_json(
                model=model,
                system=INN_SYSTEM_PROMPT,
                user=build_inn_user_message(host, page_text(html), entry.get("source", "")),
                schema=INN_SCHEMA,
                # Рассуждающим моделям (gpt-5-nano и подобным) тесный бюджет
                # вывода не даёт дойти до ответа: рассуждения съедают его целиком,
                # и содержимое приходит пустым. Нерассуждающие остановятся раньше,
                # так что запас им ничего не стоит.
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            if data is None:
                score.failed += 1
                score.details.append(f"{host}: модель не ответила")
                continue

            got = "".join(ch for ch in str(data.get("inn") or "") if ch.isdigit())
            if not got:
                score.missed += 1
                score.details.append(f"{host}: пусто, ожидался {expected}")
            elif not validate_inn_checksum(got):
                score.invalid += 1
                score.details.append(f"{host}: {got} — контрольная сумма не сошлась (отсечено)")
            elif got == expected:
                score.correct += 1
            else:
                score.wrong += 1
                score.details.append(f"{host}: {got}, ожидался {expected}")

        score.seconds = time.monotonic() - started
        score.cost_rub = client.cost_rub(model)
        usage = client.usage.get(model)
        print(f"    точность {score.accuracy:5.1f}%  "
              f"верно {score.correct} / мимо {score.wrong} / пусто {score.missed} / "
              f"брак {score.invalid} / сбой {score.failed}  "
              f"{score.cost_rub:.3f} ₽  {score.seconds:.0f} c"
              + (f"  ({usage.input_tokens} вх. токенов)" if usage else ""))
        for line in score.details[:4]:
            print(f"      {line}")
        scores.append(score)

    # ------------------------------------------------------------------ итог
    print("\n" + "=" * 92)
    print("ВЫБОР МОДЕЛИ")
    print("=" * 92)
    print(f"{'модель':42} {'точность':>9} {'верно':>7} {'мимо':>6} "
          f"{'₽ за прогон':>12} {'₽ за 1000 сайтов':>18}")
    print("-" * 92)
    for s in sorted(scores, key=lambda s: (-s.accuracy, s.cost_rub)):
        per_1000 = s.cost_rub / s.total * 1000 if s.total else 0
        print(f"{s.model:42} {s.accuracy:8.1f}% {s.correct:7} {s.wrong:6} "
              f"{s.cost_rub:12.3f} {per_1000:18.0f}")

    good = [s for s in scores if s.accuracy >= 100.0]
    if good:
        cheapest = min(good, key=lambda s: s.cost_rub)
        print(f"\nСамая дешёвая из безошибочных: {cheapest.model}")
        print(f"  {cheapest.cost_rub / cheapest.total * 1000:.0f} ₽ на 1000 сайтов")
    else:
        best = max(scores, key=lambda s: s.accuracy)
        print(f"\nНи одна не взяла 100%. Лучшая: {best.model} ({best.accuracy:.1f}%)")

    out = Path("results") / f"benchmark_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["model", "accuracy_pct", "correct", "wrong", "missed",
                    "invalid", "failed", "cost_rub", "rub_per_1000_sites", "seconds"])
        for s in scores:
            w.writerow([s.model, f"{s.accuracy:.1f}", s.correct, s.wrong, s.missed,
                        s.invalid, s.failed, f"{s.cost_rub:.4f}",
                        f"{s.cost_rub / s.total * 1000:.1f}" if s.total else "",
                        f"{s.seconds:.1f}"])
    print(f"\nCSV: {out.resolve()}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Замер моделей на эталоне из детерминированно найденных ИНН.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    p.add_argument("--prepare", action="store_true", help="собрать кэш страниц и эталон")
    p.add_argument("--run", action="store_true", help="прогнать модели по эталону")
    p.add_argument("--from-serp", type=Path, metavar="CSV")
    p.add_argument("--models", help="список моделей через запятую")
    p.add_argument("--limit", type=int, help="взять только первые N сайтов эталона")
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--max-pages", type=int, default=6)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv(Path(__file__).with_name(".env"))

    if args.prepare:
        if not args.from_serp or not args.from_serp.exists():
            raise SystemExit("Для --prepare нужен --from-serp <csv выгрузки шага 1>")
        hosts, seen = [], set()
        with args.from_serp.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                value = (row.get("host") or row.get("url") or "").strip()
                host = (host_of(value) if "//" in value else value).lower()
                if host and host not in seen:
                    seen.add(host)
                    hosts.append(host)
        prepare(hosts, args.workers, args.max_pages)

    if args.run:
        models = [m.strip() for m in args.models.split(",")] if args.models else DEFAULT_MODELS
        run(models, args.limit)

    if not args.prepare and not args.run:
        p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
