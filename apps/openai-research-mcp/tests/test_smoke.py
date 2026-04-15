from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_mcp.bundle import bundle_integrity_report
from server import build_service


class SmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["MCP_AUDIT_LOG_PATH"] = str(Path(self.tmp.name) / "events.jsonl")
        os.environ["MCP_STATIC_TOKENS_FILE"] = str(ROOT / "config" / "static_tokens.example.json")
        os.environ["MCP_DOC_JSON_PATH"] = str(ROOT / "data" / "example_documents.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bundle_ok(self):
        report = bundle_integrity_report(ROOT)
        self.assertTrue(report["ok"], report)

    def test_search_and_fetch(self):
        service = build_service()
        search = service.search_contract("canonical", limit=5, token="reader-token")
        self.assertEqual(search["results"][0]["id"], "doc-citations-001")
        fetch = service.fetch_contract("doc-citations-001", token="reader-token")
        self.assertEqual(fetch["id"], "doc-citations-001")

    def test_export_requires_scope(self):
        service = build_service()
        with self.assertRaises(Exception):
            service.export_report_handoff("t", "n", ["doc-citations-001"], token="reader-token")
        payload = service.export_report_handoff("t", "n", ["doc-citations-001"], token="export-token")
        self.assertIn("artifact_id", payload)

    def test_cli_verify(self):
        out = subprocess.check_output([sys.executable, "server.py", "verify-bundle"], cwd=ROOT)
        data = json.loads(out)
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()