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


class ArtifactHandoffSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        os.environ["MCP_AUDIT_LOG_PATH"] = str(tmp_path / "events.jsonl")
        os.environ["MCP_STATIC_TOKENS_FILE"] = str(ROOT / "config" / "static_tokens.example.json")
        os.environ["MCP_DOC_JSON_PATH"] = str(ROOT / "data" / "example_documents.json")
        os.environ.pop("MCP_PUBLIC_ARTIFACT_BASE_URL", None)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_export_payload_conforms_to_artifact_handoff_schema(self):
        schema_path = ROOT / "schemas" / "artifact_handoff.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        service = build_service()
        payload = service.export_report_handoff(
            "Schema-backed artifact handoff",
            "Validate the public artifact handoff payload shape.",
            ["doc-citations-001"],
            token="export-token",
        )

        required = set(schema["required"])
        self.assertTrue(required.issubset(payload.keys()), payload)

        allowed = set(schema["properties"].keys())
        if schema.get("additionalProperties") is False:
            self.assertFalse(set(payload.keys()) - allowed, payload)

        self.assertIsInstance(payload["artifact_id"], str)
        self.assertIsInstance(payload["object_key"], str)
        self.assertIsInstance(payload["sha256"], str)
        self.assertIsInstance(payload["manifest_object_key"], str)
        self.assertNotIn("local_path", payload)


if __name__ == "__main__":
    unittest.main()
