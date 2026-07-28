"""Invariant 0.4 / milestone M3: substances must be pairwise distinguishable.

The metric is deliberately the SHAPE distance (cosine on mean-centered rows), not raw
cosine on retained fractions. The tests below pin that choice by asserting the failure
mode the work order names: four substances that collapse everything uniformly, merely
to different depths, must FAIL, because that is one lesion with four labels.
"""

from __future__ import annotations

import pytest

from noetica_impair.readout.metrics import (
    DissociationMatrix, FacultyVector, center, cosine_distance, l2,
)


def fv(consistency=1.0, calibration=1.0, lookahead=1.0, working_memory=1.0,
       fluency=1.0, competence=1.0):
    return FacultyVector(consistency=consistency, calibration=calibration,
                         lookahead=lookahead, working_memory=working_memory,
                         fluency=fluency, competence=competence)


def test_uniform_collapse_is_flagged_not_celebrated():
    """Four 'substances' that damage everything equally are ONE lesion."""
    m = DissociationMatrix(dose=0.6)
    for i, name in enumerate(("A", "B", "C", "D")):
        v = 0.9 - i * 0.2                      # different severity, identical shape
        m.add(name, fv(v, v, v, v, v, v))
    verdict = m.check(threshold=0.15)
    assert not verdict.distinct, "uniform collapse must fail the dissociation test"
    assert len(verdict.failing) == 6          # all pairs
    assert "one lesion" in verdict.report()


def test_distinct_profiles_pass():
    """Each substance hits a different faculty first."""
    m = DissociationMatrix(dose=0.6)
    m.add("ALCOHOL",  fv(consistency=0.4, working_memory=0.3, calibration=0.4))
    m.add("HEROIN",   fv(competence=0.5, lookahead=0.9, calibration=0.95, fluency=0.6))
    m.add("COCAINE",  fv(lookahead=0.2, calibration=0.35, consistency=0.9))
    m.add("CANNABIS", fv(working_memory=0.5, consistency=0.85, competence=0.55))
    verdict = m.check(threshold=0.15)
    assert verdict.distinct, verdict.report()


def test_severity_is_not_evidence_of_dissociation():
    """Severity differs wildly, shape does not -> still fails."""
    m = DissociationMatrix(dose=0.6)
    m.add("X", fv(0.95, 0.95, 0.95, 0.95, 0.95, 0.95))
    m.add("Y", fv(0.10, 0.10, 0.10, 0.10, 0.10, 0.10))
    verdict = m.check()
    assert m.severity("Y") > m.severity("X")
    assert not verdict.distinct


def test_center_removes_severity():
    a = center([0.9, 0.9, 0.5, 0.9, 0.9, 0.9])
    b = center([0.5, 0.5, 0.1, 0.5, 0.5, 0.5])   # same shape, worse overall
    assert cosine_distance(a, b) < 1e-9


def test_fluency_competence_gap_direction():
    intoxicant = fv(fluency=0.95, competence=0.45)
    coarse_lesion = fv(fluency=0.45, competence=0.45)
    assert intoxicant.fluency_competence_gap > 0.4
    assert coarse_lesion.fluency_competence_gap == pytest.approx(0.0)


def test_retained_against_sober_normalises():
    sober = fv(consistency=0.8, competence=0.5)
    impaired = fv(consistency=0.4, competence=0.5)
    r = impaired.retained_against(sober)
    assert r.consistency == pytest.approx(0.5)
    assert r.competence == pytest.approx(1.0)


def test_equivalence_reports_margin_and_no_match():
    from noetica_impair.readout.equivalence import match

    catalogue = [
        ("ALCOHOL", 0.4, fv(consistency=0.5, competence=0.5)),
        ("COCAINE", 0.6, fv(lookahead=0.2)),
    ]
    close = match("gematria", fv(consistency=0.52, competence=0.48), catalogue)
    assert close.matched and close.substance == "ALCOHOL"
    assert "reads as ALCOHOL@0.4-equivalent" in close.report()

    far = match("gematria", fv(0.01, 0.01, 0.01, 0.01, 0.01, 0.01), catalogue,
                max_distance=0.1)
    assert not far.matched
    assert "NO mechanical equivalent" in far.report()
