from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import store

REPO_ROOT = Path(__file__).resolve().parents[3]
TELEMETRY_ROOT = REPO_ROOT / "telemetry"
MANIFESTS_DIR = TELEMETRY_ROOT / "manifests"
CONTROLS_PATH = TELEMETRY_ROOT / "controls" / "global_controls.json"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(event_type: str) -> dict[str, Any]:
    path = MANIFESTS_DIR / f"{event_type}.json"
    if not path.exists():
        raise FileNotFoundError(f"unknown telemetry manifest: {event_type}")
    return _read_json(path)


def load_controls() -> dict[str, Any]:
    if not CONTROLS_PATH.exists():
        return {"controls": []}
    return _read_json(CONTROLS_PATH)


def _default_control_state_for_plane(plane: str) -> str:
    controls = load_controls().get("controls", [])
    for control in controls:
        if plane in control.get("applies_to_planes", []):
            return str(control.get("default_state", "enabled"))
    return "enabled"


def _control_state_for_plane(plane: str, control_snapshot: dict[str, str] | None) -> str:
    controls = load_controls().get("controls", [])
    for control in controls:
        if plane in control.get("applies_to_planes", []):
            control_id = str(control.get("control_id"))
            if control_snapshot and control_id in control_snapshot:
                return str(control_snapshot[control_id])
            return str(control.get("default_state", "enabled"))
    return _default_control_state_for_plane(plane)


def _to_milliseconds(raw_value: Any) -> float | None:
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    return None


def _bucket_duration(value_ms: float, allowed_values: list[str]) -> str:
    def parse_unit(raw: str) -> float:
        raw = raw.strip().lower()
        if raw.endswith("ms"):
            return float(raw[:-2])
        if raw.endswith("s"):
            return float(raw[:-1]) * 1000.0
        return float(raw)

    for label in allowed_values:
        token = label.lower()
        if token.startswith("lt_"):
            upper = parse_unit(token.removeprefix("lt_"))
            if value_ms < upper:
                return label
        elif token.startswith("gt_"):
            lower = parse_unit(token.removeprefix("gt_"))
            if value_ms > lower:
                return label
        elif "_to_" in token:
            lower_raw, upper_raw = token.split("_to_", 1)
            lower = parse_unit(lower_raw)
            upper = parse_unit(upper_raw)
            if lower <= value_ms < upper:
                return label
        elif token.endswith("s") or token.endswith("ms"):
            threshold = parse_unit(token)
            if value_ms <= threshold:
                return label
    return allowed_values[-1] if allowed_values else str(int(value_ms))


def _transform_field(spec: dict[str, Any], value: Any) -> Any:
    transform = str(spec.get("transform", "none"))
    if transform in {"none", "aggregate_only"}:
        return value
    if transform == "hash":
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]
    if transform == "truncate":
        return str(value)[:32]
    if transform == "bucket":
        numeric = _to_milliseconds(value)
        allowed = list(spec.get("allowed_values", []))
        if numeric is None or not allowed:
            return str(value)
        return _bucket_duration(numeric, allowed)
    if transform == "drop":
        return None
    return value


def _integrity_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def reduce_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    control_snapshot: dict[str, str] | None = None,
    policy_version: str = "telemetry-policy-v0.1",
) -> dict[str, Any]:
    manifest = load_manifest(event_type)
    created_at = str(payload.get("created_at") or _utcnow_iso())
    plane = str(manifest["plane"])
    control_state = _control_state_for_plane(plane, control_snapshot)

    reduced_fields: dict[str, Any] = {}
    transformed_fields: list[str] = []
    missing_required: list[str] = []

    for field in manifest.get("fields", []):
        name = str(field["name"])
        if name not in payload:
            if field.get("required"):
                missing_required.append(name)
            continue
        transformed = _transform_field(field, payload[name])
        if transformed is not None:
            reduced_fields[name] = transformed
        if str(field.get("transform", "none")) not in {"none", "aggregate_only"}:
            transformed_fields.append(name)

    blocked_reason = None
    if missing_required:
        action = "BLOCK"
        blocked_reason = f"missing_required_fields:{','.join(sorted(missing_required))}"
    elif manifest.get("essential") is False and control_state in {"disabled", "high_privacy"}:
        action = "BLOCK"
        blocked_reason = "disabled_by_user"
    else:
        action = "TRANSFORM_ALLOW" if transformed_fields else "ALLOW"

    destinations = [] if action == "BLOCK" else list(manifest.get("destinations", []))
    subject_ref = str(payload.get("subject_ref") or f"telemetry://{event_type}")
    retention_days = int(manifest.get("retention_days", 1))
    retention_deadline = (
        datetime.fromisoformat(created_at.replace("Z", "+00:00")) + timedelta(days=retention_days)
    ).isoformat()

    outcome = {
        "event": event_type,
        "plane": plane,
        "manifest_version": str(manifest.get("version", "1.0.0")),
        "policy_version": policy_version,
        "control_snapshot": control_snapshot or {},
        "control_state": control_state,
        "action": action,
        "blocked_reason": blocked_reason,
        "transformed_fields": sorted(set(transformed_fields)),
        "destinations": destinations,
        "created_at": created_at,
        "retention_deadline": retention_deadline,
        "subject_ref": subject_ref,
        "reduced_fields": reduced_fields,
    }
    return outcome


