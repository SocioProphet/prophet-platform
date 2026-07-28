"""Fluency vs competence split (probe 6.5) -- the core readout.

The same task is scored twice: surface fluency (how well-formed the continuation is,
via normalised loglikelihood) and correctness (did it pick the right answer). The
signature of an intoxicant is competence falling while fluency holds. If both drop
together the intervention is too coarse and is a general lesion, not a drug -- so this
probe is also the rig's own coarseness detector.

Fluency is measured on the model's OWN preferred continuation, not on the correct
one. Scoring fluency on the gold answer would make fluency and competence the same
measurement wearing two hats.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Probe, ProbeResult, Subject

# (prompt, correct, distractors)
ITEMS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("The capital city of France is", " Paris", (" Lyon", " Geneva", " Brussels")),
    ("Water boils at sea level at a temperature of", " 100 degrees Celsius",
     (" 50 degrees Celsius", " 200 degrees Celsius", " 10 degrees Celsius")),
    ("If you have three apples and eat one, you have", " two apples",
     (" four apples", " five apples", " no apples")),
    ("The largest planet in the solar system is", " Jupiter",
     (" Mars", " Mercury", " Venus")),
    ("A decade is a period of", " ten years", (" one year", " a hundred years", " five years")),
    ("The chemical symbol for gold is", " Au", (" Ag", " Gd", " Go")),
    ("Sound travels more slowly than", " light", (" sand", " thought", " colour")),
    ("A triangle has", " three sides", (" four sides", " five sides", " two sides")),
)


@dataclass
class FluencyCompetenceProbe(Probe):
    name: str = "fluency_competence"
    version: str = "v1"
    items: tuple = field(default=ITEMS)

    def run(self, subject: Subject) -> ProbeResult:
        correct = 0
        fluencies: list[float] = []
        for prompt, gold, distractors in self.items:
            options = [gold, *distractors]
            scores = [subject.loglikelihood(prompt, o) for o in options]
            best = max(range(len(options)), key=lambda i: scores[i])
            correct += int(best == 0)
            # Per-character normalisation so long and short continuations compare.
            chosen = options[best]
            fluencies.append(scores[best] / max(len(chosen), 1))

        n = len(self.items)
        competence = correct / n
        mean_fluency = sum(fluencies) / n
        # Map mean per-char loglikelihood into (0,1]; monotone, so ordering is what
        # matters and the constant only sets the scale.
        fluency = float(pow(2.718281828, mean_fluency))
        return ProbeResult(
            name=self.name,
            score=competence,
            detail={
                "competence": competence,
                "fluency": min(fluency, 1.0),
                "mean_logprob_per_char": mean_fluency,
                "n_items": n,
            },
        )
