from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.runtime_main as runtime_main

client = TestClient(runtime_main.app)


def test_runtime_readyz_exposes_config_state(monkeypatch, tmp_path: Path) -> None:
    cfg = {
        "mode": "bootstrap",
        "control_node_profile_ref": "urn:srcos:control-node:test",
        "node_commander_runtime_ref": "urn:srcos:node-commander:test",
        "promotion_gate_ref": "urn:srcos:image-gate:test",
        "evidence_dir": "/tmp/evidence",
        "image_ref": "example/image:test",
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("NODE_COMMANDER_CONFIG", str(cfg_path))

    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["config_loaded"] is True


def test_runtime_status_reflects_loaded_config(monkeypatch, tmp_path: Path) -> None:
    cfg = {
        "mode": "bootstrap",
        "control_node_profile_ref": "urn:srcos:control-node:test",
        "node_commander_runtime_ref": "urn:srcos:node-commander:test",
        "promotion_gate_ref": "urn:srcos:image-gate:test",
        "evidence_dir": "/tmp/evidence",
        "image_ref": "example/image:test",
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("NODE_COMMANDER_CONFIG", str(cfg_path))

    resp = client.get("/v1/node-commander/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["config_loaded"] is True
    assert body["control_node_profile_ref"] == "urn:srcos:control-node:test"
    assert body["image_ref"] == "example/image:test"
