"""Coverage for tools/advisory_check.py — the fail-closed OSV advisory gate.

Injects the HTTP transport so no live OSV is needed. Pins the load-bearing behaviour: a version
with known advisories is BLOCKED; a clean version is ALLOWED; an unreachable service is BLOCKED
(fail-closed — no re-vendor into the unknown); the OSV query shape is correct; and the air-gapped
override is explicit.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("advisory_check", ROOT / "tools" / "advisory_check.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["advisory_check"] = m
    spec.loader.exec_module(m)
    return m


ac = _load()


def test_vulnerable_version_is_blocked():
    def post(url, body):
        return {"vulns": [{"id": "GHSA-xxxx", "summary": "RCE in parser",
                           "database_specific": {"severity": "CRITICAL"}}]}
    r = ac.assess("lodash", "npm", "4.17.4", http_post=post)
    assert r["checked"] and r["vulnerable"] and r["recommendation"] == "block"
    assert r["advisories"][0]["id"] == "GHSA-xxxx" and r["advisories"][0]["severity"] == "CRITICAL"


def test_clean_version_is_allowed():
    r = ac.assess("lodash", "npm", "4.17.21", http_post=lambda u, b: {})
    assert r["checked"] and r["vulnerable"] is False and r["recommendation"] == "allow"


def test_unreachable_service_fails_closed():
    def post(u, b):
        raise OSError("no network")
    r = ac.assess("x", "npm", "1.0.0", http_post=post)
    assert r["checked"] is False and r["recommendation"] == "block" and "fail-closed" in r["reason"]


def test_osv_query_shape_is_correct():
    seen = {}

    def post(url, body):
        seen["url"], seen["body"] = url, body
        return {}
    ac.assess("hellgraph", "npm", "0.4.45", http_post=post)
    assert seen["url"] == ac.OSV_QUERY_URL
    assert seen["body"] == {"version": "0.4.45", "package": {"name": "hellgraph", "ecosystem": "npm"}}


def test_main_exit_codes(monkeypatch):
    monkeypatch.setattr(ac, "_http_post", lambda u, b: {"vulns": [{"id": "GHSA-1"}]})
    assert ac.main(["--package", "p", "--ecosystem", "npm", "--version", "1.0.0"]) == 1  # blocked
    monkeypatch.setattr(ac, "_http_post", lambda u, b: {})
    assert ac.main(["--package", "p", "--ecosystem", "npm", "--version", "1.0.1"]) == 0  # allowed


def test_allow_unverified_override(monkeypatch):
    def boom(u, b):
        raise OSError("offline")
    monkeypatch.setattr(ac, "_http_post", boom)
    assert ac.main(["--package", "p", "--ecosystem", "npm", "--version", "1.0.0"]) == 1
    assert ac.main(["--package", "p", "--ecosystem", "npm", "--version", "1.0.0", "--allow-unverified"]) == 0
