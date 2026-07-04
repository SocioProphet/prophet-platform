"""Proof-of-Emptiness tests — erase-as-isomorphism and no-silent-sinks enforcement."""

from __future__ import annotations

from tools.proof_of_emptiness import (
    empty_digest,
    empty_form,
    is_valid_poe,
    prove_emptiness,
    shred,
)
from tools.ghost_audit import StateDelta, audit
from tools import membrane_identity as mid
import pytest


def test_certified_erasure_reaches_emptiness():
    poe = prove_emptiness(subject_ref="urn:srcos:agent:worker", object_ref="urn:srcos:asset:x",
                          type_name="UserGraph", pre_state={"nodes": [1, 2, 3], "secret": "s"})
    r = poe["receipt"]
    assert r["type"] == "ProofOfEmptiness"
    assert r["certified"] is True
    assert r["postDigest"] == r["emptiedDigest"] == empty_digest("UserGraph")
    assert is_valid_poe(poe) is True


def test_uncertified_erasure_is_flagged():
    # A "deletion" that leaves residual data does NOT reach ∅ — not a valid PoE.
    poe = prove_emptiness(subject_ref="s", object_ref="o", type_name="UserGraph",
                          pre_state={"nodes": [1, 2, 3]}, post_state={"nodes": [2]})
    assert poe["receipt"]["certified"] is False
    assert is_valid_poe(poe) is False


def test_unit_is_not_empty():
    # An empty-looking ack {} must not be confused with the typed empty value.
    assert empty_form("UserGraph") != {}
    assert empty_digest("UserGraph") != empty_digest("SystemGraph")


def test_shred_is_deterministic_and_typed():
    a = shred({"a": 1}, "T")
    b = shred({"b": 2, "c": 3}, "T")
    assert a == b == empty_form("T")


# --- Ghost-audit integration: erasures need a valid PoE -----------------------

def erasure(rid=None):
    return StateDelta(id="del-1", action="filesystem.erase", subject="s", authorized_by=rid, is_erasure=True)


def test_erasure_with_valid_poe_is_attested():
    poe = prove_emptiness(subject_ref="s", object_ref="o", type_name="Asset", pre_state={"x": 1})
    rid = poe["receipt"]["id"]
    report = audit([poe], [erasure(rid)])
    assert report.clean
    assert report.attested == 1


def test_erasure_without_poe_is_a_ghost():
    report = audit([], [erasure(None)])
    assert report.ghosts[0].reason == "uncertified_erase"
    assert report.ghostry == 1.0


def test_erasure_with_uncertified_poe_is_a_ghost():
    poe = prove_emptiness(subject_ref="s", object_ref="o", type_name="Asset",
                          pre_state={"x": 1}, post_state={"x": 1})  # didn't reach ∅
    rid = poe["receipt"]["id"]
    report = audit([poe], [erasure(rid)])
    assert report.ghosts[0].reason == "uncertified_erase"


def test_erasure_authorized_by_ordinary_receipt_is_a_silent_sink():
    # A normal enforced-allow receipt cannot authorize a deletion — that's the sink.
    from tools.capability_membrane import CapabilityRequest, TENSION_REQUIRED, resolve_capability
    r = resolve_capability(CapabilityRequest(surface="filesystem", action="filesystem.write",
            access_level="scopedWrite", subject_ref="s", tension_members=TENSION_REQUIRED["R5"],
            membrane_decision="ALLOW"))
    report = audit([r.sealed], [erasure(r.receipt["id"])])
    assert report.ghosts[0].reason == "not_a_proof_of_emptiness"


@pytest.mark.skipif(not mid.HAVE_CRYPTO, reason="cryptography not installed")
def test_poe_is_signable_by_identity_root():
    ident = mid.IdentityRoot.from_seed(bytes(range(32)))
    poe = prove_emptiness(subject_ref="s", object_ref="o", type_name="Asset",
                          pre_state={"x": 1}, signer=ident)
    assert poe["signature"].startswith("ed25519:")
    assert mid.verify_sealed(poe) is True
    assert is_valid_poe(poe) is True
