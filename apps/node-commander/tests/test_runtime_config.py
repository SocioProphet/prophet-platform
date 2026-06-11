from __future__ import annotations

import json
from pathlib import Path

from app.config import load_config


def test_load_config_from_env(tmp_path: Path, monkeypatch) -> None:
    cfg = {
        "mode": "bootstrap",
        "control_node_profile_ref": "urn:srcos:control-node:test"
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("NODE_COMMANDER_CONFIG", str(cfg_path))

    loaded = load_config()
    assert loaded["config_loaded"] is True
    assert loaded["control_node_profile_ref"] == "urn:srcos:control-node:test"
