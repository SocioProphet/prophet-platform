#!/usr/bin/env python3
"""Summarize optional Agentplane Gate 4 smoke artifacts.

This script is intentionally local and record-only. It does not execute Agentplane.
It reads already-emitted Agentplane smoke artifacts and writes a compact summary
that the platform Gate 4 demo record can reference.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts/professional-intelligence-client-opportunity-review"
DEFAULT_OUTPUT = ROOT / "build/professional-intelligence/agentplane-smoke-summary.json"
EXPECTED_FILES = [
    "professional-intelligence-workflow-step.json",
    "run-artifact.json",
    "replay-artifact.json",
]


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid-json: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--required", action="store_true", help="Fail when expected artifacts are missing or invalid.")
    args = parser.parse_args()

    files: list[dict[str, Any]] = []
    failures: list[str] = []
    for name in EXPECTED_FILES:
        path = args.artifact_dir / name
        payload, error = load_json(path)
        if error:
            failures.append(f"{name}: {error}")
            files.append({"name": name, "present": False, "error": error})
            continue
        files.append(
            {
                "name": name,
                "present": True,
                "kind": payload.get("kind"),
                "result": payload.get("result"),
                "bundle": payload.get("bundle"),
            }
        )

    summary = {
        "schemaVersion": "v0.1",
        "kind": "ProfessionalIntelligenceAgentplaneSmokeSummary",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "artifactDir": str(args.artifact_dir),
        "required": args.required,
        "passed": not failures,
        "failures": failures,
        "files": files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if failures and args.required:
        print(f"ERR: Agentplane smoke summary failed; wrote {args.output}", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 2

    print(f"OK: Agentplane smoke summary wrote {args.output}")
    if failures:
        print("WARN: expected artifacts were missing or invalid; rerun with --required to fail", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
