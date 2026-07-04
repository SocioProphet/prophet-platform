"""Adversarial board — gapi §8 exploit surfaces as membrane assertions.

The gapi recon (§8) enumerated the failure classes any capability-scoped message
bus must handle. This board proves the membrane's response to each. These are
protocol/transport attacks, distinct from the governance-decision board.
"""

from __future__ import annotations

from tools.capability_membrane import (
    CapabilityRequest,
    TENSION_REQUIRED,
    resolve_capability,
    seal_receipt,
)
from tools import membrane_identity as mid
import pytest

FULL_TENSION = TENSION_REQUIRED["R5"]


def req(**over):
    base = dict(surface="filesystem", action="filesystem.read", access_level="readOnly",
                subject_ref="urn:srcos:agent:test", tension_members=FULL_TENSION)
    base.update(over)
    return CapabilityRequest(**base)


# §8: Origin spoofing / confusion → replaced by attested identity. No identity
# tension member ⇒ can't even satisfy the R0 floor {policy, identity} ⇒ deny.
def test_origin_spoofing_maps_to_missing_attested_identity():
    r = resolve_capability(req(tension_members=("policy",)))   # identity absent
    assert "identity" in r.missing_tension
    assert r.execution_decision == "deny"


# §8: Token leakage / reuse across contexts. A token minted for a low-radius
# read, replayed to drive a high-radius `control` action, presents only its
# low-radius tension ⇒ fail-closed on the missing higher-radius members.
def test_token_replay_across_scope_fails_closed():
    low_radius_tension = TENSION_REQUIRED["R1"]      # what a read token carries
    r = resolve_capability(req(surface="browser", action="rpc.dispatch",
                               access_level="control", tension_members=low_radius_tension))
    assert r.radius == "R5"
    assert r.execution_decision == "deny"
    assert r.missing_tension


# §8: Callback hijacking / confused routing. The response's subject binding is
# sealed into the receipt; swapping subjectRef changes the seal ⇒ tamper-evident.
def test_callback_hijack_breaks_the_seal():
    r = resolve_capability(req(subject_ref="urn:srcos:agent:alice"))
    hijacked = dict(r.receipt, subjectRef="urn:srcos:agent:mallory")
    assert seal_receipt(hijacked)["sealHash"] != r.sealed["sealHash"]


@pytest.mark.skipif(not mid.HAVE_CRYPTO, reason="cryptography not installed")
def test_callback_hijack_breaks_the_signature():
    ident = mid.IdentityRoot.from_seed(bytes(range(32)))
    r = resolve_capability(req(subject_ref="urn:srcos:agent:alice"), signer=ident)
    # Attacker swaps the subject but cannot re-sign; keeping the old sealHash+sig
    # leaves a receipt whose re-seal no longer matches, and the signature is over
    # the original seal — verification of a re-sealed hijack fails.
    hijacked_receipt = dict(r.receipt, subjectRef="urn:srcos:agent:mallory")
    reseal = seal_receipt(hijacked_receipt)
    forged = dict(reseal, signerDid=r.sealed["signerDid"],
                  signature=r.sealed["signature"], svidRef=r.sealed.get("svidRef"))
    assert mid.verify_sealed(forged) is False


# §8: Handler namespace collision — calling reserved/internal services. Reserved
# namespaces floor to R5; an ordinary caller lacks post_authority_ref ⇒ denied.
def test_handler_namespace_collision_denied_for_ordinary_caller():
    r = resolve_capability(req(action="_g_connect", tension_members=TENSION_REQUIRED["R3"]))
    assert r.radius == "R5"
    assert "post_authority_ref" in r.missing_tension
    assert r.execution_decision == "deny"


def test_reserved_handler_allowed_only_with_top_authority():
    r = resolve_capability(req(action="__cb", tension_members=FULL_TENSION))
    assert r.radius == "R5"
    assert r.execution_decision == "allow"     # full R5 tension incl. post_authority_ref


# §8: Legacy protocol downgrade — forcing an unenforced path. A foreign/observed
# surface can NEVER be counted as an enforced allow, no matter the membrane says.
def test_downgrade_to_observed_is_never_an_enforced_allow():
    r = resolve_capability(req(surface="computer", action="computer.control",
                               access_level="control", owned=False, membrane_decision="ALLOW"))
    assert r.verdict == "observed"
    assert r.enforced is False
    assert r.allowed is False


# §8: Unsafe URL / relay-redirect injection → sanitize. An injection attempt
# routed as REDACT proceeds only rewritten, with a mask obligation attached.
def test_url_injection_forces_redact_rewrite_with_obligation():
    r = resolve_capability(req(surface="httpApi", action="url.expand",
                               access_level="draftOnly", membrane_decision="REDACT"))
    assert r.execution_decision == "rewrite"
    assert {"name": "mask_fields", "when": "runtime"} in r.obligations


# §8: Message queue flooding (DoS). Rate-limiting is the transport/gateway's job,
# NOT the membrane's — but a flooding signal surfaced as QUARANTINE still denies.
# (Honest boundary: the membrane is a per-call decision, stateless across calls.)
def test_flooding_signalled_as_quarantine_denies():
    r = resolve_capability(req(membrane_decision="QUARANTINE", risk_level="critical"))
    assert r.execution_decision == "deny"
