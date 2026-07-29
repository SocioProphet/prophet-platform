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
    # ── standards-based attestation (derived; NOT part of the id-hash) ──
    statement: dict[str, Any] | None = None     # in-toto Statement v1
    signature: str | None = None                # base64 Ed25519 sig over canonical statement bytes
    public_key: str | None = None               # base64 raw Ed25519 public key (None → unsigned)
    # ── exhaust accounting (W6.1; observability, NOT part of the id-hash — receipts
    #    persisted before these fields existed must keep verifying) ──
    bytes_in: int | None = None                 # canonical-serialized size of the inputs
    bytes_out: int | None = None                # canonical-serialized size of the outputs
    exhaust_sha: str | None = None              # sha of the ExhaustRecord (sourceos-spec), when emitted


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
    grant_id: str | None = None                 # zero-trust capability grant (kernel-issued)
    actor: str = "user"
    session: str | None = None                  # session/kernel id for stateful kinds
    no_cache: bool = False                       # bypass the content-addressed compute memo


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
    # ── zero-trust conformance (OUR kernel: SocioProphet/mcp-a2a-zero-trust) ──
    grant_check: dict[str, Any] | None = None   # conforming ToolGrantCheck emitted before dispatch
    attestation: dict[str, Any] | None = None   # conforming AttestationBundle over the signed receipt
    memoized: bool = False                       # served from the compute memo cache
    artifacts: list[str] = []                    # content-addressed digests of each output blob
