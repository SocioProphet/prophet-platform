from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SERVICE_DIR = "eval-fabric-api"
SERVICE_REF = "apps/eval-fabric-api"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest_json(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def service_root() -> Path:
    return state_home() / "prophet-platform" / SERVICE_DIR


def payloads_root() -> Path:
    return service_root() / "payloads"


def events_root() -> Path:
    return service_root() / "events"


def receipts_root() -> Path:
    return service_root() / "receipts"


def ensure_dirs() -> None:
    for p in [payloads_root(), events_root(), receipts_root()]:
        p.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Emission:
    payload_path: Path
    event_path: Path
    receipt_path: Path
    payload_ref: str
    event_ref: str
    receipt_ref: str


def emit_artifacts(
    *,
    event_type: str,
    action: str,
    status: str,
    subject_ref: str,
    payload: dict[str, Any],
    scope_ref: str | None = None,
    classifiers: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> Emission:
    ensure_dirs()
    correlation_id = correlation_id or str(uuid.uuid4())
    created_at = utc_now()

    payload_path = payloads_root() / f"{correlation_id}.payload.json"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload_ref = f"file://{payload_path.resolve()}"

    envelope_id = str(uuid.uuid4())
    receipt_id = str(uuid.uuid4())

    envelope = {
        "version": "0.1",
        "envelope_id": envelope_id,
        "created_at": created_at,
        "event_type": event_type,
        "producer": SERVICE_REF,
        "subject_ref": subject_ref,
        "payload_ref": payload_ref,
        "correlation_id": correlation_id,
    }
    if scope_ref:
        envelope["scope_ref"] = scope_ref
    if classifiers:
        envelope["classifiers"] = classifiers

    envelope_hash = digest_json(envelope)
    receipt = {
        "version": "0.1",
        "receipt_id": receipt_id,
        "created_at": created_at,
        "service_ref": SERVICE_REF,
        "action": action,
        "status": status,
        "subject_ref": subject_ref,
        "envelope_ref": f"event://{envelope_id}",
        "policy_refs": [],
        "evidence_refs": [],
        "output_refs": [payload_ref],
        "metrics": metrics or {},
        "hash": envelope_hash,
        "hash_algo": "sha256",
        "correlation_id": correlation_id,
    }

    event_path = events_root() / f"{correlation_id}.event.json"
    receipt_path = receipts_root() / f"{correlation_id}.receipt.json"
    event_path.write_text(json.dumps({**envelope, "receipt_ref": f"receipt://{receipt_id}"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return Emission(
        payload_path=payload_path,
        event_path=event_path,
        receipt_path=receipt_path,
        payload_ref=payload_ref,
        event_ref=f"file://{event_path.resolve()}",
        receipt_ref=f"file://{receipt_path.resolve()}",
    )


def maybe_emit_artifacts(**kwargs: Any) -> Emission | None:
    if os.environ.get("EVAL_FABRIC_EMIT_RECEIPTS", "0") != "1":
        return None
    return emit_artifacts(**kwargs)
