"""The Universal Compute Contract.

One shape for every kind of compute — a notebook cell, a graph query, a Spark
job, a model inference, an agent run. Databricks welded one paradigm (Spark) to
one surface (notebook). This is the generalization: `submit(spec, backend,
entitlement) -> result`, where the result is uniform not just in shape but in
GOVERNANCE — every compute emits the same hash-chained receipt and carries an
epistemic status. Heterogeneous compute, homogeneous evidence.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# The epistemic ladder — the warrant a compute output carries. A graph read is
# `observed`; a model/derived computation is `derived`; a checked result is
# `verified`; only a human/policy promotion reaches `attested`.
EpistemicStatus = Literal[
    "hypothesis", "observed", "derived", "verified", "attested", "simulated", "unknown"
]


class ComputeOutput(BaseModel):
    type: str                                   # stream | result | table | graph | error | degraded
    text: str | None = None
    data: dict[str, Any] | None = None          # rich payload (rows, png, html, nodes…)
    mime: list[str] | None = None


class Receipt(BaseModel):
    """The universal, hash-chained, replayable unit. Identical across all kinds."""
    id: str
    project: str
    kind: str
    backend: str
    runtime: str
    inputs_sha: str
    outputs_sha: str
    status: str
    actor: str
    epistemic_status: EpistemicStatus
    prev: str | None = None
    ts: float


class GraphNode(BaseModel):
    id: str
    labels: list[str] = []
    properties: dict[str, Any] = {}


class GraphEdge(BaseModel):
    label: str
    from_: str = Field(alias="from")
    to: str
    properties: dict[str, Any] = {}
    model_config = {"populate_by_name": True}


class GraphDelta(BaseModel):
    """The provenance subgraph a run produces. Compute + knowledge, one object model."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    written: bool = False                       # did we persist it to the graph?


class ComputeRequest(BaseModel):
    kind: str                                   # notebook | graph-query | graph-stats | spark | …
    spec: dict[str, Any] = {}                   # kind-specific payload (code, query, label…)
    backend: str | None = None                  # explicit backend, else the kind's default
    project: str = "default"
    entitlement: str | None = None              # caller-presented paid entitlement token
    actor: str = "user"
    session: str | None = None                  # session/kernel id for stateful kinds


class ComputeResult(BaseModel):
    status: str                                 # ok | error | degraded | entitlement_required
    kind: str
    backend: str
    epistemic_status: EpistemicStatus
    outputs: list[ComputeOutput] = []
    receipt: Receipt | None = None
    graph_delta: GraphDelta | None = None
    error: str | None = None
    degraded: str | None = None
    entitlement_required: bool = False
    message: str | None = None
