from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from supplier_discovery_v2.pipeline import run_pipeline
    from supplier_discovery_v2.query_planner import load_positions
else:
    from .pipeline import run_pipeline
    from .query_planner import load_positions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Изолированный поиск релевантных поставщиков и публичных контактов.")
    parser.add_argument("--key", help="ключ/позиция пользователя")
    parser.add_argument("--request", type=Path, help="JSON заявки или позиции")
    parser.add_argument("--quantity")
    parser.add_argument("--region")
    parser.add_argument("--description")
    parser.add_argument("--max-serp-queries", type=int, default=3)
    parser.add_argument("--max-direct-sites", type=int, default=8)
    parser.add_argument("--catalog-limit", type=int, default=2)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "out")
    parser.add_argument("--db", type=Path, default=Path(__file__).resolve().parent / "data" / "discovery.sqlite3")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="только планирование, без сети")
    mode.add_argument("--dry-run", action="store_true", help="планирование с явным dry-run, без сети")
    mode.add_argument("--live", action="store_true", help="разрешить ограниченный read-only live-прогон")
    args = parser.parse_args(argv)
    try:
        positions = load_positions(args.request, args.key, args.quantity, args.region, args.description)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    selected_mode = "live" if args.live else "dry-run" if args.dry_run else "plan"
    report = run_pipeline(positions, selected_mode, args.out_dir, args.db, args.max_serp_queries, args.max_direct_sites, args.catalog_limit)
    print(json.dumps({"mode": report.get("mode"), "stats": report.get("stats", {}), "out_dir": str(args.out_dir), "db": str(args.db), "writes_to_current_system": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
