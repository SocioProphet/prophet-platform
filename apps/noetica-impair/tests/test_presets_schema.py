"""Preset validation rules (work order section 4) and portability across archs."""

from __future__ import annotations

import pytest

from noetica_impair.models import registry
from noetica_impair.substances import presets as P
from noetica_impair.substances.schema import PresetError, SubstancePreset, compile_preset


def test_no_preset_enables_both_attention_ops():
    for name, preset in P.ALL.items():
        preset.validate()
        assert not (preset.distance_decay_alpha and preset.broaden_tau), name


def test_conflicting_attention_ops_rejected():
    bad = SubstancePreset(name="BAD", distance_decay_alpha=1.0, broaden_tau=1.0)
    with pytest.raises(PresetError, match="opposite"):
        bad.validate()


def test_conflicting_temperature_rejected():
    with pytest.raises(PresetError, match="flatten OR sharpen"):
        SubstancePreset(name="BAD", k_flat=1.0, k_sharp=1.0).validate()


def test_moe_ops_skip_on_dense_with_warning(caplog):
    """Portability rule: skip-and-log, never raise."""
    dense = registry.get("toy-dense")
    c = compile_preset(P.get("ALCOHOL_MOE"), dense, seed=0, strict_limbs=False)
    assert any("router_ops" in s for s in c.skipped)
    assert c.interventions, "the non-MoE limbs must still compile"


def test_moe_ops_compile_on_moe():
    moe = registry.get("toy-moe")
    c = compile_preset(P.get("ALCOHOL_MOE"), moe, seed=0, strict_limbs=False)
    assert not any("router_ops" in s for s in c.skipped)
    assert any(iv.kind == "router_ops" for iv in c.interventions)


def test_sae_ops_skipped_without_artifact():
    dense = registry.get("toy-dense")   # has_sae False
    c = compile_preset(P.get("ALCOHOL"), dense, seed=0, strict_limbs=False)
    assert any("sae_steer" in s for s in c.skipped)
    assert any("self_monitor_ablate" in s for s in c.skipped)


def test_placebo_is_refused():
    """A preset whose every op was skipped must not run labelled as a drug."""
    hollow = SubstancePreset(name="HOLLOW", router_sigma=1.0)
    with pytest.raises(PresetError, match="placebo"):
        compile_preset(hollow, registry.get("toy-dense"), seed=0)


def test_core_four_compile_to_distinct_intervention_profiles():
    """Necessary (not sufficient) for dissociation: the four presets are not aliases."""
    moe = registry.get("toy-moe")
    profiles = {}
    for name in P.CORE_FOUR:
        c = compile_preset(P.get(name), moe, seed=0, strict_limbs=False)
        profiles[name] = {iv.kind for iv in c.interventions}
    names = list(profiles)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert profiles[a] != profiles[b], f"{a} and {b} compile to the same ops"


def test_heroin_does_not_suppress_caution():
    """The stated distinction from ALCOHOL must be real in the preset, not just prose."""
    heroin_concepts = {f.concept for f in P.HEROIN.features}
    alcohol_concepts = {f.concept for f in P.ALCOHOL.features}
    assert "hedging_caution" in alcohol_concepts
    assert "hedging_caution" not in heroin_concepts
    assert "error_aversion" in heroin_concepts


def test_cannabis_paranoia_is_superlinear():
    threat = [f for f in P.CANNABIS.features if f.concept == "threat_tom"]
    assert threat and threat[0].dose_exponent > 1.0
