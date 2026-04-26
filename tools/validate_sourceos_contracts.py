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
    "fingerprint.v0.schema.json": [],
    "config-source.v0.schema.json": [],
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def validate_file(schema_path: Path, document_path: Path) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SourceOS contract examples against JSON schemas")
    parser.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR)
    parser.add_argument("--example-dir", type=Path, default=EXAMPLE_DIR)
    args = parser.parse_args()

    for schema_name, examples in SCHEMA_EXAMPLES.items():
        schema_path = args.schema_dir / schema_name
        if not schema_path.exists():
            raise SystemExit(f"ERR: missing schema {schema_path}")
        jsonschema.Draft202012Validator.check_schema(load_json(schema_path))
        for example_name in examples:
            example_path = args.example_dir / example_name
            if not example_path.exists():
                raise SystemExit(f"ERR: missing example {example_path}")
            validate_file(schema_path, example_path)

    print("SourceOS contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
