from __future__ import annotations

from typing import Any


def normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def path_allowed(
    path: str,
    allowed_roots: list[str],
    variant_root: str | None = None,
) -> bool:
    current = normalize(path)
    roots = [normalize(root).rstrip("/") for root in allowed_roots if root.strip()]
    if current.startswith("coem/") and variant_root:
        target = normalize(variant_root).rstrip("/")
        return current == target or current.startswith(target + "/")
    return any(current == root or current.startswith(root + "/") for root in roots)


def filter_codegraph_result(
    result: Any,
    allowed_roots: list[str],
    variant_root: str | None = None,
) -> Any:
    if isinstance(result, list):
        return [
            item
            for item in (
                filter_codegraph_result(value, allowed_roots, variant_root)
                for value in result
            )
            if item is not None
        ]
    if not isinstance(result, dict):
        return result

    path = result.get("filePath") or result.get("file_path") or result.get("file")
    if path and not path_allowed(str(path), allowed_roots, variant_root):
        return None

    filtered = dict(result)
    if isinstance(filtered.get("node"), dict):
        node = filter_codegraph_result(
            filtered["node"], allowed_roots, variant_root
        )
        if node is None:
            return None
        filtered["node"] = node
    for key in ("entryPoints", "nodes", "codeBlocks", "results", "affected"):
        if isinstance(filtered.get(key), list):
            filtered[key] = [
                item
                for item in (
                    filter_codegraph_result(value, allowed_roots, variant_root)
                    for value in filtered[key]
                )
                if item is not None
            ]
    if isinstance(filtered.get("affected"), list):
        filtered["nodeCount"] = len(filtered["affected"])
        filtered["scoped"] = True
    if isinstance(filtered.get("relatedFiles"), list):
        filtered["relatedFiles"] = [
            value
            for value in filtered["relatedFiles"]
            if path_allowed(str(value), allowed_roots, variant_root)
        ]
    if isinstance(filtered.get("nodes"), list) and isinstance(
        filtered.get("edges"), list
    ):
        ids = {
            node.get("id")
            for node in filtered["nodes"]
            if isinstance(node, dict)
        }
        filtered["edges"] = [
            edge
            for edge in filtered["edges"]
            if edge.get("source") in ids and edge.get("target") in ids
        ]
    return filtered
