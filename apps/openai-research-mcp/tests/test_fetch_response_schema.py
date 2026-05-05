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


class FetchResponseSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        os.environ["MCP_AUDIT_LOG_PATH"] = str(tmp_path / "events.jsonl")
        os.environ["MCP_STATIC_TOKENS_FILE"] = str(ROOT / "config" / "static_tokens.example.json")
        os.environ["MCP_DOC_JSON_PATH"] = str(ROOT / "data" / "example_documents.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_fetch_payload_conforms_to_schema(self):
        schema_path = ROOT / "schemas" / "fetch_response.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        service = build_service()
        payload = service.fetch_contract("doc-citations-001", token="reader-token")

        required = set(schema["required"])
        self.assertTrue(required.issubset(payload.keys()), payload)

        allowed = set(schema["properties"].keys())
        if schema.get("additionalProperties") is False:
            self.assertFalse(set(payload.keys()) - allowed, payload)

        self.assertIsInstance(payload["id"], str)
        self.assertIsInstance(payload["title"], str)
        self.assertIsInstance(payload["text"], str)
        self.assertIsInstance(payload["url"], str)
        self.assertTrue(payload["url"].startswith(("http://", "https://")), payload)
        if "metadata" in payload:
            self.assertIsInstance(payload["metadata"], dict)


if __name__ == "__main__":
    unittest.main()
