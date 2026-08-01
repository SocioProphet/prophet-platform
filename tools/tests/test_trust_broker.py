from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import trust_broker as tb  # type: ignore

NOW = "2026-08-01T00:00:00+00:00"
FUTURE = "2026-12-31T00:00:00+00:00"
PAST = "2025-01-01T00:00:00+00:00"
SECRET = b"lab-secret-key"


def _registry(*signers):
    r = tb.KeyRegistry()
    for s in signers:
        r.add(s, SECRET)
    return r


def _signed_manifest(mid="capman-1", *, expiry=FUTURE, revoked=False, signer="root", signed_at=NOW, algo="hmac-blake2b"):
    m = {
        "manifest_id": mid, "kind": "capability", "provider": "mcp://x",
        "capabilities": [{"name": "drive.search"}], "expiry": expiry,
        "revocation": {"revoked": revoked},
    }
    payload = tb.canonical_signing_bytes(m, exclude=("signature",))
    m["signature"] = {"signer": signer, "algorithm": algo, "signature": tb.mac_sign(payload, SECRET), "signed_at": signed_at}
    return m


def test_valid_manifest_is_trusted():
    broker = tb.TrustBroker(_registry("root"))
    d = broker.verify_manifest(_signed_manifest(), NOW)
    assert d.trusted and d.reasons == []
    assert broker.transparency_log[-1]["trusted"] is True


def test_tamper_breaks_signature():
    broker = tb.TrustBroker(_registry("root"))
    m = _signed_manifest()
    m["provider"] = "mcp://evil"  # tamper after signing
    d = broker.verify_manifest(m, NOW)
    assert not d.trusted and "bad_signature" in d.reasons


def test_expired_and_revoked_and_unsigned():
    broker = tb.TrustBroker(_registry("root"))
    assert "expired" in broker.verify_manifest(_signed_manifest(expiry=PAST), NOW).reasons
    assert "revoked" in broker.verify_manifest(_signed_manifest(revoked=True), NOW).reasons
    unsigned = {"manifest_id": "m", "kind": "capability", "provider": "p", "capabilities": [{"name": "x"}], "expiry": FUTURE}
    assert "unsigned" in broker.verify_manifest(unsigned, NOW).reasons


def test_unknown_signer_and_asymmetric_unavailable():
    broker = tb.TrustBroker(tb.KeyRegistry())  # no keys registered
    assert "unknown_signer" in broker.verify_manifest(_signed_manifest(), NOW).reasons
    d = broker.verify_manifest(_signed_manifest(algo="ed25519"), NOW)
    assert "verifier_unavailable" in d.reasons


def test_stale_via_max_age():
    broker = tb.TrustBroker(_registry("root"), max_age_seconds=3600)
    old = _signed_manifest(signed_at="2026-07-31T20:00:00+00:00")  # >1h before NOW
    assert "stale" in broker.verify_manifest(old, NOW).reasons


def _signed_catalog(threshold, n_valid, n_invalid=0):
    entry = {
        "entry_id": "cat-1", "role": "targets", "version": 1, "targets": ["capman-1"],
        "expiry": FUTURE, "delegation": {"threshold": threshold, "keys": ["k"]},
    }
    payload = tb.canonical_signing_bytes(entry, exclude=("signatures",))
    sigs = []
    for i in range(n_valid):
        sigs.append({"signer": f"s{i}", "algorithm": "hmac-blake2b", "signature": tb.mac_sign(payload, SECRET), "signed_at": NOW})
    for i in range(n_invalid):
        sigs.append({"signer": f"bad{i}", "algorithm": "hmac-blake2b", "signature": "deadbeef", "signed_at": NOW})
    entry["signatures"] = sigs
    return entry


def test_catalog_delegation_threshold():
    reg = _registry("s0", "s1", "bad0")
    broker = tb.TrustBroker(reg)
    # 2 valid signatures, threshold 2 -> trusted
    assert broker.verify_catalog(_signed_catalog(2, n_valid=2), NOW).trusted
    # 1 valid + 1 invalid, threshold 2 -> not trusted
    d = broker.verify_catalog(_signed_catalog(2, n_valid=1, n_invalid=1), NOW)
    assert not d.trusted and any("insufficient_signatures" in r for r in d.reasons)


def test_transparency_log_appends_every_check():
    broker = tb.TrustBroker(_registry("root"))
    broker.verify_manifest(_signed_manifest(), NOW)
    broker.verify_manifest(_signed_manifest(revoked=True), NOW)
    assert len(broker.transparency_log) == 2
    assert [e["trusted"] for e in broker.transparency_log] == [True, False]
