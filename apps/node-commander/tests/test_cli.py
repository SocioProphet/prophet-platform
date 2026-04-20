from __future__ import annotations

import json
from pathlib import Path

from app import cli


def test_print_config_reads_env(tmp_path: Path, monkeypatch, capsys) -> None:
    cfg = {
        "mode": "bootstrap",
        "control_node_profile_ref": "urn:srcos:control-node:test"
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("NODE_COMMANDER_CONFIG", str(cfg_path))

    rc = cli.main(["print-config"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"control_node_profile_ref": "urn:srcos:control-node:test"' in out
