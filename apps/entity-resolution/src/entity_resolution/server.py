"""entity-resolution service — the real ER resolver (regis had only a validator).

  GET  /healthz
  POST /resolve              { records[] , as_of? } → entities + golden_records + concordance +
                             proof-carrying decision ledger, all pinned with a deterministic replay_key
  POST /resolve/incremental  { prior_golden[], new_records[], as_of? } → delta: which new records attached
                             to an existing entity vs formed new ones, without re-resolving the estate (O(new))
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from .resolver import Record, resolve, resolve_incremental

app = FastAPI(title="entity-resolution", version="0.1.0")


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


def _rec(r: RecordIn) -> Record:
    return Record(id=r.id, name=r.name, attributes=r.attributes, scope=r.scope, primes=frozenset(r.primes))


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "entity-resolution"}


@app.post("/resolve")
def resolve_endpoint(req: ResolveRequest) -> dict[str, Any]:
    return resolve([_rec(r) for r in req.records], as_of=req.as_of)


@app.post("/resolve/incremental")
def resolve_incremental_endpoint(req: IncrementalRequest) -> dict[str, Any]:
    return resolve_incremental(req.prior_golden, [_rec(r) for r in req.new_records], as_of=req.as_of)
