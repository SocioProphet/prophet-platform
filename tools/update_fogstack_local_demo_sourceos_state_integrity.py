#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from emit_sourceos_state_integrity_demo_report import build_report, rel, update_artifact_index, write_json

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def append_once(values: list[Any], value: Any) -> None:
    if value not in values:
        values.append(value)


def update_summary(summary_path: Path, report_path: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    artifacts = summary.setdefault("artifacts", {})
    if not isinstance(artifacts, dict):
        raise SystemExit(f"ERR: summary artifacts must be an object: {summary_path}")
    artifacts["sourceos_state_integrity_report"] = rel(report_path)

    checks = summary.setdefault("checks", [])
    if not isinstance(checks, list):
        raise SystemExit(f"ERR: summary checks must be a list: {summary_path}")
    append_once(checks, "sourceos_state_integrity_report_indexed")

    write_json(summary_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach SourceOS state-integrity evidence to a FogStack local demo run")
    parser.add_argument("--summary-json", required=True, type=Path)
    parser.add_argument("--artifact-index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    summary_path = args.summary_json if args.summary_json.is_absolute() else ROOT / args.summary_json
    artifact_index_path = args.artifact_index if args.artifact_index.is_absolute() else ROOT / args.artifact_index
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    write_json(output_path, build_report())
    update_artifact_index(artifact_index_path, "sourceos_state_integrity_report", output_path)
    update_summary(summary_path, output_path)

    if args.summary:
        print(f"SourceOS state integrity report: {rel(output_path)}")
        print(f"FogStack full summary updated: {rel(summary_path)}")
        print(f"Artifact index updated: {rel(artifact_index_path)}")
    else:
        print(json.dumps({"status": "passed", "report": rel(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
