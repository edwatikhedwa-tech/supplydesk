"""Runs the attachment pipeline over inputs.json. It reads ONLY inputs.json and the attachment files.
It never opens ground_truth.json, catalog.py or generate_fixtures.py (the scorer does, afterwards).

  python -m benchmarks.attachment_intelligence.run_pipeline --tag a1 [--no-ai] [--budget 3] [--emails m01,m02]

Output: results/attachments_<tag>.json (per email: per-file analysis, merged lines with matches, AI ledger, timings).
Second invocation with the same --tag re-uses the on-disk cache by content hash: it must make 0 AI calls and 0 OCR runs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent

from mail import attachment_intelligence as AI  # noqa: E402


def load_env_key() -> None:
    if os.getenv("ROUTERAI_KEY"):
        return
    for name in (".env", ".env.local"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.match(r"^\s*ROUTERAI_KEY\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#") and m.group(1).strip("\"'"):
                    os.environ["ROUTERAI_KEY"] = m.group(1).strip("\"'")
                    return
    raise SystemExit("ROUTERAI_KEY is not configured")


class CappedModels:
    """Adds a hard rouble cap on top of the production adapter; records every call."""

    def __init__(self, inner, cap: float, shared=None) -> None:
        self.inner, self.cap, self.spent, self.calls, self.shared = inner, cap, 0.0, 0, shared

    def call(self, stage, system, user, schema):
        if self.spent + (self.shared.spent if self.shared else 0.0) >= self.cap:
            raise SystemExit(f"BUDGET CAP {self.cap} RUB reached after {self.calls} calls - stopped")
        reply = self.inner.call(stage, system, user, schema)
        self.calls += 1
        self.spent += reply.cost_rub or 0.0
        return reply


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--budget", type=float, default=3.0, help="rouble cap for this benchmark (separate from the mail benchmark)")
    ap.add_argument("--model", default="mistralai/mistral-nemo")
    ap.add_argument("--vision-model", default="", help="vision model for pages OCR could not finish (empty = off)")
    ap.add_argument("--no-text-ai", action="store_true", help="do not send OCR rows to a text model (measured: no gain)")
    ap.add_argument("--emails", default="")
    args = ap.parse_args()
    inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    models = text_models = None
    if not args.no_ai:
        load_env_key()
        from backend.integrations.llm.routerai_client import RouterAiClient
        from mail.message_analysis import RouterAiAnalysisModels
        models = CappedModels(RouterAiAnalysisModels(RouterAiClient(), cheap_model=args.model, strong_model=None), args.budget)
        text_models = None if args.no_text_ai else models
    vision = None
    if args.vision_model and models is not None:
        vision = CappedModels(RouterAiAnalysisModels(models.inner.client, cheap_model=args.vision_model, strong_model=None), args.budget, shared=models)
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    cache_path = out_dir / f"attachment_cache_{args.tag}.json"
    repeat = cache_path.exists()          # a second invocation on the same cache is the idempotency check: its report must not overwrite the first
    cache = AI.FileCache(cache_path)
    wanted = set(filter(None, args.emails.split(",")))
    report = {"tag": args.tag, "version": AI.ANALYSIS_VERSION, "emails": [], "totals": {}}
    ai_calls = ocr_pages = cache_hits = analysed = 0
    t0 = time.time()
    for email in inputs["emails"]:
        if wanted and email["email_id"] not in wanted:
            continue
        positions = inputs["requests"][email["request_id"]]["positions"]
        results = []
        for att in email["attachments"]:
            data = (HERE / att["path"]).read_bytes()
            r = AI.analyze_attachment(data, att["filename"], models=text_models, cache=cache, vision=vision)
            results.append(r)
            analysed += 1
            cache_hits += bool(r["cache_hit"])
            ai_calls += len(r["ai_calls"])
            ocr_pages += r["ocr_pages"]
        merged = AI.merge_attachments(results, positions)
        report["emails"].append({"email_id": email["email_id"], "files": [{"path": a["path"], **{k: r[k] for k in (
            "sha256", "status", "kind", "parser", "needs_ocr", "is_quote", "currency", "vat_mode", "delivery_days", "reasons", "manual_review",
            "cache_hit", "latency_ms", "ocr_pages", "ai_calls", "facts", "unparsed")}} for a, r in zip(email["attachments"], results)], "merged": merged})
    report["totals"] = {"attachments": analysed, "cache_hits": cache_hits, "ai_calls": ai_calls, "ocr_pages": ocr_pages,
                        "spent_rub": round((models.spent + (vision.spent if vision else 0.0)), 4) if models else 0.0, "seconds": round(time.time() - t0, 1)}
    (out_dir / (f"attachments_{args.tag}_repeat.json" if repeat else f"attachments_{args.tag}.json")).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["totals"], ensure_ascii=False))


if __name__ == "__main__":
    main()
