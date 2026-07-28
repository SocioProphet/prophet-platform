"""The forbidden-circuit gate, wired into compilation.

Available-but-not-called is not a gate. These pin that it actually blocks.
"""

from __future__ import annotations

import pytest

from noetica_impair.conformance.lawful import ForbiddenCircuit
from noetica_impair.models import registry
from noetica_impair.substances import presets as P
from noetica_impair.substances.schema import PresetError, compile_preset

GATE = ForbiddenCircuit(
    forbidden_circuit_id="fc-refusal-001", circuit_pattern=r"refusal|guard",
    prohibition_basis="ablating trained refusal behaviour is deployment-gated",
    enforcement_mode="deployment_gate", detection_method="concept match")
AUDIT = ForbiddenCircuit(
    forbidden_circuit_id="fc-threat-002", circuit_pattern=r"threat",
    prohibition_basis="threat-appraisal steering requires post-hoc audit",
    enforcement_mode="post_training_audit", detection_method="concept match")


@pytest.fixture
def meta():
    return registry.get("toy-dense")


def test_a_deployment_gated_preset_refuses_to_compile(meta):
    """MDMA suppresses refusal_guard — the case the gate exists for."""
    with pytest.raises(PresetError, match="deployment-gated circuit"):
        compile_preset(P.MDMA, meta, seed=0, strict_limbs=False, forbidden=[GATE])


def test_the_refusal_names_the_circuit_and_offers_no_override(meta):
    with pytest.raises(PresetError) as ei:
        compile_preset(P.MDMA, meta, seed=0, strict_limbs=False, forbidden=[GATE])
    msg = str(ei.value)
    assert "refusal_guard" in msg and "fc-refusal-001" in msg
    assert "no flag to override" in msg


def test_an_advisory_mode_compiles_and_is_recorded(meta):
    c = compile_preset(P.CANNABIS, meta, seed=0, strict_limbs=False, forbidden=[AUDIT])
    assert c.forbidden_advisory == ["threat_tom~fc-threat-002"]
    assert "forbidden_advisory" in c.describe()


def test_an_unaffected_preset_is_untouched(meta):
    c = compile_preset(P.COCAINE, meta, seed=0, strict_limbs=False, forbidden=[GATE, AUDIT])
    assert c.forbidden_advisory == []


def test_no_declarations_means_no_gate(meta):
    """Absent declarations must not silently block everything."""
    c = compile_preset(P.MDMA, meta, seed=0, strict_limbs=False)
    assert c.interventions


def test_the_gate_runs_before_interventions_are_built(meta):
    """A blocked preset must never yield a CompiledSubstance at all."""
    try:
        compile_preset(P.MDMA, meta, seed=0, strict_limbs=False, forbidden=[GATE])
        assert False, "should have raised"
    except PresetError:
        pass
