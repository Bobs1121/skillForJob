from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from traceability.mcp_stdio import StdioMcpServer
from traceability.scope_filter import filter_codegraph_result


REPO = Path(os.environ.get("CODE_REPO", ".")).expanduser().resolve()
COMMAND = os.environ.get("CODEGRAPH_CMD", "codegraph")
ALLOWED_ROOTS = [
    item.strip()
    for item in os.environ.get(
        "CODE_ALLOWED_ROOTS",
        "coem/TARGET_VARIANT,asw,adas,integration,rte,mmwave",
    ).split(",")
    if item.strip()
]
VARIANT_ROOT = os.environ.get(
    "CODE_VARIANT_ROOT", "coem/TARGET_VARIANT"
).strip() or None


def _command_prefix() -> list[str]:
    parts = shlex.split(COMMAND, posix=os.name != "nt")
    if len(parts) == 1 and parts[0].lower().endswith(".ps1"):
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            parts[0],
        ]
    return parts


def run_codegraph(args: list[str]) -> Any:
    completed = subprocess.run(
        _command_prefix() + args,
        cwd=REPO,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    output = completed.stdout.strip()
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return {"text": output}
    return filter_codegraph_result(parsed, ALLOWED_ROOTS, VARIANT_ROOT)


def query(args: dict[str, Any]) -> Any:
    command = [
        "query",
        args["search"],
        "-p",
        str(REPO),
        "-j",
        "-l",
        str(args.get("limit", 20)),
    ]
    if args.get("kind"):
        command.extend(["-k", args["kind"]])
    return run_codegraph(command)


def relation(command_name: str, args: dict[str, Any]) -> Any:
    command = [
        command_name,
        args["symbol"],
        "-p",
        str(REPO),
        "-j",
    ]
    if command_name == "impact":
        command.extend(["-d", str(args.get("depth", 2))])
    else:
        command.extend(["-l", str(args.get("limit", 20))])
    return run_codegraph(command)


def context(args: dict[str, Any]) -> Any:
    return run_codegraph([
        "context",
        args["task"],
        "-p",
        str(REPO),
        "--max-nodes",
        str(args.get("max_nodes", 30)),
        "--max-code",
        str(args.get("max_code", 8)),
        "--format",
        "json",
    ])


def main() -> None:
    server = StdioMcpServer("scoped-codegraph", "1.0.0")
    server.add_tool(
        "code_search",
        "Search code symbols and keep only paths allowed for the target product.",
        {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "kind": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["search"],
        },
        query,
    )
    for tool, command_name in (
        ("code_callers", "callers"),
        ("code_callees", "callees"),
        ("code_impact", "impact"),
    ):
        server.add_tool(
            tool,
            f"Run CodeGraph {command_name} analysis in the product scope.",
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "depth": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["symbol"],
            },
            lambda args, selected=command_name: relation(selected, args),
        )
    server.add_tool(
        "code_context",
        "Build task context and remove files outside the product scope.",
        {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "max_nodes": {"type": "integer", "minimum": 1, "maximum": 200},
                "max_code": {"type": "integer", "minimum": 0, "maximum": 50},
            },
            "required": ["task"],
        },
        context,
    )
    server.run()


if __name__ == "__main__":
    main()
