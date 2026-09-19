"""EDW-21: minimal review workflow for suspected duplicate suppliers (no UI needed).

    python scripts/merge_review.py --db PATH --owner EMAIL scan          # fill the queue (changes no supplier data)
    python scripts/merge_review.py --db PATH --owner EMAIL list [--status pending]
    python scripts/merge_review.py --db PATH --owner EMAIL show ID       # both cards, evidence, what would move
    python scripts/merge_review.py --db PATH --owner EMAIL decide ID merge|reject|later|undo [--confirm-unknown-inn]

Opening the database applies pending migrations (the same thing the app does on start). Nothing is merged
unless you run `decide ID merge`; every merge is reversible with `decide ID undo`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mail.repository import MailRepository  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=ROOT / "mail-data" / "supplier.sqlite3")
    ap.add_argument("--owner", required=True, help="Email владельца рабочего пространства.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    p_list = sub.add_parser("list")
    p_list.add_argument("--status")
    p_show = sub.add_parser("show")
    p_show.add_argument("id", type=int)
    p_dec = sub.add_parser("decide")
    p_dec.add_argument("id", type=int)
    p_dec.add_argument("decision", choices=["merge", "reject", "later", "undo"])
    p_dec.add_argument("--confirm-unknown-inn", action="store_true")
    args = ap.parse_args(argv)

    repo = MailRepository(args.db)
    with repo.connect() as c:
        user = c.execute(
            """SELECT u.id, wm.workspace_id FROM users u JOIN workspace_members wm ON wm.user_id=u.id
               WHERE LOWER(u.email)=LOWER(?) AND wm.role='owner' ORDER BY wm.workspace_id LIMIT 1""", (args.owner,)).fetchone()
    if not user:
        print("Пользователь не найден.", file=sys.stderr)
        return 2
    ws, uid = int(user["workspace_id"]), int(user["id"])
    try:
        if args.cmd == "scan":
            out = repo.register_merge_candidates(ws)
        elif args.cmd == "list":
            out = repo.list_merge_candidates(ws, status=args.status)
        elif args.cmd == "show":
            out = repo.get_merge_review(ws, args.id)
        else:
            out = repo.decide_merge_candidate(ws, uid, args.id, args.decision, confirm_unknown_inn=args.confirm_unknown_inn)
    except ValueError as exc:
        print(f"Отказ: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
