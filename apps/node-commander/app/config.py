from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("/app/config/example.config.json")


def _resolve_config_path() -> Path:
    configured = os.environ.get("NODE_COMMANDER_CONFIG")
    if configured:
        return Path(configured)
    return DEFAULT_CONFIG_PATH


def load_config() -> dict[str, Any]:
    path = _resolve_config_path()
    if not path.exists():
        return {
            "mode": "bootstrap",
            "control_node_profile_ref": None,
            "node_commander_runtime_ref": None,
            "promotion_gate_ref": None,
            "evidence_dir": None,
            "image_ref": None,
            "config_path": str(path),
            "config_loaded": False,
        }

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data = dict(data)
    data["config_path"] = str(path)
    data["config_loaded"] = True
    return data
