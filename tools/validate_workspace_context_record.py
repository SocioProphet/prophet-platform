#!/usr/bin/env python3
"""Validate Workspace Context platform record fixture."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/workspace-context/workspace-context-record.v0.1.json"
EXAMPLE = ROOT / "contracts/workspace-context/workspace-context-record.v0.1.example.json"


def main():
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        for key in schema["required"]:
            assert key in example, f"missing {key}"
        assert example["version"] == "0.1"
        assert example["platform_refs"]["event_envelope_ref"]
        assert example["platform_refs"]["evidence_receipt_ref"]
        assert example["workroom_ref"]
        assert example["workspace_object_ref"]
    except Exception as exc:
        print(f"ERR: {exc}", file=sys.stderr)
        return 2
    print("OK: Workspace Context record validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
