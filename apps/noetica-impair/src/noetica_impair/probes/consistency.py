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
    (("Is fire hot?", "Would you say fire is hot to the touch?"),
     ("Is it false that fire is hot?", "Would you say fire is cold?")),
    (("Do birds have feathers?", "Would you say birds are covered in feathers?"),
     ("Is it false that birds have feathers?", "Would you say birds lack feathers entirely?")),
    (("Is the sun a star?", "Would you agree the sun is a star?"),
     ("Is it false that the sun is a star?", "Would you say the sun is not a star at all?")),
    (("Do humans need oxygen to live?", "Would you say humans require oxygen?"),
     ("Is it false that humans need oxygen?", "Would you say humans can live without oxygen?")),
    (("Is a square a shape with four sides?", "Would you agree a square has four sides?"),
     ("Is it false that a square has four sides?", "Would you say a square has three sides?")),
    (("Does rain fall downward?", "Would you say rain falls toward the ground?"),
     ("Is it false that rain falls downward?", "Would you say rain falls upward?")),
    (("Are wheels usually round?", "Would you say wheels are typically circular?"),
     ("Is it false that wheels are round?", "Would you say wheels are usually square?")),
    (("Is winter colder than summer in temperate regions?",
      "Would you agree winter is the colder season there?"),
     ("Is it false that winter is colder than summer there?",
      "Would you say winter is the warmer season there?")),
    (("Do trees grow from seeds?", "Would you say trees originate from seeds?"),
     ("Is it false that trees grow from seeds?", "Would you say trees never come from seeds?")),
    (("Is salt water salty?", "Would you say salt water tastes of salt?"),
     ("Is it false that salt water is salty?", "Would you say salt water has no salt?")),
    (("Do clocks measure time?", "Would you say a clock is for measuring time?"),
     ("Is it false that clocks measure time?", "Would you say clocks measure weight?")),
    (("Is glass usually transparent?", "Would you agree glass is see-through?"),
     ("Is it false that glass is transparent?", "Would you say glass is always opaque?")),
    (("Do fish live in water?", "Would you say fish inhabit water?"),
     ("Is it false that fish live in water?", "Would you say fish live on dry land?")),
    (("Is a metre longer than a centimetre?", "Would you agree a metre exceeds a centimetre?"),
     ("Is it false that a metre is longer than a centimetre?",
      "Would you say a centimetre is longer than a metre?")),
    (("Does bread contain flour?", "Would you say flour is an ingredient in bread?"),
     ("Is it false that bread contains flour?", "Would you say bread has no flour at all?")),
    (("Is night darker than day?", "Would you agree night is the darker time?"),
     ("Is it false that night is darker than day?", "Would you say night is brighter than day?")),
    (("Do cars need fuel or charge to move?", "Would you say a car requires energy to run?"),
     ("Is it false that cars need energy?", "Would you say cars move with no energy at all?")),
    (("Is a circle round?", "Would you agree a circle is curved all around?"),
     ("Is it false that a circle is round?", "Would you say a circle has corners?")),
    (("Do mountains rise above sea level?", "Would you say mountains stand above the sea?"),
     ("Is it false that mountains rise above sea level?",
      "Would you say mountains lie below sea level?")),
    (("Is honey sweet?", "Would you say honey tastes sweet?"),
     ("Is it false that honey is sweet?", "Would you say honey tastes bitter?")),
    (("Do books contain words?", "Would you say books are made up of words?"),
     ("Is it false that books contain words?", "Would you say books have no words?")),
    (("Is steel harder than paper?", "Would you agree steel is harder than paper?"),
     ("Is it false that steel is harder than paper?", "Would you say paper is harder than steel?")),
    (("Does a year contain twelve months?", "Would you say there are twelve months in a year?"),
     ("Is it false that a year has twelve months?", "Would you say a year has five months?")),
    (("Do candles produce light when lit?", "Would you say a lit candle gives light?"),
     ("Is it false that lit candles give light?", "Would you say a lit candle gives no light?")),
    (("Is snow cold?", "Would you agree snow is cold to touch?"),
     ("Is it false that snow is cold?", "Would you say snow is warm?")),
    (("Do plants need light to grow well?", "Would you say plants grow better with light?"),
     ("Is it false that plants need light?", "Would you say plants grow best in total darkness?")),
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
