"""The experiment grid driver, and the container entrypoint for remote planes.

One sweep = one model, one driver, the dose ladder. The dose=0 point is run FIRST and
every later point is normalised against it (invariant 0.3): the sober control is the
same rig on the same seed, not a fresh process.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..drivers.base import Driver
from ..drivers.mechanical import MechanicalDriver
from ..drivers.topical import TopicalDriver
from ..models import loaders
from ..probes.battery import Battery
from ..provenance.log import RunLog, RunRecord, new_run_id
from ..readout.metrics import DissociationMatrix, DoseResponse, FacultyVector
from ..substances import presets as P


@dataclass
class SweepResult:
    model_key: str
    label: str
    sober: FacultyVector
    dose_response: DoseResponse
    records: list[RunRecord]

    def at(self, dose: float) -> FacultyVector:
        return self.dose_response.points[dose]


def run_sweep(
    lm: Any,
    driver: Driver,
    *,
    doses: tuple[float, ...],
    label: str,
    log: RunLog,
    seed: int = 0,
    battery: Battery | None = None,
    plane: str = "local",
    driver_kind: str = "mechanical",
    substance: str | None = None,
    stimulus: str | None = None,
    feature_artifact: str | None = None,
    skipped: list[str] | None = None,
    interventions: list[dict] | None = None,
) -> SweepResult:
    battery = battery or Battery()
    if doses[0] != 0.0:
        doses = (0.0, *doses)

    sober_fv: FacultyVector | None = None
    sober_run_id: str | None = None
    dr = DoseResponse(substance=label, model_key=lm.meta.key)
    records: list[RunRecord] = []

    for dose in doses:
        subject = driver.subject(dose)
        raw_fv, results = battery.run(subject)

        if sober_fv is None:
            sober_fv = raw_fv
            retained = raw_fv.retained_against(raw_fv)   # all 1.0 by construction
        else:
            retained = raw_fv.retained_against(sober_fv)

        dr.add(dose, retained)
        rec = RunRecord(
            run_id=new_run_id(), ts=time.time(), model_key=lm.meta.key, arch=lm.meta.arch,
            driver=driver_kind, dose=dose, seed=seed,
            substance_preset=substance, topical_stimulus_id=stimulus,
            feature_artifact_version=feature_artifact,
            faculty_vector=retained.as_dict(),
            sober_ref_run_id=sober_run_id,
            interventions=interventions or [],
            skipped_ops=skipped or [],
            weights_ref=lm.weights_ref, plane=plane,
            output_hashes=[f"{k}:{r.score:.6f}" for k, r in sorted(results.items())],
        )
        log.append(rec)
        records.append(rec)
        if sober_run_id is None:
            sober_run_id = rec.run_id

    assert sober_fv is not None
    return SweepResult(lm.meta.key, label, sober_fv, dr, records)


def run_substance(
    model_key: str, substance: str, *, doses, log: RunLog, seed: int = 0,
    features=None, plane: str = "local", strict_limbs: bool = True, **load_kw: Any,
) -> SweepResult:
    lm = loaders.load(model_key, seed=seed, **load_kw)
    driver = MechanicalDriver(lm, P.get(substance), seed=seed, features=features,
                              strict_limbs=strict_limbs)
    try:
        return run_sweep(
            lm, driver, doses=doses, label=substance, log=log, seed=seed, plane=plane,
            driver_kind="mechanical", substance=substance,
            skipped=driver.compiled.skipped + [
                f"LOST LIMB: {l}" for l in driver.compiled.lost_limbs],
            interventions=[iv.describe() for iv in driver.compiled.interventions],
            feature_artifact=getattr(features, "version", None),
        )
    finally:
        driver.close()


def run_topical(
    model_key: str, stimulus: str, *, doses, log: RunLog, seed: int = 0,
    plane: str = "local", **load_kw: Any,
) -> SweepResult:
    lm = loaders.load(model_key, seed=seed, **load_kw)
    driver = TopicalDriver(lm, stimulus)
    try:
        return run_sweep(
            lm, driver, doses=doses, label=stimulus, log=log, seed=seed, plane=plane,
            driver_kind="topical", stimulus=stimulus,
        )
    finally:
        driver.close()


@dataclass
class TemporalResult:
    label: str
    trajectory: Any
    records: list[RunRecord]


def run_temporal(
    lm: Any, driver: Any, *, peak_dose: float, log: RunLog, label: str,
    seed: int = 0, repeats: int = 2, envelope: Any = None, plane: str = "local",
    substance: str | None = None, smoothing: int = 5,
) -> TemporalResult:
    """Measure the faculty trajectory WITHIN a run, under a moving dose.

    The sober control is the same rig at dose 0 on the same seed (invariant 0.3), run
    through the identical item sequence, so per-item difficulty cancels. The envelope
    stays installed for the control -- at dose 0 it is inert, and swapping the rig
    between the two runs would reintroduce exactly the confound the pairing removes.
    """
    from ..probes.temporal import TemporalProbe
    from ..readout.trajectory import build_trajectory

    probe = TemporalProbe(repeats=repeats)
    rig = getattr(driver, "rig", None)
    if envelope is not None and rig is not None:
        rig.set_envelope(envelope)

    details: dict[float, dict] = {}
    records: list[RunRecord] = []
    sober_run_id: str | None = None

    for dose in (0.0, peak_dose):
        subject = driver.subject(dose)          # resets the clock to 0
        result = probe.run(subject)
        details[dose] = result.detail
        rec = RunRecord(
            run_id=new_run_id(), ts=time.time(), model_key=lm.meta.key, arch=lm.meta.arch,
            driver=getattr(driver, "name", "mechanical"), dose=dose, seed=seed,
            substance_preset=substance,
            faculty_vector={"temporal_mean": result.score},
            sober_ref_run_id=sober_run_id,
            interventions=[iv.describe() for iv in getattr(rig, "interventions", [])],
            weights_ref=lm.weights_ref, plane=plane,
            output_hashes=[f"temporal:{result.score:.6f}"],
        )
        log.append(rec)
        records.append(rec)
        if sober_run_id is None:
            sober_run_id = rec.run_id

    traj = build_trajectory(
        label=label, impaired_detail=details[peak_dose], sober_detail=details[0.0],
        envelope=envelope, peak_dose=peak_dose, smoothing=smoothing,
    )
    return TemporalResult(label=label, trajectory=traj, records=records)


def build_dissociation(
    sweeps: dict[str, SweepResult], *, dose: float = 0.6
) -> DissociationMatrix:
    m = DissociationMatrix(dose=dose)
    for name, sw in sweeps.items():
        if dose not in sw.dose_response.points:
            raise KeyError(f"{name}: no measurement at d={dose}")
        m.add(name, sw.at(dose))
    return m


def main(argv: list[str] | None = None) -> int:
    """Container entrypoint. Configuration arrives as env vars (see planes.base)."""
    model = os.environ.get("IMPAIR_MODEL", "toy-dense")
    substance = os.environ.get("IMPAIR_SUBSTANCE") or None
    stimulus = os.environ.get("IMPAIR_STIMULUS") or None
    doses = tuple(
        float(x) for x in os.environ.get("IMPAIR_DOSES", "0,0.2,0.4,0.6,0.8").split(",") if x
    )
    seed = int(os.environ.get("IMPAIR_SEED", "0"))
    out = Path(os.environ.get("IMPAIR_OUT", "./out"))
    plane = os.environ.get("IMPAIR_PLANE", "local")
    retain_raw = os.environ.get("IMPAIR_RETAIN_RAW", "0") == "1"
    weights = os.environ.get("IMPAIR_WEIGHTS") or None
    quant = os.environ.get("IMPAIR_QUANT") or None
    # Default STRICT: a run refuses to be labelled with a substance whose
    # defining mechanism was skipped. Set 0 to run a knowingly-partial lesion.
    strict = os.environ.get("IMPAIR_STRICT_LIMBS", "1") == "1"

    log = RunLog(out / "runs.jsonl", retain_raw=retain_raw)
    load_kw: dict[str, Any] = {}
    if weights:
        load_kw["local_path"] = weights
    if quant:
        load_kw["quantization"] = quant

    if substance:
        sw = run_substance(model, substance, doses=doses, log=log, seed=seed,
                           plane=plane, strict_limbs=strict, **load_kw)
    elif stimulus:
        sw = run_topical(model, stimulus, doses=doses, log=log, seed=seed,
                         plane=plane, **load_kw)
    else:
        print("set IMPAIR_SUBSTANCE or IMPAIR_STIMULUS", file=sys.stderr)
        return 2

    print(f"{sw.label} on {sw.model_key}: {len(sw.records)} runs -> {log.path}")
    for d in sorted(sw.dose_response.points):
        fv = sw.dose_response.points[d]
        print(f"  d={d:<4g} competence={fv.competence:.3f} fluency={fv.fluency:.3f} "
              f"gap={fv.fluency_competence_gap:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
