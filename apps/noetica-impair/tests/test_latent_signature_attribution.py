"""Teeth for the latent-signature model-attribution contract (prophet-workspace#76 item 4).

The dangerous failure this guards against is an attribution rig that says "yes, that's
model X" to anything — a forged signature, an unknown model, an ambiguous match. These
tests pin that it (1) attributes a genuine re-measurement to the right model,
(2) does NOT cross-attribute one model to another, (3) REJECTS an impostor that matches
nothing, (4) REJECTS a signature whose fingerprint or provenance was tampered after
minting, and (5) is deterministic. No weights and no torch: the contract is checkable
anywhere.
"""

from __future__ import annotations

import pytest

from noetica_impair.attribution import (
    SignatureRegistry,
    attribute,
    signature_distance,
    verify_signature_receipt,
)
from noetica_impair.attribution.fixtures import (
    DEFAULT_MODELS,
    build_registry,
    forged_signature,
    remeasure,
    synthetic_signature,
)


# ── provenance integrity ──────────────────────────────────────────────────────

def test_minted_signature_receipt_verifies():
    sig = synthetic_signature("gemma-2-9b-it")
    ok, reason = verify_signature_receipt(sig)
    assert ok, reason


def test_receipt_is_estate_chain_compatible():
    """The receipt is the estate Receipt shape and verifies under the gateway's rule."""
    from noetica_impair.provenance.log import sha
    sig = synthetic_signature("gemma-2-9b-it")
    r = sig.receipt
    assert r["kind"] == "latent-signature"
    body = {k: r[k] for k in (
        "project", "kind", "backend", "runtime", "inputs_sha", "outputs_sha",
        "status", "actor", "epistemic_status", "prev", "ts")}
    assert sha(body) == r["id"]


def test_tampered_fingerprint_is_rejected():
    sig = synthetic_signature("gemma-2-9b-it")
    # forge: change one feature id, keep the genuine receipt
    first = next(iter(sig.fingerprint))
    sig.fingerprint[first][0] = 999999
    ok, reason = verify_signature_receipt(sig)
    assert not ok
    assert "fingerprint" in reason


def test_tampered_provenance_is_rejected():
    sig = synthetic_signature("gemma-2-9b-it")
    sig.layer = 99  # claim a different capture site than the receipt was minted over
    ok, reason = verify_signature_receipt(sig)
    assert not ok
    assert "provenance" in reason


def test_unprovenanced_signature_is_refused():
    sig = synthetic_signature("gemma-2-9b-it", mint=False)
    ok, reason = verify_signature_receipt(sig)
    assert not ok


# ── the distance ──────────────────────────────────────────────────────────────

def test_identical_signature_distance_is_zero():
    sig = synthetic_signature("gemma-2-9b-it")
    assert signature_distance(sig, sig) == pytest.approx(0.0)


def test_distance_is_symmetric_and_deterministic():
    a = synthetic_signature("gemma-2-9b-it")
    b = synthetic_signature("llama-3.1-8b")
    assert signature_distance(a, b) == signature_distance(b, a)
    # rebuilt from scratch -> identical fingerprints -> identical distance
    a2 = synthetic_signature("gemma-2-9b-it")
    b2 = synthetic_signature("llama-3.1-8b")
    assert signature_distance(a2, b2) == signature_distance(a, b)


def test_same_model_closer_than_different_model():
    sig = synthetic_signature("gemma-2-9b-it")
    same = remeasure(sig)
    other = synthetic_signature("llama-3.1-8b")
    assert signature_distance(sig, same) < signature_distance(sig, other)


# ── attribution: accept the genuine ───────────────────────────────────────────

def test_remeasurement_attributes_to_the_same_model():
    reg = build_registry()
    enrolled = reg.signatures["gemma-2-9b-it"]
    candidate = remeasure(enrolled)
    res = attribute(candidate, reg)
    assert res.receipt_ok
    assert res.matched, res.report()
    assert res.attributed_model == "gemma-2-9b-it"
    assert res.margin >= 0.10


@pytest.mark.parametrize("model_id", DEFAULT_MODELS)
def test_every_enrolled_model_self_attributes(model_id):
    reg = build_registry()
    candidate = remeasure(reg.signatures[model_id])
    res = attribute(candidate, reg)
    assert res.matched and res.attributed_model == model_id, res.report()


# ── attribution: reject what must be rejected ──────────────────────────────────

def test_impostor_matches_nothing_and_is_refused():
    reg = build_registry()
    # a signature for a model NOT in the registry, claiming to be one that is
    impostor = forged_signature("gemma-2-9b-it", salt="totally-different")
    # its fingerprint is unrelated to the enrolled gemma signature
    res = attribute(impostor, reg)
    assert not res.matched, res.report()
    assert "max_distance" in res.reason


def test_unknown_model_is_not_forced_to_a_label():
    reg = build_registry()
    unknown = synthetic_signature("some-unknown-model-x")
    res = attribute(unknown, reg)
    assert not res.matched


def test_forged_receipt_is_refused_before_distance():
    reg = build_registry()
    candidate = remeasure(reg.signatures["gemma-2-9b-it"])
    candidate.fingerprint[next(iter(candidate.fingerprint))][0] = 424242
    res = attribute(candidate, reg)
    assert not res.receipt_ok
    assert not res.matched
    assert res.attributed_model is None


def test_no_cross_attribution_between_models():
    reg = build_registry()
    for target in DEFAULT_MODELS:
        cand = remeasure(reg.signatures[target])
        res = attribute(cand, reg)
        assert res.attributed_model == target
        # and every OTHER model is strictly farther
        d_target = signature_distance(cand, reg.signatures[target])
        for other in DEFAULT_MODELS:
            if other != target:
                assert d_target < signature_distance(cand, reg.signatures[other])


def test_empty_registry_refuses():
    res = attribute(synthetic_signature("gemma-2-9b-it"), SignatureRegistry())
    assert not res.matched
    assert "empty" in res.reason


def test_enrol_refuses_tampered_signature():
    reg = SignatureRegistry()
    sig = synthetic_signature("gemma-2-9b-it")
    sig.fingerprint[next(iter(sig.fingerprint))][0] = 111111
    with pytest.raises(ValueError):
        reg.enrol(sig)
