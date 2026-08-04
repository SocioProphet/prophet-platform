"""The DEPLOYED masking policy must actually mask.

These tests read `GATEWAY_MASKING_POLICY` out of deploy/values/compute-gateway.yaml — the
literal string the cluster will receive — rather than a fixture written to agree with them.
A policy that is only asserted to be correct in a test fixture proves nothing about the one
that ships, and this whole layer exists because the policy was previously absent and the PDP
silently returned outputs unchanged. A YAML typo must fail CI, not quietly revert the gateway
to passthrough.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
VALUES = ROOT / "deploy" / "values" / "compute-gateway.yaml"
sys.path.insert(0, str(ROOT / "apps" / "compute-gateway" / "src"))

from compute_gateway import masking  # noqa: E402
from compute_gateway.contract import ComputeOutput  # noqa: E402


@pytest.fixture(scope="module")
def deployed_policy() -> dict:
    raw = yaml.safe_load(VALUES.read_text(encoding="utf-8"))["config"]["GATEWAY_MASKING_POLICY"]
    return json.loads(raw)


@pytest.fixture(autouse=True)
def _install_policy(monkeypatch, deployed_policy):
    monkeypatch.setenv("GATEWAY_MASKING_POLICY", json.dumps(deployed_policy))
    monkeypatch.delenv("GATEWAY_MASKING_POLICIES", raising=False)


def _records(*recs) -> list[ComputeOutput]:
    """The PDP walks `data["nodes"]` and nothing else — see test_masking_coverage_boundary."""
    return [ComputeOutput(type="graph", data={"nodes": [dict(r) for r in recs]})]


def test_policy_is_parseable_and_non_empty(deployed_policy):
    """The failure this guards is a YAML/JSON typo silently disabling enforcement."""
    assert deployed_policy["mask_fields"], "an empty mask_fields set is passthrough with extra steps"
    assert deployed_policy["forbidden_mixtures"], "the no_health_adtech veto must be configured"
    assert deployed_policy.get("policy_version"), "a decision with no policy version is unattributable"


def test_direct_identifiers_are_masked_not_returned_raw(deployed_policy):
    out = masking.apply(
        _records({"email": "ada@example.com", "ssn": "123-45-6789", "city": "Cambridge"}),
        kind="graph-query", project="default", actor="analyst", entitlement=None)
    rec = out[0].data["nodes"][0]
    assert rec["email"] != "ada@example.com", "email left in cleartext by the deployed policy"
    assert rec["ssn"] != "123-45-6789", "ssn left in cleartext by the deployed policy"
    # A masking policy that redacts everything is useless; non-identifiers must survive.
    assert rec["city"] == "Cambridge"


def test_the_masking_decision_is_emitted_as_a_sealed_output():
    """The decision IS the evidence — that is the whole claim against WKC-style masking,
    whose enforcement leaves no verifiable artifact."""
    out = masking.apply(_records({"email": "ada@example.com"}),
                        kind="graph-query", project="default", actor="analyst", entitlement=None)
    decisions = [o for o in out if o.type == "masking-decision"]
    assert len(decisions) == 1, "no masking-decision output — the enforcement left no artifact"
    d = decisions[0].data
    assert d["schema_version"] == "identity-prime.masking-decision.v1"
    assert d["verdict"] == "allow_masked"
    assert d["applied_transforms"], "verdict claims masking but names no transformed field"


def test_forbidden_mixture_withholds_the_records_entirely():
    """no_health_adtech is a veto, not a masking rule: the records are withheld, not masked."""
    out = masking.apply(
        _records({"topic": "health", "email": "ada@example.com"}),
        kind="graph-query", project="default", actor="adtech-bot", entitlement="adtech")
    assert len(out) == 1 and out[0].type == "masking-decision", \
        "records survived a forbidden identity mixture — the veto did not withhold them"
    assert out[0].data["verdict"] == "deny"
    assert out[0].data["forbidden_mixture"]


def test_unknown_scheme_fails_closed(monkeypatch, deployed_policy):
    """Fail-closed under a bad policy: an unrecognised scheme must redact, never pass raw
    through. A typo in a scheme name is otherwise an invisible hole."""
    broken = json.loads(json.dumps(deployed_policy))
    broken["mask_fields"]["email"] = "not-a-real-scheme"
    monkeypatch.setenv("GATEWAY_MASKING_POLICY", json.dumps(broken))
    out = masking.apply(_records({"email": "ada@example.com"}),
                        kind="graph-query", project="default", actor="analyst", entitlement=None)
    assert out[0].data["nodes"][0]["email"] != "ada@example.com"


def test_non_read_kinds_are_untouched():
    """The PDP governs reads. A write path must not be silently rewritten by it."""
    assert "notebook" not in masking.READ_KINDS


def test_masking_coverage_boundary_is_nodes_only():
    """KNOWN LIMIT, asserted so it cannot be mistaken for coverage.

    masking._iter_records reads `data["nodes"]` and returns [] for anything else, so a result
    shaped as rows / table / edges is returned UNMASKED even with this policy active. That is
    the current boundary of the moat, not a claim about it. Widening it means changing
    _iter_records, which is a larger change than turning the policy on; this test exists so
    the next person reads the boundary from a failing assertion rather than from an incident.
    """
    rows = [ComputeOutput(type="table", data={"rows": [{"email": "ada@example.com"}]})]
    out = masking.apply(rows, kind="graph-query", project="default",
                        actor="analyst", entitlement=None)
    assert out[0].data["rows"][0]["email"] == "ada@example.com", \
        "row-shaped outputs are now masked — good; update this test and the PR note"
