from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import capability_broker as cb  # type: ignore

LANE = ROOT / "contracts" / "workspace-control-plane"
EVENT_SCHEMA = json.loads((LANE / "schemas" / "event.v0.schema.json").read_text())
POLICY = json.loads((LANE / "examples" / "discovery-policy.v0.json").read_text())

NOW = "2026-08-01T00:00:00+00:00"
FUTURE = "2026-12-31T00:00:00+00:00"
PAST = "2025-01-01T00:00:00+00:00"


def capman(mid, cap, *, provider="p", expiry=FUTURE, signed=True, revoked=False, revocation=True):
    m = {
        "manifest_id": mid,
        "kind": "capability",
        "provider": provider,
        "capabilities": [{"name": cap, "transport": "mcp"}],
        "expiry": expiry,
    }
    if signed:
        m["signature"] = {"signer": "root", "algorithm": "ed25519", "signature": "s", "signed_at": NOW}
    if revocation:
        m["revocation"] = {"revoked": revoked}
    return m


def _valid_event(ev):
    return list(Draft202012Validator(EVENT_SCHEMA).iter_errors(ev)) == []


def test_deterministic_order_local_beats_mcp():
    sources = [
        cb.Source("mcp_server", capman("m-mcp", "drive.search")),
        cb.Source("local_manifest", capman("m-local", "drive.search")),
    ]
    r = cb.resolve("drive.search", sources, POLICY, now=NOW)
    assert r.resolved
    assert r.lane == "local_manifest"  # earlier lane wins regardless of source order
    assert r.manifest_id == "m-local"
    assert _valid_event(r.event)
    assert r.event["activity"] == "CapabilityResolved"


def test_expired_is_rejected_and_falls_through():
    sources = [
        cb.Source("local_manifest", capman("m-exp", "drive.search", expiry=PAST)),
        cb.Source("mcp_server", capman("m-mcp", "drive.search")),
    ]
    r = cb.resolve("drive.search", sources, POLICY, now=NOW)
    assert r.resolved and r.lane == "mcp_server"
    assert any(x["reason"] == "expired" for x in r.rejected)


def test_unsigned_rejected_when_policy_requires_signed():
    assert POLICY["trust_requirements"]["require_signed"] is True
    sources = [cb.Source("local_manifest", capman("m", "drive.search", signed=False))]
    r = cb.resolve("drive.search", sources, POLICY, now=NOW)
    assert not r.resolved
    assert any(x["reason"] == "unsigned" for x in r.rejected)


def test_revoked_and_missing_revocation_field_rejected():
    r1 = cb.resolve("x", [cb.Source("local_manifest", capman("m1", "x", revoked=True))], POLICY, now=NOW)
    assert not r1.resolved and any(x["reason"] == "revoked" for x in r1.rejected)
    # require_revocation_check is on -> a manifest with no revocation field is rejected
    r2 = cb.resolve("x", [cb.Source("local_manifest", capman("m2", "x", revocation=False))], POLICY, now=NOW)
    assert not r2.resolved and any(x["reason"] == "no_revocation_field" for x in r2.rejected)


def test_catalog_gating():
    man = capman("m-cat", "remote.tool")
    sources = [cb.Source("trusted_catalog", man)]
    # No catalog -> not trusted.
    r_none = cb.resolve("remote.tool", sources, POLICY, now=NOW)
    assert not r_none.resolved
    assert any(x["reason"] == "not_in_trusted_catalog" for x in r_none.rejected)
    # A valid catalog entry listing the manifest -> trusted.
    catalog = [{
        "entry_id": "cat-1", "role": "targets", "version": 1, "targets": ["m-cat"],
        "expiry": FUTURE, "delegation": {"threshold": 1, "keys": ["k"]},
        "signatures": [{"signer": "k", "algorithm": "ed25519", "signature": "s", "signed_at": NOW}],
    }]
    r_ok = cb.resolve("remote.tool", sources, POLICY, catalogs=catalog, now=NOW)
    assert r_ok.resolved and r_ok.lane == "trusted_catalog"


def test_unresolved_emits_conformant_event():
    r = cb.resolve("nope", [], POLICY, now=NOW)
    assert not r.resolved
    assert r.event["activity"] == "CapabilityUnresolved"
    assert _valid_event(r.event)
