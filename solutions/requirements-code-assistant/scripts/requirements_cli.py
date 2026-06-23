from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from traceability.requirements_store import RequirementStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    get_parser = sub.add_parser("get")
    get_parser.add_argument("requirement_id")
    search_parser = sub.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--feature")
    search_parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    store = RequirementStore(args.vault)
    if args.command == "list":
        result = [
            {
                "requirement_id": record.data.get("requirement_id"),
                "feature": record.data.get("feature"),
                "kind": record.data.get("kind"),
                "_note": record.path.relative_to(store.vault).as_posix(),
            }
            for record in store.records()
        ]
    elif args.command == "get":
        result = store.get(args.requirement_id) or {
            "error": "requirement_not_found",
            "requirement_id": args.requirement_id,
        }
    else:
        result = store.search(args.query, args.feature, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

