#!/usr/bin/env python3
"""Validate platform receipt-spine binding schema and examples.

This validator is intentionally lightweight and stdlib-only so it can run in the
existing platform tools validation lane without broad dependency changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "evidence" / "platform-receipt-spine-binding.v0.1.json"
EXAMPLE_PATH = ROOT / "docs" / "generated" / "evidence" / "examples" / "platform-receipt-spine-binding.fogstack-runtime.example.json"
LOCK_PATH = ROOT / "standards.lock.yaml"
REQUIRED_STORAGE_COMMIT = "8c264939fbf123628e64c78e01cb1400cc8503df"


class ValidationError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValidationError(f"missing file: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"expected object in {path.relative_to(ROOT)}")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_schema(schema: dict[str, Any]) -> None:
    props = schema.get("properties", {})
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "binding schema must use JSON Schema draft 2020-12")
    require(schema.get("type") == "object", "binding schema must describe an object")
    require(schema.get("additionalProperties") is False, "binding schema must be strict")
    require(props.get("kind", {}).get("const") == "PlatformReceiptSpineBinding", "schema must declare PlatformReceiptSpineBinding kind")
    require("receiptSpineKind" in props, "schema must define receiptSpineKind")
    require("fieldMappings" in props, "schema must define fieldMappings")


def validate_example(example: dict[str, Any]) -> None:
    require(example.get("apiVersion") == "prophet-platform.socioprophet.org/v0.1", "example apiVersion mismatch")
    require(example.get("kind") == "PlatformReceiptSpineBinding", "example kind mismatch")
    require(example.get("receiptSpineKind") == "ExecutionReceipt", "FogStack runtime example must map to ExecutionReceipt")
    require(str(example.get("receiptSpineRef", "")).startswith("urn:srcos:receipt:execution:"), "receiptSpineRef must use execution receipt namespace")
    require(example.get("subjectRef"), "example must include subjectRef")

    standards = example.get("standardsRefs", {})
    require(standards.get("standardsStorageCommit") == REQUIRED_STORAGE_COMMIT, "example must reference the merged receipt-spine storage commit")
    require("138-evidence-receipt-spine.md" in standards.get("receiptSpine", ""), "example must point at evidence receipt spine standard")

    mappings = example.get("fieldMappings")
    require(isinstance(mappings, list) and mappings, "example must include fieldMappings")
    mapped_receipt_fields = {entry.get("receiptSpineField") for entry in mappings if isinstance(entry, dict)}
    for required_field in {"id", "issuedTimeUtc", "subjectRef", "evidenceRefs"}:
        require(required_field in mapped_receipt_fields, f"fieldMappings must include receipt spine field {required_field}")

    refs = example.get("fogstackArtifactRefs")
    require(isinstance(refs, list) and len(refs) >= 2, "example must include FogStack artifact refs")


def validate_lock() -> None:
    if not LOCK_PATH.exists():
        raise ValidationError("missing standards.lock.yaml")
    text = LOCK_PATH.read_text(encoding="utf-8")
    require(REQUIRED_STORAGE_COMMIT in text, "standards.lock.yaml must pin standards-storage at the merged receipt-spine commit")
    require("138-evidence-receipt-spine.md" in text, "standards.lock.yaml must list the receipt spine standard as consumed documentation")


def main() -> int:
    try:
        validate_schema(load_json(SCHEMA_PATH))
        validate_example(load_json(EXAMPLE_PATH))
        validate_lock()
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("OK: validated platform receipt-spine binding and standards lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
