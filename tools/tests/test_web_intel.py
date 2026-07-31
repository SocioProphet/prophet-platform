from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import emit_web_intel_scorecard as em  # type: ignore
import validate_web_intel_contracts as vc  # type: ignore

LANE = ROOT / "contracts" / "web-intel"


def test_meet_is_lowest_level():
    assert em.meet_all(["proved", "empirical", "synthetic"]) == "synthetic"
    assert em.meet_all(["proved", "bounded"]) == "bounded"


def test_rejected_absorbs():
    assert em.meet_all(["proved", "rejected"]) == "rejected"


def test_empty_meet_is_speculative():
    assert em.meet_all([]) == "speculative"


def test_compute_scorecard_conforms_and_meets():
    components = [
        json.loads((LANE / "examples" / "site_audit.completed.json").read_text()),
        json.loads((LANE / "examples" / "backlink_profile.assessed.json").read_text()),
        json.loads((LANE / "examples" / "ai_visibility.probed.json").read_text()),
        json.loads((LANE / "examples" / "serp_rank.tracked.json").read_text()),
    ]
    sc = em.compute_scorecard(components, subject="socioprophet.com", relation="self")

    # overall level is the meet of components (all empirical here).
    assert sc["overall_epistemic_level"] == "empirical"
    # headline was extracted from the heterogeneous components.
    assert sc["headline"]["site_health_score"] == 61.5
    assert sc["headline"]["ai_visibility_score"] == 40.0
    assert sc["headline"]["share_of_voice_pct"] == 6.2
    assert len(sc["value_drivers"]) == 4

    # and it validates against the committed scorecard schema.
    schema = json.loads((LANE / "events" / "webintel.scorecard.generated.v0.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(sc))
    assert errors == [], [e.message for e in errors]


def test_one_weak_component_caps_the_scorecard():
    components = [
        {"event_id": "a", "epistemic_level": "proved", "site_health_score": 90},
        {"event_id": "b", "epistemic_level": "synthetic", "authority_score": 50},
    ]
    sc = em.compute_scorecard(components, subject="x.example", relation="competitor")
    assert sc["overall_epistemic_level"] == "synthetic"  # capped by the weakest


def test_contracts_validator_passes():
    assert vc.main() == 0
