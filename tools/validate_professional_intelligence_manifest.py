#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

try:
    import yaml  # pyyaml
except Exception:
    print("ERR: missing dependency pyyaml (pip install pyyaml)", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "professional-intelligence.manifest.yaml"

REQUIRED_TOP_LEVEL = ["apiVersion", "kind", "metadata", "principles", "capabilities", "demoAcceptance"]
REQUIRED_WORKSPACE_OS_KEYS = [
    "status",
    "ownerRepos",
    "runtimeRepo",
    "contractPaths",
    "controlRefs",
    "recoveredSubstrateRefs",
    "notes",
]
REQUIRED_WORKSPACE_OS_CONTRACTS = {
    "SocioProphet/prophet-workspace:contracts/workspace/workroom.schema.json",
    "SocioProphet/prophet-workspace:contracts/workspace/professional-workroom.schema.json",
    "SocioProphet/prophet-workspace:contracts/workspace/professional-workroom.v0.1.example.json",
}
REQUIRED_WORKSPACE_OS_CONTROLS = {
    "SocioProphet/prophet-workspace:docs/workroom-substrate-alignment-v0.md",
    "SocioProphet/prophet-workspace:tools/validate_professional_workrooms.py",
    "SocioProphet/workspace-inventory:inventory/estate-overlays/prophet-workspace-workroom-substrate.yaml",
    "SocioProphet/systems-learning-loops:kb/receipts/prophet-workspace-workroom-substrate.receipt.yaml",
}
REQUIRED_RECOVERED_REFS = {
    "policyDecisionRefs",
    "topicPackRefs",
    "memoryScopeRefs",
    "privacyDecisionRefs",
    "audioReviewRefs",
    "learningReceiptRefs",
    "semanticReceiptRefs",
    "adoptionEventRefs",
}
CLAIM_BOUNDARY_REQUIREMENTS = [
    "Contract alignment does not imply runtime implementation.",
    "Runtime implementation does not imply demo readiness without evidence and adoption telemetry.",
    "Prophet Workspace owns workroom product semantics; Prophet Platform owns runtime deployment and service composition.",
]


def fail(message: str) -> int:
    print(f"ERR: {message}", file=sys.stderr)
    return 1


def expect_mapping(value: object, label: str) -> bool:
    if isinstance(value, dict):
        return True
    print(f"ERR: {label} must be a mapping/object", file=sys.stderr)
    return False


def expect_nonempty_list(value: object, label: str) -> bool:
    if isinstance(value, list) and value:
        return True
    print(f"ERR: {label} must be a non-empty list", file=sys.stderr)
    return False


def require_set_contains(values: object, required: set[str], label: str) -> int:
    if not isinstance(values, list):
        print(f"ERR: {label} must be a list", file=sys.stderr)
        return 1
    actual = set(values)
    missing = sorted(required - actual)
    if missing:
        print(f"ERR: {label} missing required values: {missing}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if not MANIFEST.exists():
        return fail(f"missing {MANIFEST.relative_to(ROOT)}")

    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    if not expect_mapping(data, "manifest"):
        return 2
    assert isinstance(data, dict)

    bad = 0
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            print(f"ERR: manifest missing top-level key {key!r}", file=sys.stderr)
            bad += 1

    metadata = data.get("metadata")
    if not expect_mapping(metadata, "metadata"):
        bad += 1
    elif metadata.get("name") != "professional-intelligence-os":
        print("ERR: metadata.name must be professional-intelligence-os", file=sys.stderr)
        bad += 1

    if not expect_nonempty_list(data.get("principles"), "principles"):
        bad += 1

    capabilities = data.get("capabilities")
    if not expect_mapping(capabilities, "capabilities"):
        bad += 1
        capabilities = {}
    assert isinstance(capabilities, dict)

    workspace_os = capabilities.get("workspaceOS")
    if not expect_mapping(workspace_os, "capabilities.workspaceOS"):
        bad += 1
        workspace_os = {}
    assert isinstance(workspace_os, dict)

    for key in REQUIRED_WORKSPACE_OS_KEYS:
        if key not in workspace_os:
            print(f"ERR: workspaceOS missing key {key!r}", file=sys.stderr)
            bad += 1

    if workspace_os.get("status") != "contract-aligned":
        print("ERR: workspaceOS.status must be contract-aligned for this manifest tranche", file=sys.stderr)
        bad += 1

    if workspace_os.get("runtimeRepo") != "SocioProphet/prophet-platform":
        print("ERR: workspaceOS.runtimeRepo must remain SocioProphet/prophet-platform", file=sys.stderr)
        bad += 1

    owner_repos = workspace_os.get("ownerRepos", [])
    bad += require_set_contains(owner_repos, {"SocioProphet/prophet-workspace"}, "workspaceOS.ownerRepos")
    bad += require_set_contains(workspace_os.get("contractPaths", []), REQUIRED_WORKSPACE_OS_CONTRACTS, "workspaceOS.contractPaths")
    bad += require_set_contains(workspace_os.get("controlRefs", []), REQUIRED_WORKSPACE_OS_CONTROLS, "workspaceOS.controlRefs")
    bad += require_set_contains(workspace_os.get("recoveredSubstrateRefs", []), REQUIRED_RECOVERED_REFS, "workspaceOS.recoveredSubstrateRefs")

    claim_boundary = data.get("claimBoundary", [])
    bad += require_set_contains(claim_boundary, set(CLAIM_BOUNDARY_REQUIREMENTS), "claimBoundary")

    demo_required = data.get("demoAcceptance", {}).get("required") if isinstance(data.get("demoAcceptance"), dict) else None
    if not expect_nonempty_list(demo_required, "demoAcceptance.required"):
        bad += 1

    if bad:
        return 2

    print("OK: professional-intelligence.manifest.yaml structure valid")
    print("OK: workspaceOS contract-aligned evidence present")
    print("OK: claim boundaries present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
