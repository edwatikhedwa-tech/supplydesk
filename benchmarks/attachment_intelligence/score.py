"""Scorer: compares results/attachments_<tag>.json with ground_truth.json. Not imported by the pipeline.

  python -m benchmarks.attachment_intelligence.score <tag> [--json]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def toks(s: str) -> set[str]:
    return set(re.findall(r"[a-zа-я0-9]+", (s or "").lower().replace("ё", "е")))


def jacc(a: str, b: str) -> float:
    x, y = toks(a), toks(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def skun(s: str | None) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", (s or "").lower())


def same_price(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= 0.005 * max(1.0, abs(float(b))) if abs(float(b)) >= 100 else abs(float(a) - float(b)) < 0.006


def unit_n(u: str | None) -> str:
    return {"pcs": "шт", "шт.": "шт", "pc": "шт", "м.": "м"}.get((u or "").lower().strip(), (u or "").lower().strip())


def align(truth_lines: list[dict], facts: list[dict]) -> dict[int, dict]:
    """Greedy 1-1 alignment truth line -> extracted fact by (price, qty, name, sku) similarity."""
    cands = []
    for i, t in enumerate(truth_lines):
        for j, f in enumerate(facts):
            sim = max(jacc(t["name"], f["name"]), 1.0 if t["sku"] and skun(t["sku"]) == skun(f.get("sku")) else 0.0)
            if sim < 0.45:
                continue
            score = sim + (1.5 if same_price(f.get("price"), t["price"]) else 0) + (0.5 if f.get("qty") == t["qty"] else 0)
            cands.append((score, i, j))
    used_t, used_f, out = set(), set(), {}
    for score, i, j in sorted(cands, reverse=True):
        if i in used_t or j in used_f:
            continue
        used_t.add(i)
        used_f.add(j)
        out[i] = facts[j]
    return out


def prov_ok(fmt: str, truth_src: dict, loc: dict) -> bool:
    if not loc:
        return False
    if fmt == "xlsx":
        return loc.get("sheet") == truth_src.get("sheet") and loc.get("row") == truth_src.get("row")
    if fmt == "docx":
        return ({k: loc.get(k) for k in ("table", "row")} == truth_src) if "table" in truth_src else loc.get("paragraph") == truth_src.get("paragraph")
    if fmt == "pdf":
        return loc.get("page") == truth_src.get("page") and "bbox" in loc
    return "bbox" in loc and loc.get("page") == truth_src.get("page")


def pct(a: float, b: float) -> str:
    return f"{100 * a / b:.0f}%" if b else "—"


def main(tag: str, as_json: bool = False) -> dict:
    gt = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
    rep = json.loads((ROOT / "results" / f"attachments_{tag}.json").read_text(encoding="utf-8"))
    truth = {f["sha256"]: f for f in gt["files"]}
    res: dict[str, dict] = {}
    email_of: dict[str, dict] = {}
    for e in rep["emails"]:
        for f in e["files"]:
            res.setdefault(f["sha256"], f)
        for ml in e["merged"]["lines"]:
            email_of[(e["email_id"], ml["doc"], ml["loc"].__repr__())] = ml
    merged_by_doc: dict[tuple[str, str], list[dict]] = defaultdict(list)     # (email_id, doc12) -> merged lines
    for e in rep["emails"]:
        for ml in e["merged"]["lines"]:
            merged_by_doc[(e["email_id"], ml["doc"])].append(ml)

    fmt_of = lambda t: {"pdf": "pdf", "scan_pdf": "scan_pdf", "xlsx": "xlsx", "docx": "docx", "png": "image", "jpg": "image"}[t["format"]]
    agg: dict[str, Counter] = defaultdict(Counter)
    cat_agg: dict[str, Counter] = defaultdict(Counter)
    failures: Counter = Counter()
    fail_examples: dict[str, list[str]] = defaultdict(list)
    total = Counter()
    hallucinated: list[str] = []

    def bump(t, key, n=1):
        for a in (agg[fmt_of(t)], cat_agg[t["category"]], total):
            a[key] += n

    for sha, t in truth.items():
        r = res.get(sha)
        if r is None:
            continue
        if not any(t["file"] == f["path"].split("/")[-1] for e in rep["emails"] for f in e["files"]):
            continue
        bump(t, "files")
        bump(t, "parsed", r["status"] == "ok")
        bump(t, "ocr", t["needs_ocr"])
        bump(t, "ai_files", bool(r["ai_calls"]))
        bump(t, "latency_ms", r["latency_ms"] if not r["cache_hit"] else 0)
        bump(t, "ai_cost", sum(c["cost_rub"] or 0 for c in r["ai_calls"]))
        bump(t, "manual", r["manual_review"])
        bump(t, "exp_manual", t["expected_manual_review"] or bool(t["lines_needing_review"]))
        # quote detection
        bump(t, "quote_tp", t["is_quote"] and r["is_quote"] and not t["expected_manual_review"])
        bump(t, "quote_fn", t["is_quote"] and not r["is_quote"] and not t["expected_manual_review"])
        bump(t, "quote_fp", (not t["is_quote"]) and r["is_quote"])
        # manual review detection (doc-level, expected = damaged/unreadable or contains ambiguous lines)
        exp_m = t["expected_manual_review"] or bool(t["lines_needing_review"])
        bump(t, "review_tp", exp_m and r["manual_review"])
        bump(t, "review_fn", exp_m and not r["manual_review"])
        bump(t, "review_fp", (not exp_m) and r["manual_review"])
        if (not exp_m) and r["manual_review"]:
            failures["validator (false review flag)"] += 1
            fail_examples["validator (false review flag)"].append(f"{t['file']} {t['id']}: {','.join(r['reasons'])}")
        if exp_m and not r["manual_review"]:
            failures["validator (missed review)"] += 1
            fail_examples["validator (missed review)"].append(f"{t['file']} {t['id']}")
        # doc-level terms
        if t["is_quote"]:
            bump(t, "vat_n")
            bump(t, "vat_ok", r["vat_mode"] == t["vat_mode"])
            if t["delivery_days"] is not None:
                bump(t, "deliv_n")
                bump(t, "deliv_ok", r["delivery_days"] == t["delivery_days"])
        facts = [f for f in r["facts"]]
        bump(t, "facts", len(facts))
        bump(t, "facts_with_loc", sum(1 for f in facts if f.get("loc")))
        tl = t["lines"]
        pairs = align(tl, facts)
        fm = fmt_of(t)
        base_fmt = "image" if fm == "image" else ("pdf" if fm in ("pdf", "scan_pdf") else fm)
        must = {round(m["value"], 2) for m in t["must_not_extract"]}
        legit_prices = {round(l["price"], 2) for l in tl if l["price"] is not None}
        aligned_f = {id(f) for f in pairs.values()}
        for f in facts:
            if id(f) not in aligned_f:
                bump(t, "unaligned_facts")
                if f.get("price") is not None:
                    bad = round(f["price"], 2) in must and round(f["price"], 2) not in legit_prices
                    hallucinated.append(f"{t['file']} {t['id']}: {f['name'][:40]} price={f['price']} {'MUST-NOT' if bad else 'unaligned'}")
                    bump(t, "hallucinated")
        if t["expected_manual_review"]:
            for f in facts:      # a fact from an unreadable/hard file is fine only if it is right or flagged
                pass
            continue
        for i, l in enumerate(tl):
            bump(t, "lines")
            f = pairs.get(i)
            # a fact the pipeline marked for review is an abstention, not an extraction
            flagged = bool(f and f.get("review") and f["review"] != "price_on_request")
            if f is None or flagged:
                bump(t, "line_missed")
                cls = ("parser" if r["status"] != "ok" or not t["needs_ocr"] else "ocr") if f is None else "validator (arithmetic flag)"
                if f is not None and not t["needs_ocr"]:
                    cls = "validator (arithmetic flag)"
                failures[cls] += 1
                fail_examples[cls].append(f"{t['file']} {t['id']} row {l['source']}: {l['name'][:40]} price={l['price']}")
                continue
            ok_price = same_price(f.get("price"), l["price"])
            ok_qty = f.get("qty") is not None and float(f["qty"]) == float(l["qty"])
            ok_unit = unit_n(f.get("unit")) == unit_n(l["unit"]) or not f.get("unit")
            ok_prod = jacc(l["name"], f["name"]) >= 0.6 or (l["sku"] and skun(l["sku"]) == skun(f.get("sku")))
            bump(t, "prod_ok", bool(ok_prod))
            bump(t, "price_n"); bump(t, "price_ok", ok_price)
            bump(t, "qty_n"); bump(t, "qty_ok", ok_qty)
            bump(t, "unit_n"); bump(t, "unit_ok", ok_unit)
            if l["sku"]:
                bump(t, "sku_n"); bump(t, "sku_ok", skun(f.get("sku")) == skun(l["sku"]))
            if f.get("sku"):
                bump(t, "sku_pred"); bump(t, "sku_pred_ok", bool(l["sku"]) and skun(f["sku"]) == skun(l["sku"]))
            if l["price"] is not None:
                bump(t, "price_pred", f.get("price") is not None); bump(t, "price_truth")
                bump(t, "price_pred_ok", ok_price)
            elif f.get("price") is not None:
                hallucinated.append(f"{t['file']} {t['id']}: invented price {f['price']} for a line without price ({l['name'][:35]})")
                bump(t, "hallucinated")
            if not ok_price:
                cls = "model/prompt (AI row)" if f.get("source") == "ai_cheap" else ("ocr" if t["needs_ocr"] else "parser")
                failures[cls] += 1
                fail_examples[cls].append(f"{t['file']} {t['id']}: {l['name'][:35]} truth={l['price']} got={f.get('price')} review={f.get('review')}")
            full = ok_price and ok_qty and ok_prod
            bump(t, "line_full", full)
            # provenance
            bump(t, "prov_n"); bump(t, "prov_ok", prov_ok(base_fmt if base_fmt != "image" else "img", l["source"], f.get("loc") or {}))
            # position matching
            ml = next((m for m in merged_by_doc.get((next(e["email_id"] for e in rep["emails"] if any(x["sha256"] == sha for x in e["files"])), sha[:12]), [])
                       if m["source_text"] == f["source_text"] and m["loc"] == f["loc"]), None)
            if ml is None:
                continue
            m = ml["match"]
            kind, pid = l["match_kind"], l["matched_pid"]
            st = m["status"]
            if kind == "exact":
                out = "correct" if st == "exact" and m["pid"] == pid else "false_match" if st in ("exact", "analog") else "safe_abstain"
            elif kind == "analog":
                out = "correct" if st == "analog" and m["pid"] == pid else "false_match" if st == "exact" or (st == "analog") else "safe_abstain"
            elif kind == "extra":
                out = "correct" if st == "unmatched" else "false_match" if st in ("exact", "analog") else "safe_abstain"
            else:
                out = "correct" if st == "ambiguous" else "false_match" if st in ("exact", "analog") else "safe_abstain"
            bump(t, "pos_n"); bump(t, f"pos_{out}")
            if out != "correct":
                failures["position matching"] += 1 if out == "false_match" else 0
                fail_examples[f"position {out}"].append(f"{t['file']} {t['id']}: truth={kind}/{pid} got={st}/{m['pid']} ({m['reason']}) :: {l['name'][:45]}")

    # ------------------------------------------------------------------ multi-attachment
    multi = []
    pos_of_email = {e["email_id"]: e for e in gt["emails"]}
    for e in rep["emails"]:
        g = pos_of_email[e["email_id"]]
        if len(g["files"]) < 2:
            continue
        entry = {"email": e["email_id"], "relation": g["relation"], "unique_documents": e["merged"]["unique_documents"],
                 "duplicates": e["merged"]["duplicate_attachments"], "conflicts": len(e["merged"]["conflicts"]),
                 "confirmed": len(e["merged"]["confirmed_by_two_sources"]), "manual_review": e["merged"]["manual_review"]}
        # expected conflicts from truth: exact-matched positions with different prices in different docs
        docs = [truth[f["sha256"]] for f in e["files"]]
        by_pid: dict[str, set] = defaultdict(set)
        for d in docs:
            for l in d["lines"]:
                if l["match_kind"] == "exact" and l["price"] is not None:
                    by_pid[l["matched_pid"]].add((d["sha256"], round(l["price"] / l["price_per"], 4)))
        exp_conf = {p for p, s in by_pid.items() if len({x[0] for x in s}) > 1 and (max(x[1] for x in s) - min(x[1] for x in s)) > 0.005 * max(x[1] for x in s)}
        got_conf = {c["pid"] for c in e["merged"]["conflicts"]}
        entry.update({"expected_conflicts": len(exp_conf), "conflict_tp": len(exp_conf & got_conf), "conflict_fp": len(got_conf - exp_conf), "conflict_fn": len(exp_conf - got_conf)})
        multi.append(entry)

    # ------------------------------------------------------------------ output
    def row(name: str, c: Counter) -> list[str]:
        ex_n = c["lines"]
        return [name, str(c["files"]), pct(c["parsed"], c["files"]), str(c["ocr"]), str(c["ai_files"]),
                pct(c["line_full"], ex_n), pct(c["pos_correct"], c["pos_n"]), str(c["manual"]),
                f"{c['latency_ms'] / max(1, c['files']):.0f} ms", f"{c['ai_cost'] / max(1, c['files']):.4f} ₽"]

    header = "| format | files | parsed | OCR required | AI required | extraction accuracy | position-match accuracy | manual review | avg latency | avg AI cost |\n|---|---|---|---|---|---|---|---|---|---|\n"
    lines = [header + "\n".join("| " + " | ".join(row(k, v)) + " |" for k, v in sorted(agg.items())) + "\n" + "| " + " | ".join(row("ALL", total)) + " |"]
    lines.append("\n**by category**\n\n" + header + "\n".join("| " + " | ".join(row(k, v)) + " |" for k, v in sorted(cat_agg.items())))
    T = total
    metrics = {
        "parsing_success": pct(T["parsed"], T["files"]),
        "quote_detection_precision": pct(T["quote_tp"], T["quote_tp"] + T["quote_fp"]), "quote_detection_recall": pct(T["quote_tp"], T["quote_tp"] + T["quote_fn"]),
        "product_extraction": pct(T["prod_ok"], T["lines"]),
        "sku_precision": pct(T["sku_pred_ok"], T["sku_pred"]), "sku_recall": pct(T["sku_ok"], T["sku_n"]),
        "price_precision": pct(T["price_pred_ok"], T["price_pred"]), "price_recall": pct(T["price_pred_ok"], T["price_truth"]),
        "qty_accuracy": pct(T["qty_ok"], T["qty_n"]), "unit_accuracy": pct(T["unit_ok"], T["unit_n"]),
        "vat_accuracy": pct(T["vat_ok"], T["vat_n"]), "delivery_date_accuracy": pct(T["deliv_ok"], T["deliv_n"]),
        "position_matching_correct": pct(T["pos_correct"], T["pos_n"]), "position_false_match": pct(T["pos_false_match"], T["pos_n"]), "position_safe_abstain": pct(T["pos_safe_abstain"], T["pos_n"]),
        "provenance_coverage": pct(T["facts_with_loc"], T["facts"]), "provenance_correct_locator": pct(T["prov_ok"], T["prov_n"]),
        "hallucinated_facts": T["hallucinated"], "manual_review_precision": pct(T["review_tp"], T["review_tp"] + T["review_fp"]), "manual_review_recall": pct(T["review_tp"], T["review_tp"] + T["review_fn"]),
        "extraction_full_line_accuracy": pct(T["line_full"], T["lines"]), "lines_missed_or_flagged": T["line_missed"],
    }
    out = {"tag": tag, "totals": rep["totals"], "metrics": metrics, "failures": dict(failures), "multi_attachment": multi, "tables": lines,
           "hallucinated": hallucinated, "examples": {k: v[:12] for k, v in fail_examples.items()}}
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("\n".join(lines))
        print("\nMETRICS\n" + "\n".join(f"  {k}: {v}" for k, v in metrics.items()))
        print("\nFAILURES", dict(failures))
        print("\nMULTI-ATTACHMENT\n" + "\n".join("  " + json.dumps(m, ensure_ascii=False) for m in multi))
        print("\nHALLUCINATED", len(hallucinated))
        for h in hallucinated[:15]:
            print("  ", h)
        for k, v in fail_examples.items():
            print(f"\n[{k}] {len(v)}")
            for x in v[:10]:
                print("   ", x)
    return out


if __name__ == "__main__":
    main(sys.argv[1], "--json" in sys.argv)
