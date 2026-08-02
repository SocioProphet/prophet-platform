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


def _signed_manifest(mid="capman-1", *, expiry=FUTURE, revoked=False, signer="root", signed_at=NOW, algo="hmac-sha256"):
    m = {
        "manifest_id": mid, "kind": "capability", "provider": "mcp://x",
        "capabilities": [{"name": "drive.search"}], "expiry": expiry,
        "revocation": {"revoked": revoked},
    }
    payload = tb.canonical_signing_bytes(m, exclude=("signature",))
    sig = tb.mac_sign(tb.signing_input(payload, signed_at), SECRET)
    m["signature"] = {"signer": signer, "algorithm": algo, "signature": sig, "signed_at": signed_at}
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
        sigs.append({"signer": f"s{i}", "algorithm": "hmac-sha256", "signature": tb.mac_sign(tb.signing_input(payload, NOW), SECRET), "signed_at": NOW})
    for i in range(n_invalid):
        sigs.append({"signer": f"bad{i}", "algorithm": "hmac-sha256", "signature": "deadbeef", "signed_at": NOW})
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


# ---- hardening follow-up (Copilot #1190) ----

def test_unknown_algorithm_is_distinct_from_unavailable():
    broker = tb.TrustBroker(_registry("root"))
    d = broker.verify_manifest(_signed_manifest(algo="totally-made-up"), NOW)
    assert "unknown_algorithm" in d.reasons and "verifier_unavailable" not in d.reasons


def test_malformed_signature_does_not_crash():
    broker = tb.TrustBroker(_registry("root"))
    m = {"manifest_id": "m", "kind": "capability", "provider": "p",
         "capabilities": [{"name": "x"}], "expiry": FUTURE, "signature": "not-a-dict"}
    d = broker.verify_manifest(m, NOW)  # must not raise
    assert not d.trusted and "malformed_signature" in d.reasons
    assert broker.transparency_log[-1]["subject_id"] == "m"  # still recorded


def test_bad_timestamp_fails_closed():
    broker = tb.TrustBroker(_registry("root"))
    d = broker.verify_manifest(_signed_manifest(expiry="not-a-date"), NOW)  # attacker-controlled
    assert not d.trusted and "bad_timestamp" in d.reasons


def test_catalog_max_age_enforced():
    reg = _registry("s0", "s1")
    broker = tb.TrustBroker(reg, max_age_seconds=3600)
    # Two valid signatures, but signed >1h before NOW -> none count -> below threshold.
    entry = {"entry_id": "cat-old", "role": "targets", "version": 1, "targets": ["x"],
             "expiry": FUTURE, "delegation": {"threshold": 2, "keys": ["k"]}}
    payload = tb.canonical_signing_bytes(entry, exclude=("signatures",))
    old = "2026-07-31T20:00:00+00:00"  # >1h before NOW
    entry["signatures"] = [
        {"signer": "s0", "algorithm": "hmac-sha256", "signature": tb.mac_sign(tb.signing_input(payload, old), SECRET), "signed_at": old},
        {"signer": "s1", "algorithm": "hmac-sha256", "signature": tb.mac_sign(tb.signing_input(payload, old), SECRET), "signed_at": old},
    ]
    d = broker.verify_catalog(entry, NOW)
    assert not d.trusted and any("insufficient_signatures" in r for r in d.reasons)
    # Fresh signatures (re-signed over NOW, since signed_at is authenticated) -> trusted.
    entry["signatures"] = [
        {"signer": "s0", "algorithm": "hmac-sha256", "signature": tb.mac_sign(tb.signing_input(payload, NOW), SECRET), "signed_at": NOW},
        {"signer": "s1", "algorithm": "hmac-sha256", "signature": tb.mac_sign(tb.signing_input(payload, NOW), SECRET), "signed_at": NOW},
    ]
    assert broker.verify_catalog(entry, NOW).trusted


def test_replay_with_edited_signed_at_is_rejected():
    # signed_at is authenticated: taking an old valid signature and editing
    # signed_at to NOW must NOT verify (defeats the max-age bypass, Copilot #1190).
    broker = tb.TrustBroker(_registry("root"), max_age_seconds=3600)
    m = _signed_manifest(signed_at="2026-07-31T20:00:00+00:00")  # old but validly signed
    m["signature"]["signed_at"] = NOW  # attacker edits timestamp without re-signing
    d = broker.verify_manifest(m, NOW)
    assert not d.trusted and "bad_signature" in d.reasons


def test_nonstring_signer_does_not_crash():
    broker = tb.TrustBroker(_registry("root"))
    m = {"manifest_id": "m", "kind": "capability", "provider": "p",
         "capabilities": [{"name": "x"}], "expiry": FUTURE,
         "signature": {"signer": {"not": "a-string"}, "algorithm": "hmac-sha256",
                       "signature": "x", "signed_at": NOW}}
    d = broker.verify_manifest(m, NOW)  # must not raise (unhashable signer)
    assert not d.trusted and "malformed_signature" in d.reasons
