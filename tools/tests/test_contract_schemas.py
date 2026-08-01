"""Make the JSON-Schema contracts load-bearing, not decorative — both ways.

The review caught that the .json contracts were shipped but never exercised: nothing
checked they were well-formed, that the shipped examples conform, or that they REJECT a
malformed document. This closes that: each schema is validated as a Draft 2020-12 schema,
each example must conform, and a deliberately broken document must fail AT THE SCHEMA
(not only at the Python validator).
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

jsonschema = pytest.importorskip("jsonschema")

ROOT = pathlib.Path(__file__).resolve().parents[2]

PAIRS = [
    (
        "contracts/AgentCoordinateVector.v0.1.json",
        "contracts/examples/agent-coordinate-vector-michael-agent.example.json",
    ),
    (
        "contracts/BoundaryTransition.v0.2.json",
        "contracts/examples/boundary-transition-v0.2-ai-invocation.example.json",
    ),
]


def _load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("schema_rel,example_rel", PAIRS)
def test_schema_wellformed_and_example_conforms(schema_rel, example_rel):
    schema = _load(schema_rel)
    jsonschema.Draft202012Validator.check_schema(schema)  # the schema itself is valid
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(_load(example_rel)))
    assert errors == [], [e.message for e in errors]


def test_agent_coordinate_vector_schema_bites():
    schema = _load("contracts/AgentCoordinateVector.v0.1.json")
    v = jsonschema.Draft202012Validator(schema)
    good = _load("contracts/examples/agent-coordinate-vector-michael-agent.example.json")
    assert list(v.iter_errors(good)) == []
    # ten coordinates -> rejected by the SCHEMA (required), not only by the py validator
    ten = copy.deepcopy(good)
    del ten["coordinates"]["hod"]
    with pytest.raises(jsonschema.ValidationError):
        v.validate(ten)
    # twelve coordinates -> rejected (additionalProperties: false)
    twelve = copy.deepcopy(good)
    twelve["coordinates"]["shadow"] = {"primary": False}
    with pytest.raises(jsonschema.ValidationError):
        v.validate(twelve)


def test_boundary_transition_schema_bites():
    schema = _load("contracts/BoundaryTransition.v0.2.json")
    v = jsonschema.Draft202012Validator(schema)
    good = _load("contracts/examples/boundary-transition-v0.2-ai-invocation.example.json")
    assert list(v.iter_errors(good)) == []
    # v0.2 requires the actantial frame
    no_actants = copy.deepcopy(good)
    del no_actants["actants"]
    with pytest.raises(jsonschema.ValidationError):
        v.validate(no_actants)
    # an out-of-enum boundaryType is rejected
    bad_enum = copy.deepcopy(good)
    bad_enum["boundaryType"] = "telepathy"
    with pytest.raises(jsonschema.ValidationError):
        v.validate(bad_enum)
