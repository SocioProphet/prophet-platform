"""The four substance presets (work order section 4).

What matters here is the PROFILE SHAPE, not the absolute numbers. Magnitudes are
hand-set (open fork 10.4 default) so that at d~=0.6 the intended dissociation is
visible while output is still parseable. They are calibration constants, not
findings, and they are expected to move once real weights are measured.

The pharmacology is a design metaphor for a mechanical parameter vector -- these are
hypotheses about which computational faculty each profile should damage first, and
the dissociation matrix is what tests them. ALCOHOL and HEROIN are deliberately built
to be distinguishable: alcohol suppresses caution (disinhibition), heroin explicitly
does NOT (caution_suppress off) and instead suppresses aversion while sedating. If
those two rows are not separable in the dissociation matrix, the rig has failed to
express the distinction and invariant 0.4 says stop.
"""

from __future__ import annotations

from .schema import FeatureOp, SubstancePreset

ALCOHOL = SubstancePreset(
    name="ALCOHOL",
    limbs=("gaba_a", "nmda_antagonism"),
    rationale=(
        "TWO limbs, which is why alcohol looks like several things at once. GABA-A "
        "potentiation gives disinhibition -- caution suppressed, self-monitoring "
        "ablated, confidence intact while accuracy falls. NMDA antagonism gives the "
        "encoding failure behind blackout.\n\n"
        "That second limb is shared with PCP, and the weighting is the honest part: "
        "ethanol's NMDA inhibition is PARTIAL (~50% at LTP-blocking concentrations), so "
        "alcohol carries a WEAK layer-bypass term where PCP carries a strong one. The "
        "prediction that follows is specific: alcohol and PCP should sit closer on "
        "binding/consistency faculties than on anything else, and separate cleanly on "
        "disinhibition, which PCP has no limb for."
    ),
    distance_decay_alpha=1.2, distance_decay_window=8,   # WM over distance
    residual_sigma=0.35,
    layer_bypass=0.18, bypass_min_layer_frac=0.5,        # nmda limb, deliberately weak
    k_flat=0.8,
    eos_bias=0.0,
    features=(FeatureOp("hedging_caution", strength=1.5, sign=-1),),
    self_monitor_ablate=0.9,                              # gaba_a limb
)

HEROIN = SubstancePreset(
    name="HEROIN",
    limbs=("mu_opioid",),
    rationale=(
        "mu-opioid: NOT disinhibition. Suppressed aversion plus sedation -> drive "
        "collapse and euphoric complacency. Caution suppression is deliberately OFF; "
        "that absence is what separates this row from ALCOHOL."
    ),
    broaden_tau=0.6,                                      # mild broaden
    magnitude_gain=0.7,                                   # sedation, toward uniform
    eos_bias=6.0,                                         # drive collapse -> shorter
    features=(FeatureOp("error_aversion", strength=1.8, sign=-1),),   # analgesia, high
    self_monitor_ablate=0.35,                             # low-med
)

COCAINE = SubstancePreset(
    name="COCAINE",
    limbs=("monoamine_reuptake",),
    rationale=(
        "DA/NE reuptake: near-inverse of alcohol. Grandiose, overconfident, verbose, "
        "impulsive, punding. Sharpened rather than flattened -- both alcohol and "
        "cocaine wreck calibration, but in opposite directions."
    ),
    residual_sigma=0.1,                                   # low
    lookahead_sigma=0.9, lookahead_min_layer_frac=0.6,    # impulsivity: late layers only
    k_sharp=1.5,                                          # sharpen
    eos_bias=-6.0,                                        # verbose / pressured
    perseveration_bias=2.5,                               # punding
    features=(FeatureOp("reward_value", strength=1.6, sign=+1),),     # grandiosity
)

CANNABIS = SubstancePreset(
    name="CANNABIS",
    limbs=("cb1_partial",),
    rationale=(
        "CB1 PARTIAL agonism, and the partial is load-bearing. THC's effect on anxiety "
        "is BIPHASIC, not merely dose-escalating: anxiolytic at low dose via CB1 on "
        "cortical glutamatergic terminals, anxiogenic at high dose via CB1 on GABAergic "
        "terminals. The sign genuinely flips.\n\n"
        "So the threat op inverts below a crossover dose rather than rising "
        "monotonically. That makes cannabis the ONLY non-monotonic row in the panel, "
        "and it is a much stronger dissociator than 'broadening' alone -- no other "
        "substance here changes the direction of a faculty effect as dose rises. It "
        "also predicts something falsifiable: a cannabis dose-response curve for threat "
        "that dips before it climbs."
    ),
    broaden_tau=2.5,                                      # 3.2, never with 3.1
    residual_sigma=0.15,
    k_flat=0.5,
    features=(
        FeatureOp("salience", strength=0.8, sign=+1),
        # Anxiolytic below d=0.5, anxiogenic above it. Superlinear once it flips.
        FeatureOp("threat_tom", strength=2.0, sign=+1,
                  dose_exponent=2.0, biphasic_crossover=0.5),
    ),
)

