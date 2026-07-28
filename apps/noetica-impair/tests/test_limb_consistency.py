"""The declared pharmacology must match the compiled parameter vector.

Presets carry a receptor-level story (``limbs``) and a set of numbers. Nothing
previously checked that these agreed, which is exactly how a preset ends up
justified by prose it does not implement — the failure that produced the wrong claim
"LSD and psilocybin differ mainly in duration".
"""

from __future__ import annotations

import pytest

from noetica_impair.models import registry
from noetica_impair.substances import limbs as L
from noetica_impair.substances import presets as P
from noetica_impair.substances.schema import PresetError, SubstancePreset


def has_field(preset: SubstancePreset, field: str) -> bool:
    v = getattr(preset, field, None)
    return bool(v) if not isinstance(v, (int, float)) else v != 0


@pytest.mark.parametrize("name", P.PANEL)
def test_every_substance_declares_limbs(name):
    assert P.get(name).limbs, f"{name} has no declared mechanism"


@pytest.mark.parametrize("name", P.PANEL)
def test_declared_limbs_are_present_in_the_parameter_vector(name):
    preset = P.get(name)
    for lid in preset.limbs:
        limb = L.get(lid)
        if not limb.requires_any:
            continue
        assert any(has_field(preset, f) for f in limb.requires_any), (
            f"{name} declares limb {lid!r} ({limb.receptor}) but none of "
            f"{limb.requires_any} is set — the prose and the numbers disagree"
        )


def test_unknown_limb_is_rejected():
    with pytest.raises(PresetError, match="unknown mechanism limb"):
        SubstancePreset(name="BAD", residual_sigma=0.1, limbs=("telepathy",)).validate()


# ── the specific corrections ─────────────────────────────────────────────────

def test_lsd_and_psilocybin_differ_by_more_than_duration():
    """The claim that started this: they do NOT differ mainly in duration."""
    shared = L.shared(P.LSD.limbs, P.PSILOCYBIN.limbs)
    sep = L.distinguishing(P.LSD.limbs, P.PSILOCYBIN.limbs)
    assert shared == {"ht2a_agonism"}, "they must share the psychedelic limb"
    assert sep == {"d2_partial", "ht1a_transporter"}, (
        "LSD carries D2 partial agonism psilocybin lacks; psilocin carries "
        "transporter/5-HT1A activity LSD lacks"
    )
    # And they take OPPOSITE signs on logit temperature, not merely different sizes.
    assert P.LSD.k_sharp > 0 and P.LSD.k_flat == 0
    assert P.PSILOCYBIN.k_flat > 0 and P.PSILOCYBIN.k_sharp == 0


def test_only_lsd_amplifies_reward_among_the_psychedelics():
    lsd = {f.concept for f in P.LSD.features}
    psi = {f.concept for f in P.PSILOCYBIN.features}
    assert "reward_value" in lsd, "the D2 limb"
    assert "reward_value" not in psi, "psilocybin has no meaningful D2 affinity"
    assert "self_reference" in psi, "ego dissolution"
    assert "self_reference" not in lsd


def test_cannabis_threat_is_biphasic_and_uniquely_so():
    """CB1 partial agonism flips sign: anxiolytic low, anxiogenic high."""
    threat = [f for f in P.CANNABIS.features if f.concept == "threat_tom"]
    assert threat and threat[0].biphasic_crossover is not None
    others = [
        n for n in P.PANEL if n != "CANNABIS"
        if any(f.biphasic_crossover is not None for f in P.get(n).features)
    ]
    assert not others, f"biphasic action should be unique to cannabis, also found in {others}"


def test_biphasic_op_actually_inverts_below_the_crossover():
    from noetica_impair.hooks.sae import FeatureSteering, SyntheticSAE
    sae = SyntheticSAE(d_model=8, d_sae=16, layer=0, seed=0)
    iv = FeatureSteering(sae=sae, feature_ids=[0, 1], strength=1.0, sign=+1,
                         concept="threat_tom", biphasic_crossover=0.5)
    iv.set_dose(0.2)
    assert iv.biphasic_crossover == 0.5
    # low dose -> inverted (anxiolytic); high dose -> declared sign (anxiogenic)
    import torch
    h = torch.ones(1, 3, 8)
    lo = iv._hook(None, None, h.clone())
    iv.set_dose(0.9)
    hi = iv._hook(None, None, h.clone())
    assert torch.sign((lo - h).sum()) != torch.sign((hi - h).sum()), (
        "the biphasic op must change DIRECTION across the crossover, not just magnitude"
    )


