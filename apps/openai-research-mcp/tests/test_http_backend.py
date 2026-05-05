from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_mcp.errors import BackendProtocolError, DocumentNotFoundError
from research_mcp.models import AuthContext
from research_mcp.store import HttpSearchFetchBackend


class _BackendHandler(BaseHTTPRequestHandler):
    seen_headers: dict[str, str] = {}

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        return None

    def _send_json(self, status: int, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        _BackendHandler.seen_headers = {key: value for key, value in self.headers.items()}
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/search":
            q = query.get("q", [""])[0]
            if q == "malformed":
                return self._send_json(200, {"results": {"not": "a list"}})
            return self._send_json(
                200,
                {
                    "results": [
                        {
                            "id": "remote-doc",
                            "title": "Remote Canonical Doc",
                            "text": "remote body",
                            "url": "https://example.com/remote#fragment",
                            "metadata": {"source": "remote"},
                        }
                    ]
                },
            )
        if parsed.path == "/fetch":
            document_id = query.get("id", [""])[0]
            if document_id == "missing":
                return self._send_json(404, {"error": "not_found"})
            if document_id == "bad-url":
                return self._send_json(200, {"id": "bad-url", "title": "Bad", "text": "bad", "url": "/relative"})
            return self._send_json(
                200,
                {
                    "id": document_id,
                    "title": "Fetched Remote Doc",
                    "text": "remote fetch body",
                    "url": "https://example.com/fetched#ignored",
                },
            )
        return self._send_json(404, {"error": "not_found"})


class HttpBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _BackendHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def test_search_forwards_identity_headers_and_normalizes_urls(self):
        backend = HttpSearchFetchBackend(self.base_url)
        auth = AuthContext(subject="subject-a", organization="org-a", scopes=("documents:read",))

        docs = backend.search("canonical", limit=5, auth_context=auth)

        self.assertEqual([doc.id for doc in docs], ["remote-doc"])
        self.assertEqual(docs[0].url, "https://example.com/remote")
        self.assertEqual(_BackendHandler.seen_headers.get("X-Subject"), "subject-a")
        self.assertEqual(_BackendHandler.seen_headers.get("X-Organization"), "org-a")
        self.assertEqual(_BackendHandler.seen_headers.get("X-Scopes"), "documents:read")

    def test_fetch_maps_404_to_document_not_found(self):
        backend = HttpSearchFetchBackend(self.base_url)
        with self.assertRaises(DocumentNotFoundError):
            backend.fetch("missing", auth_context=AuthContext(anonymous_read=True))

    def test_search_rejects_malformed_results_payload(self):
        backend = HttpSearchFetchBackend(self.base_url)
        with self.assertRaises(BackendProtocolError):
            backend.search("malformed", limit=5, auth_context=AuthContext(anonymous_read=True))

    def test_fetch_rejects_invalid_canonical_url(self):
        backend = HttpSearchFetchBackend(self.base_url)
        with self.assertRaises(Exception):
            backend.fetch("bad-url", auth_context=AuthContext(anonymous_read=True))


if __name__ == "__main__":
    unittest.main()
