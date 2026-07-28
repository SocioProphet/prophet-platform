"""Mechanism limbs -- the receptor-level story, made explicit and machine-readable.

Presets used to be ad-hoc parameter vectors with a paragraph of justification. The
problem with that is drift: the prose says one thing, the numbers say another, and
nothing checks. Worse, it invites exactly the error this file was written to fix --
claiming two substances differ "mainly in duration" when they differ at the receptor.

So each substance declares the LIMBS it acts through. Limbs are shared across
substances the way real mechanisms are, which makes the dissociation predictions
principled rather than decorative: substances sharing a limb should be CLOSE on the
faculties that limb drives, and separated by the limbs they do not share.
``tests/test_limb_consistency.py`` asserts that every declared limb is actually
present in the compiled parameter vector, so the pharmacology and the code cannot
drift apart.

IMPORTANT EPISTEMIC BOUNDARY. The receptor pharmacology below is drawn from the
literature and is checkable. The mapping from a receptor action to a computational
operation is an ANALOGY -- a hypothesis about which faculty should degrade, not an
established fact about either brains or transformers. The rig tests the analogy; it
does not presuppose it. Nothing here should be cited as a claim about neuroscience.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Limb:
    id: str
    receptor: str
    pharmacology: str
    computation: str
    #: preset fields that MUST be non-zero if a substance declares this limb
    requires_any: tuple[str, ...] = ()
    #: intervention kinds that can actually EXPRESS this limb at runtime. If none of
    #: these survives compilation, the limb is silently absent from the run.
    expressed_by: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


LIMBS: dict[str, Limb] = {}


def _add(limb: Limb) -> Limb:
    LIMBS[limb.id] = limb
    return limb


GABA_A = _add(Limb(
    id="gaba_a",
    expressed_by=("self_monitor_ablate", "sae_steer"),
    receptor="GABA-A positive allosteric modulation",
    pharmacology=(
        "Potentiates inhibitory tone. Behaviourally: disinhibition, loss of "
        "self-monitoring, confidence preserved while accuracy falls."
    ),
    computation="suppress caution/hedging features + ablate self-monitoring",
    requires_any=("self_monitor_ablate",),
))

NMDA_ANTAGONISM = _add(Limb(
    id="nmda_antagonism",
    expressed_by=("layer_bypass",),
    receptor="NMDA receptor antagonism",
    pharmacology=(
        "Blocks NMDA-dependent LTP. In hippocampus this is the encoding failure behind "
        "alcoholic blackout; as an open-channel block (PCP) it produces dissociation "
        "and derailment. Note ethanol's NMDA inhibition is PARTIAL (~50% at "
        "LTP-blocking concentrations), which is why alcohol carries this limb weakly "
        "while PCP carries it as its defining action."
    ),
    computation="layer bypass -- stages of integration do not happen",
    requires_any=("layer_bypass",),
    references=("Lovinger et al., Science 1989 (ethanol inhibits NMDA current)",),
))

MU_OPIOID = _add(Limb(
    id="mu_opioid",
    expressed_by=("logit_ops", "sae_steer"),
    receptor="mu-opioid agonism",
    pharmacology="Analgesia, sedation, drive collapse, euphoric complacency. NOT disinhibition.",
    computation="suppress error/aversion features + logit magnitude down + EOS bias up",
    requires_any=("magnitude_gain", "eos_bias"),
))

MONOAMINE_REUPTAKE = _add(Limb(
    id="monoamine_reuptake",
    expressed_by=("sae_steer",),
    receptor="monoamine transporter reuptake inhibition (DAT/NET/SERT)",
    pharmacology=(
        "Blocks clearance, so it AMPLIFIES signal the system was already producing. "
        "Effect is contingent on endogenous activity."
    ),
    computation="feature steering in PROPORTIONAL mode (edit scales with live activation)",
    requires_any=("features",),
))

MONOAMINE_RELEASE = _add(Limb(
    id="monoamine_release",
    expressed_by=("sae_steer",),
    receptor="transporter-substrate release (reverses the transporter)",
    pharmacology=(
        "Drives efflux regardless of firing, so output stops tracking input. This is "
        "the real reason methamphetamine is not 'cocaine but more'. MDMA shares the "
        "mechanism but is SERT-preferring rather than DAT-preferring -- same limb, "
        "different target concept."
    ),
    computation="feature steering in CONSTANT mode (injected regardless of activation)",
    requires_any=("features",),
))

CB1_PARTIAL = _add(Limb(
    id="cb1_partial",
    expressed_by=("attn_broaden",),
    receptor="CB1 partial agonism",
    pharmacology=(
        "Presynaptic inhibition of transmitter release. Critically BIPHASIC: anxiolytic "
        "at low dose via CB1 on cortical GLUTAMATERGIC terminals, anxiogenic at high "
        "dose via CB1 on GABAergic terminals. The sign of the threat effect flips with "
        "dose -- no other substance in this panel does that."
    ),
    computation="attention broadening + a threat feature op whose SIGN inverts below a crossover dose",
    requires_any=("broaden_tau",),
    references=("Rey et al., Neuropsychopharmacology 2012 (biphasic CB1/GABA-B)",),
))

HT2A_AGONISM = _add(Limb(
    id="ht2a_agonism",
    expressed_by=("mlp_attenuation",),
    receptor="5-HT2A agonism",
    pharmacology=(
        "The shared psychedelic limb. Read through REBUS: high-level priors are relaxed "
        "so incoming data outweighs learned expectation. LSD has HIGHER 5-HT2A affinity "
        "than psilocin."
    ),
    computation="feed-forward (prior) attenuation in later layers",
    requires_any=("mlp_attenuation",),
))

D2_PARTIAL = _add(Limb(
    id="d2_partial",
    expressed_by=("sae_steer",),
    receptor="dopamine D2 partial agonism",
    pharmacology=(
        "THE limb that separates LSD from psilocybin. LSD is a D2 partial agonist; "
        "psilocybin has no meaningful D2 affinity. It underlies LSD's later, more "
        "stimulant-like phase and its psychotomimetic edge. PCP also carries D2 "
        "activity, contributing agitation on top of its NMDA block."
    ),
    computation="amplify reward/salience features (proportional) + logit sharpening",
    requires_any=("features",),
    references=(
        "Watts et al., Life Sci 1998 (LSD is a D2 partial agonist)",
        "Marona-Lewicka & Nichols (distinct temporal phases; D2-mediated late phase)",
    ),
))

HT1A_TRANSPORTER = _add(Limb(
    id="ht1a_transporter",
    expressed_by=("sae_steer",),
    receptor="5-HT1A agonism + serotonin/norepinephrine transporter interaction",
    pharmacology=(
        "Carried by psilocin and NOT by LSD: tryptamines interact with SERT and "
        "partially NET, whereas LSD and mescaline do not. Associated with the more "
        "affective/embodied character and stronger ego dissolution."
    ),
    computation="suppress self-reference features + amplify affiliation",
    requires_any=("features",),
))

OXYTOCIN_PROSOCIAL = _add(Limb(
    id="oxytocin_prosocial",
    expressed_by=("sae_steer",),
    receptor="oxytocin release secondary to 5-HT release / 5-HT1A",
    pharmacology=(
        "The empathogenic limb: threat appraisal and defensive guarding fall, "
        "affiliation rises, WITHOUT the competence lesion the sedatives produce."
    ),
    computation="suppress threat + refusal-guard features, amplify affiliation",
    requires_any=("features",),
))


def get(limb_id: str) -> Limb:
    if limb_id not in LIMBS:
        raise KeyError(f"unknown limb {limb_id!r}; known: {sorted(LIMBS)}")
    return LIMBS[limb_id]


def shared(a: tuple[str, ...], b: tuple[str, ...]) -> set[str]:
    return set(a) & set(b)


def distinguishing(a: tuple[str, ...], b: tuple[str, ...]) -> set[str]:
    return set(a) ^ set(b)
