"""FacultyVector, dose-response curves, and the dissociation matrix (section 7).

Every faculty score is normalised as *fraction of sober performance retained*, so
1.0 = untouched and 0.0 = destroyed, and rows are comparable across models whose
absolute baselines differ.

The acceptance test for invariant 0.4 deserves a note, because the obvious
implementation is wrong. Comparing substance rows by plain cosine distance conflates
two different things: HOW BADLY a substance degrades (severity) and WHICH FACULTIES
it degrades first (shape). Four substances that all collapse everything, but to
different depths, have near-zero pairwise cosine distance in the retained-fraction
space only if their profiles are parallel -- but a uniform lesion at four different
strengths IS parallel, and that is precisely the failure mode the work order says to
flag ("one lesion with four labels").

So the test runs on MEAN-CENTERED rows: subtract each row's own mean degradation and
compare what is left. Uniform collapse maps to the zero vector and fails, which is
the intended behaviour. Severity is reported separately, never as evidence of
dissociation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

#: Scalar faculties used for dissociation. wm_curve is summarised by its AUC here and
#: reported in full separately -- alcohol and cannabis hit working memory with
#: different curve SHAPES, which a scalar cannot express (see probes/working_memory).
FACULTIES = ("consistency", "calibration", "lookahead", "working_memory", "fluency", "competence")


@dataclass
class FacultyVector:
    consistency: float = 1.0
    calibration: float = 1.0          # retained calibration (1 - normalised ECE)
    hedge_rate: float = 1.0           # assertion-under-uncertainty, reported not scored
    lookahead: float = 1.0
    working_memory: float = 1.0       # AUC of wm_curve
    fluency: float = 1.0
    competence: float = 1.0
    wm_curve: list[float] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in FACULTIES}
        d["hedge_rate"] = self.hedge_rate
        d["wm_curve"] = list(self.wm_curve)
        return d

    def scalars(self) -> list[float]:
        return [float(getattr(self, k)) for k in FACULTIES]

    def retained_against(self, sober: "FacultyVector") -> "FacultyVector":
        """Express this vector as the fraction of the sober control it retains."""

        def frac(a: float, b: float) -> float:
            return 1.0 if b == 0 else max(0.0, a / b)

        out = FacultyVector(
            **{k: frac(getattr(self, k), getattr(sober, k)) for k in FACULTIES},
            hedge_rate=frac(self.hedge_rate, sober.hedge_rate),
        )
        out.wm_curve = [
            frac(a, b) for a, b in zip(self.wm_curve, sober.wm_curve)
        ] if sober.wm_curve else list(self.wm_curve)
        return out

    @property
    def fluency_competence_gap(self) -> float:
        """The core readout: positive means fluency held while competence fell.

        Near zero (or negative) means the intervention is too coarse -- it damaged the
        surface as much as the content, and is a general lesion rather than an
        intoxicant.
        """
        return self.fluency - self.competence


def auc(curve: Sequence[float]) -> float:
    if not curve:
        return 1.0
    return sum(curve) / len(curve)


# --- vector geometry ----------------------------------------------------------

def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return 1.0 - _dot(a, b) / (na * nb)


def l2(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def center(row: Sequence[float]) -> list[float]:
    """Remove overall severity, leaving the degradation SHAPE."""
    m = sum(row) / len(row)
    return [x - m for x in row]


#: A centered row must vary by at least this fraction of its own scale before its
#: direction is meaningful. Below it, the row is flat and its "direction" is float noise.
FLAT_REL_TOL = 1e-6


def _is_flat(centered: Sequence[float], original: Sequence[float]) -> bool:
    scale = max((abs(x) for x in original), default=0.0)
    return _norm(centered) <= max(FLAT_REL_TOL * max(scale, 1e-12), 1e-12)


@dataclass
class DissociationMatrix:
    """substance -> retained-fraction per faculty, at one fixed dose."""

    dose: float
    rows: dict[str, list[float]] = field(default_factory=dict)
    faculties: tuple[str, ...] = FACULTIES

    def add(self, substance: str, fv: FacultyVector) -> None:
        self.rows[substance] = fv.scalars()

    def severity(self, substance: str) -> float:
        row = self.rows[substance]
        return 1.0 - (sum(row) / len(row))

    def shape_distance(self, a: str, b: str) -> float:
        """Cosine distance between mean-centered rows, guarded for flat profiles.

        The guard is not a nicety. A uniformly-degraded row centers to floating-point
        residue (~1e-16), and the cosine between two such noise vectors is arbitrary --
        in practice it returns values up to 2.0, i.e. MAXIMAL distance. Without this
        check the single failure mode invariant 0.4 exists to catch (four substances
        that are one lesion wearing four labels) would be reported as perfect
        dissociation. A flat profile has no shape, so it is indistinguishable by shape
        from anything, including another flat profile.
        """
        ca, cb = center(self.rows[a]), center(self.rows[b])
        if _is_flat(ca, self.rows[a]) or _is_flat(cb, self.rows[b]):
            return 0.0
        return cosine_distance(ca, cb)

    def pairwise(self) -> dict[tuple[str, str], float]:
        names = sorted(self.rows)
        return {
            (x, y): self.shape_distance(x, y)
            for i, x in enumerate(names) for y in names[i + 1 :]
        }

    def check(self, threshold: float = 0.15) -> "DissociationVerdict":
        pw = self.pairwise()
        failing = {k: v for k, v in pw.items() if v < threshold}
        return DissociationVerdict(
            dose=self.dose, threshold=threshold, pairwise=pw, failing=failing,
            severities={s: self.severity(s) for s in self.rows},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dose": self.dose, "faculties": list(self.faculties),
            "rows": {k: list(v) for k, v in self.rows.items()},
            "pairwise_shape_distance": {f"{a}|{b}": v for (a, b), v in self.pairwise().items()},
        }


@dataclass
class DissociationVerdict:
    dose: float
    threshold: float
    pairwise: dict[tuple[str, str], float]
    failing: dict[tuple[str, str], float]
    severities: dict[str, float]

    @property
    def distinct(self) -> bool:
        return not self.failing

    def report(self) -> str:
        if self.distinct:
            lines = [f"DISSOCIATION HOLDS at d={self.dose:g} "
                     f"(min pairwise shape distance {min(self.pairwise.values()):.3f} "
                     f">= {self.threshold})"]
        else:
            lines = [
                f"DISSOCIATION FAILED at d={self.dose:g}: the following substance pairs "
                f"degrade the same faculties in the same order, which means one lesion "
                f"with several labels -- flag and stop (invariant 0.4)."
            ]
            for (a, b), v in sorted(self.failing.items(), key=lambda kv: kv[1]):
                lines.append(f"  {a} vs {b}: shape distance {v:.3f} < {self.threshold}")
        lines.append("severity (mean degradation, NOT evidence of dissociation):")
        for s, v in sorted(self.severities.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {s}: {v:.3f}")
        return "\n".join(lines)


@dataclass
class DoseResponse:
    """faculty -> [(dose, retained_fraction)] for one substance on one model."""

    substance: str
    model_key: str
    points: dict[float, FacultyVector] = field(default_factory=dict)

    def add(self, dose: float, fv: FacultyVector) -> None:
        self.points[float(dose)] = fv

    def curve(self, faculty: str) -> list[tuple[float, float]]:
        return [(d, getattr(self.points[d], faculty)) for d in sorted(self.points)]

    def monotone(self, faculty: str, tol: float = 1e-6) -> bool:
        vals = [v for _, v in self.curve(faculty)]
        return all(b <= a + tol for a, b in zip(vals, vals[1:]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "substance": self.substance, "model_key": self.model_key,
            "curves": {f: self.curve(f) for f in FACULTIES},
        }


def nearest_mechanical(
    topical: FacultyVector,
    catalogue: Iterable[tuple[str, float, FacultyVector]],
) -> tuple[str, float, float]:
    """Section 7 headline: map a topical stimulus onto (substance, dose) by L2.

    Returns ``(substance, dose, distance)`` -- e.g. "charged-topic X reads as
    ALCOHOL@0.4-equivalent". Distance is returned so a poor match can be reported as
    a poor match instead of being quietly rounded to the nearest label.
    """
    best: tuple[str, float, float] | None = None
    t = topical.scalars()
    for name, dose, fv in catalogue:
        d = l2(t, fv.scalars())
        if best is None or d < best[2]:
            best = (name, dose, d)
    if best is None:
        raise ValueError("empty mechanical catalogue")
    return best
