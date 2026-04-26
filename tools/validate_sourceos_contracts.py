#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover
    raise SystemExit("ERR: jsonschema is required to validate SourceOS contracts") from exc


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "contracts" / "sourceos"
EXAMPLE_DIR = SCHEMA_DIR / "examples"

SCHEMA_EXAMPLES = {
    "release-set.v0.schema.json": ["release-set.m2-demo.v0.json"],
    "boot-release-set.v0.schema.json": ["boot-release-set.m2-demo.v0.json"],
    "fingerprint.v0.schema.json": ["fingerprint.m2-demo.v0.json"],
    "config-source.v0.schema.json": ["config-source.m2-demo.v0.json"],
    "compliance-result.v0.schema.json": ["compliance-result.m2-demo.v0.json"],
    "proof-index.v0.schema.json": ["proof-index.m2-demo.v0.json"],
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def validate_file(schema_path: Path, document_path: Path) -> dict[str, Any]:
    schema = load_json(schema_path)
    document = load_json(document_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda err: list(err.path))
    if errors:
        print(f"ERR: {document_path} failed {schema_path.name}")
        for err in errors:
            loc = ".".join(str(part) for part in err.path) or "<root>"
            print(f"  - {loc}: {err.message}")
        raise SystemExit(1)
    print(f"OK: {document_path.relative_to(ROOT)} validates against {schema_path.relative_to(ROOT)}")
    return document


def require_equal(left: Any, right: Any, message: str) -> None:
    if left != right:
        raise SystemExit(f"ERR: {message}: {left!r} != {right!r}")


def validate_lifecycle_links(examples: dict[str, dict[str, Any]]) -> None:
    release = examples["release-set.m2-demo.v0.json"]
    boot = examples["boot-release-set.m2-demo.v0.json"]
    config = examples["config-source.m2-demo.v0.json"]
    fingerprint = examples["fingerprint.m2-demo.v0.json"]
    compliance = examples["compliance-result.m2-demo.v0.json"]
    proof = examples["proof-index.m2-demo.v0.json"]

    require_equal(boot["parent_release_set_ref"], release["id"], "boot release set parent must reference release set id")
    require_equal(config["id"], release["provenance"]["config_sources"][0], "release set config source must reference config source id")

    release_ref = "contracts/sourceos/examples/release-set.m2-demo.v0.json"
    boot_ref = "contracts/sourceos/examples/boot-release-set.m2-demo.v0.json"
    config_ref = "contracts/sourceos/examples/config-source.m2-demo.v0.json"
    fingerprint_ref = "contracts/sourceos/examples/fingerprint.m2-demo.v0.json"
    compliance_ref = "contracts/sourceos/examples/compliance-result.m2-demo.v0.json"

    require_equal(fingerprint["policy"]["release_set_ref"], release_ref, "fingerprint release set ref must point at demo release set")
    require_equal(fingerprint["policy"]["boot_release_set_ref"], boot_ref, "fingerprint boot release set ref must point at demo boot release set")
    require_equal(fingerprint["provenance"]["config_source_refs"][0], config_ref, "fingerprint config source ref must point at demo config source")

    require_equal(compliance["release_set_ref"], release_ref, "compliance release set ref must point at demo release set")
    require_equal(compliance["boot_release_set_ref"], boot_ref, "compliance boot release set ref must point at demo boot release set")
    require_equal(compliance["fingerprint_ref"], fingerprint_ref, "compliance fingerprint ref must point at demo fingerprint")
    require_equal(compliance["status"], "compliant", "M2 demo compliance result must be compliant")

    refs = {entry["ref"] for entry in proof["entries"]}
    required_refs = {release_ref, boot_ref, config_ref, fingerprint_ref, compliance_ref}
    missing = sorted(required_refs - refs)
    if missing:
        raise SystemExit("ERR: proof index missing required refs: " + ", ".join(missing))

    require_equal(proof["release_set_ref"], release_ref, "proof index release set ref must point at demo release set")
    require_equal(proof["boot_release_set_ref"], boot_ref, "proof index boot release set ref must point at demo boot release set")
    print("OK: SourceOS M2 lifecycle proof links are coherent")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SourceOS contract examples against JSON schemas")
    parser.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR)
    parser.add_argument("--example-dir", type=Path, default=EXAMPLE_DIR)
    args = parser.parse_args()

    loaded_examples: dict[str, dict[str, Any]] = {}
    for schema_name, examples in SCHEMA_EXAMPLES.items():
        schema_path = args.schema_dir / schema_name
        if not schema_path.exists():
            raise SystemExit(f"ERR: missing schema {schema_path}")
        jsonschema.Draft202012Validator.check_schema(load_json(schema_path))
        for example_name in examples:
            example_path = args.example_dir / example_name
            if not example_path.exists():
                raise SystemExit(f"ERR: missing example {example_path}")
            loaded_examples[example_name] = validate_file(schema_path, example_path)

    validate_lifecycle_links(loaded_examples)
    print("SourceOS contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
