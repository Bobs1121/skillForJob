#!/usr/bin/env python3
"""Validate a cr60-analysis-intake.v1 handoff and emit intake-manifest.v1.

The bridge deliberately does not connect to SSH, inspect a bag, or resolve a
source branch. It only normalizes the upstream contract for the deterministic
cr60-debug-harness CLI, preserving every remote path and source selector.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping


HANDOFF_SCHEMA = "cr60-analysis-intake.v1"
MANIFEST_SCHEMA = "intake-manifest.v1"


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned or "case-unknown"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _file_stem(path: str) -> str:
    name = path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def _bag_items(case: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    raw_items = case.get("bag_paths")
    if raw_items is None:
        raw_items = case.get("files")
    if raw_items is None and case.get("bag"):
        raw_items = [case.get("bag")]

    items: list[tuple[str, dict[str, Any]]] = []
    for item in _as_list(raw_items):
        if isinstance(item, str):
            path = item.strip()
            metadata: dict[str, Any] = {}
        elif isinstance(item, Mapping):
            path = str(item.get("path") or item.get("bag") or "").strip()
            metadata = dict(item)
        else:
            path = ""
            metadata = {}
        if path:
            items.append((path, metadata))
    return items


def convert_handoff(
    payload: Mapping[str, Any],
    *,
    source_path: str = "",
    allow_partial: bool = False,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Return ``manifest, errors, warnings`` without touching external state."""
    errors: list[str] = []
    warnings: list[str] = []
    if str(payload.get("schema_version", "")) != HANDOFF_SCHEMA:
        errors.append(
            f"unsupported handoff schema: expected {HANDOFF_SCHEMA}, "
            f"got {payload.get('schema_version', 'missing')}"
        )

    status = str(payload.get("status", "ready"))
    if status == "blocked":
        errors.append("handoff status is blocked; repair upstream inputs before analysis")
    if status == "partial" and not allow_partial:
        errors.append("handoff status is partial; rerun with --allow-partial after user approval")
    if status not in {"ready", "partial", "blocked"}:
        warnings.append(f"unknown handoff status preserved as {status!r}")

    environment = payload.get("environment")
    data = payload.get("data")
    if not isinstance(environment, Mapping):
        errors.append("handoff.environment must be an object")
        environment = {}
    if not isinstance(data, Mapping):
        errors.append("handoff.data must be an object")
        data = {}

    server = environment.get("server")
    arbe = environment.get("arbe")
    if not isinstance(server, Mapping) or not str(server.get("host", "")).strip():
        warnings.append("environment.server.host is missing; the downstream profile must supply it")
    if not isinstance(arbe, Mapping) or not str(arbe.get("workspace", "")).strip():
        warnings.append("environment.arbe.workspace is missing; source-context matching may be blocked")

    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        errors.append("handoff.data.cases must be a non-empty list")
        raw_cases = []

    manifest_cases: list[dict[str, Any]] = []
    used_ids: dict[str, int] = {}
    for case_index, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, Mapping):
            errors.append(f"data.cases[{case_index}] must be an object")
            continue
        base_id = _safe_id(str(raw_case.get("case_id") or raw_case.get("tr_id") or ""))
        bag_items = _bag_items(raw_case)
        if not bag_items:
            errors.append(f"data.cases[{case_index}] has no bag_paths/files/bag")
            continue

        functions = raw_case.get("functions_hint", raw_case.get("functions", []))
        if isinstance(functions, str):
            functions = [functions]
        if not isinstance(functions, list):
            warnings.append(f"{base_id}: functions hint is not a list; discarded")
            functions = []

        for bag_index, (bag_path, file_metadata) in enumerate(bag_items):
            candidate_id = base_id
            if len(bag_items) > 1:
                candidate_id = _safe_id(f"{base_id}__{_file_stem(bag_path)}")
            used_ids[candidate_id] = used_ids.get(candidate_id, 0) + 1
            if used_ids[candidate_id] > 1:
                candidate_id = f"{candidate_id}__{used_ids[candidate_id]}"

            suffix = Path(bag_path.replace("\\", "/")).suffix.lower()
            if suffix and suffix != ".bag":
                warnings.append(f"{candidate_id}: {suffix} is preserved and will be marked unsupported by Sprint1")

            manifest_cases.append(
                {
                    "case_id": candidate_id,
                    "parent_case_id": str(raw_case.get("case_id") or raw_case.get("tr_id") or candidate_id),
                    "tr_id": raw_case.get("tr_id"),
                    "bag": bag_path,
                    "format": file_metadata.get("format") or suffix.lstrip("."),
                    "size_bytes": file_metadata.get("size_bytes"),
                    "sha256": file_metadata.get("sha256"),
                    "functions": list(functions),
                    "customer_claim": raw_case.get("customer_claim", ""),
                    "preferred_radar": raw_case.get("preferred_radar", "auto"),
                    "source_selector": dict(raw_case.get("source_selector", {}) or {}),
                    "upstream_provenance": {
                        "handoff_id": payload.get("handoff_id", ""),
                        "handoff_path": source_path,
                        "case_index": case_index,
                        "bag_index": bag_index,
                        "data_dir": raw_case.get("data_dir", ""),
                        "file_metadata": file_metadata,
                    },
                }
            )

    if errors:
        return None, errors, warnings

    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "source_kind": "cr60-analysis-intake.v1",
        "upstream_handoff": {
            "schema_version": payload.get("schema_version"),
            "handoff_id": payload.get("handoff_id", ""),
            "status": status,
            "path": source_path,
        },
        "upstream_environment": dict(environment),
        "data_root": data.get("root", ""),
        "cases": manifest_cases,
    }
    return manifest, errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", help="cr60-analysis-intake.v1 JSON")
    parser.add_argument("--output-manifest", required=True, help="output intake-manifest.v1 JSON")
    parser.add_argument("--allow-partial", action="store_true", help="consume a partial handoff after explicit user approval")
    args = parser.parse_args()

    handoff_path = Path(args.handoff)
    try:
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "errors": [f"cannot read handoff: {exc}"]}, ensure_ascii=False))
        return 2
    if not isinstance(payload, Mapping):
        print(json.dumps({"status": "error", "errors": ["handoff root must be a JSON object"]}, ensure_ascii=False))
        return 2

    manifest, errors, warnings = convert_handoff(
        payload,
        source_path=str(handoff_path.resolve()),
        allow_partial=bool(args.allow_partial),
    )
    if errors or manifest is None:
        print(json.dumps({"status": "error", "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
        return 2

    output_path = Path(args.output_manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ready_with_warnings" if warnings else "ready",
                "output_manifest": str(output_path.resolve()),
                "case_count": len(manifest["cases"]),
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
