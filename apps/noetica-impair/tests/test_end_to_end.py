"""End-to-end: driver -> battery -> sweep -> provenance, on the local plane.

This proves PLUMBING, not science. The toy fixtures are randomly initialised, so the
faculty numbers here are noise and must never be read as a result. What it does prove
is that the sober control is paired correctly, the dose ladder is walked, and every
run lands in an append-only log with a verifying receipt chain.
"""

from __future__ import annotations

import pytest

from noetica_impair.drivers.mechanical import MechanicalDriver
from noetica_impair.drivers.topical import TopicalDriver
from noetica_impair.experiments.run_matrix import build_dissociation, run_sweep
from noetica_impair.models import loaders
from noetica_impair.probes.battery import Battery
from noetica_impair.probes.consistency import ConsistencyProbe
from noetica_impair.probes.fluency_competence import FluencyCompetenceProbe
from noetica_impair.probes.hedging import HedgingProbe
from noetica_impair.probes.lookahead import LookaheadProbe
from noetica_impair.probes.working_memory import WorkingMemoryProbe
from noetica_impair.provenance.log import RunLog, verify_chain
from noetica_impair.substances import presets as P


def fast_battery() -> Battery:
    return Battery(
        probes=[ConsistencyProbe(), HedgingProbe(), LookaheadProbe(),
                WorkingMemoryProbe(distances=(4, 16, 48), n_items=2),
                FluencyCompetenceProbe()],
        version="battery/test-fast",
    )


@pytest.fixture(scope="module")
def sweeps(tmp_path_factory):
    out = tmp_path_factory.mktemp("e2e")
    log = RunLog(out / "runs.jsonl")
    lm = loaders.load("toy-dense", seed=5, device="cpu")
    results = {}
    for name in ("ALCOHOL", "COCAINE", "CANNABIS"):
        drv = MechanicalDriver(lm, P.get(name), seed=5, strict_limbs=False)
        try:
            results[name] = run_sweep(
                lm, drv, doses=(0.0, 0.6), label=name, log=log, seed=5,
                battery=fast_battery(), substance=name,
                skipped=drv.compiled.skipped,
                interventions=[i.describe() for i in drv.compiled.interventions],
            )
        finally:
            drv.close()
    return results, log


def test_sweep_produces_paired_sober_control(sweeps):
    results, _ = sweeps
    sw = results["ALCOHOL"]
    sober = sw.dose_response.points[0.0]
    # dose=0 is normalised against itself, so every faculty retains exactly 1.0.
    assert all(v == pytest.approx(1.0) for v in sober.scalars())
    assert sw.records[0].sober_ref_run_id is None
    assert sw.records[1].sober_ref_run_id == sw.records[0].run_id


def test_every_run_is_receipted_and_chained(sweeps):
    _, log = sweeps
    records = log.read_all()
    assert len(records) == 6            # 3 substances x 2 doses
    ok, msg = verify_chain(records)
    assert ok, msg


def test_provenance_records_skipped_ops(sweeps):
    """A dense toy model cannot run the SAE limbs; the log must say so."""
    _, log = sweeps
    rec = log.read_all()[0]
    assert any("sae_steer" in s for s in rec["skipped_ops"])
    assert rec["weights_ref"] == "__toy_llama__"


def test_dissociation_matrix_builds_from_sweeps(sweeps):
    results, _ = sweeps
    m = build_dissociation(results, dose=0.6)
    assert set(m.rows) == {"ALCOHOL", "COCAINE", "CANNABIS"}
    verdict = m.check()
    # No assertion on distinctness: on random weights the faculty scores are noise.
    # Real M3 acceptance runs on real weights, on an accelerator plane.
    assert isinstance(verdict.report(), str)


def test_topical_driver_shares_the_battery(sweeps):
    """Invariant 0.2: the identical battery measures a prompt-level stimulus."""
    _, log = sweeps
    lm = loaders.load("toy-dense", seed=5, device="cpu")
    drv = TopicalDriver(lm, "gematria")
    try:
        sw = run_sweep(lm, drv, doses=(0.0, 0.6), label="gematria", log=log, seed=5,
                       battery=fast_battery(), driver_kind="topical", stimulus="gematria")
    finally:
        drv.close()
    assert sw.records[-1].driver == "topical"
    assert sw.records[-1].topical_stimulus_id == "gematria"
    ok, _ = verify_chain(log.read_all())
    assert ok


def test_topical_driver_touches_no_weights():
    lm = loaders.load("toy-dense", seed=5, device="cpu")
    before = {k: v.clone() for k, v in lm.model.state_dict().items()}
    drv = TopicalDriver(lm, "messianic_frame")
    drv.subject(0.8)
    after = lm.model.state_dict()
    assert all((before[k] == after[k]).all() for k in before)
