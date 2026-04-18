from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_receipt_for_subject(state_root: str, subject_ref: str) -> Path | None:
    base = Path(state_root)
    if not base.exists():
        return None
    candidates: list[Path] = []
    for path in base.rglob('*.json'):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if payload.get('subject_ref') == subject_ref:
            candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def build_subject_readout(state_root: str, subject_ref: str) -> dict[str, Any] | None:
    receipt_path = find_latest_receipt_for_subject(state_root, subject_ref)
    if receipt_path is None:
        return None
    receipt = _read_json(receipt_path) or {}
    return {
        'subject_ref': subject_ref,
        'receipt_ref': str(receipt_path),
        'action': receipt.get('action'),
        'status': receipt.get('status'),
        'evidence_bundle_ref': receipt.get('evidence_bundle_ref'),
    }
