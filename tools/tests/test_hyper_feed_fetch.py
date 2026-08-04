"""Theorems of node-to-node fetch (tools.hyper_feed.fetch) — the pull half of federation: discover
by Hamming, fetch, and admit ONLY verified objects (digest + attestation). Fail-closed."""
from __future__ import annotations

from tools.hyper_feed import fetch as ff
from tools.hyper_feed import manifest as hf


def _entry(ref, code, content, op_set="discourse", att=None):
    return {"ref_id": ref, "op_set": op_set, "code": code, "digest": hf.content_digest(content),
            **({"attestation_ref": att} if att else {})}


def test_admit_accepts_matching_content():
    e = _entry("r1", "ff00", b"data")
    r = ff.admit(e, b"data")
    assert r.admitted and r.reason == "ok" and r.content == b"data"


def test_admit_rejects_tampered_content():
    e = _entry("r1", "ff00", b"data")
    r = ff.admit(e, b"tampered")
    assert not r.admitted and r.reason == "digest-mismatch" and r.content is None


def test_admit_rejects_invalid_attestation():
    e = _entry("r1", "ff00", b"data", att="att:bad")
    r = ff.admit(e, b"data", attestation_verifier=lambda a: False)
    assert not r.admitted and r.reason == "attestation-invalid"


def test_admit_rejects_attested_entry_when_no_verifier():
    # THEOREM (fail-closed): an entry that CLAIMS an attestation but cannot be verified — no verifier
    # supplied — must be REJECTED, never admitted on the peer's own digest alone. (Regression guard:
    # this exact path previously returned reason="ok".)
    e = _entry("r1", "ff00", b"data", att="att:present")
    r = ff.admit(e, b"data")  # no verifier
    assert not r.admitted and r.reason == "attestation-unverifiable" and r.content is None


def test_admit_treats_a_throwing_verifier_as_rejection():
    # THEOREM: a verifier that raises is a rejection, not a crash of the caller.
    def boom(_):
        raise RuntimeError("verifier down")
    e = _entry("r1", "ff00", b"data", att="att:boom")
    r = ff.admit(e, b"data", attestation_verifier=boom)
    assert not r.admitted and r.reason.startswith("attestation-error")


def test_require_attestation_rejects_unattested_entry():
    # THEOREM: strict mesh — an entry with NO attestation_ref is rejected when attestation is required,
    # even though its digest matches.
    e = _entry("r1", "ff00", b"data")  # no att
    assert ff.admit(e, b"data").admitted  # lax default still admits on digest
    r = ff.admit(e, b"data", require_attestation=True)
    assert not r.admitted and r.reason == "attestation-missing"


def test_federate_default_rejects_attested_content_without_a_verifier():
    # THEOREM: the DEFAULT federation path (no verifier) no longer trusts attested content on digest
    # alone — it rejects it as unverifiable. This is the fail-OPEN that shipped green before.
    m = hf.build_manifest("peer", "t1", [_entry("r1", "ff00", b"x", att="att:present")], now="T")
    res = ff.federate("ff00", m, fetcher=lambda rid: b"x", max_hamming=2)
    assert res == [ff.AdmitResult("r1", False, "attestation-unverifiable")]


def test_federate_pulls_and_admits_only_verified():
    m = hf.build_manifest("peer", "t1", [
        _entry("r_near", "ff01", b"near-content", att="att:near"),
        _entry("r_far", "0000", b"far-content"),
    ], now="T")
    store = {"r_near": b"near-content"}  # the peer serves this; digest matches
    res = ff.federate("ff00", m, fetcher=lambda rid: store[rid], max_hamming=4,
                      attestation_verifier=lambda a: True)
    assert [(r.ref_id, r.admitted) for r in res] == [("r_near", True)]  # r_far excluded by Hamming
    assert res[0].content == b"near-content"


def test_federate_rejects_a_tampering_peer():
    m = hf.build_manifest("peer", "t1", [_entry("r1", "ff00", b"honest")], now="T")
    res = ff.federate("ff00", m, fetcher=lambda rid: b"SWAPPED", max_hamming=2)
    assert res == [ff.AdmitResult("r1", False, "digest-mismatch")]  # the swap is caught


def test_federate_treats_a_fetch_failure_as_rejection():
    m = hf.build_manifest("peer", "t1", [_entry("r1", "ff00", b"x")], now="T")

    def boom(_):
        raise ConnectionError("peer down")

    res = ff.federate("ff00", m, fetcher=boom, max_hamming=2)
    assert not res[0].admitted and res[0].reason.startswith("fetch-failed")
