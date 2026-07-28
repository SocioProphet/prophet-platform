"""SubstancePreset schema, validation, and compilation to interventions.

A substance is a *named vector of intervention parameters*, each a base magnitude
that the global dose scales. Validation enforces the work order's rules:

  * a preset may not enable both attention distance-decay (3.1) and broadening (3.2)
    -- they are opposite signs on one axis and would silently cancel;
  * every referenced feature set must exist in the pinned discovery artifact for the
    target model;
  * ops the target architecture cannot support are SKIPPED WITH A LOGGED WARNING
    rather than raising, so one preset file stays portable across dense and MoE rigs.

The skip-don't-fail rule matters for interpretation as much as ergonomics: an ALCOHOL
run on a dense model and on an MoE model are different lesions, and the skip list is
recorded in provenance so nobody later compares them as if they were the same.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..hooks.attention import AttentionBroadening, DistanceDecayAttenuation
from ..hooks.base import Intervention
from ..hooks.layers import LayerBypass
from ..hooks.logits import LogitOps, PerseverationBias
from ..hooks.mlp import MLPAttenuation
from ..hooks.residual import DepthScaledResidualNoise
from ..hooks.router import RouterOps
from ..hooks.sae import FeatureSteering, SelfMonitorAblation

log = logging.getLogger("noetica_impair.substances")


class PresetError(ValueError):
    pass


@dataclass(frozen=True)
class FeatureOp:
    """A steer on one discovered concept. Negative strength suppresses."""

    concept: str
    strength: float
    sign: int  # -1 suppress, +1 amplify
    #: "proportional" = reuptake inhibition (scales the live activation);
    #: "constant" = release (injects regardless of activation). See hooks.sae.
    mode: str = "proportional"
    dose_exponent: float = 1.0
    #: Below this dose the sign inverts (CB1 partial agonism; see limbs.CB1_PARTIAL).
    biphasic_crossover: float | None = None
    layer: int | None = None  # None -> artifact's default layer for the concept


@dataclass(frozen=True)
class SubstancePreset:
    name: str
    rationale: str = ""
    #: Receptor-level mechanism limbs (see substances.limbs). Shared limbs predict
    #: which substances should sit close on which faculties; test_limb_consistency
    #: asserts every declared limb is actually present in the parameter vector.
    limbs: tuple[str, ...] = ()

    # 3.1 / 3.2 -- mutually exclusive
    distance_decay_alpha: float = 0.0
    distance_decay_window: int = 8
    broaden_tau: float = 0.0

    # 3.3
    residual_sigma: float = 0.0
    # lookahead reduction: late-layer-only residual noise. Realised as a SECOND
    # DepthScaledResidualNoise gated to the top layer band, not a distinct primitive.
    lookahead_sigma: float = 0.0
    lookahead_min_layer_frac: float = 0.6

    # 3.4
    k_flat: float = 0.0
    k_sharp: float = 0.0
    eos_bias: float = 0.0
    magnitude_gain: float = 0.0
    perseveration_bias: float = 0.0

    # 3.5 / 3.6
    features: tuple[FeatureOp, ...] = ()
    self_monitor_ablate: float = 0.0

    # NEW MECHANISMS (beyond the work order's 3.1-3.7)
    # Feed-forward attenuation = relaxed priors (psychedelics). Distinct axis: it
    # changes the RATIO between two intact computations rather than corrupting either.
    mlp_attenuation: float = 0.0
    mlp_min_layer_frac: float = 0.5
    # Layer bypass = disconnection (dissociatives). Distinct from residual noise:
    # noise corrupts a computation, bypass means it did not happen.
    layer_bypass: float = 0.0
    bypass_min_layer_frac: float = 0.4
    bypass_max_layer_frac: float = 0.95
    # Pharmacokinetics. Named envelope from hooks.envelope; "constant" is the default
    # and reproduces the original static-dose behaviour exactly.
    envelope: str = "constant"

    # 3.7 (MoE only)
    router_sigma: float = 0.0
    router_flatten: float = 0.0
    anti_route: float = 0.0
    expert_dropout: float = 0.0
    topk_reduce_at: float | None = None

    def validate(self) -> None:
        if self.distance_decay_alpha and self.broaden_tau:
            raise PresetError(
                f"{self.name}: distance-decay (3.1) and broadening (3.2) are opposite "
                "signs on the same axis; a preset may enable only one"
            )
        if self.k_flat and self.k_sharp:
            raise PresetError(f"{self.name}: choose logit flatten OR sharpen, not both")
        for f in self.features:
            if f.sign not in (-1, 1):
                raise PresetError(f"{self.name}: feature {f.concept} has invalid sign {f.sign}")
        from .limbs import LIMBS
        for lid in self.limbs:
            if lid not in LIMBS:
                raise PresetError(f"{self.name}: unknown mechanism limb {lid!r}")
        from ..hooks.envelope import ENVELOPES
        if self.envelope not in ENVELOPES:
            raise PresetError(
                f"{self.name}: unknown envelope {self.envelope!r}; known: {sorted(ENVELOPES)}"
            )

    @property
    def moe_ops_declared(self) -> bool:
        return any(
            (self.router_sigma, self.router_flatten, self.anti_route, self.expert_dropout)
        ) or (self.topk_reduce_at is not None)


@dataclass
class CompiledSubstance:
    preset: SubstancePreset
    interventions: list[Intervention] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    #: Declared mechanism limbs with NO surviving intervention to express them. A run
    #: with lost limbs is not the substance it is labelled as.
    lost_limbs: list[str] = field(default_factory=list)
    #: forbidden-circuit declarations this preset matched (advisory ones; blocking
    #: matches raise before a CompiledSubstance is ever returned)
    forbidden_advisory: list[str] = field(default_factory=list)

    def describe(self) -> dict[str, Any]:
        return {
            "substance": self.preset.name,
            "skipped_ops": self.skipped,
            "lost_limbs": self.lost_limbs,
            "forbidden_advisory": self.forbidden_advisory,
            "interventions": [iv.describe() for iv in self.interventions],
        }


def compile_preset(
    preset: SubstancePreset,
    meta: Any,
    *,
    seed: int = 0,
    features: Any = None,
    strict_limbs: bool = True,
    forbidden: Any = None,
) -> CompiledSubstance:
    """Turn a preset into concrete interventions for one model.

    ``features`` is a ``FeatureArtifact`` (see provenance.features). Without one, all
    SAE-based ops are skipped -- presets stay runnable as pure-mechanical lesions, but
    provenance records exactly which limbs were amputated.
    """
    preset.validate()
    out = CompiledSubstance(preset=preset)

    # Forbidden-circuit gate, BEFORE any intervention is constructed. Finding out
    # afterwards that you ablated a deployment-gated circuit is not a check, it is an
    # incident report. `deployment_gate` blocks; other enforcement modes are advisory
    # and recorded in provenance.
    if forbidden:
        from ..conformance.lawful import check_forbidden, preset_concepts
        chk = check_forbidden(preset_concepts(preset), list(forbidden))
        if not chk.allowed:
            raise PresetError(
                f"{preset.name} steers a deployment-gated circuit: "
                f"{', '.join(chk.blocking)}.\n{chk.report()}\n"
                "Compilation refused. Lift the declaration or drop the concept from "
                "the preset -- there is no flag to override a deployment gate here."
            )
        out.forbidden_advisory = list(chk.advisory)
        if chk.advisory:
            log.warning("%s: advisory forbidden-circuit matches %s",
                        preset.name, chk.advisory)

    if preset.distance_decay_alpha:
        out.interventions.append(DistanceDecayAttenuation(
            alpha=preset.distance_decay_alpha, window=preset.distance_decay_window, seed=seed))
    if preset.broaden_tau:
        out.interventions.append(AttentionBroadening(tau=preset.broaden_tau, seed=seed))
    if preset.residual_sigma:
        out.interventions.append(DepthScaledResidualNoise(sigma=preset.residual_sigma, seed=seed))
    if preset.lookahead_sigma:
        out.interventions.append(DepthScaledResidualNoise(
            sigma=preset.lookahead_sigma, seed=seed + 1,
            min_layer_frac=preset.lookahead_min_layer_frac))
    if any((preset.k_flat, preset.k_sharp, preset.eos_bias, preset.magnitude_gain)):
        out.interventions.append(LogitOps(
            k_flat=preset.k_flat, k_sharp=preset.k_sharp, eos_bias=preset.eos_bias,
            magnitude_gain=preset.magnitude_gain, seed=seed))
    if preset.perseveration_bias:
        out.interventions.append(PerseverationBias(bias=preset.perseveration_bias, seed=seed))
    if preset.mlp_attenuation:
        out.interventions.append(MLPAttenuation(
            strength=preset.mlp_attenuation, min_layer_frac=preset.mlp_min_layer_frac,
            seed=seed))
    if preset.layer_bypass:
        out.interventions.append(LayerBypass(
            fraction=preset.layer_bypass, min_layer_frac=preset.bypass_min_layer_frac,
            max_layer_frac=preset.bypass_max_layer_frac, seed=seed))

    # --- SAE ops ---------------------------------------------------------
    wants_sae = bool(preset.features) or bool(preset.self_monitor_ablate)
    if wants_sae:
        if not getattr(meta, "has_sae", False) or features is None:
            reason = "no SAE for this model" if not getattr(meta, "has_sae", False) else (
                "no pinned feature-discovery artifact supplied")
            for f in preset.features:
                out.skipped.append(f"sae_steer:{f.concept} ({reason})")
            if preset.self_monitor_ablate:
                out.skipped.append(f"self_monitor_ablate ({reason})")
            log.warning("%s: skipping SAE ops -- %s", preset.name, reason)
        else:
            for f in preset.features:
                try:
                    sae, ids = features.resolve(f.concept, layer=f.layer)
                except KeyError:
                    out.skipped.append(f"sae_steer:{f.concept} (absent from artifact "
                                       f"{features.version})")
                    log.warning("%s: concept %r not in artifact %s",
                                preset.name, f.concept, features.version)
                    continue
                out.interventions.append(FeatureSteering(
                    sae=sae, feature_ids=ids, strength=f.strength, sign=f.sign,
                    concept=f.concept, mode=f.mode, dose_exponent=f.dose_exponent,
                    biphasic_crossover=f.biphasic_crossover,
                    artifact_version=features.version, seed=seed))
            if preset.self_monitor_ablate:
                try:
                    sae, ids = features.resolve("consistency")
                    out.interventions.append(SelfMonitorAblation(
                        sae=sae, feature_ids=ids, strength=preset.self_monitor_ablate,
                        artifact_version=features.version, seed=seed))
                except KeyError:
                    out.skipped.append("self_monitor_ablate (no consistency features)")

    # --- MoE ops ---------------------------------------------------------
    if preset.moe_ops_declared:
        if not getattr(meta, "is_moe", False) or getattr(meta, "router_path", None) is None:
            out.skipped.append(f"router_ops (model {meta.key} is {meta.arch}, no router)")
            log.warning("%s: skipping router ops on non-MoE model %s", preset.name, meta.key)
        else:
            out.interventions.append(RouterOps(
                sigma_r=preset.router_sigma, k_r=preset.router_flatten,
                anti_route=preset.anti_route, expert_dropout=preset.expert_dropout,
                topk_reduce_at=preset.topk_reduce_at, seed=seed))

    if not out.interventions:
        raise PresetError(
            f"{preset.name} compiled to zero interventions on {meta.key}; every declared "
            f"op was skipped ({out.skipped}). Refusing to run a placebo labelled as a drug."
        )

    # A preset can compile to SOMETHING and still not be the substance it claims to be.
    # MDMA without a feature artifact keeps only a logit op; METH loses the constant-mode
    # release op that is the entire reason it is not COCAINE. "Non-empty" is far too weak
    # a bar -- check that every DECLARED LIMB still has something expressing it.
    from .limbs import LIMBS
    present = {iv.kind for iv in out.interventions}
    for lid in preset.limbs:
        limb = LIMBS.get(lid)
        if limb is None or not limb.expressed_by:
            continue
        if not (set(limb.expressed_by) & present):
            out.lost_limbs.append(lid)
    if out.lost_limbs and strict_limbs:
        raise PresetError(
            f"{preset.name} on {meta.key} lost mechanism limb(s) {out.lost_limbs} -- "
            f"every intervention that could express them was skipped ({out.skipped}). "
            "The run would be labelled as this substance while missing what makes it "
            "that substance. Supply a feature-discovery artifact, or pass "
            "strict_limbs=False to run it knowingly as a partial lesion."
        )
    if out.lost_limbs:
        log.warning("%s: running WITHOUT limbs %s", preset.name, out.lost_limbs)
    return out
