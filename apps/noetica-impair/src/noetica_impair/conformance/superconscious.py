"""Emit superconscious interpretability-harness documents from this rig.

The estate already owns the governance vocabulary for interpretability work --
``SocioProphet/superconscious``, ``schemas/interpretability/*.v0.json``: ProviderBinding,
ArtifactSourceLock, FeatureRegistryEntry, InterventionSpec. This rig conforms to it
rather than running a parallel one, per the estate's spec-first rule.

The mapping is mostly clean:

    FeatureSteering / SelfMonitorAblation -> feature_steering   (target: feature)
    LogitOps / PerseverationBias          -> logit_bias         (target: logit)
    DepthScaledResidualNoise              -> activation_addition(target: activation_site)

**It is not clean for three ops, and that is a real gap, not an oversight.** The v0
``intervention_kind`` enum has no term for editing attention scores or MoE router
gates:

  * ``attn_broaden`` divides pre-softmax scores -- multiplicative, and not an addition
    to the residual stream;
  * ``router_ops`` perturbs expert SELECTION, which is neither an activation edit nor
    a logit bias on the vocabulary;
  * ``attn_distance_decay`` is additive, but on the attention score matrix rather than
    an activation site, so calling it ``activation_addition`` overstates the fit.

These are reported as ``ConformanceGap`` rather than filed under the nearest-looking
enum term. Mis-filing them would put a false claim into a governance record, which is
worse than an explicit gap: the harness check script exists precisely to stop a
provider claiming observables or interventions it does not have.

Nothing here executes anything. These are declarations about what the rig does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..hooks.base import Intervention
from ..models.registry import ArchMeta

SCHEMA_VERSION = "0.1.0"
PROVIDER_BINDING_ID = "pb-noetica-impair-white-box-local"


def _slug(s: str) -> str:
    """Ids must match ^<prefix>-[a-z0-9][a-z0-9._-]*$ -- no urns, no underscores."""
    return re.sub(r"[^a-z0-9._-]+", "-", s.lower()).strip("-")


def lock_id(meta: "ArchMeta", kind: str) -> str:
    return f"asl-{_slug(meta.key)}-{kind}"


def feature_entry_id(meta: "ArchMeta", concept: str) -> str:
    return f"fre-{_slug(meta.key)}-{_slug(concept)}"

#: Interventions with an exact v0 term.
INTERVENTION_KIND_MAP: dict[str, tuple[str, str]] = {
    "sae_steer": ("feature_steering", "feature"),
    "self_monitor_ablate": ("feature_steering", "feature"),
    "logit_ops": ("logit_bias", "logit"),
    "perseveration": ("logit_bias", "logit"),
    "residual_noise": ("activation_addition", "activation_site"),
}

#: Observables this rig reads that v0 has no term for. Reported alongside the
#: intervention gaps because they are one finding, not two: MoE routing is absent
#: from the v0 vocabulary on BOTH axes -- you can neither declare that you observe an
#: expert distribution nor that you intervene on one.
UNREPRESENTABLE_OBSERVABLES: dict[str, str] = {
    "moe_router_distribution": (
        "per-layer P(expert|token) from the MoE gate, the basis of the routing-KL "
        "readout; v0 supported_observables has no routing term"
    ),
}

#: Interventions v0 cannot express. Reported, never coerced.
UNREPRESENTABLE: dict[str, str] = {
    "attn_distance_decay": (
        "additive edit to the pre-softmax attention SCORE matrix; v0 has no "
        "attention-site target and 'activation_addition' implies the residual stream"
    ),
    "attn_broaden": (
        "multiplicative rescaling of pre-softmax attention scores; v0 has no "
        "multiplicative intervention_kind at all"
    ),
    "mlp_attenuation": (
        "multiplicative rescaling of the feed-forward branch; v0's nearest term, "
        "'activation_addition', is additive, and there is no multiplicative kind"
    ),
    "layer_bypass": (
        "discards a layer's update by blending toward its own input -- a STRUCTURAL "
        "edit, not an activation edit. 'activation_patching' means substituting "
        "activations from another run, which is a different operation"
    ),
    "router_ops": (
        "perturbs MoE expert SELECTION (gate logits, top-k, expert dropout); v0 has no "
        "routing intervention_kind -- 'probe_guided_routing' means routing guided BY a "
        "probe, which is a different thing"
    ),
}


@dataclass
class ConformanceGap:
    intervention_kind: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"intervention_kind": self.intervention_kind, "reason": self.reason}


def provider_binding() -> dict[str, Any]:
    """This rig as an interpretability provider: white-box, local, offline."""
    return {
        "schema_version": SCHEMA_VERSION,
        "binding_kind": "provider-binding",
        "provider_binding_id": PROVIDER_BINDING_ID,
        "provider_name": "noetica-impair",
        "provider_display_name": "Noetica Impairment Rig (local white-box)",
        "access_mode": "white_box",
        "provider_surface": {
            "surface_kind": "local_model_runtime",
            "execution_location": "local_offline",
            "source_uri": None,
            "terms_or_policy_ref": None,
        },
        # White-box access is what entitles this rig to claim these. The harness check
        # script forbids a black-box provider from claiming any of them.
        # Exact v0 enum terms. Note what is NOT here: see UNREPRESENTABLE_OBSERVABLES.
        "supported_observables": [
            "residual_stream",
            "attention",
            "sae_features",
            "logits",
            "logprobs",
        ],
        "supported_interventions": [
            "feature_steering",
            "activation_addition",
            "logit_bias",
        ],
        "governance_class": "local_offline",
        "runtime_claims": {
            "live_runtime_execution": True,
            "internal_state_replay": True,
            "white_box_replay_possible": True,
            "runtime_evidence_ref": None,
        },
        "evidence_requirements": [
            "paired dose=0 sober control on the same seed and the same rig",
            "append-only run log with a verifying receipt chain",
            "pinned feature-discovery artifact for any feature_steering intervention",
        ],
        # Enum-valued. Note the omission of "runtime_action": this rig emits evidence,
        # it is not an authority on what that evidence means for a governed system.
        "authority_scope": [
            "candidate_discovery",
            "behavior_benchmark",
            "steering_experiment",
            "white_box_feature_claim",
        ],
        "non_claims": [
            "does not claim the induced states resemble human intoxication",
            "does not claim substance names denote pharmacological mechanisms",
            "does not claim features are the model's concepts; they are SAE directions",
            "does not claim results transfer across models without replication",
        ],
    }


def source_locks(meta: ArchMeta) -> list[dict[str, Any]]:
    """Source locks for the model and, where pinned, its SAE.

    A feature index is meaningless without the exact SAE artifact it was discovered
    against, which is why the width and average-L0 are part of the lock rather than
    incidental metadata.
    """
    ref = {"provider_binding_id": PROVIDER_BINDING_ID, "access_mode": "white_box"}
    synthetic = meta.hf_id.startswith("__toy_")

    locks = [{
        "schema_version": SCHEMA_VERSION,
        "lock_kind": "artifact-source-lock",
        "source_lock_id": lock_id(meta, "model"),
        "artifact_kind": "model",
        "artifact_identity": {
            "artifact_id": meta.hf_id,
            "name": meta.hf_id,
            "model_family": meta.arch,
            "layer": None, "width": None, "average_l0": None,
            "feature_index": None, "registry_url": None,
        },
        "provider_binding_ref": ref,
        "immutable_reference": {
            "source_type": "local_fixture" if synthetic else "huggingface_repo",
            "source": meta.hf_id,
            "requested_ref": None, "resolved_ref": None, "path": None,
            "retrieved_at": None,
        },
        "integrity": {
            "content_sha256_status": "synthetic_fixture" if synthetic else "unavailable",
            "content_sha256": None, "metadata_sha256": None, "size_bytes": None,
        },
        "access_boundary": {
            # Invariant 0.6: weights are already on disk; the rig refuses to fetch.
            "download_required": False,
            "credentials_required": False,
            "egress_required": False,
            "license_or_terms_ref": None,
        },
        "replay_class": "synthetic_fixture" if synthetic else "manifest_only",
        "known_limitations": [
            "weights are referenced by local path; content hashing is not yet wired, so "
            "replay is manifest-level rather than bit-exact",
        ],
        "non_claims": ["does not assert the local weights match any upstream release"],
    }]

    if meta.has_sae and meta.sae_release:
        locks.append({
            "schema_version": SCHEMA_VERSION,
            "lock_kind": "artifact-source-lock",
            "source_lock_id": lock_id(meta, "sae"),
            "artifact_kind": "sae",
            "artifact_identity": {
                "artifact_id": meta.sae_release,
                "name": meta.sae_release,
                "model_family": meta.hf_id,
                "layer": meta.sae_layer,
                "width": meta.sae_width,
                "average_l0": meta.sae_average_l0,
                "feature_index": None, "registry_url": None,
            },
            "provider_binding_ref": ref,
            "immutable_reference": {
                "source_type": "huggingface_repo", "source": meta.sae_release,
                "requested_ref": None, "resolved_ref": None, "path": None,
                "retrieved_at": None,
            },
            "integrity": {
                "content_sha256_status": "unavailable",
                "content_sha256": None, "metadata_sha256": None, "size_bytes": None,
            },
            "access_boundary": {
                "download_required": False, "credentials_required": False,
                "egress_required": False, "license_or_terms_ref": None,
            },
            "replay_class": "manifest_only",
            "known_limitations": [],
            "non_claims": ["does not assert SAE features are interpretable concepts"],
        })
    return locks


def intervention_spec(
    iv: Intervention, meta: ArchMeta, *, doses: tuple[float, ...]
) -> dict[str, Any] | ConformanceGap:
    """One InterventionSpec, or a gap when v0 cannot express the op."""
    if iv.kind in UNREPRESENTABLE:
        return ConformanceGap(iv.kind, UNREPRESENTABLE[iv.kind])

    kind, target_kind = INTERVENTION_KIND_MAP[iv.kind]
    params = iv.describe()
    required = [{"source_lock_id": lock_id(meta, "model"),
                 "artifact_kind": "model"}]
    if kind == "feature_steering":
        required.append({"source_lock_id": lock_id(meta, "sae"),
                         "artifact_kind": "sae"})

    return {
        "schema_version": SCHEMA_VERSION,
        "intervention_kind": kind,
        "intervention_id": f"iv-{_slug(meta.key)}-{_slug(iv.kind)}",
        "provider_binding_ref": {
            "provider_binding_id": PROVIDER_BINDING_ID, "access_mode": "white_box",
        },
        "target": {
            "target_kind": target_kind,
            "model_id": meta.hf_id,
            "source_lock_id": lock_id(meta, "model"),
            "feature_entry_id": (
                feature_entry_id(meta, str(params.get("concept") or "unnamed"))
                if target_kind == "feature" else None
            ),
            "layer": params.get("layer"),
            "position_selector": "all_positions",
            "description": f"{iv.kind}: {params}",
        },
        # The dose ladder IS the coefficient schedule -- one scalar scaling every
        # active hook (invariant 0.1).
        "coefficient_schedule": {
            "schedule_kind": "linear_sweep" if len(doses) > 1 else "single_alpha",
            "alpha": doses[-1] if len(doses) == 1 else None,
            "values": list(doses),
            "unit": "dose (0=sober, 1=full)",
        },
        "position_policy": {
            "policy_kind": "all_assistant_tokens",
            "details": "applied at every position of every forward pass while installed",
        },
        # v0 encodes a governance rule here: feature_steering REQUIRES both a policy
        # decision and an off-target audit. Steering a discovered feature is a gated
        # action, not a free parameter -- so this is conditional, not a constant.
        "safety_policy": {
            "policy_ref": "policy://interpretability/noetica-impair-local-white-box",
            "policy_decision_required": kind == "feature_steering",
            "off_target_audit_required": True,
            "human_review_required": False,
        },
        "required_source_locks": required,
        "expected_effect": _expected_effect(iv.kind),
        "forbidden_effects": [
            "must not perturb anything at dose=0 (bit-for-bit)",
            "must not be applied to a model not held locally",
            "must not degrade fluency and competence equally -- that is a coarse "
            "lesion, not a dissociable impairment",
        ],
        "evaluation_plan_ref": None,
        # Seeded generators + a fixed battery make the run reproducible, but the
        # weights are only manifest-pinned, so the honest class is manifest_only.
        "replay_class": "manifest_only",
        "non_claims": [
            "does not claim this intervention isolates a single mechanism",
            "does not claim the substance name denotes a pharmacological mechanism",
        ],
    }


def _expected_effect(kind: str) -> str:
    return {
        "sae_steer": "suppress or amplify a discovered concept direction, shifting the "
                     "faculty that concept supports while leaving others intact",
        "self_monitor_ablate": "remove the consistency/self-correction feature subset, "
                               "raising contradiction rate without harming fluency",
        "logit_ops": "reshape the output distribution (flatten/sharpen, EOS pressure, "
                     "magnitude) without altering internal computation",
        "perseveration": "invert the repetition penalty, producing stereotyped "
                         "re-entry into recent output",
        "residual_noise": "depth-scaled perturbation so later-layer executive "
                          "computation degrades before early-layer syntax",
    }.get(kind, "see intervention parameters")


@dataclass
class HarnessDeclaration:
    provider_binding: dict[str, Any]
    source_locks: list[dict[str, Any]]
    intervention_specs: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[ConformanceGap] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_binding": self.provider_binding,
            "source_locks": self.source_locks,
            "intervention_specs": self.intervention_specs,
            "conformance_gaps": [g.as_dict() for g in self.gaps],
        }


def declare(
    interventions: list[Intervention], meta: ArchMeta, *, doses: tuple[float, ...],
    strict: bool = False,
) -> HarnessDeclaration:
    """Build the full harness declaration for a compiled substance on a model.

    ``strict=True`` raises if any op cannot be expressed in v0 -- use it when the
    declaration must be complete to be meaningful.
    """
    decl = HarnessDeclaration(
        provider_binding=provider_binding(), source_locks=source_locks(meta)
    )
    for iv in interventions:
        out = intervention_spec(iv, meta, doses=doses)
        if isinstance(out, ConformanceGap):
            decl.gaps.append(out)
        else:
            decl.intervention_specs.append(out)
    if strict and decl.gaps:
        raise ValueError(
            "interpretability-harness v0 cannot express: "
            + "; ".join(f"{g.intervention_kind} ({g.reason})" for g in decl.gaps)
        )
    return decl


def feature_registry_entries(artifact: Any, meta: ArchMeta) -> list[dict[str, Any]]:
    """One FeatureRegistryEntry per discovered concept.

    ``claim_status`` is deliberately ``candidate_only``: contrastive ranking produces
    candidates, and only a causal test (steer the feature, measure the faculty) earns
    ``causal_tested``. Promoting on discovery alone is exactly the over-claim the
    harness doctrine is built to prevent.
    """
    entries = []
    for concept, entry in sorted(getattr(artifact, "concepts", {}).items()):
        entries.append({
            "schema_version": SCHEMA_VERSION,
            "entry_kind": "feature-registry-entry",
            "feature_entry_id": feature_entry_id(meta, concept),
            "registry_source": {
                "registry_name": "noetica-impair-discovery",
                "provider_binding_id": PROVIDER_BINDING_ID,
                "registry_url": None,
                "export_ref": getattr(artifact, "version", None),
            },
            "feature_identity": {
                "model_id": meta.hf_id,
                "sae_id": meta.sae_release,
                "transcoder_id": None, "probe_id": None,
                "layer": entry.get("layer"),
                "feature_index": entry.get("feature_ids", [None])[0],
                "feature_id": f"{meta.key}:L{entry.get('layer')}:{concept}",
                "feature_kind": "sae_feature",
            },
            "source_lock_refs": [
                {"source_lock_id": lock_id(meta, "sae"),
                 "artifact_kind": "sae"},
            ],
            "explanation": {
                "status": "human_proposed",
                "text": f"top-{len(entry.get('feature_ids', []))} features ranked by "
                        f"contrastive activation difference for concept {concept!r}",
                "explanation_authority": "human",
                "confidence": None,
            },
            "activation_evidence_summary": {
                "top_examples_ref": getattr(artifact, "contrast_sha", None),
                "negative_examples_ref": getattr(artifact, "contrast_sha", None),
                "activation_statistics_ref": None,
                "position_policy": "mean over all positions of the contrast prompts",
            },
            "evidence_refs": [getattr(artifact, "version", None) or "unpinned-discovery"],
            "claim_status": "candidate_only",
            "replay_class": "manifest_only",
            "non_claims": [
                "does not claim this feature set IS the concept",
                "does not claim causal sufficiency; contrastive ranking is correlational",
            ],
        })
    return entries
