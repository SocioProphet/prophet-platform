from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import validate_control_plane_contracts as vc  # type: ignore

LANE = ROOT / "contracts" / "workspace-control-plane"


def _schema(name: str) -> dict:
    return json.loads((LANE / "schemas" / f"{name}.schema.json").read_text())


def _example(name: str) -> dict:
    return json.loads((LANE / "examples" / f"{name}.json").read_text())


def test_all_frozen_schemas_present_and_examples_conform():
    assert vc.main() == 0


def test_claim_requires_epistemic_and_contradiction_status():
    schema = _schema("claim.v0")
    bad = _example("claim.v0")
    del bad["contradiction_status"]
    assert list(Draft202012Validator(schema).iter_errors(bad)), "claim must require contradiction_status"

    bad2 = _example("claim.v0")
    bad2["epistemic_level"] = "made-up"
    assert list(Draft202012Validator(schema).iter_errors(bad2)), "epistemic_level enum must have teeth"


def test_attention_mark_mode_enum_has_teeth():
    schema = _schema("attention-mark.v0")
    bad = _example("attention-mark.v0")
    bad["mode"] = "snooze"  # not in pin|watch|revisit|incubate|hold|forget
    assert list(Draft202012Validator(schema).iter_errors(bad))


def test_signed_manifests_require_a_signature():
    for name in ("capability-manifest.v0", "topic-manifest.v0"):
        schema = _schema(name)
        bad = _example(name)
        del bad["signature"]
        assert list(Draft202012Validator(schema).iter_errors(bad)), f"{name} must require a signature"


def test_catalog_entry_requires_signatures_and_role_enum():
    schema = _schema("catalog-entry.v0")
    bad = _example("catalog-entry.v0")
    bad["role"] = "delegate"  # not a TUF role
    assert list(Draft202012Validator(schema).iter_errors(bad))


def test_discovery_policy_resolution_order_is_constrained():
    schema = _schema("discovery-policy.v0")
    bad = _example("discovery-policy.v0")
    bad["resolution_order"] = ["crawl_the_internet"]
    assert list(Draft202012Validator(schema).iter_errors(bad)), "resolution_order must be a constrained enum"


def test_event_is_object_centric():
    # case_id + object_refs + activity + actor are mandatory (spec D12).
    schema = _schema("event.v0")
    for field in ("case_id", "object_refs", "activity", "actor"):
        bad = _example("event.v0")
        del bad[field]
        assert list(Draft202012Validator(schema).iter_errors(bad)), f"event must require {field}"
