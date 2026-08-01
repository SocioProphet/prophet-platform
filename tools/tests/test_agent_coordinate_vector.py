"""Tests for AgentCoordinateVector (S0).

Every gate is exercised BOTH ways. The headline rule — 'an agent with ten or
twelve coordinates is REJECTED' — is pinned by an explicit drop-one and add-one
test, not merely by a happy-path pass.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from tools.agent_coordinate_vector import (
    AXES,
    OPERATOR_AXES,
    is_valid,
    validate,
)


def _valid_vector() -> dict:
    coords = {axis: {"primary": False, "operator": "none"} for axis in AXES}
    coords["tiferet"] = {"primary": True, "operator": "meet"}
    coords["chesed"]["operator"] = "pushout"
    coords["gevurah"]["operator"] = "pullback"
    return {
        "schemaVersion": "v0.1",
        "kind": "AgentCoordinateVector",
        "agentId": "michael-agent",
        "coordinates": coords,
    }


# --------------------------------------------------------------------------- #
# The pass path
# --------------------------------------------------------------------------- #


def test_canonical_vector_is_valid():
    assert validate(_valid_vector()) == []
    assert is_valid(_valid_vector())


def test_exactly_eleven_axes_present():
    assert len(AXES) == 11


# --------------------------------------------------------------------------- #
# 'ten or twelve is rejected' — the headline, both directions
# --------------------------------------------------------------------------- #


def test_ten_coordinates_rejected():
    doc = _valid_vector()
    del doc["coordinates"]["hod"]  # now ten
    errs = validate(doc)
    assert any("missing coordinate axes" in e and "hod" in e for e in errs)
    assert not is_valid(doc)


def test_twelve_coordinates_rejected():
    doc = _valid_vector()
    doc["coordinates"]["shadow"] = {"primary": False}  # now twelve
    errs = validate(doc)
    assert any("unknown coordinate axes" in e and "shadow" in e for e in errs)
    assert not is_valid(doc)


# --------------------------------------------------------------------------- #
# exactly one primary — rejects zero and two
# --------------------------------------------------------------------------- #


def test_zero_primaries_rejected():
    doc = _valid_vector()
    doc["coordinates"]["tiferet"]["primary"] = False
    assert any("no primary axis" in e for e in validate(doc))


def test_two_primaries_rejected():
    doc = _valid_vector()
    doc["coordinates"]["malchut"]["primary"] = True  # tiferet already primary
    errs = validate(doc)
    assert any("exactly one primary" in e for e in errs)


def test_non_boolean_primary_rejected():
    doc = _valid_vector()
    doc["coordinates"]["binah"]["primary"] = "yes"
    assert any("boolean 'primary'" in e for e in validate(doc))


# --------------------------------------------------------------------------- #
# operator-axis coherence — the middle column cannot be miswired
# --------------------------------------------------------------------------- #


def test_tiferet_must_be_meet():
    doc = _valid_vector()
    doc["coordinates"]["tiferet"]["operator"] = "pushout"
    errs = validate(doc)
    assert any("must be realised by 'meet'" in e for e in errs)


def test_gevurah_cannot_glue():
    doc = _valid_vector()
    doc["coordinates"]["gevurah"]["operator"] = "pushout"  # restrictive axis gluing
    errs = validate(doc)
    assert any("gevurah" in e and "pullback" in e for e in errs)


def test_non_operator_axis_claiming_operator_rejected():
    doc = _valid_vector()
    doc["coordinates"]["netzach"]["operator"] = "meet"
    assert any("not an operator axis" in e for e in validate(doc))


def test_unknown_operator_rejected():
    doc = _valid_vector()
    doc["coordinates"]["chesed"]["operator"] = "colimit"
    assert any("unknown operator" in e for e in validate(doc))


def test_operator_axes_have_expected_operators():
    assert OPERATOR_AXES == {"chesed": "pushout", "gevurah": "pullback", "tiferet": "meet"}


# --------------------------------------------------------------------------- #
# envelope
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("field,bad", [("schemaVersion", "v9"), ("kind", "Nope")])
def test_envelope_constants_enforced(field, bad):
    doc = _valid_vector()
    doc[field] = bad
    assert not is_valid(doc)


def test_missing_agent_id_rejected():
    doc = _valid_vector()
    doc["agentId"] = ""
    assert any("agentId" in e for e in validate(doc))


def test_coordinates_must_be_object():
    doc = _valid_vector()
    doc["coordinates"] = []
    assert any("coordinates must be an object" in e for e in validate(doc))


def test_non_object_document_rejected():
    assert validate("not a dict")
    assert validate(None)


# --------------------------------------------------------------------------- #
# the shipped example validates
# --------------------------------------------------------------------------- #


def test_shipped_example_is_valid():
    example = (
        pathlib.Path(__file__).resolve().parents[2]
        / "contracts" / "examples" / "agent-coordinate-vector-michael-agent.example.json"
    )
    doc = json.loads(example.read_text(encoding="utf-8"))
    assert validate(doc) == []
