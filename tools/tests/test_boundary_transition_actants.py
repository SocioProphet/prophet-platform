"""Tests for BoundaryTransition v0.2 actantial frame — both ways.

The frame is only worth adding if it is enforced: a crossing that omits who or
what is doing the acting must be REFUSED, and the closed inventory must reject an
invented role. The skeleton must drop surface while keeping shape.
"""

from __future__ import annotations

import json
import pathlib

from tools.boundary_transition_actants import (
    REQUIRED_ROLES,
    ROLES,
    is_valid,
    skeleton,
    validate_actants,
    validate_boundary_transition,
)


def _full_actants() -> dict:
    return {
        "root": "summarize",
        "initiator": "prophet-mesh/research-agent",
        "interactant": "filing/ASX-GYG",
        "recipient": "analyst",
        "cause": "requested briefing",
        "time": "2026-08-01T18:45:00Z",
        "place": "ai-invocation-boundary",
        "intention": "decision-ready briefing",
        "manner": "extractive, no network",
    }


# -- pass path -------------------------------------------------------------- #


def test_nine_roles_defined():
    assert len(ROLES) == 9
    assert REQUIRED_ROLES == ("root", "initiator")


def test_full_frame_valid():
    assert validate_actants(_full_actants()) == []


def test_minimal_frame_valid():
    assert validate_actants({"root": "open", "initiator": "user"}) == []


# -- refusal paths ---------------------------------------------------------- #


def test_missing_root_refused():
    a = _full_actants()
    del a["root"]
    assert any("'root'" in e for e in validate_actants(a))


def test_missing_initiator_refused():
    a = _full_actants()
    del a["initiator"]
    assert any("'initiator'" in e for e in validate_actants(a))


def test_empty_required_role_refused():
    a = _full_actants()
    a["initiator"] = ""
    assert any("'initiator'" in e for e in validate_actants(a))


def test_unknown_role_refused():
    a = _full_actants()
    a["vibe"] = "good"
    assert any("unknown actant role" in e and "vibe" in e for e in validate_actants(a))


def test_non_string_optional_role_refused():
    a = _full_actants()
    a["manner"] = 42
    assert any("'manner'" in e for e in validate_actants(a))


def test_actants_must_be_object():
    assert validate_actants(["root", "initiator"])


# -- envelope-level obligation ---------------------------------------------- #


def test_v02_requires_actants():
    doc = {"schemaVersion": "v0.2", "kind": "BoundaryTransition"}
    assert any("requires an 'actants' frame" in e for e in validate_boundary_transition(doc))


def test_v01_schemaversion_refused_on_v02_validator():
    doc = {"schemaVersion": "v0.1", "actants": {"root": "x", "initiator": "y"}}
    assert not is_valid(doc)


# -- de-identification lever ------------------------------------------------ #


def test_skeleton_drops_surface_keeps_shape():
    sk = skeleton(_full_actants())
    assert sk == {role: True for role in ROLES}
    # every value is a plain boolean — no descriptor text survives
    assert all(isinstance(v, bool) for v in sk.values())


def test_skeleton_marks_absent_roles_false():
    sk = skeleton({"root": "open", "initiator": "user"})
    assert sk["root"] is True and sk["initiator"] is True
    assert sk["recipient"] is False and sk["intention"] is False


# -- shipped example -------------------------------------------------------- #


def test_shipped_example_valid():
    example = (
        pathlib.Path(__file__).resolve().parents[2]
        / "contracts" / "examples" / "boundary-transition-v0.2-ai-invocation.example.json"
    )
    doc = json.loads(example.read_text(encoding="utf-8"))
    assert validate_boundary_transition(doc) == []
