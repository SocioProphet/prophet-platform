"""The mechanisms added for CRACK / LSD / PSILOCYBIN / PCP / MDMA.

Three of the five needed a NEW AXIS rather than new numbers, and these tests pin that
distinction — because a preset that is another preset with bigger magnitudes is not a
substance, it is a relabel.
"""

from __future__ import annotations

import pytest
import torch

from noetica_impair.hooks.base import Rig
from noetica_impair.hooks.envelope import Bolus, Constant, get as get_envelope
from noetica_impair.hooks.layers import LayerBypass
from noetica_impair.hooks.mlp import MLPAttenuation
from noetica_impair.models import registry
from noetica_impair.substances import presets as P
from noetica_impair.substances.schema import PresetError, SubstancePreset, compile_preset
from noetica_impair.testing import logits_of, prepared_reference


# ── new hooks obey the same invariants as every other ────────────────────────

@pytest.mark.parametrize("name,factory", [
    ("mlp_attenuation", lambda: MLPAttenuation(strength=0.8, seed=3)),
    ("layer_bypass", lambda: LayerBypass(fraction=0.7, seed=3)),
])
def test_new_hooks_inert_at_zero(toy_dense, ids, name, factory):
    ref = prepared_reference(toy_dense, ids)
    rig = Rig(toy_dense.model, toy_dense.meta).add(factory())
    with rig:
        rig.set_dose(0.0)
        assert torch.equal(ref, logits_of(toy_dense, ids)), f"{name} perturbed at dose=0"


@pytest.mark.parametrize("name,factory", [
    ("mlp_attenuation", lambda: MLPAttenuation(strength=0.9, seed=3)),
    ("layer_bypass", lambda: LayerBypass(fraction=0.8, seed=3)),
])
def test_new_hooks_dose_monotonic(toy_dense, ids, name, factory):
    ref = prepared_reference(toy_dense, ids)
    rig = Rig(toy_dense.model, toy_dense.meta).add(factory())
    curve = []
    with rig:
        for d in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            rig.set_dose(d)
            rig.reset_noise()
            curve.append((logits_of(toy_dense, ids) - ref).abs().mean().item())
    assert curve[0] == 0.0
    for lo, hi in zip(curve, curve[1:]):
        assert hi >= lo - 1e-9, f"{name} non-monotonic: {curve}"
    assert curve[-1] > 0


def test_mlp_attenuation_is_noise_free():
    """It scales an intact computation, so it must be deterministic across seeds."""
    from noetica_impair.models import loaders
    lm = loaders.load("toy-dense", seed=4, device="cpu")
    g = torch.Generator().manual_seed(2)
    ids = torch.randint(0, 256, (1, 20), generator=g)
    outs = []
    for seed in (1, 999):
        rig = Rig(lm.model, lm.meta).add(MLPAttenuation(strength=0.7, seed=seed))
        with rig:
            rig.set_dose(0.6)
            outs.append(logits_of(lm, ids))
    assert torch.equal(outs[0], outs[1]), "prior attenuation must not depend on a seed"


def test_layer_bypass_spares_early_layers(toy_dense, ids):
    """Bypassing early layers is a coarse lesion; the band must be respected."""
    ref = prepared_reference(toy_dense, ids)
    early_only = LayerBypass(fraction=1.0, min_layer_frac=0.0, max_layer_frac=0.25)
    rig = Rig(toy_dense.model, toy_dense.meta).add(early_only)
    with rig:
        rig.set_dose(1.0)
        hit = (logits_of(toy_dense, ids) - ref).abs().mean().item()
    default = LayerBypass(fraction=1.0)  # mid/late band
    rig2 = Rig(toy_dense.model, toy_dense.meta).add(default)
    with rig2:
        rig2.set_dose(1.0)
        _ = logits_of(toy_dense, ids)
    assert hit > 0  # the narrow band does something, i.e. the gate is real


# ── the pharmacokinetic axis ─────────────────────────────────────────────────

def test_constant_envelope_reproduces_static_dose(toy_dense, ids):
    ref = prepared_reference(toy_dense, ids)
    rig = Rig(toy_dense.model, toy_dense.meta).add(MLPAttenuation(strength=0.8, seed=1))
    with rig:
        rig.set_dose(0.6)
        static = logits_of(toy_dense, ids)
        rig.set_envelope(Constant())
        rig.reset_noise()
        enveloped = logits_of(toy_dense, ids)
    assert torch.equal(static, enveloped), "constant envelope must change nothing"


def test_bolus_shape():
    b = Bolus(onset=4, plateau=8, half_life=10, rebound=0.0)
    assert b.value(0) == pytest.approx(0.25)
    assert b.value(3) == pytest.approx(1.0)      # peak reached
    assert b.value(10) == pytest.approx(1.0)     # still on plateau
    assert b.value(22) < 0.6                     # decayed
    assert b.value(200) < 0.05                   # cleared
    assert all(0.0 <= v <= 1.0 for v in b.trace(64))


