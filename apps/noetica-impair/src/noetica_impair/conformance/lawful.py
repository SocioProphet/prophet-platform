"""Lawful-learning conformance: claim ledger, circuit registry, forbidden circuits.

Three superconscious schemas govern what a rig like this may assert and what it may
touch. The rig has been producing all three kinds of evidence without naming them.

**Claim ledger (M/T/S/E/G).** Every claim carries a tag, and the tag determines what
must back it. This maps onto the rig's own epistemics almost exactly:

    E  empirical      -- a measurement. Needs empirical_measurement_ref (a receipt).
    T  typological    -- a PARALLEL, not a finding. The whole receptor->computation
                         mapping is this: "GABA-A potentiation resembles self-monitor
                         ablation" is an analogy under test, never a result.
    G  governance     -- an invariant the rig enforces (dose-0 is bit-for-bit sober).
    M  mathematical   -- follows from a definition.
    S  speculative    -- a hypothesis with a test artifact and nothing more.

Mis-tagging is the failure this prevents. Calling the pharmacological analogy an E
claim would dress a metaphor as a measurement, which is precisely what the limbs
module warns against in prose -- here it becomes mechanical.

Everything the rig emits enters as ``captured``. Promotion is a human decision made
elsewhere; the tier-2 non_claims include ``no_public_claim_promotion``, so a rig that
promoted its own claims would violate the doctrine it conforms to.

**Circuit registry.** Every entry needs BOTH discovery evidence and ablation evidence.
The rig produces exactly that pair -- the pinned feature artifact discovers, the
steering/ablation run intervenes -- so its outputs are registry entries that were
never being written down.

**Forbidden circuits.** This is the one that bites. A preset that suppresses
``refusal_guard`` is steering a circuit someone may have declared off-limits. The rig
checks declarations BEFORE compiling a run, because discovering afterwards that you
ablated a deployment-gated circuit is not a check, it is an incident report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

TAG_RE = re.compile(r"^(M|T|S|E|G)(\|(M|T|S|E|G))*$")

#: The schemas constrain ids to a namespace, not free text. Enforced here so a caller
#: cannot mint an id that only fails at validation time, far from where it was chosen.
CLAIM_ID_RE = re.compile(r"^claim\.[a-z0-9_.-]+$")
CIRCUIT_ID_RE = re.compile(r"^circuit\.[a-z0-9_.-]+$")
CLAIM_MIN_LEN = 10


def claim_id(slug: str) -> str:
    """Build a conformant claim id from a slug."""
    return f"claim.{re.sub(r'[^a-z0-9_.-]+', '-', slug.lower()).strip('-')}"


def circuit_id(slug: str) -> str:
    return f"circuit.{re.sub(r'[^a-z0-9_.-]+', '-', slug.lower()).strip('-')}"

CLAIM_STATUS = ("captured", "under_review", "promoted", "retracted")
ALLOCATION_TYPES = ("composition", "superposition", "mixed", "unknown")
REGISTRY_STATUS = ("candidate", "admitted", "deprecated", "forbidden")
ENFORCEMENT_MODES = (
    "detection_only", "training_time_prevention", "post_training_audit",
    "deployment_gate",
)

#: Which supporting field each tag obliges. A tag without its evidence is the
#: mis-tagging this discipline exists to catch.
TAG_REQUIRES = {
    "M": "mathematical_dependency",
    "T": "typological_parallel_target",
    "S": "speculative_test_artifact",
    "E": "empirical_measurement_ref",
    "G": "governance_invariant_ref",
}


class LawfulError(ValueError):
    pass


# ── claim ledger ─────────────────────────────────────────────────────────────

def claim_entry(
    *,
    claim_id_: str,
    claim: str,
    tag: str,
    status: str = "captured",
    mathematical_dependency: str | None = None,
    typological_parallel_target: str | None = None,
    speculative_test_artifact: str | None = None,
    empirical_measurement_ref: str | None = None,
    governance_invariant_ref: str | None = None,
    claim_demarcation: str | None = None,
    source_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a ledger entry, refusing a tag whose evidence is absent."""
    if not CLAIM_ID_RE.match(claim_id_):
        raise LawfulError(
            f"claim_id {claim_id_!r} must match {CLAIM_ID_RE.pattern} -- use claim_id()"
        )
    if len(claim) < CLAIM_MIN_LEN:
        raise LawfulError(
            f"claim text is {len(claim)} chars; the schema requires at least "
            f"{CLAIM_MIN_LEN}. A claim too short to state itself is not auditable."
        )
    if not TAG_RE.match(tag):
        raise LawfulError(f"invalid tag {tag!r}; expected M/T/S/E/G, pipe-separated")
    if status not in CLAIM_STATUS:
        raise LawfulError(f"invalid status {status!r}")
    if status == "promoted":
        raise LawfulError(
            "this rig may not promote its own claims: the tier-2 binding declares "
            "no_public_claim_promotion. Emit as 'captured' and let promotion be a "
            "human decision made elsewhere."
        )

    supplied = {
        "mathematical_dependency": mathematical_dependency,
        "typological_parallel_target": typological_parallel_target,
        "speculative_test_artifact": speculative_test_artifact,
        "empirical_measurement_ref": empirical_measurement_ref,
        "governance_invariant_ref": governance_invariant_ref,
    }
    for t in tag.split("|"):
        need = TAG_REQUIRES[t]
        if not supplied.get(need):
            raise LawfulError(
                f"claim tagged {t} but {need!r} is missing. A {t}-tagged claim without "
                "its supporting reference is exactly the mis-tagging this discipline "
                "exists to prevent."
            )

    out: dict[str, Any] = {"claim_id": claim_id_, "claim": claim, "tag": tag,
                           "status": status}
    out.update({k: v for k, v in supplied.items() if v})
    if claim_demarcation:
        out["claim_demarcation"] = claim_demarcation
    if source_refs:
        out["source_refs"] = list(source_refs)
    return out


