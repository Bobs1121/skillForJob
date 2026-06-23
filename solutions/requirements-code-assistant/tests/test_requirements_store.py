from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from traceability.requirements_store import RequirementStore


class RequirementStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = RequirementStore(ROOT / "templates" / "vault")

    def test_valid_template(self) -> None:
        result = self.store.validate()
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["parsed_requirements"], 1)

    def test_get_and_search(self) -> None:
        item = self.store.get("EXAMPLE-FEATURE-001")
        self.assertIsNotNone(item)
        self.assertEqual(item["conditions"]["example_threshold"], 1.0)
        results = self.store.search("example threshold")
        self.assertEqual(results[0]["requirement_id"], "EXAMPLE-FEATURE-001")


if __name__ == "__main__":
    unittest.main()

