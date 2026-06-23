from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from traceability.scope_filter import filter_codegraph_result, path_allowed


class ScopeFilterTests(unittest.TestCase):
    def test_variant_filter(self) -> None:
        roots = ["coem/TARGET_VARIANT", "asw", "adas"]
        self.assertTrue(
            path_allowed(
                "coem/TARGET_VARIANT/a.c", roots, "coem/TARGET_VARIANT"
            )
        )
        self.assertFalse(
            path_allowed("coem/OTHER/a.c", roots, "coem/TARGET_VARIANT")
        )
        self.assertTrue(
            path_allowed("asw/common.c", roots, "coem/TARGET_VARIANT")
        )

    def test_context_filter(self) -> None:
        source = {
            "nodes": [
                {"id": "a", "filePath": "coem/TARGET_VARIANT/a.c"},
                {"id": "b", "filePath": "coem/OTHER/b.c"},
            ],
            "edges": [{"source": "a", "target": "b", "kind": "calls"}],
            "relatedFiles": [
                "coem/TARGET_VARIANT/a.c",
                "coem/OTHER/b.c",
            ],
        }
        filtered = filter_codegraph_result(
            source,
            ["coem/TARGET_VARIANT", "asw"],
            "coem/TARGET_VARIANT",
        )
        self.assertEqual([node["id"] for node in filtered["nodes"]], ["a"])
        self.assertEqual(filtered["edges"], [])
        self.assertEqual(
            filtered["relatedFiles"], ["coem/TARGET_VARIANT/a.c"]
        )

    def test_query_result_filter(self) -> None:
        source = [
            {"node": {"id": "a", "filePath": "coem/TARGET_VARIANT/a.c"}},
            {"node": {"id": "b", "filePath": "coem/OTHER/b.c"}},
        ]
        filtered = filter_codegraph_result(
            source,
            ["coem/TARGET_VARIANT", "asw"],
            "coem/TARGET_VARIANT",
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["node"]["id"], "a")

    def test_impact_filter(self) -> None:
        source = {
            "affected": [
                {"name": "a", "filePath": "coem/TARGET_VARIANT/a.c"},
                {"name": "b", "filePath": "coem/OTHER/b.c"},
            ],
            "nodeCount": 2,
        }
        filtered = filter_codegraph_result(
            source,
            ["coem/TARGET_VARIANT", "asw"],
            "coem/TARGET_VARIANT",
        )
        self.assertEqual(len(filtered["affected"]), 1)
        self.assertEqual(filtered["nodeCount"], 1)
        self.assertTrue(filtered["scoped"])


if __name__ == "__main__":
    unittest.main()
