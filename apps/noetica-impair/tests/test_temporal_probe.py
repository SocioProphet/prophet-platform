"""The within-run trajectory: the measurement crack and meth were missing.

Until this existed, CRACK and COCAINE were separable by construction only — they share
a parameter vector exactly and differ solely in kinetics, which a static battery
averages away.
"""

from __future__ import annotations

import math

import pytest

from noetica_impair.hooks.envelope import Bolus, Constant, get as get_envelope
from noetica_impair.probes.temporal import ITEMS, TemporalProbe
from noetica_impair.readout.trajectory import (
    build_trajectory, compare_kinetics, FacultyTrajectory,
)


class ScriptedSubject:
    """A subject whose correctness follows a supplied schedule."""

    def __init__(self, schedule):
        self.schedule = schedule
        self.calls = 0

    def generate(self, prompt, *, max_new_tokens=64):
        return ""

    def loglikelihood(self, prompt, continuation):
        # choose() calls this once per option, correct option first
        idx = self.calls // 2
        self.calls += 1
        correct = self.schedule[min(idx, len(self.schedule) - 1)]
        is_first = self.calls % 2 == 1
        return 0.0 if (is_first == bool(correct)) else -1.0


def sober_detail(n):
    return {"per_item": [1.0] * n, "cum_tokens": list(range(0, n * 10, 10))}


# ── the probe ────────────────────────────────────────────────────────────────

def test_probe_reports_every_item_separately():
    n = len(ITEMS)
    p = TemporalProbe(repeats=1)
    r = p.run(ScriptedSubject([1] * n))
    assert len(r.detail["per_item"]) == n
    assert len(r.detail["cum_tokens"]) == n
    assert r.score == pytest.approx(1.0)


def test_clock_positions_are_monotonic_and_start_at_zero():
    r = TemporalProbe(repeats=1).run(ScriptedSubject([1] * len(ITEMS)))
    ct = r.detail["cum_tokens"]
    assert ct[0] == 0, "the first item is scored at clock position zero"
    assert all(b > a for a, b in zip(ct, ct[1:])), "the clock must advance"


def test_probe_does_not_claim_dose_alignment():
    """Invariant 0.2: the probe cannot see the dose, and must say so."""
    r = TemporalProbe(repeats=1).run(ScriptedSubject([1] * len(ITEMS)))
    assert r.detail["dose_aligned"] is False


def test_items_are_independent_so_position_is_not_context_length():
    """Each item is its own prompt; nothing accumulates."""
    prompts = [p for p, _, _ in ITEMS]
    assert len(set(prompts)) == len(prompts), "items must be distinct"
    assert all(len(p) < 120 for p in prompts), "items must stay short and self-contained"


# ── trajectory construction ──────────────────────────────────────────────────

def test_retained_is_normalised_per_item_against_sober():
    """Item difficulty must not masquerade as onset."""
    n = 10
    imp = {"per_item": [1, 1, 0, 0, 0, 1, 1, 1, 1, 1], "cum_tokens": list(range(n))}
    sob = {"per_item": [1, 1, 0, 1, 1, 1, 1, 1, 1, 1], "cum_tokens": list(range(n))}
    t = build_trajectory(label="X", impaired_detail=imp, sober_detail=sob, smoothing=1)
    # item 2 failed in BOTH -> that is item difficulty, not drug effect
    assert t.retained[2] == 1.0
    assert t.retained[3] == 0.0 and t.retained[4] == 0.0


def test_trajectory_requires_scores():
    with pytest.raises(ValueError, match="no per-item"):
        build_trajectory(label="X", impaired_detail={"per_item": []},
                         sober_detail={"per_item": []})


def test_dose_curve_follows_the_envelope():
    n = 40
    imp = {"per_item": [1] * n, "cum_tokens": list(range(0, n * 4, 4))}
    t = build_trajectory(label="CRACK", impaired_detail=imp, sober_detail=sober_detail(n),
                         envelope=get_envelope("crack"), peak_dose=1.0)
    assert max(t.dose) > 0.9, "the bolus must reach its peak"
    assert t.dose[-1] < 0.2, "and must have cleared by the end"
    assert t.envelope_name == "bolus"


def test_constant_envelope_produces_a_flat_dose_curve():
    n = 20
    imp = {"per_item": [1] * n, "cum_tokens": list(range(n))}
    t = build_trajectory(label="C", impaired_detail=imp, sober_detail=sober_detail(n),
                         envelope=Constant(), peak_dose=0.6)
    assert all(d == pytest.approx(0.6) for d in t.dose)
    assert not t.dose_falls, "a flat envelope has nothing to recover from"


# ── kinetic statistics ───────────────────────────────────────────────────────

def make(label, retained, dose, smoothing=3):
    return FacultyTrajectory(label=label, retained=list(retained), dose=list(dose),
                             cum_tokens=list(range(len(retained))), smoothing=smoothing)


