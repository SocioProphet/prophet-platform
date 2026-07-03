from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SERVICE_DIR = 'deepdive-orchestrator'


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _root() -> Path:
    if v := os.environ.get('SOCIOPROFIT_STATE_HOME'):
        return Path(v) / 'prophet-platform'
    return Path.home() / '.local' / 'state' / 'prophet-platform'


def maybe_emit_receipt(*, event_type: str, subject_ref: str, payload: dict[str, Any]) -> dict[str, str] | None:
    if os.environ.get('DEEPDIVE_ORCHESTRATOR_EMIT_RECEIPTS', '0') != '1':
        return None

    correlation_id = str(uuid.uuid4())
    root = _root()
    payload_dir = root / 'payloads' / SERVICE_DIR
    receipt_dir = root / 'receipts' / SERVICE_DIR
    payload_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    payload_path = payload_dir / f'{correlation_id}.payload.json'
    receipt_path = receipt_dir / f'{correlation_id}.receipt.json'

    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    receipt = {
        'version': '0.1',
        'created_at': _now(),
        'event_type': event_type,
        'subject_ref': subject_ref,
        'payload_ref': f'file://{payload_path.resolve()}',
        'correlation_id': correlation_id,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {
        'payload_ref': f'file://{payload_path.resolve()}',
        'receipt_ref': f'file://{receipt_path.resolve()}',
    }
