"""Theorems of the twin-attestation wiring (tools.hyper_feed.attestation): a manifest attestation_ref
encodes a twin VerifiableReference, and the verifier reflects the twin's /verify verdict — fail-closed
on an unparseable attestation or an unreachable twin."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from tools.hyper_feed.attestation import decode_attestation, encode_attestation, twin_attestation_verifier


def test_encode_decode_round_trip_and_rejects_junk():
    att = encode_attestation("ctx", "proofhex", "vkhex")
    assert decode_attestation(att) == {"context": "ctx", "proof": "proofhex", "verify_key": "vkhex"}
    assert decode_attestation("att:@@not-base64@@") is None
    assert decode_attestation("plain-ref") is None            # not the att: prefix
    assert decode_attestation("att:" + __import__("base64").urlsafe_b64encode(b'{"context":"c"}').decode()) is None  # missing fields


def _stub_twin(verified: bool):
    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            n = int(self.headers.get("content-length", 0))
            self.rfile.read(n)
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"verified": verified}).encode())

        def log_message(self, *_a) -> None:  # silence
            return

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_verifier_reflects_the_twin_verdict():
    att = encode_attestation("ctx", "p", "vk")
    srv, url = _stub_twin(True)
    try:
        assert twin_attestation_verifier(url)(att) is True
    finally:
        srv.shutdown()
    srv, url = _stub_twin(False)
    try:
        assert twin_attestation_verifier(url)(att) is False   # twin says forged ⇒ reject
    finally:
        srv.shutdown()


def test_verifier_is_fail_closed():
    # an unparseable attestation ⇒ False without trusting anything
    assert twin_attestation_verifier("http://127.0.0.1:1")("not-an-attestation") is False
    # a well-formed attestation but an unreachable twin ⇒ False (never admit on an unverifiable proof)
    att = encode_attestation("ctx", "p", "vk")
    assert twin_attestation_verifier("http://127.0.0.1:1", timeout=0.5)(att) is False