def test_early_peak_and_recovery_read_as_a_brief_bolus():
    """The crack shape: hits fast, then comes back within the run."""
    retained = [1, .6, .2, .2, .4, .7, .95, 1, 1, 1, 1, 1]
    dose =     [1, 1, 1, .8, .5, .3, .1, 0, 0, 0, 0, 0]
    t = make("CRACK", retained, dose)
    assert t.peak_index < len(retained) // 2
    assert t.dose_falls
    assert t.recovery > 0.6, "performance returned, so recovery must be high"


def test_sustained_dose_shows_no_recovery():
    """The meth shape: arrives and stays."""
    retained = [1, .9, .6, .4, .3, .3, .3, .3, .3, .3, .3, .3]
    dose =     [1] * 12
    t = make("METH", retained, dose)
    assert not t.dose_falls
    assert t.recovery < 0.2


def test_recovery_is_nan_when_nothing_was_impaired():
    t = make("SOBER", [1] * 10, [0] * 10)
    assert math.isnan(t.recovery)


def test_dose_alignment_detects_an_envelope_that_is_not_driving_anything():
    """If impairment ignores the dose, every downstream statistic is noise."""
    aligned = make("A", [1, .7, .4, .4, .7, 1, 1, 1], [0, .5, 1, 1, .5, 0, 0, 0])
    assert aligned.dose_alignment > 0.7
    flat = make("B", [1, .5, 1, .5, 1, .5, 1, .5], [0, .5, 1, 1, .5, 0, 0, 0])
    assert flat.dose_alignment < 0.5


def test_compare_kinetics_separates_a_brief_bolus_from_a_sustained_one():
    brief = make("CRACK", [1, .5, .2, .4, .8, 1, 1, 1, 1, 1, 1, 1],
                 [1, 1, .8, .4, .1, 0, 0, 0, 0, 0, 0, 0])
    sustained = make("METH", [1, 1, 1, .9, .8, .7, .6, .5, .45, .4, .4, .4],
                     [.2, .4, .6, .8, 1, 1, 1, 1, 1, 1, 1, 1])
    cmp = compare_kinetics(brief, sustained)
    assert cmp.separable, cmp.report()
    assert "peak" in cmp.reason or "recovery" in cmp.reason


def test_compare_kinetics_refuses_identical_shapes():
    a = make("A", [1, .8, .5, .5, .5, .5, .5, .5], [1] * 8)
    b = make("B", [1, .8, .5, .5, .5, .5, .5, .5], [1] * 8)
    cmp = compare_kinetics(a, b)
    assert not cmp.separable
    assert "same shape in time" in cmp.reason


def test_compare_kinetics_warns_when_separation_is_really_magnitude():
    """A strength difference must not be reported as a time-course result."""
    weak = make("WEAK", [1, .98, .96, .95, .95, .95, .95, .95], [1] * 8)
    strong = make("STRONG", [1, .5, .2, .1, .1, .1, .1, .1], [1] * 8)
    cmp = compare_kinetics(weak, strong)
    assert any("magnitude in disguise" in w for w in cmp.warnings), cmp.warnings


def test_compare_kinetics_warns_when_the_envelope_is_not_driving():
    noisy = make("NOISY", [1, .4, 1, .4, 1, .4, 1, .4], [0, .3, .6, 1, 1, .6, .3, 0])
    other = make("OTHER", [1, .9, .8, .7, .6, .5, .4, .3], [0, .3, .6, 1, 1, .6, .3, 0])
    cmp = compare_kinetics(noisy, other)
    assert any("may not be driving" in w for w in cmp.warnings), cmp.warnings


def test_summary_is_json_safe():
    import json
    t = make("X", [1, .6, .3, .5, .9, 1], [1, 1, .6, .3, 0, 0])
    json.dumps(t.summary())


def test_a_flat_trajectory_cannot_support_a_kinetic_claim():
    """Regression: the first toy demo reported CRACK and COCAINE 'separable' by 21
    items while CRACK's peak impairment was 0.000. peak_index on a constant curve is
    argmin of a constant — index 0 — so the comparison was arithmetic on noise."""
    moved = make("COCAINE", [1, .9, .7, .5, .4, .4, .4, .4], [1] * 8)
    flat = make("CRACK", [1, 1, 1, 1, 1, 1, 1, 1], [1, 1, .5, 0, 0, 0, 0, 0])
    cmp = compare_kinetics(moved, flat)
    assert not cmp.separable
    assert "no measurable impairment in CRACK" in cmp.reason
    assert cmp.warnings


def test_undefined_alignment_is_warned_not_silently_dropped():
    a = make("A", [1, .8, .5, .5, .6, .8], [0.5] * 6)     # constant dose -> nan corr
    b = make("B", [1, .9, .8, .3, .2, .2], [0.5] * 6)
    cmp = compare_kinetics(a, b)
    assert any("undefined" in w for w in cmp.warnings), cmp.warnings
