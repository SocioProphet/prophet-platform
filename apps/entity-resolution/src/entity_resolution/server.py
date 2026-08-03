"""entity-resolution service — the real ER resolver (regis had only a validator).

  GET  /healthz
  POST /extract/mentions     { text, source_id, source_type?, locality?, gazetteer? } → a regis-conformant
                             MentionSet (NER head of the spine: overlapping/multi-labelled spans, FIPS PII hashing)
  POST /resolve              { records[] , as_of? } → entities + golden_records + concordance +
                             proof-carrying decision ledger, all pinned with a deterministic replay_key
  POST /resolve/incremental  { prior_golden[], new_records[], as_of? } → delta: which new records attached
                             to an existing entity vs formed new ones, without re-resolving the estate (O(new))
  POST /resolve/materialize  { records[]?, text?+source_id? , as_of? } → resolve, then WRITE resolved
                             nodes/edges to HellGraph and emit a SHA-256 hash-chained receipt (live spine).
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from .graph_sink import GraphSink, materialize
from .ner import extract_mentions, mentions_to_records
from .resolver import Record, resolve, resolve_incremental

app = FastAPI(title="entity-resolution", version="0.1.0")


def get_sink() -> GraphSink:
    """The live HellGraph + receipt sink. Overridden in tests via
    app.dependency_overrides[get_sink] to inject a mock-transport sink."""
    return GraphSink()


class RecordIn(BaseModel):
    id: str
    name: str
    attributes: dict[str, str] = {}
    scope: str = ""
    primes: list[str] = []


class ResolveRequest(BaseModel):
    records: list[RecordIn]
    as_of: str | None = None


class IncrementalRequest(BaseModel):
    prior_golden: list[dict[str, Any]]   # golden_records values from a prior /resolve
    new_records: list[RecordIn]
    as_of: str | None = None


class ExtractRequest(BaseModel):
    text: str
    source_id: str
    source_type: str = "document"
    locality: str = "CITIZEN_FOG"
    event_ir_id: str | None = None
    gazetteer: dict[str, str] = {}
    scope_realm: str = "FOG"


class MaterializeRequest(BaseModel):
    # Either supply records directly, or supply text+source_id to run extract -> resolve first.
    records: list[RecordIn] = []
    text: str | None = None
    source_id: str | None = None
    source_type: str = "document"
    locality: str = "CITIZEN_FOG"
    gazetteer: dict[str, str] = {}
    as_of: str | None = None


def _rec(r: RecordIn) -> Record:
    return Record(id=r.id, name=r.name, attributes=r.attributes, scope=r.scope, primes=frozenset(r.primes))


def _rec_dict(d: dict[str, Any]) -> Record:
    return Record(id=d["id"], name=d["name"], attributes=d.get("attributes", {}),
                  scope=d.get("scope", ""), primes=frozenset(d.get("primes", [])))


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "entity-resolution"}


@app.post("/extract/mentions")
def extract_endpoint(req: ExtractRequest) -> dict[str, Any]:
    return extract_mentions(
        req.text, source_id=req.source_id, source_type=req.source_type,
        locality=req.locality, event_ir_id=req.event_ir_id,
        gazetteer=req.gazetteer or None, scope_realm=req.scope_realm,
    )


@app.post("/resolve")
def resolve_endpoint(req: ResolveRequest) -> dict[str, Any]:
    return resolve([_rec(r) for r in req.records], as_of=req.as_of)


@app.post("/resolve/incremental")
def resolve_incremental_endpoint(req: IncrementalRequest) -> dict[str, Any]:
    return resolve_incremental(req.prior_golden, [_rec(r) for r in req.new_records], as_of=req.as_of)


@app.post("/resolve/materialize")
def resolve_materialize_endpoint(req: MaterializeRequest,
                                 sink: GraphSink = Depends(get_sink)) -> dict[str, Any]:
    """Live spine: extract (optional) -> resolve -> write to HellGraph -> emit SHA-256 receipt.

    The sink is injected via Depends(get_sink); tests override get_sink to supply a
    mock-transport sink, production builds one from HELLGRAPH_URL/COMPUTE_GATEWAY_URL.
    """
    mention_set: dict[str, Any] | None = None
    if req.text is not None and req.source_id:
        mention_set = extract_mentions(
            req.text, source_id=req.source_id, source_type=req.source_type,
            locality=req.locality, gazetteer=req.gazetteer or None,
        )
        records = [_rec_dict(d) for d in mentions_to_records(mention_set)]
    else:
        records = [_rec(r) for r in req.records]

    resolution = resolve(records, as_of=req.as_of)
    landed = materialize(resolution, mention_set, sink=sink)
    return {
        "resolution": resolution,
        "mention_set": mention_set,
        "graph": landed["graph"],
        "receipt": landed["receipt"],
        "seal": landed["seal"],
    }