def measurement_claim(*, claim_id_: str, claim: str, receipt_ref: str,
                      demarcation: str | None = None) -> dict[str, Any]:
    """An E claim: something the rig actually measured, anchored to its receipt."""
    return claim_entry(
        claim_id_=claim_id_, claim=claim, tag="E",
        empirical_measurement_ref=receipt_ref,
        claim_demarcation=demarcation or
        "holds for this model, seed and battery version only",
    )


def analogy_claim(*, claim_id_: str, claim: str, receptor: str) -> dict[str, Any]:
    """A T claim: a receptor->computation PARALLEL, which is never a measurement.

    Every limb in ``substances.limbs`` is one of these. Tagging them E would dress the
    metaphor as a result.
    """
    return claim_entry(
        claim_id_=claim_id_, claim=claim, tag="T",
        typological_parallel_target=receptor,
        claim_demarcation=(
            "a hypothesis about which faculty should degrade, not a claim about brains "
            "or transformers. The rig tests the analogy; it does not presuppose it."
        ),
    )


def invariant_claim(*, claim_id_: str, claim: str, invariant_ref: str) -> dict[str, Any]:
    """A G claim: an invariant the rig enforces in code and asserts in tests."""
    return claim_entry(claim_id_=claim_id_, claim=claim, tag="G",
                       governance_invariant_ref=invariant_ref)


# ── circuit registry ─────────────────────────────────────────────────────────

