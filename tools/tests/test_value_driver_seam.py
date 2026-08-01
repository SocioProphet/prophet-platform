from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import emit_value_driver_score as vd  # type: ignore

SCHEMA = json.loads(
    (ROOT / "contracts" / "crystal-atlas" / "events" / "intel.value_driver.scored.v0.schema.json").read_text()
)
EXAMPLE = ROOT / "contracts" / "crystal-atlas" / "examples" / "intel.value_driver.scored.v0.json"


def test_committed_example_conforms():
    errors = list(Draft202012Validator(SCHEMA).iter_errors(json.loads(EXAMPLE.read_text())))
    assert errors == [], [e.message for e in errors]


def test_substitution_finding_scores_and_conforms():
    finding = {
        "source_event_type": "procurement.substitution.recommended.v0",
        "source_event_id": "corr-1",
        "estimated_savings_pct": 60.0,
        "substitution_confidence": 80.0,
        "coverage_completeness": 100.0,
        "epistemic_level": "empirical",
    }
    ev = vd.compute_scored_event(finding, subject="vendor://acme")
    # 0.5*60 + 0.3*80 + 0.2*100 = 30 + 24 + 20 = 74
    assert ev["overall_value_score"] == 74.0
    assert {d["driver"] for d in ev["value_drivers"]} == {"Cost Efficiency", "Switching Risk", "Continuity"}
    errors = list(Draft202012Validator(SCHEMA).iter_errors(ev))
    assert errors == [], [e.message for e in errors]


def test_diligence_risk_is_inverted():
    finding = {
        "source_event_type": "diligence.risk.pack.generated.v0",
        "source_event_id": "corr-2",
        "risk_score": 70.0,
        "coverage_completeness": 50.0,
    }
    ev = vd.compute_scored_event(finding, subject="target://x")
    # risk_exposure = (100-70)=30 *0.6 = 18 ; coverage 50 *0.4 = 20 ; overall 38
    assert ev["overall_value_score"] == 38.0
    assert list(Draft202012Validator(SCHEMA).iter_errors(ev)) == []


def test_emit_refuses_out_of_contract_event(tmp_path, monkeypatch):
    # Fail-closed: an unknown/missing source_event_type must not enter append-only state.
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    ev = vd.compute_scored_event(
        {"source_event_type": "something.else.v0", "source_event_id": "c3", "value_score": 42.0},
        subject="x",
    )
    import pytest

    with pytest.raises(vd.OutOfContractEvent):
        vd.emit(ev)
    # nothing was written
    assert not (tmp_path / "prophet-platform").exists()

    # a missing source_event_id is also refused
    good_type = vd.compute_scored_event(
        {"source_event_type": "procurement.substitution.recommended.v0", "source_event_id": "", "estimated_savings_pct": 10},
        subject="x",
    )
    with pytest.raises(vd.OutOfContractEvent):
        vd.emit(good_type)


def test_emit_writes_a_valid_event(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    ev = vd.compute_scored_event(
        {"source_event_type": "procurement.substitution.recommended.v0", "source_event_id": "c1", "estimated_savings_pct": 60, "substitution_confidence": 80, "coverage_completeness": 100},
        subject="vendor://acme",
    )
    corr = vd.emit(ev)
    assert (tmp_path / "prophet-platform" / "payloads" / "value-driver-scorer" / f"{corr}.payload.json").exists()


def test_unknown_type_fallback_is_out_of_contract():
    # The emitter still computes a generic fallback score for resilience...
    ev = vd.compute_scored_event(
        {"source_event_type": "something.else.v0", "source_event_id": "c3", "value_score": 42.0},
        subject="x",
    )
    assert ev["overall_value_score"] == 42.0
    assert len(ev["value_drivers"]) == 1
    # ...but the schema admits only the four Crystal Atlas downstream types, so an
    # out-of-contract source_event_type is (correctly) rejected — the enum has teeth.
    errors = list(Draft202012Validator(SCHEMA).iter_errors(ev))
    assert errors, "expected the strict source_event_type enum to reject an unknown finding type"
