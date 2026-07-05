"""Membrane board — falsifiability tests for the capability membrane kernel.

Governance you cannot falsify is theater. This board exists to PROVE the
non-allow paths actually fire — denials, quarantines, require-signature,
redact, autonomy-block, and the enforce-vs-observe boundary — not just the
happy path. Every case below asserts a decision the membrane must REFUSE,
DEGRADE, or merely OBSERVE.
"""

from __future__ import annotations

import re

import json
import subprocess
import sys
from pathlib import Path

from tools.capability_membrane import (
    CapabilityRequest,
    TENSION_REQUIRED,
    evaluate_autonomy,
    gate,
    request_from_operation_decision,
    resolve_capability,
    seal_receipt,
)

_MEMBRANE = Path(__file__).resolve().parents[1] / "capability_membrane.py"


def operation(outcome, **over):
    """A minimal ProphetOperationsActionDecision skeleton for adapter tests."""
    d = {
        "kind": "ProphetOperationsActionDecision",
        "schema_version": "v1",
        "decision_id": "op-1",
        "decided_at": "2026-07-03T00:00:00Z",
        "recommendation_ref": "rec-1",
        "subject": {"id": "urn:srcos:subject:svc-a"},
        "proposed_action": {"type": "deployment.apply"},
        "decision": {"outcome": outcome, "risk_level": "high"},
        "basis": {"policy_refs": ["urn:srcos:policy:ops-default"]},
        "controls": {},
    }
    d.update(over)
    return d

# Full tension set for the top radius — hand this to owned requests that should
# pass the fail-closed gate so a test isolates the dimension under scrutiny.
FULL_TENSION = TENSION_REQUIRED["R5"]

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def req(**over) -> CapabilityRequest:
    base = dict(
        surface="filesystem",
        action="filesystem.read",
        access_level="readOnly",
        subject_ref="urn:srcos:agent:test",
        tension_members=FULL_TENSION,
        requested_autonomy_level="L0",
    )
    base.update(over)
    return CapabilityRequest(**base)


# --------------------------------------------------------------------------- #
# Happy path (control) — a real ALLOW must be reachable, or every deny is vacuous
# --------------------------------------------------------------------------- #

def test_allow_path_is_reachable():
    r = resolve_capability(req())
    assert r.execution_decision == "allow"
    assert r.verdict == "allowed"
    assert r.enforced is True
    assert r.allowed is True


# --------------------------------------------------------------------------- #
# Fail-closed on missing tension members (Tensegrity Invariant 1)
# --------------------------------------------------------------------------- #

def test_missing_tension_member_fails_closed():
    # shell.exec scopedWrite → radius R3, which requires 'revocation'. Omit it.
    partial = tuple(m for m in TENSION_REQUIRED["R3"] if m != "revocation")
    r = resolve_capability(req(surface="shell", action="shell.exec",
                               access_level="scopedWrite", tension_members=partial))
    assert r.radius == "R3"
    assert "revocation" in r.missing_tension
    assert r.execution_decision == "deny"
    assert r.verdict == "denied"
    assert any("missing" in x for x in r.reasons)


def test_no_tension_at_all_denies_even_with_allow_membrane():
    r = resolve_capability(req(surface="shell", action="shell.exec",
                               access_level="scopedWrite", tension_members=(),
                               membrane_decision="ALLOW"))
    assert r.execution_decision == "deny"


# --------------------------------------------------------------------------- #
# Membrane decision domain — DENY / QUARANTINE / REQUIRE_SIGNATURE / REDACT
# --------------------------------------------------------------------------- #

def test_membrane_deny():
    r = resolve_capability(req(membrane_decision="DENY"))
    assert r.execution_decision == "deny"
    assert r.verdict == "denied"


def test_membrane_quarantine_denies():
    r = resolve_capability(req(membrane_decision="QUARANTINE"))
    assert r.execution_decision == "deny"


def test_require_signature_defers():
    r = resolve_capability(req(membrane_decision="REQUIRE_SIGNATURE"))
    assert r.execution_decision == "ask"
    assert r.verdict == "deferred"
    assert r.allowed is False