# MoE variants: the same profiles expressed through the router, for the Mixtral and
# DeepSeek rigs. Kept separate rather than folded in, because "alcohol on a dense
# model" and "alcohol on a router" are different lesions and must not be silently
# compared. Section 3.7's DeepSeek split rule applies automatically -- ArchMeta only
# ever exposes routed gates.
ALCOHOL_MOE = SubstancePreset(
    name="ALCOHOL_MOE",
    rationale="alcohol profile driven through the router: misrouting -> fluent but "
              "wrong expertise, which is the clean MoE reading of fluent-but-wrong.",
    distance_decay_alpha=1.2, residual_sigma=0.35, k_flat=0.8,
    self_monitor_ablate=0.9,
    router_sigma=1.5, expert_dropout=0.25,
)

CANNABIS_MOE = SubstancePreset(
    name="CANNABIS_MOE",
    rationale="broadening expressed as gate-entropy flattening: a hedged expert "
              "mixture rather than a committed one.",
    broaden_tau=2.5, residual_sigma=0.15, k_flat=0.5,
    router_flatten=2.0, anti_route=0.3,
)



# ─── Expanded set ────────────────────────────────────────────────────────────
# Three of these required NEW mechanisms rather than new numbers. That distinction
# is the whole discipline: a preset that is an existing preset with bigger
# magnitudes is not a substance, it is a relabel, and the dissociation matrix will
# say so.

CRACK = SubstancePreset(
    name="CRACK",
    limbs=("monoamine_reuptake",),
    rationale=(
        "Smoked cocaine. At the receptor this is NOT a different drug -- same reuptake "
        "inhibition, and deliberately the SAME parameter vector as COCAINE. The entire "
        "difference is kinetics: near-instant onset, brief peak, steep decay, crash. "
        "So it is expressed as an envelope, not as bigger numbers. If the two rows "
        "separate in the dissociation matrix, that separation is caused by the time "
        "course and nothing else -- which is exactly the claim worth testing."
    ),
    residual_sigma=COCAINE.residual_sigma,
    lookahead_sigma=COCAINE.lookahead_sigma,
    lookahead_min_layer_frac=COCAINE.lookahead_min_layer_frac,
    k_sharp=COCAINE.k_sharp,
    eos_bias=COCAINE.eos_bias,
    perseveration_bias=COCAINE.perseveration_bias * 1.6,   # compulsive redosing
    features=COCAINE.features,
    envelope="crack",
)

LSD = SubstancePreset(
    name="LSD",
    limbs=("ht2a_agonism", "d2_partial"),
    rationale=(
        "5-HT2A agonism read through REBUS -- relaxed high-level priors, so incoming "
        "context outweighs learned expectation -- PLUS a dopaminergic limb.\n\n"
        "That second limb is the correction. LSD is a D2 PARTIAL AGONIST; psilocybin "
        "has no meaningful D2 affinity. It is not true that these two differ mainly in "
        "duration: LSD carries a stimulant-like valuation limb that psilocybin lacks "
        "entirely, and psilocin carries transporter activity (SERT, partly NET) that "
        "LSD lacks. LSD also binds 5-HT2A with higher affinity than psilocin.\n\n"
        "The honest complication, pre-registered: Holze et al. (2022) compared the two "
        "head-to-head and found LARGELY COMPARABLE subjective effects at matched doses, "
        "with duration the robust difference. So the prediction here is deliberately "
        "two-sided -- the MECHANICAL vectors differ (D2 vs transporter limb) while the "
        "measured FACULTY vectors may well converge. If they converge, that mirrors the "
        "human literature rather than refuting the rig."
    ),
    mlp_attenuation=0.75, mlp_min_layer_frac=0.45,   # ht2a: prior relaxation
    broaden_tau=1.8,                                  # entropy up
    k_sharp=0.5,                                      # d2: stimulant edge, NOT flatten
    features=(
        FeatureOp("salience", strength=1.4, sign=+1),
        # d2_partial -- the limb psilocybin does not have
        FeatureOp("reward_value", strength=1.1, sign=+1),
        FeatureOp("threat_tom", strength=0.9, sign=+1, dose_exponent=2.0),
    ),
    envelope="lsd",
)

