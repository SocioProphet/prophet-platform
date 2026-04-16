from __future__ import annotations

from fastapi import FastAPI

from . import service

app = FastAPI(title="Prophet Platform Node Commander", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "node-commander"}


@app.get("/readyz")
def readyz() -> dict:
    return {"status": "ready", "service": "node-commander"}


@app.get("/v1/node-commander/status")
def status() -> dict:
    return service.get_status_view()


@app.get("/v1/node-commander/heartbeat")
def heartbeat() -> dict:
    return service.get_heartbeat_view()