def test_redact_rewrites_with_mask_obligation():
    r = resolve_capability(req(membrane_decision="REDACT"))
    assert r.execution_decision == "rewrite"
    assert {"name": "mask_fields", "when": "runtime"} in r.obligations
    # rewrite still proceeds (masked), so the receipt verdict is allowed
    assert r.verdict == "allowed"


# --------------------------------------------------------------------------- #
# Autonomy ladder (fail-closed, mirrors tritfabric autonomy_gate)
# --------------------------------------------------------------------------- #

def test_autonomy_overclaim_blocks():
    # Request L4 without the conductor_response_envelope evidence token.
    r = resolve_capability(req(requested_autonomy_level="L4", autonomy_evidence=()))
    assert r.autonomy.ok is False
    assert r.execution_decision == "deny"
    assert r.autonomy.granted_level == "L0"


def test_autonomy_admitted_with_evidence():
    r = resolve_capability(req(requested_autonomy_level="L4",
                               autonomy_evidence=("conductor_response_envelope",)))
    assert r.autonomy.ok is True
    assert r.execution_decision == "allow"


def test_evaluate_autonomy_reports_ceiling():
    d = evaluate_autonomy("L5", ("evidence_dossier",))
    assert d.ok is False
    assert d.granted_level == "L3"          # ceiling the evidence supports
    assert "at most L3" in d.reason


def test_autonomy_l0_always_satisfied():
    d = evaluate_autonomy("L0", ())
    assert d.ok is True


# --------------------------------------------------------------------------- #
# Enforce-vs-observe — the honesty boundary over foreign surfaces
# --------------------------------------------------------------------------- #

def test_foreign_surface_is_observed_not_enforced():
    # A frontier client's computer_use: we cannot prevent it, only receipt it.
    r = resolve_capability(req(surface="computer", action="computer.screencapture",
                               access_level="control", tension_members=FULL_TENSION,
                               membrane_decision="ALLOW", owned=False))
    assert r.enforced is False
    assert r.verdict == "observed"
    assert r.allowed is False               # advisory, never counts as an enforced allow
    assert any("foreign surface" in x for x in r.reasons)
    assert r.receipt["receiptClass"] == "probe"


def test_owned_surface_enforces():
    r = resolve_capability(req(surface="shell", action="shell.exec",
                               access_level="scopedWrite", owned=True))
    assert r.enforced is True
    assert r.receipt["receiptClass"] == "execution"


# --------------------------------------------------------------------------- #
# Radius floors — OS/deploy surfaces never sit below their floor
# --------------------------------------------------------------------------- #

def test_computer_surface_floors_to_r3():
    r = resolve_capability(req(surface="computer", action="computer.click",
                               access_level="none", tension_members=FULL_TENSION))
    assert r.radius == "R3"


def test_destructive_deployment_requires_r5_authority():
    # destructive → R5, which needs post_authority_ref. Provide everything but it.
    partial = tuple(m for m in TENSION_REQUIRED["R5"] if m != "post_authority_ref")
    r = resolve_capability(req(surface="deployment", action="deployment.apply",
                               access_level="destructive", tension_members=partial))
    assert r.radius == "R5"
    assert "post_authority_ref" in r.missing_tension
    assert r.execution_decision == "deny"


# --------------------------------------------------------------------------- #
# Receipt + seal conformance (sourceos-spec + agentplane binding)
# --------------------------------------------------------------------------- #

def test_receipt_conforms_to_agent_machine_receipt():
    r = resolve_capability(req())
    rc = r.receipt
    assert rc["type"] == "AgentMachineReceipt"
    assert rc["specVersion"] == "2.0.0"
    assert rc["verdict"] in {"allowed", "denied", "deferred", "failed", "observed"}
    assert SHA256.match(rc["decisionHash"])
    assert SHA256.match(rc["evidenceHash"])
    assert rc["id"].startswith("urn:srcos:agent-machine-receipt:")


def test_seal_is_deterministic_and_tamper_evident():
    r = resolve_capability(req())
    again = seal_receipt(r.receipt)
    assert again["sealHash"] == r.sealed["sealHash"]       # deterministic
    mutated = dict(r.receipt, verdict="allowed_but_tampered")
    assert seal_receipt(mutated)["sealHash"] != r.sealed["sealHash"]  # tamper-evident
    assert SHA256.match(r.sealed["sealHash"])
    assert r.sealed["type"] == "SealedReasoningEvidence"