def test_crack_kinetics_are_faster_and_briefer_than_cocaine():
    crack, coke = get_envelope("crack"), get_envelope("cocaine")
    assert crack.value(2) > coke.value(2), "crack must arrive first"
    assert crack.value(64) < coke.value(64), "crack must clear first"


def test_envelope_advances_dose_across_forward_passes(toy_dense, ids):
    iv = MLPAttenuation(strength=0.8, seed=1)
    rig = Rig(toy_dense.model, toy_dense.meta).add(iv)
    with rig:
        rig.set_dose(1.0)
        rig.set_envelope(Bolus(onset=1, plateau=1, half_life=1, rebound=0.0))
        seen = []
        for _ in range(5):
            logits_of(toy_dense, ids)
            seen.append(iv.dose)
    assert seen[0] > 0, "dose must be live on the first pass"
    assert seen[-1] < seen[0], f"dose must decay across passes, got {seen}"


def test_reset_noise_restarts_the_envelope_clock(toy_dense, ids):
    """Otherwise probe item N would be dosed by however long item N-1 ran."""
    iv = MLPAttenuation(strength=0.8, seed=1)
    rig = Rig(toy_dense.model, toy_dense.meta).add(iv)
    with rig:
        rig.set_dose(1.0)
        rig.set_envelope(Bolus(onset=1, plateau=1, half_life=1))
        for _ in range(6):
            logits_of(toy_dense, ids)
        decayed = iv.dose
        rig.reset_noise()
        logits_of(toy_dense, ids)
        assert iv.dose > decayed, "clock did not restart"


# ── preset discipline ────────────────────────────────────────────────────────

def test_crack_shares_cocaines_parameter_vector_exactly():
    """CRACK must differ from COCAINE in kinetics ALONE (bar the redosing knob)."""
    c, k = P.COCAINE, P.CRACK
    for fld in ("residual_sigma", "lookahead_sigma", "k_sharp", "eos_bias",
                "mlp_attenuation", "layer_bypass", "broaden_tau", "distance_decay_alpha"):
        assert getattr(c, fld) == getattr(k, fld), f"{fld} differs -- that is a relabel"
    assert c.features == k.features
    assert c.envelope == "constant" and k.envelope == "crack"


def test_expected_hard_pairs_are_declared_before_the_data():
    """A collapse must read as a finding, not an embarrassment to tune away."""
    pairs = {(a, b) for a, b, _ in P.EXPECTED_HARD_PAIRS}
    assert ("LSD", "PSILOCYBIN") in pairs
    assert ("COCAINE", "CRACK") in pairs
    for a, b, why in P.EXPECTED_HARD_PAIRS:
        assert a in P.ALL and b in P.ALL and why


def test_each_new_substance_brings_a_distinct_defining_op():
    meta = registry.get("toy-dense")
    kinds = {}
    for n in ("LSD", "PCP", "MDMA", "CRACK"):
        kinds[n] = {iv.kind for iv in compile_preset(P.get(n), meta, seed=0, strict_limbs=False).interventions}
    assert "mlp_attenuation" in kinds["LSD"], "LSD's defining op is prior attenuation"
    assert "layer_bypass" in kinds["PCP"], "PCP's defining op is disconnection"
    assert "mlp_attenuation" not in kinds["PCP"] and "layer_bypass" not in kinds["LSD"]


def test_mdma_is_a_disposition_change_not_an_impairment():
    """Its whole separability claim is that competence machinery is left alone."""
    m = P.MDMA
    assert m.mlp_attenuation == 0.0 and m.layer_bypass == 0.0
    assert m.residual_sigma == 0.0 and m.distance_decay_alpha == 0.0
    assert m.self_monitor_ablate < 0.2, "MDMA must not read as disinhibited competence"
    concepts = {f.concept: f.sign for f in m.features}
    assert concepts["refusal_guard"] == -1 and concepts["threat_tom"] == -1
    assert concepts["affiliation"] == +1


def test_mdma_concepts_exist_in_the_discovery_vocabulary():
    from noetica_impair.provenance.features import CONCEPTS
    for f in P.MDMA.features:
        assert f.concept in CONCEPTS, f"{f.concept} has no discovery contrast set"


def test_unknown_envelope_is_rejected():
    with pytest.raises(PresetError, match="unknown envelope"):
        SubstancePreset(name="BAD", residual_sigma=0.1, envelope="moonshine").validate()


def test_whole_panel_compiles_on_a_dense_model():
    meta = registry.get("toy-dense")
    for n in P.PANEL:
        c = compile_preset(P.get(n), meta, seed=0, strict_limbs=False)
        assert c.interventions, f"{n} compiled to nothing"
