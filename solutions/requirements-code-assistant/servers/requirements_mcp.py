from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from traceability.mcp_stdio import StdioMcpServer
from traceability.requirements_store import RequirementStore


def main() -> None:
    vault = os.environ.get("REQUIREMENTS_VAULT")
    if not vault:
        raise SystemExit("REQUIREMENTS_VAULT is required")
    store = RequirementStore(vault)
    server = StdioMcpServer("requirements-traceability", "1.0.0")
    server.add_tool(
        "requirements_search",
        "Search atomic requirements by natural language and optional feature.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "feature": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["query"],
        },
        lambda args: store.search(
            args["query"], args.get("feature"), int(args.get("limit", 10))
        ),
    )
    server.add_tool(
        "requirements_get",
        "Get one complete atomic requirement by stable requirement ID.",
        {
            "type": "object",
            "properties": {"requirement_id": {"type": "string"}},
            "required": ["requirement_id"],
        },
        lambda args: store.get(args["requirement_id"]) or {
            "error": "requirement_not_found",
            "requirement_id": args["requirement_id"],
        },
    )
    server.add_tool(
        "requirements_list_features",
        "List features represented in the requirement vault.",
        {"type": "object", "properties": {}},
        lambda _args: store.list_features(),
    )
    server.add_tool(
        "requirements_validate",
        "Validate note metadata, JSON blocks, and unique requirement IDs.",
        {"type": "object", "properties": {}},
        lambda _args: store.validate(),
    )
    server.run()


if __name__ == "__main__":
    main()

