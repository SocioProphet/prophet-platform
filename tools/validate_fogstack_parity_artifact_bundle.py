#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "artifacts" / "runtime" / "fogstack-parity-readiness"
RECORD = BUNDLE / "fogstack-parity-readiness.record.json"
SUMMARY = BUNDLE / "fogstack-local-demo.full.summary.json"
INDEX = BUNDLE / "demo-artifacts.index.json"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def main() -> int:
    problems: list[str] = []

    for path in (RECORD, SUMMARY, INDEX):
        if not path.exists():
            problems.append(f"missing required bundle file: {path.relative_to(ROOT)}")

    if problems:
        print(json.dumps({"passed": False, "problems": problems}, indent=2))
        return 1

    record = load(RECORD)
    summary = load(SUMMARY)
    index = load(INDEX)

    if record.get("kind") != "FogStackParityReadinessRecord":
        problems.append("parity record kind mismatch")
    if record.get("status") != "passed":
        problems.append("parity record must be passed")
    if record.get("errors") != []:
        problems.append("parity record errors must be empty")
    if record.get("parity_target") != "credible-mvp-ibm-style-parity":
        problems.append("parity target mismatch")

    if summary.get("kind") != "FogStackLocalDemoFullRun":
        problems.append("summary kind mismatch")
    if summary.get("status") != "passed":
        problems.append("summary must be passed")

    if index.get("kind") != "FogStackLocalDemoArtifactIndex":
        problems.append("artifact index kind mismatch")

    refs = []
    for item in index.get("artifacts", []):
        if isinstance(item, dict) and item.get("ref"):
            refs.append((item.get("id"), str(item["ref"]), item.get("digest")))

    if len(refs) < 40:
        problems.append(f"expected at least 40 artifact refs, found {len(refs)}")

    for artifact_id, ref, digest in refs:
        if "/tmp/fogstack-parity-readiness" in ref:
            problems.append(f"{artifact_id}: tmp ref is not portable: {ref}")
            continue
        path = ROOT / ref if not Path(ref).is_absolute() else Path(ref)
        if not path.exists():
            problems.append(f"{artifact_id}: referenced artifact missing: {ref}")
            continue
        if digest and digest != sha256_file(path):
            problems.append(f"{artifact_id}: digest mismatch")

    checked = {item.get("id"): item.get("status") for item in record.get("checked_lanes", []) if isinstance(item, dict)}
    expected = {
        "node_inventory": "passed",
        "immutable_update_readiness": "passed",
        "cluster_readiness": "passed",
        "gitops_readiness": "passed",
        "live_cluster_preflight": "blocked",
        "live_apply_plan": "blocked",
        "runtime_adapter": "passed",
        "runtime_dry_run": "passed",
    }
    for lane, status in expected.items():
        if checked.get(lane) != status:
            problems.append(f"{lane}: expected {status}, got {checked.get(lane)}")

    non_claims = [
        "Validator checks persisted FogStack parity evidence artifacts only.",
        "Validator does not execute infrastructure.",
        "Validator does not mutate a cluster.",
        "Validator does not authorize live apply.",
        "Validator does not certify full Signadot feature parity."
    ]
    report = {
        "validator": "prophet-platform.fogstack-parity-artifact-bundle.validator.v1",
        "passed": not problems,
        "problems": problems,
        "bundle": str(BUNDLE.relative_to(ROOT)),
        "artifact_refs": len(refs),
        "non_claims": non_claims,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": FogStack parity artifact bundle")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
