#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a Fog Stack validation record from verifier JSON")
    parser.add_argument("--verifier-json", required=True, type=Path)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", choices=["local", "ci"], default="ci")
    parser.add_argument("--evidence-ref", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    verifier = load_json(args.verifier_json)
    summary = verifier.get("summary") or {}
    if not isinstance(summary, dict):
        raise SystemExit("ERR: verifier summary is missing or malformed")

    status = "executed" if args.source == "ci" else "shape-only"
    if summary.get("status") == "fail":
        status = "failed" if args.source == "ci" else "shape-only"

    record = {
        "kind": "FogStackValidationRecord",
        "schema_version": "v0.1",
        "bundle_id": args.bundle_id,
        "version": args.version,
        "validation_path": "tools/validate_fogstack.py",
        "source": args.source,
        "status": status,
        "summary": {
            "status": summary.get("status"),
            "exit_code": summary.get("exit_code"),
            "checks_run": summary.get("checks_run"),
            "warnings": summary.get("warnings"),
            "errors": summary.get("errors"),
            "critical": summary.get("critical"),
        },
        "evidence_ref": args.evidence_ref,
    }

    text = json.dumps(record, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
