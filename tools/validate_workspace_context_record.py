#!/usr/bin/env python3
"""Validate Workspace Context platform record fixture."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/workspace-context/workspace-context-record.v0.1.json"
EXAMPLE = ROOT / "contracts/workspace-context/workspace-context-record.v0.1.example.json"


class RecordInvalid(Exception):
    """The Workspace Context record fixture failed a validation obligation."""


def require(condition: object, message: str) -> None:
    """Validation check that survives `python -O`.

    Every check in this tool was a bare `assert`. `python -O` strips all of
    them, leaving main() with nothing to do but fall through to
    `print("OK: Workspace Context record validation passed")` and return 0 --
    a validator reporting a pass for a fixture it never read. There is no
    partial failure mode here: under -O the entire tool was a no-op that
    printed OK.
    """
    if not condition:
        raise RecordInvalid(message)


def main():
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        for key in schema["required"]:
            require(key in example, f"missing {key}")
        require(example["version"] == "0.1", "version must be '0.1'")
        require(
            example["platform_refs"]["event_envelope_ref"],
            "platform_refs.event_envelope_ref must be non-empty",
        )
        require(
            example["platform_refs"]["evidence_receipt_ref"],
            "platform_refs.evidence_receipt_ref must be non-empty",
        )
        require(example["workroom_ref"], "workroom_ref must be non-empty")
        require(example["workspace_object_ref"], "workspace_object_ref must be non-empty")
    except Exception as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: Workspace Context record validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
