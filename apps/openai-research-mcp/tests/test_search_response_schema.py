from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import build_service


class SearchResponseSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        os.environ["MCP_AUDIT_LOG_PATH"] = str(tmp_path / "events.jsonl")
        os.environ["MCP_STATIC_TOKENS_FILE"] = str(ROOT / "config" / "static_tokens.example.json")
        os.environ["MCP_DOC_JSON_PATH"] = str(ROOT / "data" / "example_documents.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_search_payload_conforms_to_schema(self):
        schema_path = ROOT / "schemas" / "search_response.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        service = build_service()
        payload = service.search_contract("canonical", limit=5, token="reader-token")

        self.assertEqual(set(schema["required"]), {"results"})
        self.assertIn("results", payload)
        self.assertIsInstance(payload["results"], list)
        self.assertTrue(payload["results"], payload)

        if schema.get("additionalProperties") is False:
            self.assertFalse(set(payload.keys()) - set(schema["properties"].keys()), payload)

        item_schema = schema["properties"]["results"]["items"]
        item_required = set(item_schema["required"])
        item_allowed = set(item_schema["properties"].keys())
        for item in payload["results"]:
            self.assertTrue(item_required.issubset(item.keys()), item)
            if item_schema.get("additionalProperties") is False:
                self.assertFalse(set(item.keys()) - item_allowed, item)
            self.assertIsInstance(item["id"], str)
            self.assertIsInstance(item["title"], str)
            self.assertIsInstance(item["url"], str)
            self.assertTrue(item["url"].startswith(("http://", "https://")), item)


if __name__ == "__main__":
    unittest.main()
