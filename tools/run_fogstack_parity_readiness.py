#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def run_parity(output_dir: Path, clean: bool) -> dict[str, Any]:
    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    full_summary = output_dir / "fogstack-local-demo.full.summary.json"
    artifact_index = output_dir / "demo-artifacts.index.json"
    parity_record = output_dir / "fogstack-parity-readiness.record.json"

    full_demo_cmd = [sys.executable, "tools/run_fogstack_local_demo_full.py", "--output-dir", str(output_dir), "--summary"]
    if not clean:
        full_demo_cmd.append("--no-clean")
    run(full_demo_cmd)
    run([
        sys.executable,
        "tools/check_fogstack_parity_readiness.py",
        "--summary", str(full_summary),
        "--index", str(artifact_index),
        "--output", str(parity_record),
    ])
    return load_json(parity_record)


def render_summary(record: dict[str, Any]) -> str:
    lines = [
        f"FogStack parity readiness: {record['status']}",
        f"Parity target: {record['parity_target']}",
        f"Turn counter: {record['turn_counter']}",
        f"Checked lanes: {len(record['checked_lanes'])}",
        f"Required artifacts: {len(record['required_summary_artifacts'])}",
        f"Required index IDs: {len(record['required_index_ids'])}",
        f"Errors: {len(record['errors'])}",
        f"Record: {record['artifact_index_ref'].rsplit('/', 1)[0]}/fogstack-parity-readiness.record.json",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FogStack local demo and check credible-MVP parity readiness")
    parser.add_argument("--output-dir", type=Path, default=Path("build/fogstack-local-demo"))
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    record = run_parity(args.output_dir, clean=not args.no_clean)
    if args.summary:
        print(render_summary(record), end="")
    else:
        print(json.dumps(record, indent=2))
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
