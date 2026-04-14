from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.adapter as adapter  # type: ignore


def _seed_upstream(tmp_path: Path) -> str:
    base = tmp_path / "prophet-platform"
    payload_dir = base / "payloads" / "crystal-atlas-extract-enrich"
    payload_dir.mkdir(parents=True, exist_ok=True)
    corr = "upstream-001"
    payload = {
        "emitted_at": "2026-04-14T00:00:00+00:00",
        "left_contract_id": "left-001",
        "right_contract_id": "right-001",
        "left_clauses": [
            {"title": "Termination", "text": "Either party may terminate for cause."},
            {"title": "Audit Rights", "text": "Customer may audit annually."}
        ],
        "right_clauses": [
            {"title": "Termination", "text": "Either party may terminate for convenience."},
            {"title": "Confidentiality", "text": "Both parties will protect confidential information."}
        ]
    }
    (payload_dir / f"{corr}.payload.json").write_text(json.dumps(payload), encoding="utf-8")
    return corr


def test_replay_upstream_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path))
    corr = _seed_upstream(tmp_path)
    out_corr = adapter.replay_upstream_bundle(corr, tenant_id="demo")
    assert out_corr is not None

    out = tmp_path / "prophet-platform" / "payloads" / "crystal-atlas-contract-intel" / f"{out_corr}.payload.json"
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tenant_id"] == "demo"
    assert payload["left_contract_id"] == "left-001"
    assert payload["right_contract_id"] == "right-001"
    assert "termination" in payload["shared_families"]
    assert "audit" in payload["left_only_families"]
    assert "confidentiality" in payload["right_only_families"]
    assert "termination" in payload["changed_families"]
