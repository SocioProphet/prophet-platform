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
    local_summary = output_dir / "fogstack-local-demo.summary.json"
    artifact_index = output_dir / "demo-artifacts.index.json"
    parity_record = output_dir / "fogstack-parity-readiness.record.json"

    full_demo_cmd = [sys.executable, "tools/run_fogstack_local_demo_full.py", "--output-dir", str(output_dir), "--summary"]
    if not clean:
        full_demo_cmd.append("--no-clean")
    run(full_demo_cmd)
    run([
        sys.executable,
        "tools/update_fogstack_local_demo_apply_plan.py",
        "--summary-json", str(local_summary),
    ])
    run([
        sys.executable,
        "tools/update_fogstack_local_demo_approval_intent.py",
        "--summary-json", str(local_summary),
    ])
    full_record = load_json(full_summary)
    local_record = load_json(local_summary)
    artifacts = local_record.get("artifacts", {}) if isinstance(local_record.get("artifacts"), dict) else {}
    grafts = {
        "live_apply_plan_record": artifacts.get("deploy_live_apply_plan_record"),
        "approval_intent_record": artifacts.get("deploy_approval_intent_record"),
    }
    full_artifacts = full_record.setdefault("artifacts", {})
    checks = full_record.setdefault("checks", [])
    for key, ref in grafts.items():
        if isinstance(ref, str):
            full_artifacts[key] = ref
    for check in [
        "live_apply_plan_record_indexed",
        "live_apply_plan_summary_appended",
        "approval_intent_record_indexed",
        "approval_intent_summary_appended",
    ]:
        if check not in checks:
            checks.append(check)
    full_summary.write_text(json.dumps(full_record, indent=2) + "\n", encoding="utf-8")
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
