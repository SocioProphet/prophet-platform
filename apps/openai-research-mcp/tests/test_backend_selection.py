from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_mcp.errors import InvalidInputError
from research_mcp.store import HttpSearchFetchBackend, InMemoryDocumentBackend
from server import build_backend, doctor_payload


class BackendSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._old_env = dict(os.environ)
        os.environ["MCP_AUDIT_LOG_PATH"] = str(Path(self.tmp.name) / "events.jsonl")
        os.environ["MCP_STATIC_TOKENS_FILE"] = str(ROOT / "config" / "static_tokens.example.json")
        os.environ["MCP_DOC_JSON_PATH"] = str(ROOT / "data" / "example_documents.json")
        os.environ.pop("MCP_BACKEND_MODE", None)
        os.environ.pop("MCP_HTTP_BACKEND_URL", None)
        os.environ.pop("MCP_HTTP_BACKEND_TIMEOUT_SECONDS", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)
        self.tmp.cleanup()

    def test_default_backend_mode_is_memory(self):
        backend = build_backend()
        self.assertIsInstance(backend, InMemoryDocumentBackend)

    def test_http_backend_mode_requires_backend_url(self):
        os.environ["MCP_BACKEND_MODE"] = "http"
        with self.assertRaises(InvalidInputError):
            build_backend()

    def test_http_backend_mode_builds_http_backend(self):
        os.environ["MCP_BACKEND_MODE"] = "http"
        os.environ["MCP_HTTP_BACKEND_URL"] = "https://retrieval.example.test"
        os.environ["MCP_HTTP_BACKEND_TIMEOUT_SECONDS"] = "2.5"

        backend = build_backend()

        self.assertIsInstance(backend, HttpSearchFetchBackend)
        self.assertEqual(backend.base_url, "https://retrieval.example.test")
        self.assertEqual(backend.timeout_seconds, 2.5)

    def test_unknown_backend_mode_is_rejected(self):
        os.environ["MCP_BACKEND_MODE"] = "sqlite"
        with self.assertRaises(InvalidInputError):
            build_backend()

    def test_doctor_reports_backend_mode_without_building_backend(self):
        os.environ["MCP_BACKEND_MODE"] = "http"
        os.environ.pop("MCP_HTTP_BACKEND_URL", None)

        payload = doctor_payload()

        self.assertEqual(payload["backend_mode"], "http")
        self.assertFalse(payload["http_backend_configured"])
        self.assertTrue(payload["bundle_integrity"]["ok"])


if __name__ == "__main__":
    unittest.main()