def test_unknown_membrane_decision_raises():
    import pytest
    with pytest.raises(ValueError):
        resolve_capability(req(membrane_decision="MAYBE"))


# --------------------------------------------------------------------------- #
# Reference wiring — compose over the owned policy-fabric operation surface
# --------------------------------------------------------------------------- #

def test_operation_deny_composes_to_deny():
    request = request_from_operation_decision(
        operation("deny"), surface="deployment", access_level="scopedWrite",
        tension_members=FULL_TENSION)
    assert request.membrane_decision == "DENY"
    r = resolve_capability(request)
    assert r.execution_decision == "deny"
    # policy_refs from the operation's basis carry through onto the receipt
    assert "urn:srcos:policy:ops-default" in r.receipt["policyDecisionRef"]


def test_operation_unknown_fails_closed_to_quarantine():
    request = request_from_operation_decision(
        operation("unknown"), surface="deployment", access_level="scopedWrite",
        tension_members=FULL_TENSION)
    assert request.membrane_decision == "QUARANTINE"
    assert resolve_capability(request).execution_decision == "deny"


def test_operation_allow_with_human_approval_requires_signature():
    request = request_from_operation_decision(
        operation("allow", controls={"requires_human_approval": True}),
        surface="deployment", access_level="scopedWrite", tension_members=FULL_TENSION)
    assert request.membrane_decision == "REQUIRE_SIGNATURE"
    assert resolve_capability(request).execution_decision == "ask"


def test_operation_clean_allow_flows_through():
    request = request_from_operation_decision(
        operation("allow"), surface="deployment", access_level="scopedWrite",
        tension_members=FULL_TENSION)
    r = resolve_capability(request)
    assert r.execution_decision == "allow"
    assert r.receipt["decision"]["riskLevel"] == "high"


# --------------------------------------------------------------------------- #
# The callable gate seam a runtime invokes before executing a tool call.
# --------------------------------------------------------------------------- #

_FULL = ["policy", "identity", "provenance", "evidence", "replay", "revocation", "audit", "post_authority_ref"]


def test_gate_allows_and_returns_sealed_receipt():
    d = gate({
        "surface": "filesystem", "action": "filesystem.read", "access_level": "readOnly",
        "subject_ref": "urn:srcos:agent:x", "tension_members": ["policy", "identity", "provenance"],
    })
    assert d["allowed"] is True
    assert d["execution_decision"] == "allow"
    assert d["sealed_receipt"]["sealHash"].startswith("sha256:")


def test_gate_denies_fail_closed_on_missing_tension():
    d = gate({
        "surface": "shell", "action": "shell.exec", "access_level": "scopedWrite",
        "subject_ref": "urn:srcos:agent:x", "tension_members": ["policy", "identity"],
    })
    assert d["allowed"] is False
    assert d["execution_decision"] == "deny"
    assert d["missing_tension"]  # non-empty


def test_gate_rejects_unknown_fields():
    import pytest
    with pytest.raises(ValueError):
        gate({"surface": "shell", "access_level": "readOnly", "not_a_field": 1})


def _cli_request(payload: dict) -> int:
    proc = subprocess.run(
        [sys.executable, str(_MEMBRANE), "--request", "-"],
        input=json.dumps(payload), capture_output=True, text=True,
    )
    return proc.returncode


def test_cli_request_mode_is_fail_closed():
    # allowed → exit 0; denied → exit 3 (a runtime gates on the exit code).
    assert _cli_request({
        "surface": "filesystem", "action": "filesystem.read", "access_level": "readOnly",
        "subject_ref": "urn:srcos:agent:x", "tension_members": ["policy", "identity", "provenance"],
    }) == 0
    assert _cli_request({
        "surface": "shell", "action": "shell.exec", "access_level": "scopedWrite",
        "subject_ref": "urn:srcos:agent:x", "tension_members": ["policy", "identity"],
    }) == 3
