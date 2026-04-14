from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

SERVICE = "crystal-atlas-contract-intel"
UPSTREAM_SERVICE = os.environ.get("CRYSTAL_ATLAS_UPSTREAM_SERVICE", "crystal-atlas-extract-enrich")


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def platform_state_root() -> Path:
    return state_home() / "prophet-platform"


def _service_dir(kind: str, service: str) -> Path:
    return platform_state_root() / kind / service


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_family(title: str) -> str:
    value = title.strip().lower()
    if "terminat" in value:
        return "termination"
    if "audit" in value:
        return "audit"
    if "assign" in value:
        return "assignment"
    if "confidential" in value:
        return "confidentiality"
    if "liability" in value:
        return "limitation_of_liability"
    return value.replace(" ", "_")


def compare_clause_sets(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    left_map = {_normalize_family(item.get("title", "")): item for item in left if item.get("title")}
    right_map = {_normalize_family(item.get("title", "")): item for item in right if item.get("title")}
    shared = sorted(set(left_map) & set(right_map))
    left_only = sorted(set(left_map) - set(right_map))
    right_only = sorted(set(right_map) - set(left_map))
    changed: list[str] = []
    for fam in shared:
        if (left_map[fam].get("text") or "").strip() != (right_map[fam].get("text") or "").strip():
            changed.append(fam)
    return {
        "shared_families": shared,
        "left_only_families": left_only,
        "right_only_families": right_only,
        "changed_families": sorted(changed),
    }


def emit_contract_comparison_from_payload(payload: dict[str, Any], tenant_id: str = "default") -> str:
    left = payload.get("left_clauses") or []
    right = payload.get("right_clauses") or []
    comparison = compare_clause_sets(left, right)
    correlation_id = f"cmp-{uuid.uuid4().hex[:12]}"
    event = {
        "event_type": "contract.clauses.compared.v0",
        "created_at": payload.get("emitted_at", "2026-04-14T00:00:00+00:00"),
    }
    receipt = {
        "status": "succeeded",
        "action": "CompareClauses",
        "subject_ref": f"contract://{payload.get('left_contract_id','left')}-vs-{payload.get('right_contract_id','right')}",
        "created_at": event["created_at"],
    }
    body = {
        "event_id": correlation_id,
        "emitted_at": event["created_at"],
        "tenant_id": tenant_id,
        "producer": SERVICE,
        "comparison_id": correlation_id,
        "left_contract_id": payload.get("left_contract_id", "left"),
        "right_contract_id": payload.get("right_contract_id", "right"),
        **comparison,
    }
    _write_json(_service_dir("payloads", SERVICE) / f"{correlation_id}.payload.json", body)
    _write_json(_service_dir("events", SERVICE) / f"{correlation_id}.event.json", event)
    _write_json(_service_dir("receipts", SERVICE) / f"{correlation_id}.receipt.json", receipt)
    return correlation_id


def replay_upstream_bundle(correlation_id: str, tenant_id: str = "default") -> str | None:
    payload_path = _service_dir("payloads", UPSTREAM_SERVICE) / f"{correlation_id}.payload.json"
    payload = _read_json(payload_path)
    if payload is None:
        return None
    return emit_contract_comparison_from_payload(payload, tenant_id=tenant_id)
