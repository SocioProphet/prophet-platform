"""Append-only JSONL run log + estate-conformant receipts (work order section 8).

Two things are written, deliberately:

1. A ``RunRecord`` -- the full scientific record (faculty vector, dose-response,
   routing KL, the sober reference it is paired against).
2. A ``Receipt`` shaped EXACTLY like ``compute_gateway.contract.Receipt``, whose id is
   sha256 over the same eleven fields in the same canonical JSON encoding, chained by
   ``prev``. This is not a private log format: it means an impairment run is
   verifiable evidence in the estate's existing chain rather than a parallel one.

Append-only, never rewritten. Raw model output is hashed by default; full text only
behind an explicit per-experiment flag (open fork 10.3 default: hashes).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

BATTERY_VERSION = "battery/v1"
SPEC_VERSION = "noetica-impair/0.1.0"


def sha(obj: Any) -> str:
    """Canonical hash. Must match compute_gateway.receipts.sha byte-for-byte."""
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def hash_text(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class Receipt:
    """Field-for-field mirror of compute_gateway.contract.Receipt.

    ``id`` is the sha of exactly the eleven body fields below -- nothing else may be
    folded in, or the estate's verifier will read a valid receipt as tampered.
    """

    id: str
    project: str
    kind: str
    backend: str
    runtime: str
    inputs_sha: str
    outputs_sha: str
    status: str
    actor: str
    epistemic_status: str
    prev: str | None
    ts: float


def mint_receipt(
    *,
    project: str,
    kind: str,
    backend: str,
    runtime: str,
    inputs: Any,
    outputs: Any,
    status: str,
    actor: str,
    epistemic_status: str,
    prev: str | None,
) -> Receipt:
    body = {
        "project": project, "kind": kind, "backend": backend, "runtime": runtime,
        "inputs_sha": sha(inputs), "outputs_sha": sha(outputs), "status": status,
        "actor": actor, "epistemic_status": epistemic_status, "prev": prev,
        "ts": time.time(),
    }
    return Receipt(id=sha(body), **body)


@dataclass
class RunRecord:
    run_id: str
    ts: float
    model_key: str
    arch: str
    driver: str                       # "mechanical" | "topical"
    dose: float
    seed: int
    battery_version: str = BATTERY_VERSION
    spec_version: str = SPEC_VERSION
    substance_preset: str | None = None
    topical_stimulus_id: str | None = None
    feature_artifact_version: str | None = None
    faculty_vector: dict[str, Any] = field(default_factory=dict)
    routing_kl_per_layer: list[float] | None = None
    sober_ref_run_id: str | None = None
    output_hashes: list[str] = field(default_factory=list)
    raw_outputs: list[str] | None = None      # only when retain_raw is set
    interventions: list[dict[str, Any]] = field(default_factory=list)
    skipped_ops: list[str] = field(default_factory=list)
    weights_ref: str = ""
    plane: str = "local"
    receipt: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:16]}"


class RunLog:
    """Append-only JSONL writer with a receipt chain.

    Opened in ``"a"`` mode and flushed per record: a crashed sweep keeps every run it
    completed. Nothing here ever rewrites or deletes a line.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        project: str = "noetica-impair",
        actor: str = "noetica-impair",
        retain_raw: bool = False,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.project = project
        self.actor = actor
        self.retain_raw = retain_raw
        self._prev: str | None = self._last_receipt_id()

    def _last_receipt_id(self) -> str | None:
        """Resume the chain from an existing log rather than forking it."""
        if not self.path.exists():
            return None
        last = None
        with self.path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                r = rec.get("receipt")
                if r:
                    last = r.get("id")
        return last

    def append(self, record: RunRecord, *, epistemic_status: str = "observed") -> RunRecord:
        inputs = {
            "model_key": record.model_key, "dose": record.dose, "seed": record.seed,
            "driver": record.driver, "substance": record.substance_preset,
            "stimulus": record.topical_stimulus_id, "battery": record.battery_version,
            "features": record.feature_artifact_version, "weights": record.weights_ref,
            "interventions": record.interventions,
        }
        outputs = {
            "faculty_vector": record.faculty_vector,
            "routing_kl_per_layer": record.routing_kl_per_layer,
            "output_hashes": record.output_hashes,
        }
        rcpt = mint_receipt(
            project=self.project, kind="impairment-run", backend=record.plane,
            runtime=SPEC_VERSION, inputs=inputs, outputs=outputs, status="ok",
            actor=self.actor, epistemic_status=epistemic_status, prev=self._prev,
        )
        self._prev = rcpt.id
        record.receipt = asdict(rcpt)
        if not self.retain_raw:
            record.raw_outputs = None
        with self.path.open("a") as fh:
            fh.write(json.dumps(record.to_dict(), sort_keys=True, default=str) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return record

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open() as fh:
            for line in fh:
                if line.strip():
                    out.append(json.loads(line))
        return out


def verify_chain(records: list[dict[str, Any]]) -> tuple[bool, str]:
    """Recompute every receipt id and re-walk ``prev``. Same rules as the gateway."""
    prev: str | None = None
    for i, rec in enumerate(records):
        r = rec.get("receipt")
        if not r:
            return False, f"record {i} has no receipt"
        body = {k: r[k] for k in (
            "project", "kind", "backend", "runtime", "inputs_sha", "outputs_sha",
            "status", "actor", "epistemic_status", "prev", "ts")}
        if sha(body) != r["id"]:
            return False, f"record {i}: receipt id does not match its body (tampered)"
        if r["prev"] != prev:
            return False, f"record {i}: prev {r['prev']} breaks the chain (expected {prev})"
        prev = r["id"]
    return True, f"{len(records)} receipts verified"
