#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SERVICE_DIR = "storage-promotion"
SERVICE_REF = "apps/storage-promotion"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest_json(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    if v := os.environ.get("STORAGE_PROMOTION_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def platform_state_root() -> Path:
    return state_home() / "prophet-platform"


def payloads_root() -> Path:
    return platform_state_root() / "payloads" / SERVICE_DIR


def events_root() -> Path:
    return platform_state_root() / "events" / SERVICE_DIR


def receipts_root() -> Path:
    return platform_state_root() / "receipts" / SERVICE_DIR


def ensure_dirs() -> None:
    for path in [payloads_root(), events_root(), receipts_root()]:
        path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ReceiptBundle:
    envelope: dict[str, Any]
    receipt: dict[str, Any]


def write_payload(payload: dict[str, Any], *, stem: str) -> tuple[Path, str]:
    ensure_dirs()
    path = payloads_root() / f"{stem}.payload.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, f"file://{path.resolve()}"


def make_bundle(
    *,
    event_type: str,
    action: str,
    status: str,
    subject_ref: str,
    payload_ref: str,
    service_ref: str = SERVICE_REF,
    scope_ref: str | None = None,
    correlation_id: str | None = None,
    classifiers: list[str] | None = None,
    policy_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    output_refs: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> ReceiptBundle:
    envelope_id = str(uuid.uuid4())
    receipt_id = str(uuid.uuid4())
    created_at = utc_now()

    envelope = {
        "version": "0.1",
        "envelope_id": envelope_id,
        "created_at": created_at,
        "event_type": event_type,
        "producer": service_ref,
        "subject_ref": subject_ref,
        "payload_ref": payload_ref,
        "correlation_id": correlation_id or envelope_id,
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
        "service_ref": service_ref,
        "action": action,
        "status": status,
        "subject_ref": subject_ref,
        "envelope_ref": f"event://{envelope_id}",
        "policy_refs": policy_refs or [],
        "evidence_refs": evidence_refs or [],
        "output_refs": output_refs or [],
        "metrics": metrics or {},
        "hash": envelope_hash,
        "hash_algo": "sha256",
        "correlation_id": correlation_id or envelope_id,
    }

    envelope["receipt_ref"] = f"receipt://{receipt_id}"
    return ReceiptBundle(envelope=envelope, receipt=receipt)


def write_bundle(bundle: ReceiptBundle, *, stem: str | None = None) -> tuple[Path, Path]:
    ensure_dirs()
    stem = stem or bundle.envelope["correlation_id"]
    event_path = events_root() / f"{stem}.event.json"
    receipt_path = receipts_root() / f"{stem}.receipt.json"
    event_path.write_text(json.dumps(bundle.envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(bundle.receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return event_path, receipt_path