def test_alcohol_and_pcp_share_the_nmda_limb_at_different_weights():
    assert "nmda_antagonism" in P.ALCOHOL.limbs and "nmda_antagonism" in P.PCP.limbs
    assert 0 < P.ALCOHOL.layer_bypass < P.PCP.layer_bypass, (
        "ethanol's NMDA inhibition is partial (~50%); PCP's is its defining action"
    )
    # and they separate on the limb PCP does not have
    assert "gaba_a" in P.ALCOHOL.limbs and "gaba_a" not in P.PCP.limbs


def test_mdma_and_meth_share_the_release_limb_on_different_targets():
    assert "monoamine_release" in P.METH.limbs and "monoamine_release" in P.MDMA.limbs
    meth_const = {f.concept for f in P.METH.features if f.mode == "constant"}
    mdma_const = {f.concept for f in P.MDMA.features if f.mode == "constant"}
    assert meth_const == {"reward_value"}, "DAT-preferring"
    assert mdma_const == {"affiliation"}, "SERT-preferring"
    assert not (meth_const & mdma_const), "same mechanism, different target concept"


def test_reuptake_substances_stay_proportional():
    """Cocaine/crack amplify existing signal; they must NOT use constant mode."""
    for n in ("COCAINE", "CRACK"):
        modes = {f.mode for f in P.get(n).features}
        assert modes == {"proportional"}, f"{n} is a reuptake inhibitor, not a releaser"


def test_every_feature_concept_has_a_discovery_contrast_set():
    from noetica_impair.provenance.features import CONCEPTS
    for n in P.PANEL:
        for f in P.get(n).features:
            assert f.concept in CONCEPTS, f"{n} references undiscoverable {f.concept!r}"


def test_hard_pairs_share_a_limb():
    """A pair predicted hard to separate must actually share a mechanism."""
    for a, b, _why in P.EXPECTED_HARD_PAIRS:
        shared = L.shared(P.get(a).limbs, P.get(b).limbs)
        assert shared, f"{a}/{b} declared hard but share no mechanism limb"


def test_must_separate_pairs_differ_in_mechanism():
    """The other direction: pairs that look alike but act through different limbs.

    A collapse there falsifies the mechanism mapping rather than the rig, which is a
    sharper result than a pass — so it is pre-registered too.
    """
    for a, b, why in P.MUST_SEPARATE:
        sep = L.distinguishing(P.get(a).limbs, P.get(b).limbs)
        assert sep, f"{a}/{b} declared separable but carry identical limbs"
        assert why


def test_whole_panel_still_compiles():
    from noetica_impair.substances.schema import compile_preset
    meta = registry.get("toy-dense")
    for n in P.PANEL:
        assert compile_preset(P.get(n), meta, seed=0, strict_limbs=False).interventions


# ── the runtime guard ────────────────────────────────────────────────────────

def test_lost_limb_is_refused_by_default():
    """A preset can compile to SOMETHING and still not be the substance it claims.

    MDMA without a feature artifact keeps only a logit op; METH loses the
    constant-mode release op that is the entire reason it is not COCAINE. "Non-empty"
    was far too weak a bar and this is the guard that replaced it.
    """
    from noetica_impair.substances.schema import compile_preset
    meta = registry.get("toy-dense")            # no SAE
    for name in ("MDMA", "METH", "LSD"):
        with pytest.raises(PresetError, match="lost mechanism limb"):
            compile_preset(P.get(name), meta, seed=0)


def test_lost_limb_can_be_accepted_knowingly_and_is_recorded():
    from noetica_impair.substances.schema import compile_preset
    meta = registry.get("toy-dense")
    c = compile_preset(P.get("MDMA"), meta, seed=0, strict_limbs=False)
    assert c.lost_limbs, "the partiality must be recorded, not silently dropped"
    assert "lost_limbs" in c.describe()


def test_limbs_expressible_without_an_sae_still_compile_strictly():
    """Substances whose limbs need no feature artifact must not be blocked."""
    from noetica_impair.substances.schema import compile_preset
    meta = registry.get("toy-dense")
    for name in ("HEROIN", "CANNABIS"):
        assert compile_preset(P.get(name), meta, seed=0).interventions
