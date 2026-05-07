#!/usr/bin/env python3
"""Run the cross-repo sovereign orchestration interop proof.

This is a deterministic local runner for the proof documented in
`CROSS_REPO_INTEROP.md`. It does not actuate devices, call providers, collect
credentials, or retain camera media. It only runs fixture generation, policy
annotation, SourceOS queue/replay, AgentPlane admission when available, and
Sherlock evidence search.

Assumptions:
  - sibling repos live under ~/dev by default;
  - this script is run from SocioProphet/prophet-platform or via its path;
  - each sibling repo is already checked out locally.

Run:
  python specs/orchestration/cross_repo_interop_runner.py
  python specs/orchestration/cross_repo_interop_runner.py --dev-root ~/dev --out /tmp/sdo-cross-repo-event-loop
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_NAMES = {
    "prophet": "prophet-platform",
    "guardrail": "guardrail-fabric",
    "sourceos": "sourceos-syncd",
    "agentplane": "agentplane",
    "sherlock": "sherlock-search",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_step(name: str, command: list[str], *, cwd: Path, env: dict[str, str] | None = None, required: bool = True) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    status = "pass" if result.returncode == 0 else "fail"
    return {
        "name": name,
        "status": status,
        "required": required,
        "returncode": result.returncode,
        "cwd": str(cwd),
        "command": command,
        "output_tail": result.stdout[-4000:],
    }


def require_repo(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"missing {label} repo: {path}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the cross-repo event-native orchestration interop proof.")
    parser.add_argument("--dev-root", default=str(Path.home() / "dev"), help="directory containing sibling repos")
    parser.add_argument("--out", default="/tmp/sdo-cross-repo-event-loop", help="output artifact directory")
    parser.add_argument("--require-agentplane", action="store_true", help="fail if AgentPlane admission script is not available or does not pass")
    args = parser.parse_args(argv)

    dev_root = Path(args.dev_root).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    prophet = Path(__file__).resolve().parents[2]
    repos = {
        "prophet": prophet,
        "guardrail": dev_root / REPO_NAMES["guardrail"],
        "sourceos": dev_root / REPO_NAMES["sourceos"],
        "agentplane": dev_root / REPO_NAMES["agentplane"],
        "sherlock": dev_root / REPO_NAMES["sherlock"],
    }

    for key in ("prophet", "guardrail", "sourceos", "sherlock"):
        require_repo(repos[key], key)
    if args.require_agentplane:
        require_repo(repos["agentplane"], "agentplane")

    out.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []

    prophet_out = out / "prophet"
    steps.append(
        run_step(
            "prophet.world_class_event_loop_demo",
            [sys.executable, "specs/orchestration/world_class_event_loop_demo.py", "--out", str(prophet_out), "--compact"],
            cwd=repos["prophet"],
        )
    )

    guardrail_records = out / "event-capability.guardrail-annotated.records.json"
    steps.append(
        run_step(
            "guardrail.annotate_event_capabilities",
            [
                sys.executable,
                "-m",
                "guardrail_fabric.event_capability_cli",
                "--input",
                str(prophet_out / "event-capability.records.json"),
                "--out",
                str(guardrail_records),
            ],
            cwd=repos["guardrail"],
        )
    )

    sourceos_root = out / "sourceos-queue"
    sourceos_env = {"PYTHONPATH": str(repos["sourceos"] / "src")}
    sourceos_commands = [
        ("sourceos.queue_init", [sys.executable, "-m", "sourceos_syncd.cli", "orchestration", "init", "--root", str(sourceos_root), "--compact"]),
        ("sourceos.queue_enqueue", [sys.executable, "-m", "sourceos_syncd.cli", "orchestration", "enqueue", "--root", str(sourceos_root), "--file", str(guardrail_records), "--compact"]),
        ("sourceos.queue_summary", [sys.executable, "-m", "sourceos_syncd.cli", "orchestration", "summary", "--root", str(sourceos_root), "--compact"]),
        ("sourceos.queue_pending", [sys.executable, "-m", "sourceos_syncd.cli", "orchestration", "list", "--root", str(sourceos_root), "--state", "pending", "--compact"]),
        ("sourceos.queue_waiting", [sys.executable, "-m", "sourceos_syncd.cli", "orchestration", "list", "--root", str(sourceos_root), "--state", "waiting-approval", "--compact"]),
        ("sourceos.queue_blocked", [sys.executable, "-m", "sourceos_syncd.cli", "orchestration", "list", "--root", str(sourceos_root), "--state", "blocked", "--compact"]),
        ("sourceos.queue_replay_pending", [sys.executable, "-m", "sourceos_syncd.cli", "orchestration", "replay", "--root", str(sourceos_root), "--state", "pending", "--compact"]),
    ]
    for name, command in sourceos_commands:
        steps.append(run_step(name, command, cwd=repos["sourceos"], env=sourceos_env))

    agentplane_admission = out / "agentplane-admission.artifact.json"
    agentplane_script = repos["agentplane"] / "scripts" / "validate_event_capability_admission.py"
    if agentplane_script.exists():
        steps.append(
            run_step(
                "agentplane.admission",
                [sys.executable, str(agentplane_script), "--input", str(guardrail_records), "--out", str(agentplane_admission)],
                cwd=repos["agentplane"],
                required=args.require_agentplane,
            )
        )
    else:
        steps.append(
            {
                "name": "agentplane.admission",
                "status": "skipped",
                "required": args.require_agentplane,
                "returncode": None,
                "cwd": str(repos["agentplane"]),
                "command": [sys.executable, str(agentplane_script), "--input", str(guardrail_records)],
                "output_tail": "AgentPlane admission script not found. PR #130 may not be merged locally yet.",
            }
        )

    searches = [
        ("sherlock.search_security_approval", "security approval", out / "sherlock-security-approval.search.json"),
        ("sherlock.search_camera_denied", "camera media denied", out / "sherlock-camera-denied.search.json"),
        ("sherlock.search_fan_allowed", "fan temperature allowed", out / "sherlock-fan-allowed.search.json"),
    ]
    for name, query, target in searches:
        steps.append(
            run_step(
                name,
                [sys.executable, "tools/search_event_capability_records.py", "--index", str(guardrail_records), "--query", query, "--out", str(target)],
                cwd=repos["sherlock"],
            )
        )

    required_failures = [step for step in steps if step["required"] and step["status"] != "pass"]
    optional_failures = [step for step in steps if not step["required"] and step["status"] not in {"pass", "skipped"}]

    report = {
        "schema": "sdo.cross-repo-event-loop-interop.v0.1",
        "created_at": utc_now(),
        "status": "pass" if not required_failures else "fail",
        "dev_root": str(dev_root),
        "out": str(out),
        "steps": steps,
        "summary": {
            "total": len(steps),
            "passed": sum(1 for step in steps if step["status"] == "pass"),
            "skipped": sum(1 for step in steps if step["status"] == "skipped"),
            "required_failures": len(required_failures),
            "optional_failures": len(optional_failures),
        },
        "artifacts": {
            "prophet_demo_report": str(prophet_out / "demo-report.json"),
            "guardrail_records": str(guardrail_records),
            "sourceos_queue_root": str(sourceos_root),
            "agentplane_admission": str(agentplane_admission) if agentplane_admission.exists() else None,
            "sherlock_security_search": str(out / "sherlock-security-approval.search.json"),
            "sherlock_camera_search": str(out / "sherlock-camera-denied.search.json"),
            "sherlock_fan_search": str(out / "sherlock-fan-allowed.search.json"),
        },
    }

    write_json(out / "cross-repo-interop-report.json", report)
    print("cross-repo event loop interop " + report["status"])
    print("out=" + str(out))
    print(json.dumps(report["summary"], sort_keys=True))
    if required_failures:
        for failure in required_failures:
            print("FAILED: " + failure["name"], file=sys.stderr)
            print(failure["output_tail"], file=sys.stderr)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
