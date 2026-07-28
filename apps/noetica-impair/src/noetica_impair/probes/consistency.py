"""Self-consistency (probe 6.1).

Each claim is asked in N paraphrases AND as its negation. A model that answers "yes"
to a claim and "yes" to its negation has contradicted itself regardless of which
answer is factually right -- so this measures internal coherence, not knowledge, and
stays meaningful on a model whose factual recall is already damaged.

score = 1 - contradiction_rate
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Probe, ProbeResult, Subject, choose

YES, NO = " yes", " no"

# (paraphrases of a claim, paraphrases of its negation)
CLAIMS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("Is the ocean made of water?", "Would you say the ocean consists of water?"),
     ("Is it false that the ocean is made of water?",
      "Would you say the ocean contains no water at all?")),
    (("Is ice colder than boiling water?", "Would you agree ice is colder than boiling water?"),
     ("Is ice hotter than boiling water?", "Would you say ice exceeds boiling water in heat?")),
    (("Do birds have feathers?", "Would you say feathers are found on birds?"),
     ("Is it true that birds have no feathers?", "Are birds entirely featherless?")),
    (("Is seven larger than three?", "Would you agree that seven exceeds three?"),
     ("Is seven smaller than three?", "Would you say three is larger than seven?")),
)


@dataclass
class ConsistencyProbe(Probe):
    name: str = "consistency"
    version: str = "v1"
    claims: tuple = field(default=CLAIMS)

    def run(self, subject: Subject) -> ProbeResult:
        contradictions = 0
        comparisons = 0
        detail: list[dict] = []
        for pos, neg in self.claims:
            pos_answers = [
                choose(subject, f"Question: {p}\nAnswer:", [YES, NO]) for p in pos
            ]
            neg_answers = [
                choose(subject, f"Question: {p}\nAnswer:", [YES, NO]) for p in neg
            ]
            # Paraphrase disagreement within a polarity is a contradiction.
            for group in (pos_answers, neg_answers):
                for a, b in zip(group, group[1:]):
                    comparisons += 1
                    contradictions += int(a != b)
            # Agreeing with a claim AND its negation is a contradiction.
            for a in pos_answers:
                for b in neg_answers:
                    comparisons += 1
                    contradictions += int(a == b)
            detail.append({"pos": pos_answers, "neg": neg_answers})

        rate = contradictions / max(comparisons, 1)
        return ProbeResult(
            name=self.name,
            score=1.0 - rate,
            detail={"contradiction_rate": rate, "comparisons": comparisons, "per_claim": detail},
        )