PSILOCYBIN = SubstancePreset(
    name="PSILOCYBIN",
    limbs=("ht2a_agonism", "ht1a_transporter"),
    rationale=(
        "Shares LSD's 5-HT2A prior-relaxation limb and differs on the SECOND limb, "
        "which is the point. Psilocin interacts with the serotonin transporter and "
        "partly the norepinephrine transporter -- LSD and mescaline do not -- and has "
        "appreciable 5-HT1A activity. It has NO meaningful D2 affinity, so the "
        "stimulant/valuation limb that LSD carries is simply absent here.\n\n"
        "Computationally that is expressed as ego dissolution (suppress self-reference) "
        "and an affective rather than cognitive character (amplify affiliation), with "
        "no reward-valuation amplification and a mild FLATTEN where LSD sharpens. The "
        "two therefore differ in the SIGN of their logit-temperature op, not merely in "
        "magnitude.\n\n"
        "Still expected to be the hardest pair in the panel -- see EXPECTED_HARD_PAIRS. "
        "Holze et al. (2022) found comparable subjective effects at matched doses, so a "
        "faculty-level collapse here would be consistent with the human data and must "
        "NOT be tuned away."
    ),
    mlp_attenuation=0.7, mlp_min_layer_frac=0.45,    # ht2a: shared limb
    broaden_tau=1.5,
    k_flat=0.5,                                       # opposite sign to LSD's k_sharp
    features=(
        FeatureOp("salience", strength=1.2, sign=+1),
        # ht1a_transporter -- the limb LSD does not have
        FeatureOp("self_reference", strength=1.6, sign=-1),   # ego dissolution
        FeatureOp("affiliation", strength=1.2, sign=+1),      # affective character
        FeatureOp("threat_tom", strength=0.7, sign=+1, dose_exponent=2.0),
    ),
    envelope="psilocybin",
)

PCP = SubstancePreset(
    name="PCP",
    limbs=("nmda_antagonism", "d2_partial"),
    rationale=(
        "NMDA antagonism -- a dissociative, and mechanically the cleanest new axis of "
        "the set. Not corruption but DISCONNECTION: layers are skipped, so stages of "
        "integration simply do not happen while every other layer stays intact. The "
        "predicted signature is derailment rather than error -- locally well-formed "
        "continuations that fail to stay bound to what came before. Analgesia and "
        "flattened aversion come along as feature suppression."
    ),
    layer_bypass=0.55, bypass_min_layer_frac=0.4, bypass_max_layer_frac=0.9,
    broaden_tau=1.0,
    magnitude_gain=0.25,
    features=(
        FeatureOp("error_aversion", strength=1.4, sign=-1),
        # d2_partial: PCP carries dopaminergic activity that contributes agitation and
        # a psychotomimetic edge on top of the channel block.
        FeatureOp("reward_value", strength=0.8, sign=+1),
        FeatureOp("threat_tom", strength=1.2, sign=+1, dose_exponent=2.0),
    ),
    self_monitor_ablate=0.6,
)

MDMA = SubstancePreset(
    name="MDMA",
    limbs=("monoamine_release", "oxytocin_prosocial"),
    rationale=(
        "Serotonin release -- an empathogen, and the one preset here that is a "
        "DISPOSITION change rather than an impairment. Threat appraisal and defensive "
        "guarding fall, affiliative valuation rises, while competence, fluency and "
        "working memory should stay near baseline. That flat-competence profile is what "
        "should make it the most separable row in the matrix.\n\n"
        "It is also the scientifically load-bearing one, because it is the only preset "
        "with a TRAINING-TIME counterpart. Suppressing refusal_guard and threat while "
        "raising affiliation is, acutely, what an uncensored fine-tune has done "
        "chronically. That makes MDMA the natural probe for the contrast-pair "
        "experiment: does acute suppression on a sober base land it where its dolphin "
        "sibling already sits? If yes, training-time and inference-time modification "
        "reach the same circuit by different routes."
    ),
    k_sharp=0.3,
    features=(
        FeatureOp("threat_tom", strength=1.6, sign=-1),
        FeatureOp("refusal_guard", strength=1.5, sign=-1),
        # MDMA is a substituted amphetamine and a RELEASER like meth -- same limb,
        # SERT-preferring rather than DAT-preferring. Constant mode is the correction:
        # affiliation stops tracking whether the context warrants it.
        FeatureOp("affiliation", strength=1.8, sign=+1, mode="constant"),
    ),
    self_monitor_ablate=0.15,   # deliberately low: not a disinhibition of competence
)

