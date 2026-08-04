"""Negative control for the ResourceContract producer's verdict algebra + schema conformance.

The producer emits the SufficiencyVerdict independently of the devsecops consumer; the two MUST
agree, or the loop speaks two languages. These tests pin every precedence branch (so the algebra
is proven to DISCRIMINATE, not rubber-stamp) and prove a synthetic emitted contract validates
against the real sourceos-spec ResourceContract schema when it is reachable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import emit_resource_contracts as erc  # noqa: E402


# ── the verdict algebra must discriminate all four branches ──────────────────────
def test_gate_ineligible_is_inconclusive():
    # e.g. CPU: peak measured but the throttle signal (fired) is unknown → not gate-eligible
    assert erc.expected_verdict(peak=999, limit=1, fired_count=None,
                                gate_eligible=False, enforcement="throttle") == "INCONCLUSIVE"


def test_enforcing_and_fired_is_proved():
    assert erc.expected_verdict(peak=1, limit=1, fired_count=3,
                                gate_eligible=True, enforcement="terminate") == "PROVED"


def test_exceeded_and_never_fired_is_violation():
    assert erc.expected_verdict(peak=2.0, limit=1.0, fired_count=0,
                                gate_eligible=True, enforcement="terminate") == "VIOLATION"


def test_under_limit_never_fired_is_inconclusive():
    # the healthy-but-untested case that dominates a fresh cluster: teeth unproven, no breach
    assert erc.expected_verdict(peak=0.3, limit=1.0, fired_count=0,
                                gate_eligible=True, enforcement="terminate") == "INCONCLUSIVE"


def test_observe_mode_exceedance_is_not_violation():
    # a gauge makes no enforcement promise, so it cannot violate one
    assert erc.expected_verdict(peak=2.0, limit=1.0, fired_count=0,
                                gate_eligible=True, enforcement="observe") == "INCONCLUSIVE"


# ── unit conversions the producer relies on ─────────────────────────────────────
@pytest.mark.parametrize("s,want", [("500m", 500.0), ("2", 2000.0), ("250000u", 250.0), ("", None)])
def test_cpu_to_millicores(s, want):
    assert erc._cpu_to_millicores(s) == want


@pytest.mark.parametrize("s,want", [("128Mi", 128 * 1024**2), ("1Gi", 1024**3), ("", None)])
def test_mem_to_bytes(s, want):
    assert erc._mem_to_bytes(s) == want


# ── a synthetic emitted contract validates against the real schema ──────────────
def test_synthetic_contract_matches_sourceos_spec_schema():
    spec = Path.home() / "dev/sourceos-spec/schemas"
    if not (spec / "ResourceContract.json").is_file():
        pytest.skip("sourceos-spec schema not reachable in this environment")
    import json
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    rc = json.loads((spec / "ResourceContract.json").read_text())
    meas = json.loads((spec / "Measurement.json").read_text())
    rc["properties"]["observedPeak"] = {k: v for k, v in meas.items() if k not in ("$schema", "$id")}
    contract = {
        "schemaVersion": "0.1.0", "kind": "ResourceContract", "contractId": "x-memory",
        "resource": "memory", "limit": {"value": 134217728, "unit": "bytes"},
        "window": "PT12S", "scope": "tenant", "enforcement": "terminate",
        "negativeControl": "conformance/k8s-resource-enforcement-fires.md", "firedCount": 0,
        "observedPeak": {
            "schemaVersion": "0.1.0", "kind": "Measurement", "label": "x memory peak",
            "value": 40000000.0, "source": "measured", "instrument": "kubectl top (metrics-server)",
            "sampling": {"observed": 3, "population": 3, "unit": "samples"},
            "unobserved": 0, "gateEligible": True,
        },
    }
    errs = list(Draft202012Validator(rc).iter_errors(contract))
    assert not errs, f"synthetic contract is not schema-valid: {[e.message for e in errs][:3]}"


def test_negative_control_procedure_exists():
    """The negativeControl every emitted enforcing contract references must resolve."""
    assert (ROOT / "conformance" / "k8s-resource-enforcement-fires.md").is_file()
