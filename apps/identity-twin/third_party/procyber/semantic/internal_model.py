"""Internal model — the share/withhold equilibrium.

The `daat` coordinate of `AgentCoordinateVector` has been declarable since S0 and
computed by nothing. This is the organ that computes it, and it is the one place in
the kernel where an agent decides whether knowledge leaves it.

The shape of the decision
-------------------------
Two arms, both required:

  ADMIT     five rules, each answering "what is the strongest case for sharing this?"
            The arm is the MAXIMUM over the applicable rules — the best case anyone
            can make.

  WITHHOLD  five rules, each answering "what ceiling does this impose?"
            The arm is the MINIMUM — the most restrictive rule governs, because a
            single sufficient reason to withhold is sufficient.

  EQUILIBRIUM = meet(admit_arm, withhold_arm)

`meet` is the lattice minimum, so the withhold arm caps the result and **an admit
signal can never authorise a share on its own**. That is not enforced by a special
case here; it falls out of the algebra. `meet` also absorbs `BOTTOM`, so if either
arm was never computed the equilibrium is `BOTTOM` — an agent that only asked "why
share?" and never asked "why not?" abstains rather than shares.

Why both arms rather than a single score
----------------------------------------
A single score lets a strong reason to share numerically outweigh a sufficient reason
to withhold. Provenance that does not reach a sealed root, or a linkability risk, are
not quantities to be traded against usefulness — they are ceilings. Keeping the arms
separate and reconciling by meet is what makes them ceilings rather than weights.

What this module does not do
----------------------------
It decides; it does not transmit. Serialising and sending is the boundary crossing's
job, and a decision recorded here is an input to that, never a substitute for it. It
also holds no state across calls: an `InternalModelState` is the record of one
evaluation, so a decision is always reconstructible from its inputs.

Pure and local-first: stdlib only, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, Optional, Tuple

from procyber.semantic.semantic_algebra import (
    BOTTOM,
    VERDICT_ORDER,
    Abstain,
    SemanticAddress,
    meet,
)

SPEC_VERSION = "0.1.0"

#: Sharing requires clearing this rung of the lattice. Below it, the decision is a
#: refusal to share, not a weak share — there is no partial transmission.
SHARE_THRESHOLD = "probable"


# --------------------------------------------------------------------------- #
# 1. The request
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ShareRequest:
    """One proposed disclosure: what, to whom, under whose mandate, when.

    `counterparty_trusted` is an input, not something this module infers. Whether a
    counterparty is trusted is a trust-broker decision with its own evidence; taking
    it as a parameter keeps that seam honest.
    """

    address: SemanticAddress
    counterparty: str
    our_mandate: FrozenSet[str]
    counterparty_mandate: FrozenSet[str]
    topic: str
    as_of: str
    counterparty_trusted: bool = False
    skeleton_only: bool = False
    standing_policy_conflict: bool = False


@dataclass(frozen=True)
class RuleVerdict:
    """One rule's answer, always with its reason. A verdict with no reason is noise."""

    rule: str
    verdict: "str | Abstain"
    reason: str

    @property
    def applicable(self) -> bool:
        return self.verdict is not BOTTOM


# --------------------------------------------------------------------------- #
# 2. Admit rules — the strongest case for sharing
# --------------------------------------------------------------------------- #


def admit_generalization(req: ShareRequest) -> RuleVerdict:
    """Share the highest abstraction that still survives scrutiny.

    A derived general claim travels well: it carries less about any particular
    subject and more about the structure. Layer is the abstraction measure, and it is
    syntactic, so this cannot be argued up.
    """
    if req.address.layer >= 2 and req.address.inference in ("induced", "deduced"):
        return RuleVerdict("generalization", "sealed", "derived general claim at layer>=2")
    if req.address.layer >= 2:
        return RuleVerdict("generalization", "probable", "general but merely asserted")
    return RuleVerdict("generalization", BOTTOM, "too specific to share as a generalization")


