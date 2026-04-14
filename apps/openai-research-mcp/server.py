from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from research_mcp import APP_NAME, __version__
from research_mcp.artifacts import LocalDirectoryObjectStore, MarkdownArtifactExporter
from research_mcp.audit import JsonlAuditSink
from research_mcp.auth import StaticTokenAuthorizer, load_static_tokens
from research_mcp.bundle import bundle_integrity_report
from research_mcp.errors import ResearchMcpError
from research_mcp.service import ResearchService
from research_mcp.store import InMemoryDocumentBackend, load_documents_from_json

ROOT = Path(__file__).resolve().parent


def build_service() -> ResearchService:
    docs_path = Path(os.environ.get("MCP_DOC_JSON_PATH", str(ROOT / "data" / "example_documents.json")))
    docs = load_documents_from_json(docs_path)
    tokens_path = Path(os.environ.get("MCP_STATIC_TOKENS_FILE", str(ROOT / "config" / "static_tokens.example.json")))
    authorizer = StaticTokenAuthorizer(
        load_static_tokens(tokens_path),
        allow_anonymous_read=os.environ.get("MCP_ALLOW_ANONYMOUS_READ", "true").lower() in {"1", "true", "yes"},
    )
    audit_path = Path(os.environ.get("MCP_AUDIT_LOG_PATH", str(ROOT / "var" / "audit" / "events.jsonl")))
    object_store = LocalDirectoryObjectStore(
        ROOT / "var" / "artifacts" / "reports",
        public_base_url=os.environ.get("MCP_PUBLIC_ARTIFACT_BASE_URL"),
    )
    return ResearchService(
        backend=InMemoryDocumentBackend(docs),
        authorizer=authorizer,
        audit_sink=JsonlAuditSink(audit_path),
        exporter=MarkdownArtifactExporter(object_store),
    )


def dump(payload):
    return json.dumps(payload, indent=2, sort_keys=True)


def doctor_payload():
    return {
        "app_name": APP_NAME,
        "version": __version__,
        "bundle_integrity": bundle_integrity_report(ROOT),
        "expected_fixture_docs": str(ROOT / "data" / "example_documents.json"),
        "expected_tokens": str(ROOT / "config" / "static_tokens.example.json"),
    }


def make_handler(service: ResearchService):
    class Handler(BaseHTTPRequestHandler):
        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            return json.loads(raw)

        def _send(self, code: int, payload):
            body = dump(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                return self._send(200, {"ok": True})
            if parsed.path == "/doctor":
                return self._send(200, doctor_payload())
            if parsed.path == "/search":
                try:
                    q = parse_qs(parsed.query).get("q", [""])[0]
                    limit = int(parse_qs(parsed.query).get("limit", ["10"])[0])
                    token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip() or None
                    payload = service.search_contract(q, limit=limit, token=token)
                    return self._send(200, payload)
                except ResearchMcpError as exc:
                    return self._send(exc.http_status, exc.to_dict())
            if parsed.path == "/fetch":
                try:
                    doc_id = parse_qs(parsed.query).get("id", [""])[0]
                    token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip() or None
                    payload = service.fetch_contract(doc_id, token=token)
                    return self._send(200, payload)
                except ResearchMcpError as exc:
                    return self._send(exc.http_status, exc.to_dict())
            self._send(404, {"error": "not_found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/export":
                try:
                    token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip() or None
                    body = self._read_json()
                    payload = service.export_report_handoff(
                        title=body["title"],
                        narrative=body["narrative"],
                        document_ids=body["document_ids"],
                        token=token,
                    )
                    return self._send(200, payload)
                except ResearchMcpError as exc:
                    return self._send(exc.http_status, exc.to_dict())
            self._send(404, {"error": "not_found"})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify-bundle")
    sub.add_parser("doctor")

    p = sub.add_parser("demo-search")
    p.add_argument("query")
    p.add_argument("--token")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("demo-fetch")
    p.add_argument("document_id")
    p.add_argument("--token")

    p = sub.add_parser("demo-export")
    p.add_argument("--title", required=True)
    p.add_argument("--narrative", required=True)
    p.add_argument("--document-ids", nargs="+", required=True)
    p.add_argument("--token")

    p = sub.add_parser("serve-http")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=18080)

    args = parser.parse_args()
    service = build_service()

    if args.cmd == "verify-bundle":
        print(dump(bundle_integrity_report(ROOT)))
        return 0
    if args.cmd == "doctor":
        print(dump(doctor_payload()))
        return 0
    if args.cmd == "demo-search":
        print(dump(service.search_contract(args.query, limit=args.limit, token=args.token)))
        return 0
    if args.cmd == "demo-fetch":
        print(dump(service.fetch_contract(args.document_id, token=args.token)))
        return 0
    if args.cmd == "demo-export":
        print(dump(service.export_report_handoff(args.title, args.narrative, args.document_ids, token=args.token)))
        return 0
    if args.cmd == "serve-http":
        if not os.environ.get("MCP_PUBLIC_ARTIFACT_BASE_URL"):
            os.environ["MCP_PUBLIC_ARTIFACT_BASE_URL"] = f"http://{args.host}:{args.port}/artifacts"
        server = ThreadingHTTPServer((args.host, args.port), make_handler(build_service()))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
