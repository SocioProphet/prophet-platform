"""Local plane: run in this process.

The right plane for invariant work (hooks inert at zero, dose monotonicity,
dissociation geometry) and for toy models. It is deliberately the same code path the
remote planes execute, so "it worked locally" means something.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..provenance.log import RunLog
from .base import ExecutionPlane, PlaneHandle, RunJob


@dataclass
class LocalPlane(ExecutionPlane):
    name: str = "local"
    out_dir: str = "./out"

    def _resolve_out(self, job: RunJob) -> Path:
        # A gs:// out_uri is meaningless in-process; fall back to the local dir and say so.
        if job.out_uri.startswith("gs://"):
            return Path(self.out_dir) / job.name
        return Path(job.out_uri) / job.name

    def plan(self, job: RunJob) -> PlaneHandle:
        out = self._resolve_out(job)
        return PlaneHandle(
            plane=self.name, job_name=job.name, submitted=False,
            artifact=f"in-process run -> {out}/runs.jsonl",
            out_uri=str(out),
            detail={"note": "gs:// targets are written locally on this plane"
                    if job.out_uri.startswith("gs://") else ""},
        )

    def submit(self, job: RunJob) -> PlaneHandle:
        from ..experiments.run_matrix import run_substance, run_topical

        out = self._resolve_out(job)
        log = RunLog(out / "runs.jsonl", project=job.project, retain_raw=job.retain_raw)
        load_kw: dict[str, Any] = {}
        if job.weights_uri and not job.weights_uri.startswith("gs://"):
            load_kw["local_path"] = job.weights_uri
        if job.quantization:
            load_kw["quantization"] = job.quantization
        if job.device:
            load_kw["device"] = job.device

        if job.substance:
            sw = run_substance(job.model_key, job.substance, doses=job.doses, log=log,
                               seed=job.seed, plane=self.name, **load_kw)
        else:
            sw = run_topical(job.model_key, job.topical_stimulus, doses=job.doses, log=log,
                             seed=job.seed, plane=self.name, **load_kw)

        h = self.plan(job)
        h.submitted = True
        h.detail["runs"] = len(sw.records)
        h.detail["label"] = sw.label
        return h
