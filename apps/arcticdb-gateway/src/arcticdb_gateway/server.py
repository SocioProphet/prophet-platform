"""arcticdb-gateway service — versioned DataFrame artifacts over embedded ArcticDB (LMDB).

PHT-5 "ArcticDB gateway (dataset/version artifacts)" from the tritfabric spec
(fabric/docs/pht.md PHT-5; fabric/docs/atoms-catalog.md section 3.3): a gateway Deployment
wrapping the embedded library, so model training/backtesting artifacts get durable,
versioned, time-travelable storage behind a plain HTTP contract.

  GET  /healthz                                     liveness/readiness (opens LMDB on first call)
  POST /v1/write                                    { library, symbol, data, index?, metadata?, prune_previous? }
  GET  /v1/read?library=&symbol=&as_of=             latest, or time-travel to an integer version
  GET  /v1/versions?library=&symbol=                version catalog (newest first per symbol)

Storage: embedded ArcticDB over LMDB at ARCTIC_URI (default lmdb:///data/arcticdb — the PVC
mount in deploy/values/arcticdb-gateway.yaml). LMDB is single-writer: one replica, Recreate.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .store import BadRequest, GatewayStore, SymbolNotFound

DEFAULT_URI = "lmdb:///data/arcticdb?map_size=8GB"


class WriteRequest(BaseModel):
    library: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    # Columns-oriented payload: { "price": [1.0, 2.0], "qty": [10, 20] }
    data: dict[str, list[Any]]
    # Optional row index; ISO-8601 strings become a DatetimeIndex (the time-series canonical form).
    index: list[Any] | None = None
    metadata: dict[str, Any] | None = None
    prune_previous: bool = False


def create_app(uri: str | None = None) -> FastAPI:
    store = GatewayStore(uri or os.getenv("ARCTIC_URI", DEFAULT_URI))
    app = FastAPI(title="arcticdb-gateway", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        try:
            info = store.ping()
        except Exception as e:  # noqa: BLE001 — a broken store must fail the probe, not hide
            raise HTTPException(status_code=503, detail=f"arcticdb backend unavailable: {e}") from e
        return {"ok": True, "service": "arcticdb-gateway", "backend": store.uri.split("?")[0], **info}

    @app.post("/v1/write")
    def write(req: WriteRequest) -> dict[str, Any]:
        try:
            return store.write(
                req.library, req.symbol, req.data, req.index, req.metadata, req.prune_previous
            )
        except BadRequest as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/v1/read")
    def read(
        library: str = Query(min_length=1),
        symbol: str = Query(min_length=1),
        as_of: int | None = Query(default=None, description="integer version for time-travel"),
    ) -> dict[str, Any]:
        try:
            return store.read(library, symbol, as_of)
        except SymbolNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/v1/versions")
    def versions(
        library: str = Query(min_length=1),
        symbol: str | None = Query(default=None),
    ) -> dict[str, Any]:
        try:
            return {"library": library, "versions": store.versions(library, symbol)}
        except SymbolNotFound as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    return app


app = create_app()
