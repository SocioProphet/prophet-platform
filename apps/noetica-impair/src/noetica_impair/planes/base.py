"""Execution planes: where a run actually computes.

The rig is one thing; the machine it runs on is another. A plane takes a ``RunJob``
(a fully-specified experiment: model, substance, dose sweep, seed, battery version,
where provenance lands) and makes it happen -- in this process, on a GKE GPU Job, or
on a self-deleting GCP VM.

Why planes exist at all: the dev box cannot hold a 9B model, but the rig's
CORRECTNESS is a property of the hooks, not the weights, and that is provable on CPU
with toy configs. So invariants are tested locally and only the expensive part -- real
weights, real batteries -- is shipped out. A plane never changes what a run means;
``plane`` is recorded in provenance precisely so that claim stays falsifiable.

Every plane renders its own submission artifact and can do so WITHOUT executing it
(``plan()``), because a GPU sweep is expensive and the manifest should be reviewable
before it costs anything.
"""

from __future__ import annotations

import abc
import json
from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_DOSES = (0.0, 0.2, 0.4, 0.6, 0.8)


@dataclass
class RunJob:
    """A fully-specified experiment. Serialisable, because remote planes ship it."""

    model_key: str
    substance: str | None = None
    topical_stimulus: str | None = None
    doses: tuple[float, ...] = DEFAULT_DOSES
    seed: int = 0
    battery_version: str = "battery/v1"
    feature_artifact: str | None = None
    project: str = "noetica-impair"
    weights_uri: str | None = None      # gs:// or local path
    out_uri: str = "gs://noetica-brains/impair"
    retain_raw: bool = False
    strict_limbs: bool = True
    device: str | None = None
    quantization: str | None = None
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            tag = self.substance or self.topical_stimulus or "sober"
            self.name = f"impair-{self.model_key}-{tag}-s{self.seed}".lower().replace("_", "-")
        if bool(self.substance) == bool(self.topical_stimulus):
            raise ValueError(
                "a RunJob drives exactly one driver: set substance OR topical_stimulus"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_env(self) -> dict[str, str]:
        """Flatten to env vars -- how remote planes hand the job to the container."""
        return {
            "IMPAIR_MODEL": self.model_key,
            "IMPAIR_SUBSTANCE": self.substance or "",
            "IMPAIR_STIMULUS": self.topical_stimulus or "",
            "IMPAIR_DOSES": ",".join(str(d) for d in self.doses),
            "IMPAIR_SEED": str(self.seed),
            "IMPAIR_BATTERY": self.battery_version,
            "IMPAIR_FEATURES": self.feature_artifact or "",
            "IMPAIR_PROJECT": self.project,
            "IMPAIR_WEIGHTS": self.weights_uri or "",
            "IMPAIR_OUT": self.out_uri,
            "IMPAIR_RETAIN_RAW": "1" if self.retain_raw else "0",
            "IMPAIR_QUANT": self.quantization or "",
            "IMPAIR_STRICT_LIMBS": "1" if self.strict_limbs else "0",
        }


@dataclass
class PlaneHandle:
    plane: str
    job_name: str
    submitted: bool
    artifact: str = ""          # the rendered manifest / command
    out_uri: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        state = "submitted" if self.submitted else "planned (not submitted)"
        return f"[{self.plane}] {self.job_name}: {state} -> {self.out_uri}"


class ExecutionPlane(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def plan(self, job: RunJob) -> PlaneHandle:
        """Render the submission artifact without executing anything."""

    @abc.abstractmethod
    def submit(self, job: RunJob) -> PlaneHandle:
        """Actually run it."""

    def describe(self) -> dict[str, Any]:
        return {"plane": self.name}


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)
