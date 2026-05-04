#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator


EXAMPLE_PAIRS = (
    (
        Path("contracts/identity/IdentitySubjectContext.v0.1.json"),
        Path("docs/generated/identity/examples/identity_subject_context.example.v0.1.json"),
    ),
    (
        Path("contracts/identity/IdentitySessionContext.v0.1.json"),
        Path("docs/generated/identity/examples/identity_session_context.example.v0.1.json"),
    ),
    (
        Path("contracts/identity/IdentityProofIngressRecord.v0.1.json"),
        Path("docs/generated/identity/examples/identity_proof_ingress_record.example.v0.1.json"),
    ),
)


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_pair(root: Path, schema_rel: Path, example_rel: Path) -> None:
    schema_path = root / schema_rel
    example_path = root / example_rel

    if not schema_path.is_file():
        raise FileNotFoundError(f"missing schema: {schema_rel}")
    if not example_path.is_file():
        raise FileNotFoundError(f"missing example: {example_rel}")

    schema = load_json(schema_path)
    example = load_json(example_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)


def validate_all(root: Path, pairs: Iterable[tuple[Path, Path]] = EXAMPLE_PAIRS) -> None:
    for schema_rel, example_rel in pairs:
        validate_pair(root, schema_rel, example_rel)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate generated identity examples against identity JSON schemas."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of tools/.",
    )
    args = parser.parse_args()

    validate_all(args.root.resolve())
    print("identity contract examples validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
