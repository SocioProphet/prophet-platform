from __future__ import annotations

from fastapi import FastAPI

from .config import load_config

app = FastAPI(title="Prophet Platform Node Commander Runtime", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "node-commander"}


@app.get("/readyz")
def readyz() -> dict:
    cfg = load_config()
    return {
        "status": "ready",
        "service": "node-commander",
        "config_loaded": cfg.get("config_loaded", False),
    }


@app.get("/v1/node-commander/status")
def status() -> dict:
    cfg = load_config()
    return {
        "service": "node-commander",
        "mode": cfg.get("mode", "bootstrap"),
        "control_node_profile_ref": cfg.get("control_node_profile_ref"),
        "node_commander_runtime_ref": cfg.get("node_commander_runtime_ref"),
        "promotion_gate_ref": cfg.get("promotion_gate_ref"),
        "evidence_dir": cfg.get("evidence_dir"),
        "image_ref": cfg.get("image_ref"),
        "config_path": cfg.get("config_path"),
        "config_loaded": cfg.get("config_loaded", False),
    }


@app.get("/v1/node-commander/heartbeat")
def heartbeat() -> dict:
    cfg = load_config()
    return {
        "service": "node-commander",
        "heartbeat": "ok",
        "mode": cfg.get("mode", "bootstrap"),
        "config_loaded": cfg.get("config_loaded", False),
    }
