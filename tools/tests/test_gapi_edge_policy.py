"""Executable gapi edge policy — every gapi hyperedge resolves through the membrane.

Turns the gapi recon's descriptive guards into executable policy: each edge in
`fixtures/capability-membrane/gapi-edge-policy.json` is run through
resolve_capability and must produce the annotated ExecutionDecision, for both
the nominal (guards satisfied) and violated (a guard fails) cases. This makes
the two models one — the gapi hypergraph and the membrane agree by construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.capability_membrane import CapabilityRequest, TENSION_REQUIRED, resolve_capability

POLICY = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures/capability-membrane/gapi-edge-policy.json").read_text()
)
FULL_TENSION = TENSION_REQUIRED["R5"]


def _resolve(edge, membrane_decision):
    req = CapabilityRequest(
        surface=edge["surface"], action=edge["action"], access_level=edge["access_level"],
        subject_ref="urn:srcos:agent:gapi-edge", tension_members=FULL_TENSION,
        membrane_decision=membrane_decision,
    )
    return resolve_capability(req)


def _cases():
    for edge in POLICY["edges"]:
        yield pytest.param(edge, "nominal", id=f"{edge['edge_id']}-nominal")
        if "violated" in edge:
            yield pytest.param(edge, "violated", id=f"{edge['edge_id']}-violated")


@pytest.mark.parametrize("edge,case", list(_cases()))
def test_gapi_edge_resolves_to_annotated_decision(edge, case):
    spec = edge[case]
    r = _resolve(edge, spec["membrane_decision"])
    assert r.execution_decision == spec["expect_execution"], (
        f"{edge['edge_id']} [{case}] expected {spec['expect_execution']}, got {r.execution_decision}"
    )


def test_every_edge_has_a_nominal_decision():
    # No gapi edge is left un-governed.
    assert len(POLICY["edges"]) == 11
    for edge in POLICY["edges"]:
        assert "nominal" in edge and edge["nominal"]["membrane_decision"]


def test_all_five_membrane_decisions_are_exercised():
    seen = set()
    for edge in POLICY["edges"]:
        for case in ("nominal", "violated"):
            if case in edge:
                seen.add(edge[case]["membrane_decision"])
    assert seen == {"ALLOW", "DENY", "QUARANTINE", "REDACT", "REQUIRE_SIGNATURE"}
