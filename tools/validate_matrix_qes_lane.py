#!/usr/bin/env python3
"""Validate the Matrix/QES platform lane structure without executing app code."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "docs/PLATFORM_MATRIX_QES_FABRIC.md",
    "docs/LOCAL_DEV_MATRIX_QES_FABRIC.md",
    "docs/MATRIX_QES_IDENTITY_ALIGNMENT.md",
    "apps/matrix-qes-operator/README.md",
    "apps/matrix-qes-operator/requirements.txt",
    "apps/matrix-qes-operator/requirements-test.txt",
    "apps/matrix-qes-operator/app/main.py",
    "apps/matrix-qes-operator/app/state_machine.py",
    "apps/matrix-qes-operator/app/commands.py",
    "apps/matrix-qes-operator/app/store.py",
    "apps/matrix-qes-operator/app/replay_projection.py",
    "apps/matrix-qes-operator/tests/test_http_main.py",
    "apps/matrix-qes-operator/tests/test_state_machine.py",
    "tools/smoke_matrix_qes_operator.sh",
    "contracts/qes/events/matrix.operator.action.v1.schema.json",
    "contracts/qes/events/replay.requested.v1.schema.json",
    "contracts/qes/events/control.resolution.snapshot.v1.schema.json",
    "contracts/qes/examples/matrix.operator.action.v1.example.json",
    "contracts/qes/examples/replay.requested.v1.example.json",
    "contracts/qes/examples/control.resolution.snapshot.v1.example.json",
]

SCHEMA_EXAMPLE_PAIRS = [
    (
        "contracts/qes/events/matrix.operator.action.v1.schema.json",
        "contracts/qes/examples/matrix.operator.action.v1.example.json",
    ),
    (
        "contracts/qes/events/replay.requested.v1.schema.json",
        "contracts/qes/examples/replay.requested.v1.example.json",
    ),
    (
        "contracts/qes/events/control.resolution.snapshot.v1.schema.json",
        "contracts/qes/examples/control.resolution.snapshot.v1.example.json",
    ),
]

REQUIRED_DOC_MARKERS = {
    "docs/PLATFORM_MATRIX_QES_FABRIC.md": [
        "Matrix Client-Server API",
        "OpenFeature-compatible",
        "OpenTelemetry",
        "replay.requested.v1",
    ],
    "docs/MATRIX_QES_IDENTITY_ALIGNMENT.md": [
        "contracts/identity",
        "actor_id",
        "IdentitySubjectContext",
        "IdentitySessionContext",
    ],
}

REQUIRED_SCHEMA_KEYS = {
    "contracts/qes/events/matrix.operator.action.v1.schema.json": [
        "action_id",
        "tenant_id",
        "actor_id",
        "room_id",
        "action_type",
        "result_code",
    ],
    "contracts/qes/events/replay.requested.v1.schema.json": [
        "request_id",
        "tenant_id",
        "requested_by",
        "scope_ref",
        "reason",
    ],
    "contracts/qes/events/control.resolution.snapshot.v1.schema.json": [
        "snapshot_id",
        "targeting_key",
        "resolutions",
    ],
}


class ValidationFailure(Exception):
    pass


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValidationFailure(f"{path.relative_to(ROOT)} must contain a JSON object")
    return data


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_required_paths(errors: list[str]) -> None:
    for rel in REQUIRED_PATHS:
        require((ROOT / rel).exists(), f"missing required Matrix/QES path: {rel}", errors)


def check_python_syntax(errors: list[str]) -> None:
    for rel in [
        "apps/matrix-qes-operator/app/main.py",
        "apps/matrix-qes-operator/app/state_machine.py",
        "apps/matrix-qes-operator/app/commands.py",
        "apps/matrix-qes-operator/app/store.py",
        "apps/matrix-qes-operator/app/replay_projection.py",
        "apps/matrix-qes-operator/tests/test_http_main.py",
        "apps/matrix-qes-operator/tests/test_state_machine.py",
    ]:
        path = ROOT / rel
        if not path.exists():
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError as exc:
            errors.append(f"{rel}: Python syntax error: {exc}")


def check_schemas(errors: list[str]) -> None:
    for rel, required_keys in REQUIRED_SCHEMA_KEYS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        schema = load_json(path)
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{rel}: must use JSON Schema draft 2020-12", errors)
        require(schema.get("additionalProperties") is False, f"{rel}: top-level additionalProperties must be false", errors)
        required = set(schema.get("required", []))
        properties = set((schema.get("properties") or {}).keys())
        for key in required_keys:
            require(key in required, f"{rel}: missing required key {key!r}", errors)
            require(key in properties, f"{rel}: missing property {key!r}", errors)


def check_examples(errors: list[str]) -> None:
    for schema_rel, example_rel in SCHEMA_EXAMPLE_PAIRS:
        schema_path = ROOT / schema_rel
        example_path = ROOT / example_rel
        if not schema_path.exists() or not example_path.exists():
            continue
        schema = load_json(schema_path)
        example = load_json(example_path)
        required = schema.get("required", [])
        properties = set((schema.get("properties") or {}).keys())
        for key in required:
            require(key in example, f"{example_rel}: missing required field {key!r}", errors)
        extra = set(example) - properties
        require(not extra, f"{example_rel}: fields not declared by schema: {sorted(extra)}", errors)


def check_docs(errors: list[str]) -> None:
    for rel, markers in REQUIRED_DOC_MARKERS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            require(marker in text, f"{rel}: missing marker {marker!r}", errors)


def main() -> int:
    errors: list[str] = []
    check_required_paths(errors)
    check_python_syntax(errors)
    check_schemas(errors)
    check_examples(errors)
    check_docs(errors)

    if errors:
        print("Matrix/QES lane structural validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Matrix/QES lane structural validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
