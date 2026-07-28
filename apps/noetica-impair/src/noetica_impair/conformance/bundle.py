"""The 14-fragment interpretability harness release bundle.

This is the northstar the rig has been producing evidence *toward* without naming it.
``superconscious/schemas/composition/interpretability-harness-tier2-binding.v1.json``
declares a release bundle of exactly 14 fragment kinds, each bound by an opaque
sha256. This module maps what the rig actually produces onto that vocabulary and
reports what is still missing, rather than letting the gap stay invisible.

**Why the rig does not belong inside superconscious.** The tier-2 binding schema
requires exactly ten ``non_claims``, and four of them are:

    no_live_steering_execution
    no_runtime_provider_access
    no_runtime_feature_activation_claim
    no_public_claim_promotion

That layer is *defined* by not executing steering and not touching a provider. This
rig does both -- it is the executor. Moving it into superconscious would break the
very invariant that repo exists to declare. The correct split is already encoded in
the schema:

    noetica-impair   executes interventions, emits content-addressed fragments
    superconscious   binds those fragments by opaque hash, never resolving them
    Noetica          vendors both and renders the trail

So this module emits a bundle *for* superconscious to bind. It deliberately does not
import superconscious code, and it never resolves a hash on that side of the line.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

#: The fragment vocabulary, in the order the binding schema declares it.
FRAGMENT_KINDS = (
    "ModelArtifact", "SAEArtifact", "FeatureArtifact", "FeatureExplanation",
    "FeatureActivationSet", "SteeringIntervention", "CausalTriad", "AttributionGraph",
    "OffTargetAudit", "ManifoldBaseline", "ImplementabilityCurve",
    "RobustnessCertificate", "BenchmarkResult", "PublicInterpretabilityNote",
)

#: Exactly ten, exactly these -- the schema pins both the count and the set.
NON_CLAIMS = (
    "no_runtime_receipt_lookup", "no_runtime_non_claim_verification",
    "no_runtime_monitor_attestation", "no_timestamp_authenticity",
    "opaque_hashes_not_resolved", "no_runtime_provider_access",
    "no_runtime_feature_activation_claim", "no_live_steering_execution",
    "no_public_claim_promotion", "no_neuronpedia_release_substitution",
)

#: NOT free-form. The binding schema pins this as a const -- there is exactly one
#: release-bundle identity, and inventing a per-run id (as this module first did)
#: produces a document that looks right and fails validation.
COMPOSITION_ID = "superconscious.interpretability_harness.release_bundle"

#: Pattern ^v[0-9]+\.[0-9]+$ -- "v1" is invalid.
DOCTRINE_VERSION = "v1.0"

BOUND_MODES = {
    "receipt_integration": "hash_bound_reference",
    "authority_scope_analysis": "declared_scope_lattice_v1",
    "non_claim_analysis": "explicit_propagate_or_resolve_v1",
    "monitor_independence_analysis": "declared_monitor_independence_v1",
    "evidence_freshness_analysis": "declared_evidence_freshness_v1",
}

#: What in this rig supplies each fragment. Kinds mapped to None are NOT produced
#: here, and saying so is the point -- a bundle that quietly invented them would be
#: worse than an incomplete one.
FRAGMENT_SOURCES: dict[str, str | None] = {
    "ModelArtifact": "weights_ref recorded per run (models.loaders)",
    "SAEArtifact": "sae_release + local SAE path pinned in the feature artifact",
    "FeatureArtifact": "provenance.features discovery artifact (gated, versioned)",
    "FeatureExplanation": "substances.limbs receptor->computation rationale per concept",
    "FeatureActivationSet": "contrastive activations behind the discovery ranking",
    "SteeringIntervention": "conformance.superconscious InterventionSpec per hook",
    "CausalTriad": None,          # needs attribution, not implemented here
    "AttributionGraph": None,     # ditto
    "OffTargetAudit": "dissociation matrix + the discovery lexical control",
    "ManifoldBaseline": "the paired dose=0 sober control (invariant 0.3)",
    "ImplementabilityCurve": "readout dose-response curve per faculty",
    "RobustnessCertificate": "split-half reliability + cross-lab invariance report",
    "BenchmarkResult": "FacultyVector / battery scores per run",
    "PublicInterpretabilityNote": None,   # a promotion step this rig must not take
}


def sha256_of(obj: Any) -> str:
    """Content address for a fragment. Stable across dict ordering."""
    if isinstance(obj, (bytes, bytearray)):
        raw = bytes(obj)
    elif isinstance(obj, str):
        raw = obj.encode()
    else:
        raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass
class Fragment:
    kind: str
    opaque_hash: str
    #: local provenance for OUR side only; never travels into the binding
    source: str = ""

    def as_ref(self) -> dict[str, str]:
        return {"fragment_kind": self.kind, "opaque_hash": self.opaque_hash}


@dataclass
class BundleDraft:
    """A release bundle under construction, plus an honest account of its holes."""

    composition_id: str = COMPOSITION_ID
    binding_doctrine_version: str = DOCTRINE_VERSION
    fragments: dict[str, Fragment] = field(default_factory=dict)

    def add(self, kind: str, payload: Any, *, source: str = "") -> Fragment:
        if kind not in FRAGMENT_KINDS:
            raise ValueError(f"unknown fragment kind {kind!r}")
        f = Fragment(kind=kind, opaque_hash=sha256_of(payload),
                     source=source or (FRAGMENT_SOURCES.get(kind) or ""))
        self.fragments[kind] = f
        return f

    @property
    def missing(self) -> list[str]:
        return [k for k in FRAGMENT_KINDS if k not in self.fragments]

    @property
    def unproducible_here(self) -> list[str]:
        """Kinds this rig structurally cannot supply, as opposed to has not yet."""
        return [k for k in FRAGMENT_KINDS if FRAGMENT_SOURCES.get(k) is None]

    @property
    def complete(self) -> bool:
        return not self.missing

    def gap_report(self) -> str:
        if self.complete:
            return f"bundle complete: {len(FRAGMENT_KINDS)}/14 fragments"
        blocked = [k for k in self.missing if k in self.unproducible_here]
        pending = [k for k in self.missing if k not in blocked]
        parts = [f"{len(self.fragments)}/14 fragments present"]
        if pending:
            parts.append(f"not yet produced: {', '.join(pending)}")
        if blocked:
            parts.append(
                f"NOT PRODUCIBLE by this rig: {', '.join(blocked)} — these need "
                "attribution methods (CausalTriad, AttributionGraph) or a promotion "
                "step the rig must not take (PublicInterpretabilityNote)"
            )
        return "; ".join(parts)

    def to_binding(self) -> dict[str, Any]:
        """Render the tier-2 binding document.

        Refuses when incomplete: the schema pins ``minItems: 14`` and ``maxItems: 14``,
        so a short bundle is not a partial binding, it is an invalid one. Padding it
        with placeholder hashes would produce a document that validates while
        attesting to fragments that do not exist -- the worst possible outcome for an
        attestation layer.
        """
        if not self.complete:
            raise ValueError(
                f"cannot bind an incomplete bundle: {self.gap_report()}. The binding "
                "schema requires exactly 14 fragment refs; padding would attest to "
                "artifacts that do not exist."
            )
        if self.composition_id != COMPOSITION_ID:
            raise ValueError(
                f"composition_id is a schema const; got {self.composition_id!r}, "
                f"expected {COMPOSITION_ID!r}"
            )
        return {
            "composition_id": self.composition_id,
            "composition_kind": "certificate_fragment_composition",
            "binding_doctrine_version": self.binding_doctrine_version,
            "fragment_refs": [self.fragments[k].as_ref() for k in FRAGMENT_KINDS],
            "bound_modes": dict(BOUND_MODES),
            "non_claims": list(NON_CLAIMS),
        }

    def describe(self) -> dict[str, Any]:
        if self.composition_id != COMPOSITION_ID:
            raise ValueError(
                f"composition_id is a schema const; got {self.composition_id!r}, "
                f"expected {COMPOSITION_ID!r}"
            )
        return {
            "composition_id": self.composition_id,
            "present": sorted(self.fragments),
            "missing": self.missing,
            "unproducible_here": self.unproducible_here,
            "complete": self.complete,
            "gap_report": self.gap_report(),
        }


def draft_from_run(
    *,
    composition_id: str = COMPOSITION_ID,
    run_record: Any = None,
    feature_artifact: Any = None,
    dose_response: Any = None,
    dissociation: Any = None,
    invariance: Any = None,
    intervention_specs: Any = None,
    sober_vector: Any = None,
) -> BundleDraft:
    """Assemble whatever fragments the supplied evidence supports.

    Everything is optional: a run without an SAE legitimately has no SAEArtifact, and
    the draft reports that rather than inventing one.
    """
    d = BundleDraft(composition_id=composition_id)

    if run_record is not None:
        wr = getattr(run_record, "weights_ref", None)
        if wr:
            d.add("ModelArtifact", wr)
        rec = getattr(run_record, "receipt", None) or {}
        if rec:
            d.add("BenchmarkResult", rec)
    if feature_artifact is not None:
        d.add("FeatureArtifact", getattr(feature_artifact, "to_dict", lambda: feature_artifact)())
        rel = getattr(feature_artifact, "sae_release", None)
        if rel:
            d.add("SAEArtifact", rel)
        concepts = getattr(feature_artifact, "concepts", None)
        if concepts:
            d.add("FeatureActivationSet", concepts)
    if intervention_specs:
        d.add("SteeringIntervention", intervention_specs)
    if sober_vector is not None:
        d.add("ManifoldBaseline", getattr(sober_vector, "as_dict", lambda: sober_vector)())
    if dose_response is not None:
        d.add("ImplementabilityCurve", dose_response)
    if dissociation is not None:
        d.add("OffTargetAudit", dissociation)
    if invariance is not None:
        d.add("RobustnessCertificate",
              getattr(invariance, "as_dict", lambda: invariance)())
    return d