def admit_contextualized_specialization(req: ShareRequest) -> RuleVerdict:
    """A specific claim may travel *with* its context envelope, never without it.

    The envelope is the validity interval. A specific claim stripped of the window in
    which it held is the single easiest way to mislead a counterparty.
    """
    has_envelope = req.address.valid_from is not None or req.address.valid_until is not None
    if has_envelope:
        return RuleVerdict("contextualized_specialization", "probable", "specific claim carries its validity envelope")
    return RuleVerdict("contextualized_specialization", BOTTOM, "no context envelope to travel with")


def admit_precedent(req: ShareRequest) -> RuleVerdict:
    """A prior decision plus its receipt is reusable by others as a warrant."""
    if req.address.evidence_ref:
        return RuleVerdict("precedent", "probable", "carries an evidence pointer usable as precedent")
    return RuleVerdict("precedent", BOTTOM, "no evidence pointer, so no precedent to offer")


def admit_counter_example(req: ShareRequest) -> RuleVerdict:
    """Negative knowledge is the cheapest thing to share safely.

    A known failure tells a counterparty what not to do while revealing far less than
    the corresponding positive claim would.
    """
    if req.address.mood == "negate":
        return RuleVerdict("counter_example", "sealed", "negative knowledge: says what does not hold")
    return RuleVerdict("counter_example", BOTTOM, "not a counter-example")


def admit_capability_offer(req: ShareRequest) -> RuleVerdict:
    """"I can do X under grant Y" — an advertisement, not a disclosure of content."""
    if req.topic in req.our_mandate:
        return RuleVerdict("capability_offer", "probable", "capability lies inside our own mandate")
    return RuleVerdict("capability_offer", BOTTOM, "cannot offer a capability outside our mandate")


ADMIT_RULES: Tuple[Callable[[ShareRequest], RuleVerdict], ...] = (
    admit_generalization,
    admit_contextualized_specialization,
    admit_precedent,
    admit_counter_example,
    admit_capability_offer,
)


# --------------------------------------------------------------------------- #
# 3. Withhold rules — the ceilings
# --------------------------------------------------------------------------- #

#: A withhold rule that finds nothing wrong returns the top of the lattice: it imposes
#: no ceiling. It never returns BOTTOM, because "I did not find a problem" and "I was
#: not consulted" must not be the same value.
NO_CEILING = VERDICT_ORDER[-1]


def withhold_provenance_insufficient(req: ShareRequest) -> RuleVerdict:
    """No evidence chain, no share. Provenance is a ceiling, not a discount."""
    if not req.address.evidence_ref:
        return RuleVerdict("provenance_insufficient", "refuse", "no evidence reference on the address")
    return RuleVerdict("provenance_insufficient", NO_CEILING, "evidence reference present")


def withhold_linkability_risk(req: ShareRequest) -> RuleVerdict:
    """A grounded address identifies its subject; a skeleton does not.

    Structure may travel where the referent may not, which is exactly what
    `SemanticAddress.skeleton()` is for.
    """
    if req.skeleton_only:
        return RuleVerdict("linkability_risk", NO_CEILING, "skeleton carries structure without the referent")
    if req.address.is_grounded and not req.counterparty_trusted:
        return RuleVerdict("linkability_risk", "quarantine", "grounded address to an untrusted counterparty")
    return RuleVerdict("linkability_risk", NO_CEILING, "no linkability exposure")


def withhold_staleness(req: ShareRequest) -> RuleVerdict:
    """An expired claim may still be shared, but never as a current one."""
    until = req.address.valid_until
    if until is not None and until < req.as_of:
        return RuleVerdict("staleness", "weak", f"validity lapsed at {until}")
    return RuleVerdict("staleness", NO_CEILING, "within validity")


def withhold_out_of_mandate(req: ShareRequest) -> RuleVerdict:
    """The topic must sit inside BOTH charters. Either alone is not authority."""
    if req.topic not in req.our_mandate:
        return RuleVerdict("out_of_mandate", "refuse", "topic outside our own mandate")
    if req.topic not in req.counterparty_mandate:
        return RuleVerdict("out_of_mandate", "refuse", "topic outside the counterparty's mandate")
    return RuleVerdict("out_of_mandate", NO_CEILING, "topic within both mandates")