METH = SubstancePreset(
    name="METH",
    limbs=("monoamine_release",),
    rationale=(
        "Methamphetamine is NOT 'cocaine but more', and the rig now says why in "
        "mechanism rather than magnitude. Cocaine blocks reuptake -- it amplifies "
        "monoamine signal the brain was ALREADY producing. Meth is a RELEASER: it "
        "drives output whether or not the upstream signal is there.\n\n"
        "That distinction is exactly expressible here. Every other feature op in this "
        "file is proportional -- the edit scales with the feature's live activation "
        "f_i, so a feature that is not firing is not touched. METH uses mode="
        "'constant': the decoder direction is injected at fixed magnitude regardless "
        "of activation. Reward valuation stops tracking anything in the input.\n\n"
        "The rest follows from the long plateau rather than from bigger numbers: "
        "stereotypy (perseveration well above cocaine's) and psychosis (threat "
        "superlinear in dose) are what sustained exposure produces. CRACK and METH "
        "therefore sit at opposite ends of one kinetic axis with a shared "
        "transmitter story -- brief and steep vs slow and unrelenting."
    ),
    residual_sigma=0.15,
    lookahead_sigma=0.7, lookahead_min_layer_frac=0.6,
    k_sharp=1.2,
    eos_bias=-7.0,                                   # pressured, relentless
    perseveration_bias=4.0,                          # stereotypy/punding > cocaine
    features=(
        # The defining op: release, not reuptake.
        FeatureOp("reward_value", strength=1.3, sign=+1, mode="constant"),
        # Psychosis emerges only with sustained high exposure.
        FeatureOp("threat_tom", strength=1.7, sign=+1, dose_exponent=2.0),
    ),
    self_monitor_ablate=0.5,
    envelope="meth",
)


ALL: dict[str, SubstancePreset] = {
    p.name: p for p in (ALCOHOL, HEROIN, COCAINE, CANNABIS, CRACK, METH, LSD,
                        PSILOCYBIN, PCP, MDMA, ALCOHOL_MOE, CANNABIS_MOE)
}

#: The original four that invariant 0.4 requires to be pairwise distinguishable.
CORE_FOUR = ("ALCOHOL", "HEROIN", "COCAINE", "CANNABIS")

#: The full behavioural panel. Invariant 0.4 applies across all of it.
PANEL = ("ALCOHOL", "HEROIN", "COCAINE", "CRACK", "METH", "CANNABIS",
         "LSD", "PSILOCYBIN", "PCP", "MDMA")

#: Pairs expected to be HARD to separate, declared before the data is seen so a
#: collapse reads as a finding rather than an embarrassment to be tuned away.
#: (a, b, why)
EXPECTED_HARD_PAIRS = (
    ("LSD", "PSILOCYBIN",
     "share the 5-HT2A prior-relaxation limb. They are NOT merely 'same receptor, "
     "different duration' -- LSD carries a D2 partial-agonist limb psilocybin lacks, "
     "psilocin carries SERT/NET transporter activity LSD lacks, and the two take "
     "opposite signs on logit temperature. But Holze et al. (2022) found comparable "
     "subjective effects at matched doses, so faculty-level convergence would MATCH "
     "the human literature and must not be tuned away."),
    ("COCAINE", "CRACK", "identical parameter vector by construction; differ ONLY in "
                         "pharmacokinetics, which a static-dose battery cannot see"),
)

#: The other half of the prediction. These pairs look similar -- same transmitter
#: system, overlapping clinical picture -- but the limb model says they act through
#: DIFFERENT mechanisms and must therefore separate. A collapse here is not a
#: dissociation failure, it is evidence against the mechanism mapping itself, which is
#: a sharper and more useful result than a pass.
#: (a, b, what a collapse would falsify)
MUST_SEPARATE = (
    ("COCAINE", "METH",
     "same dopaminergic transmitter story, but reuptake inhibition (proportional: "
     "amplifies existing signal) vs transporter-substrate release (constant: drives "
     "output regardless of input). If these collapse, the release/reuptake distinction "
     "has no computational consequence and mode='constant' is not worth having."),
    ("ALCOHOL", "PCP",
     "both carry NMDA antagonism, but alcohol's is partial and paired with GABA-A "
     "disinhibition that PCP lacks entirely. If these collapse, the rig cannot tell "
     "disinhibition from disconnection."),
    ("METH", "MDMA",
     "same release limb, different transporter target (DAT- vs SERT-preferring), "
     "expressed as different target concepts. If these collapse, feature identity is "
     "not doing any work and only the mechanism class matters."),
)


def get(name: str) -> SubstancePreset:
    if name not in ALL:
        raise KeyError(f"unknown substance {name!r}; known: {sorted(ALL)}")
    return ALL[name]
