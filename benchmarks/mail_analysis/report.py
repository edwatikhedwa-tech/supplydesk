"""Render a benchmark JSON (results/mail_analysis_benchmark_<tag>.json) as tables. No letter bodies are printed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def main(tag: str) -> None:
    d = json.loads((ROOT / "results" / f"mail_analysis_benchmark_{tag}.json").read_text(encoding="utf-8"))
    s = d["summary"]
    print(f"== {tag}: models {s['models']}  letters {s['letters']} (disputed {s['disputed']})  {s['seconds']}s  spend {s['spend_rub']}  stopped={s['stopped']!r}")
    hdr = f"{'type':20s} {'n':>3s} {'noAI':>4s} {'cheap':>5s} {'strong':>6s} {'manual':>6s} {'ok':>3s} {'bad':>3s} {'disp':>4s} {'tok':>6s} {'rub':>8s} {'lat s':>6s}"
    print(hdr)
    for cat, c in s["categories"].items():
        print(f"{cat:20s} {c['n']:3d} {c['no_ai']:4d} {c['cheap_only']:5d} {c['strong']:6d} {c['manual']:6d} {c['correct']:3d} {c['incorrect']:3d} "
              f"{c['disputed']:4d} {c['avg_tokens']:6.0f} {c['avg_cost']:8.5f} {c['avg_latency_ms'] / 1000:6.1f}")
    print("cascade", s["cascade"])
    print("ai_necessity", s["ai_necessity"])
    q = s["quality"]
    print(f"classification {q['classification']['correct']}/{q['classification']['of']}  request_matching {q['request_matching']['correct']}/{q['request_matching']['of']}")
    for k in ("quote_detection", "price_extraction", "sku_extraction"):
        v = q[k]
        print(f"{k:17s} tp={v['tp']} fp={v['fp']} fn={v['fn']} precision={pct(v['precision'])} recall={pct(v['recall'])}")
    print("cost", {k: (round(v, 5) if isinstance(v, float) else v) for k, v in s["cost"].items()})
    print("idempotency", json.dumps(s["idempotency"]))
    print("judge", s["judge"])
    bad = [r for r in d["rows"] if not r["disputed"] and not (r["cls_ok"] and r["items_ok"] and r["link_ok"])]
    print(f"-- incorrect letters ({len(bad)}):")
    for r in bad:
        print(f"  {r['id']:4s} {r['cat']:18s} cls {r['expected']['cls']}->{r['actual']['cls']} items_ok={r['items_ok']} link_ok={r['link_ok']} "
              f"stage={r['actual']['stage'] if 'stage' in r['actual'] else ''} runs={r['run_statuses']} detail={r['run_details'][:1]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "baseline")