def emit_event_bundle(
    service: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    control_snapshot: dict[str, str] | None = None,
    policy_version: str = "telemetry-policy-v0.1",
) -> dict[str, Any]:
    correlation_id = str(payload.get("correlation_id") or uuid.uuid4().hex)
    outcome = reduce_event(
        event_type,
        payload,
        control_snapshot=control_snapshot,
        policy_version=policy_version,
    )

    layout = store.resolve_layout(service)
    layout.payload_dir.mkdir(parents=True, exist_ok=True)
    layout.event_dir.mkdir(parents=True, exist_ok=True)
    layout.receipt_dir.mkdir(parents=True, exist_ok=True)
    if layout.catalog_file is not None:
        layout.catalog_file.parent.mkdir(parents=True, exist_ok=True)

    payload_path = layout.payload_dir / f"{correlation_id}.payload.json"
    event_path = layout.event_dir / f"{correlation_id}.event.json"
    receipt_path = layout.receipt_dir / f"{correlation_id}.receipt.json"

    payload_doc = {
        "event": event_type,
        "plane": outcome["plane"],
        "fields": outcome["reduced_fields"],
        "control_state": outcome["control_state"],
        "destinations": outcome["destinations"],
    }
    payload_path.write_text(json.dumps(payload_doc, indent=2) + "\n", encoding="utf-8")

    event_doc = {
        "event_type": event_type,
        "plane": outcome["plane"],
        "created_at": outcome["created_at"],
        "subject_ref": outcome["subject_ref"],
        "policy_action": outcome["action"],
        "payload_ref": f"file://{payload_path.resolve()}",
    }
    event_path.write_text(json.dumps(event_doc, indent=2) + "\n", encoding="utf-8")

    receipt_doc = {
        "receipt_id": f"rcpt_{correlation_id}",
        "status": "blocked" if outcome["action"] == "BLOCK" else "recorded",
        "action": outcome["action"],
        "subject_ref": outcome["subject_ref"],
        "created_at": outcome["created_at"],
        "retention_deadline": outcome["retention_deadline"],
        "integrity_hash": _integrity_hash(payload_doc),
        "plane": outcome["plane"],
        "event_type": event_type,
        "destinations": outcome["destinations"],
        "blocked_reason": outcome["blocked_reason"],
        "transformed_fields": outcome["transformed_fields"],
    }
    receipt_path.write_text(json.dumps(receipt_doc, indent=2) + "\n", encoding="utf-8")

    catalog_entry = {
        "service": service,
        "correlation_id": correlation_id,
        "event_type": event_type,
        "plane": outcome["plane"],
        "created_at": outcome["created_at"],
        "status": receipt_doc["status"],
        "action": receipt_doc["action"],
        "subject_ref": receipt_doc["subject_ref"],
        "receipt_ref": f"file://{receipt_path.resolve()}",
        "event_ref": f"file://{event_path.resolve()}",
        "payload_ref": f"file://{payload_path.resolve()}",
    }
    if layout.catalog_file is not None:
        with layout.catalog_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(catalog_entry) + "\n")

    return {
        "service": service,
        "correlation_id": correlation_id,
        "outcome": outcome,
        "catalog_entry": catalog_entry,
        "receipt": receipt_doc,
        "event": event_doc,
        "payload": payload_doc,
    }
