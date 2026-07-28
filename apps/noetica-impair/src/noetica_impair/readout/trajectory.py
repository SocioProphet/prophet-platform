"""Faculty trajectories and the kinetic statistics that separate same-vector drugs.

``TemporalProbe`` reports per-item scores and the clock position of each item, and
knows nothing about dose. This module supplies the missing half: it maps clock
positions onto the envelope the run was configured with, and reduces the pair of
(dose curve, impairment curve) to statistics that distinguish substances whose
PARAMETER VECTORS are identical.

Cocaine and crack are that case by construction. Both must therefore be separated -- if
at all -- by shape in time: how fast impairment arrives, whether it peaks, and whether
performance comes back within the run.

Three cautions are built in rather than left to the reader.

**Everything is per-item retained fraction against the paired sober control.** Item
difficulty varies, and the sober run supplies the per-item baseline. Comparing an
impaired trajectory against its own first item instead would fold item difficulty into
the "onset".

**Alignment can be checked, not assumed.** ``dose_alignment`` correlates dose(t) with
impairment(t). If the envelope is not actually driving the effect, that correlation is
near zero and every downstream statistic is describing noise -- so it is reported next
to them, not buried.

**Recovery is only meaningful if the dose actually falls.** A flat envelope trivially
shows no recovery. ``dose_falls`` records whether there was anything to recover from.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return float("nan")
    xa, xb = list(a[:n]), list(b[:n])
    ma, mb = sum(xa) / n, sum(xb) / n
    va = [x - ma for x in xa]
    vb = [x - mb for x in xb]
    num = sum(x * y for x, y in zip(va, vb))
    den = math.sqrt(sum(x * x for x in va)) * math.sqrt(sum(y * y for y in vb))
    return float("nan") if den < 1e-12 else num / den


def _smooth(xs: Sequence[float], w: int) -> list[float]:
    """Centred moving average. Per-item scores are 0/1, so raw curves are unreadable."""
    if w <= 1:
        return list(xs)
    out: list[float] = []
    half = w // 2
    for i in range(len(xs)):
        lo, hi = max(0, i - half), min(len(xs), i + half + 1)
        window = xs[lo:hi]
        out.append(sum(window) / len(window))
    return out


@dataclass
class FacultyTrajectory:
    """Retained competence over within-run time, aligned to the dose curve."""

    label: str
    retained: list[float]              # per item, fraction of sober performance
    dose: list[float]                  # effective dose at each item's clock position
    cum_tokens: list[int]
    smoothing: int = 5
    envelope_name: str = "constant"

    @property
    def smoothed(self) -> list[float]:
        return _smooth(self.retained, self.smoothing)

    @property
    def impairment(self) -> list[float]:
        return [1.0 - r for r in self.smoothed]

    @property
    def dose_falls(self) -> bool:
        """Did the dose ever drop materially below its peak within the run?"""
        if not self.dose:
            return False
        peak = max(self.dose)
        return peak > 0 and min(self.dose[self.dose.index(peak):] or [peak]) < peak * 0.7

    @property
    def dose_alignment(self) -> float:
        """Correlation between dose(t) and impairment(t). Near zero => nothing to read."""
        return _pearson(self.dose, self.impairment)

    def onset_index(self, threshold: float = 0.9) -> int | None:
        """First item whose smoothed retained competence falls below ``threshold``."""
        for i, r in enumerate(self.smoothed):
            if r < threshold:
                return i
        return None

    @property
    def peak_index(self) -> int:
        s = self.smoothed
        return min(range(len(s)), key=lambda i: s[i]) if s else 0

    @property
    def peak_impairment(self) -> float:
        s = self.smoothed
        return 1.0 - min(s) if s else 0.0

    @property
    def recovery(self) -> float:
        """How much of the peak impairment had resolved by the end of the run.

        1.0 = fully back to sober, 0.0 = still at peak. Only interpretable when
        ``dose_falls`` — a sustained envelope has nothing to recover from, and
        reporting 0.0 there as "no recovery" would be a statement about the design
        rather than about the substance.
        """
        s = self.smoothed
        if not s or self.peak_impairment <= 1e-9:
            return float("nan")
        end_impairment = 1.0 - s[-1]
        return max(0.0, min(1.0, 1.0 - end_impairment / self.peak_impairment))

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "envelope": self.envelope_name,
            "n_items": len(self.retained),
            "onset_index": self.onset_index(),
            "peak_index": self.peak_index,
            "peak_impairment": round(self.peak_impairment, 4),
            "recovery": (None if math.isnan(self.recovery) else round(self.recovery, 4)),
            "dose_falls": self.dose_falls,
            "dose_alignment": (None if math.isnan(self.dose_alignment)
                               else round(self.dose_alignment, 4)),
            "mean_retained": round(sum(self.retained) / len(self.retained), 4)
            if self.retained else None,
        }


def build_trajectory(
    *,
    label: str,
    impaired_detail: dict[str, Any],
    sober_detail: dict[str, Any],
    envelope: Any = None,
    peak_dose: float = 1.0,
    smoothing: int = 5,
) -> FacultyTrajectory:
    """Combine an impaired and a paired-sober TemporalProbe result into a trajectory.

    ``sober_detail`` must come from the SAME rig at dose 0 on the same seed (invariant
    0.3). Per-item normalisation against it is what removes item difficulty from the
    shape; without it an "onset" could just be a run of harder items.
    """
    imp = list(impaired_detail.get("per_item", []))
    sob = list(sober_detail.get("per_item", []))
    toks = list(impaired_detail.get("cum_tokens", []))
    n = min(len(imp), len(sob), len(toks))
    if n == 0:
        raise ValueError("no per-item scores to build a trajectory from")

    # Per-item retained fraction. A sober failure carries no information about the
    # drug, so those items are held at 1.0 rather than dividing by zero.
    retained = [1.0 if sob[i] <= 0 else min(1.0, imp[i] / sob[i]) for i in range(n)]

    if envelope is None:
        dose = [peak_dose] * n
        env_name = "constant"
    else:
        dose = [max(0.0, min(1.0, peak_dose * float(envelope.value(toks[i]))))
                for i in range(n)]
        env_name = getattr(envelope, "kind", "envelope")

    return FacultyTrajectory(
        label=label, retained=retained, dose=dose, cum_tokens=toks[:n],
        smoothing=smoothing, envelope_name=env_name,
    )


@dataclass
class KineticComparison:
    """Do two substances differ in TIME COURSE rather than in magnitude?"""

    a: str
    b: str
    onset_gap: int | None
    peak_gap: int
    recovery_gap: float | None
    mean_retained_gap: float
    separable: bool
    reason: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def report(self) -> str:
        head = "KINETICALLY SEPARABLE" if self.separable else "NOT separable in time"
        lines = [f"{head}: {self.a} vs {self.b}", f"  {self.reason}"]
        lines += [f"  ! {w}" for w in self.warnings]
        return "\n".join(lines)


def compare_kinetics(
    x: FacultyTrajectory, y: FacultyTrajectory, *,
    min_peak_gap: int = 3, min_recovery_gap: float = 0.25,
    max_magnitude_gap: float = 0.10, min_alignment: float = 0.3,
    min_impairment: float = 0.05,
) -> KineticComparison:
    """Separate two trajectories on SHAPE, explicitly discounting magnitude.

    The whole claim for crack-vs-cocaine is that they differ in time course while
    delivering a comparable total insult. So a large difference in mean retained
    competence is a WARNING, not evidence: it means the presets differ in strength and
    the separation may be magnitude wearing a kinetic costume.
    """
    warns: list[str] = []

    # A trajectory with no measurable impairment has no shape to compare. peak_index on
    # a flat curve is argmin of a constant -- i.e. index 0 -- so without this guard two
    # curves could be declared "kinetically separable" when one of them never moved.
    # Observed on toy weights: CRACK at peak_impairment 0.000 "separated" from COCAINE
    # by 21 items, which was arithmetic on noise.
    flat = [t.label for t in (x, y) if t.peak_impairment < min_impairment]
    if flat:
        return KineticComparison(
            a=x.label, b=y.label, onset_gap=None, peak_gap=0, recovery_gap=None,
            mean_retained_gap=abs(sum(x.retained) / len(x.retained)
                                  - sum(y.retained) / len(y.retained)),
            separable=False,
            reason=(f"no measurable impairment in {', '.join(flat)} "
                    f"(peak < {min_impairment}) — there is no time course to compare"),
            warnings=("a trajectory that never moved cannot support a kinetic claim",),
        )

    for t in (x, y):
        al = t.dose_alignment
        if math.isnan(al):
            warns.append(
                f"{t.label}: dose/impairment correlation undefined (a constant series) "
                "— the envelope or the impairment never varied, so kinetic statistics "
                "are not interpretable"
            )
            continue
        if not math.isnan(al) and al < min_alignment:
            warns.append(
                f"{t.label}: dose/impairment correlation {al:.2f} < {min_alignment} — "
                "the envelope may not be driving the effect, so these statistics may "
                "describe noise"
            )

    ox, oy = x.onset_index(), y.onset_index()
    onset_gap = None if (ox is None or oy is None) else abs(ox - oy)
    peak_gap = abs(x.peak_index - y.peak_index)
    rx, ry = x.recovery, y.recovery
    recovery_gap = (None if (math.isnan(rx) or math.isnan(ry)) else abs(rx - ry))

    mx = sum(x.retained) / len(x.retained)
    my = sum(y.retained) / len(y.retained)
    mag_gap = abs(mx - my)
    if mag_gap > max_magnitude_gap:
        warns.append(
            f"mean retained competence differs by {mag_gap:.2f} > {max_magnitude_gap} — "
            "these presets differ in STRENGTH, so a kinetic separation here may be "
            "magnitude in disguise. Match the peak doses before claiming a time-course "
            "result"
        )

    by_peak = peak_gap >= min_peak_gap
    by_recovery = recovery_gap is not None and recovery_gap >= min_recovery_gap
    separable = bool(by_peak or by_recovery)
    if separable:
        parts = []
        if by_peak:
            parts.append(f"peak impairment {peak_gap} items apart")
        if by_recovery:
            parts.append(f"recovery differs by {recovery_gap:.2f}")
        reason = "; ".join(parts)
    else:
        reason = (
            f"peak {peak_gap} items apart (needs {min_peak_gap}), recovery gap "
            f"{'n/a' if recovery_gap is None else f'{recovery_gap:.2f}'} "
            f"(needs {min_recovery_gap}) — same shape in time"
        )

    return KineticComparison(
        a=x.label, b=y.label, onset_gap=onset_gap, peak_gap=peak_gap,
        recovery_gap=recovery_gap, mean_retained_gap=mag_gap,
        separable=separable, reason=reason, warnings=tuple(warns),
    )