def circuit_entry(
    *,
    circuit_id_: str,
    circuit_name: str,
    model_ref: str,
    discovery_evidence_ref: str,
    ablation_evidence_ref: str,
    allocation_type: str = "unknown",
    allocation_evidence: str | None = None,
    allocation_basis: str | None = None,
    registry_status: str = "candidate",
    layer_range: Sequence[int] | None = None,
    claim_refs: Sequence[str] = (),
    non_claims: Sequence[str] = (),
    replay_seal: str | None = None,
) -> dict[str, Any]:
    """A registry entry. Both evidence kinds are mandatory, by schema and by sense.

    Discovery without ablation is a correlation; ablation without discovery is a
    lesion with no named target. The rig produces both, which is what makes its
    outputs registry-shaped in the first place.
    """
    if not CIRCUIT_ID_RE.match(circuit_id_):
        raise LawfulError(
            f"circuit_id {circuit_id_!r} must match {CIRCUIT_ID_RE.pattern} -- use circuit_id()"
        )
    if allocation_type not in ALLOCATION_TYPES:
        raise LawfulError(f"invalid allocation_type {allocation_type!r}")
    if registry_status not in REGISTRY_STATUS:
        raise LawfulError(f"invalid registry_status {registry_status!r}")
    if not discovery_evidence_ref or not ablation_evidence_ref:
        raise LawfulError(
            "a circuit entry needs BOTH discovery and ablation evidence: discovery "
            "alone is a correlation, ablation alone is a lesion with no named target"
        )
    entry: dict[str, Any] = {
        "circuit_id": circuit_id_,
        "circuit_name": circuit_name,
        "model_ref": model_ref,
        "discovery_evidence_ref": discovery_evidence_ref,
        "ablation_evidence_ref": ablation_evidence_ref,
        "allocation_type": allocation_type,
        "allocation_evidence": allocation_evidence or
        "SAE feature set; allocation not separately established",
        "allocation_basis": allocation_basis or
        "contrastive discovery over minimal pairs; superposition not ruled out",
        "registry_status": registry_status,
    }
    if layer_range:
        entry["layer_range"] = list(layer_range)
    if claim_refs:
        entry["claim_refs"] = list(claim_refs)
    if non_claims:
        entry["non_claims"] = list(non_claims)
    if replay_seal:
        entry["replay_seal"] = replay_seal
    return entry


# ── forbidden circuits ───────────────────────────────────────────────────────

@dataclass
class ForbiddenCircuit:
    forbidden_circuit_id: str
    circuit_pattern: str
    prohibition_basis: str
    enforcement_mode: str
    detection_method: str

    def __post_init__(self) -> None:
        if self.enforcement_mode not in ENFORCEMENT_MODES:
            raise LawfulError(f"invalid enforcement_mode {self.enforcement_mode!r}")

    def matches(self, concept: str) -> bool:
        try:
            return bool(re.search(self.circuit_pattern, concept, re.I))
        except re.error:
            return self.circuit_pattern.lower() in concept.lower()


@dataclass
class ForbiddenCheck:
    allowed: bool
    hits: list[tuple[str, ForbiddenCircuit]] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    advisory: list[str] = field(default_factory=list)

    def report(self) -> str:
        if not self.hits:
            return "no declared forbidden circuit matches this preset"
        lines = ["forbidden-circuit matches:"]
        for concept, fc in self.hits:
            mark = "BLOCKING" if fc.enforcement_mode == "deployment_gate" else "advisory"
            lines.append(f"  [{mark}] {concept} ~ {fc.forbidden_circuit_id} "
                         f"({fc.enforcement_mode}): {fc.prohibition_basis}")
        return "\n".join(lines)


def check_forbidden(
    concepts: Iterable[str], declarations: Sequence[ForbiddenCircuit],
) -> ForbiddenCheck:
    """Check a preset's target concepts against forbidden-circuit declarations.

    ``deployment_gate`` blocks; the other modes are advisory and recorded. The check
    runs BEFORE a run compiles -- finding out afterwards that you ablated a gated
    circuit is not a check, it is an incident report.
    """
    hits: list[tuple[str, ForbiddenCircuit]] = []
    for c in concepts:
        for fc in declarations:
            if fc.matches(c):
                hits.append((c, fc))
    blocking = sorted({f"{c}~{fc.forbidden_circuit_id}" for c, fc in hits
                       if fc.enforcement_mode == "deployment_gate"})
    advisory = sorted({f"{c}~{fc.forbidden_circuit_id}" for c, fc in hits
                       if fc.enforcement_mode != "deployment_gate"})
    return ForbiddenCheck(allowed=not blocking, hits=hits,
                          blocking=blocking, advisory=advisory)


def preset_concepts(preset: Any) -> list[str]:
    """The concepts a preset steers -- what a forbidden-circuit check must cover."""
    return [f.concept for f in getattr(preset, "features", ())]
