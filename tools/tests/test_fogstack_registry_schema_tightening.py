from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_SCHEMA = Path("schemas/release/fogstack-registry-root-metadata-v0.1.schema.json")
REVOCATION_SCHEMA = Path("schemas/release/fogstack-registry-revocation-index-v0.1.schema.json")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    prefix = "#/$defs/"
    assert ref.startswith(prefix), f"unsupported local ref: {ref}"
    target = schema["$defs"][ref[len(prefix):]]
    assert isinstance(target, dict)
    return target


def validate_minimal_json_schema(
    schema_root: dict[str, Any],
    schema: dict[str, Any],
    instance: Any,
    path: str = "$",
) -> list[str]:
    errors: list[str] = []

    if "$ref" in schema:
        return validate_minimal_json_schema(schema_root, resolve_ref(schema_root, schema["$ref"]), instance, path)

    if "anyOf" in schema:
        branch_errors = [
            validate_minimal_json_schema(schema_root, branch, instance, path)
            for branch in schema["anyOf"]
        ]
        if not any(not branch for branch in branch_errors):
            errors.append(f"{path}: did not match any allowed schema")
        return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")

    if "type" in schema:
        allowed = schema["type"]
        if isinstance(allowed, str):
            allowed = [allowed]
        assert isinstance(allowed, list)

        def matches_type(type_name: str) -> bool:
            return (
                (type_name == "object" and isinstance(instance, dict))
                or (type_name == "array" and isinstance(instance, list))
                or (type_name == "string" and isinstance(instance, str))
                or (type_name == "boolean" and isinstance(instance, bool))
                or (type_name == "null" and instance is None)
            )

        if not any(matches_type(type_name) for type_name in allowed):
            errors.append(f"{path}: expected type {allowed!r}")
            return errors

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
            errors.append(f"{path}: does not match pattern {schema['pattern']}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required key {key}")

        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            allowed_keys = set(properties)
            for key in instance:
                if key not in allowed_keys:
                    errors.append(f"{path}: unexpected key {key}")

        for key, value in instance.items():
            if key in properties:
                errors.extend(
                    validate_minimal_json_schema(
                        schema_root,
                        properties[key],
                        value,
                        f"{path}.{key}",
                    )
                )

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(validate_minimal_json_schema(schema_root, schema["items"], item, f"{path}[{index}]"))

    return errors


def assert_valid(schema: dict[str, Any], instance: dict[str, Any]) -> None:
    errors = validate_minimal_json_schema(schema, schema, instance)
    assert errors == []


def assert_invalid(schema: dict[str, Any], instance: dict[str, Any]) -> None:
    errors = validate_minimal_json_schema(schema, schema, instance)
    assert errors != []


def test_registry_schemas_are_strict() -> None:
    root_schema = load_json(ROOT_SCHEMA)
    revocation_schema = load_json(REVOCATION_SCHEMA)

    assert root_schema["additionalProperties"] is False
    assert root_schema["$defs"]["release_entry"]["additionalProperties"] is False
    assert root_schema["$defs"]["sha256_digest"]["pattern"] == "^sha256:[0-9a-f]{64}$"

    assert revocation_schema["additionalProperties"] is False
    assert revocation_schema["$defs"]["revocation_entry"]["additionalProperties"] is False
    assert revocation_schema["$defs"]["revocation_entry"]["properties"]["status"]["enum"] == [
        "revoked",
        "rollback",
    ]


def test_builder_outputs_validate_against_tightened_schemas(tmp_path: Path) -> None:
    release_root = tmp_path / "registry" / "fogstack.access" / "0.1.0"
    pointer = release_root / "release-pointer.json"
    index = release_root / "registry-publication.index.json"
    revocations = tmp_path / "revocations.json"
    root = tmp_path / "registry-root.json"

    write_json(pointer, {
        "kind": "FogStackFilesystemRegistryReleasePointer",
        "schema_version": "v0.1",
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "index_ref": str(index),
        "index_digest": "sha256:test",
    })
    write_json(index, {
        "kind": "FogStackRegistryPublicationIndex",
        "schema_version": "v0.1",
        "registry_uri": "file://registry",
        "artifacts": [],
    })

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_revocation_index.py",
        "--entry", "fogstack.old:0.0.1:revoked:superseded:",
        "--output", str(revocations),
    ], check=True)

    subprocess.run([
        sys.executable,
        "tools/build_fogstack_registry_root_metadata.py",
        "--registry-uri", "file://registry",
        "--release", "fogstack.access", "0.1.0", str(release_root),
        "--revocation-index", str(revocations),
        "--signature-type", "other",
        "--signature-ref", "artifact://registry/root.sig",
        "--output", str(root),
    ], check=True)

    assert_valid(load_json(ROOT_SCHEMA), load_json(root))
    assert_valid(load_json(REVOCATION_SCHEMA), load_json(revocations))


def test_tightened_root_schema_rejects_malformed_shapes() -> None:
    root_schema = load_json(ROOT_SCHEMA)
    valid_digest = "sha256:" + ("a" * 64)

    valid_root = {
        "kind": "FogStackRegistryRootMetadata",
        "schema_version": "v0.1",
        "registry_uri": "file://registry",
        "releases": [{
            "bundle_id": "fogstack.access",
            "version": "0.1.0",
            "release_pointer_ref": "registry/fogstack.access/0.1.0/release-pointer.json",
            "release_pointer_digest": valid_digest,
            "registry_publication_index_ref": "registry/fogstack.access/0.1.0/registry-publication.index.json",
            "registry_publication_index_digest": valid_digest,
        }],
        "revocation_index_ref": None,
        "revocation_index_digest": None,
        "signed": False,
        "signature": None,
    }
    assert_valid(root_schema, valid_root)

    missing_release_ref = json.loads(json.dumps(valid_root))
    del missing_release_ref["releases"][0]["release_pointer_ref"]
    assert_invalid(root_schema, missing_release_ref)

    bad_digest = json.loads(json.dumps(valid_root))
    bad_digest["releases"][0]["release_pointer_digest"] = "sha256:wrong"
    assert_invalid(root_schema, bad_digest)

    extra_root_property = json.loads(json.dumps(valid_root))
    extra_root_property["unexpected"] = True
    assert_invalid(root_schema, extra_root_property)


def test_tightened_revocation_schema_rejects_malformed_shapes() -> None:
    revocation_schema = load_json(REVOCATION_SCHEMA)

    valid_index = {
        "kind": "FogStackRegistryRevocationIndex",
        "schema_version": "v0.1",
        "entries": [{
            "bundle_id": "fogstack.access",
            "version": "0.1.0",
            "status": "rollback",
            "reason": "bad release",
            "superseded_by": "fogstack.access@0.0.9",
        }],
    }
    assert_valid(revocation_schema, valid_index)

    invalid_status = json.loads(json.dumps(valid_index))
    invalid_status["entries"][0]["status"] = "suspended"
    assert_invalid(revocation_schema, invalid_status)

    extra_entry_property = json.loads(json.dumps(valid_index))
    extra_entry_property["entries"][0]["unexpected"] = True
    assert_invalid(revocation_schema, extra_entry_property)

    missing_reason = json.loads(json.dumps(valid_index))
    del missing_reason["entries"][0]["reason"]
    assert_invalid(revocation_schema, missing_reason)