def withhold_contradiction_with_law(req: ShareRequest) -> RuleVerdict:
    """A standing policy conflict is a veto, whatever the case for sharing."""
    if req.standing_policy_conflict:
        return RuleVerdict("contradiction_with_law", "refuse", "conflicts with a standing policy")
    if req.address.revocation_ref:
        return RuleVerdict("contradiction_with_law", "refuse", "address carries a revocation reference")
    return RuleVerdict("contradiction_with_law", NO_CEILING, "no standing conflict")


WITHHOLD_RULES: Tuple[Callable[[ShareRequest], RuleVerdict], ...] = (
    withhold_provenance_insufficient,
    withhold_linkability_risk,
    withhold_staleness,
    withhold_out_of_mandate,
    withhold_contradiction_with_law,
)


# --------------------------------------------------------------------------- #
# 4. The equilibrium
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InternalModelState:
    """The record of one evaluation: both arms, every rule, every reason."""

    admit: Tuple[RuleVerdict, ...]
    withhold: Tuple[RuleVerdict, ...]

    @property
    def admit_arm(self) -> "str | Abstain":
        """MAXIMUM over applicable admit rules — the best case for sharing.

        `BOTTOM` when no admit rule applied: nobody could state a reason to share.
        """
        applicable = [r.verdict for r in self.admit if r.applicable]
        if not applicable:
            return BOTTOM
        return max(applicable, key=VERDICT_ORDER.index)  # type: ignore[arg-type]

    @property
    def withhold_arm(self) -> "str | Abstain":
        """MINIMUM over withhold rules — the most restrictive ceiling governs.

        `BOTTOM` when the withhold rules were not run at all. That is the difference
        between "nothing objected" and "nothing was asked", and conflating the two is
        how a share slips through unexamined.
        """
        if not self.withhold:
            return BOTTOM
        return min((r.verdict for r in self.withhold), key=VERDICT_ORDER.index)  # type: ignore[arg-type]

    @property
    def equilibrium(self) -> "str | Abstain":
        """The reconciliation. `meet` caps at the withhold arm and absorbs `BOTTOM`."""
        return meet(self.admit_arm, self.withhold_arm)

    def may_share(self, threshold: str = SHARE_THRESHOLD) -> bool:
        """True only if the equilibrium clears the threshold. `BOTTOM` never clears."""
        verdict = self.equilibrium
        if verdict is BOTTOM:
            return False
        return VERDICT_ORDER.index(verdict) >= VERDICT_ORDER.index(threshold)  # type: ignore[arg-type]

    def binding_reason(self) -> str:
        """Why the answer is what it is — the rule that actually set the ceiling.

        A decision a counterparty cannot interrogate is indistinguishable from an
        arbitrary one, so the governing rule is always nameable.
        """
        if not self.withhold:
            return "withhold arm not evaluated"
        governing = min(self.withhold, key=lambda r: VERDICT_ORDER.index(r.verdict))  # type: ignore[arg-type]
        if self.admit_arm is BOTTOM:
            return "no admit rule applied: no case for sharing was made"
        return f"{governing.rule}: {governing.reason}"

    def to_json(self) -> Dict[str, object]:
        verdict = self.equilibrium
        return {
            "specVersion": SPEC_VERSION,
            "admitArm": self.admit_arm if self.admit_arm is not BOTTOM else None,
            "withholdArm": self.withhold_arm if self.withhold_arm is not BOTTOM else None,
            "equilibrium": verdict if verdict is not BOTTOM else None,
            "mayShare": self.may_share(),
            "bindingReason": self.binding_reason(),
            "admit": [
                {"rule": r.rule, "verdict": r.verdict if r.applicable else None, "reason": r.reason}
                for r in self.admit
            ],
            "withhold": [
                {"rule": r.rule, "verdict": r.verdict, "reason": r.reason} for r in self.withhold
            ],
        }


def evaluate(req: ShareRequest) -> InternalModelState:
    """Run both arms. There is no way to run one without the other."""
    return InternalModelState(
        admit=tuple(rule(req) for rule in ADMIT_RULES),
        withhold=tuple(rule(req) for rule in WITHHOLD_RULES),
    )
