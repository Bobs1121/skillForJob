from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], Any]


class StdioMcpServer:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.tools: dict[str, tuple[dict[str, Any], ToolHandler]] = {}
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

    def add_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        self.tools[name] = ({
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }, handler)

    def _send(self, payload: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    @staticmethod
    def _content(value: Any, is_error: bool = False) -> dict[str, Any]:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(value, ensure_ascii=False, indent=2),
            }],
            "isError": is_error,
        }

    def _handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        definition for definition, _ in self.tools.values()
                    ]
                },
            }
        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            if name not in self.tools:
                result = self._content({"error": f"unknown tool: {name}"}, True)
            else:
                try:
                    value = self.tools[name][1](params.get("arguments") or {})
                    result = self._content(value)
                except Exception as exc:
                    result = self._content({
                        "error": type(exc).__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(limit=5),
                    }, True)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def run(self) -> None:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                response = self._handle(json.loads(line))
            except Exception as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": str(exc)},
                }
            if response is not None:
                self._send(response)

