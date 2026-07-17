"""entity-resolution service — the real ER resolver (regis had only a validator).

  GET  /healthz
  POST /resolve   { records: [{id, name, attributes?}] } → entities (clusters) + proof-carrying
                  decision ledger (MERGE_VERIFIED / REQUIRES_REVIEW / MERGE_BLOCKED with field-level evidence)
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from .resolver import Record, resolve

app = FastAPI(title="entity-resolution", version="0.1.0")


class RecordIn(BaseModel):
    id: str
    name: str
    attributes: dict[str, str] = {}
    scope: str = ""
    primes: list[str] = []


class ResolveRequest(BaseModel):
    records: list[RecordIn]


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "entity-resolution"}


@app.post("/resolve")
def resolve_endpoint(req: ResolveRequest) -> dict[str, Any]:
    recs = [Record(id=r.id, name=r.name, attributes=r.attributes, scope=r.scope, primes=frozenset(r.primes)) for r in req.records]
    return resolve(recs)
