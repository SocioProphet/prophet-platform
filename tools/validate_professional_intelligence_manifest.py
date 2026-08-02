#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
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
    "contracts/workspace/workroom-update-request.example.json",
    "contracts/workspace/workroom-update-response.accepted.example.json",
    "contracts/workspace/workroom-update-response.invalid-runtime-mutation.example.json",
}
REQUIRED_WORKSPACE_OS_CONTROLS = {
    "SocioProphet/prophet-workspace:docs/workroom-substrate-alignment-v0.md",
    "SocioProphet/prophet-workspace:tools/validate_professional_workrooms.py",
    "docs/WORKROOM_UPDATE_RUNTIME_BOUNDARY.md",
    "tools/validate_workroom_update_contract.py",
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


# Estate refs are written `<org>/<repo>:<path>`. The org is matched against a
# known set rather than any `<a>/<b>:` shape so that an unrecognised prefix
# falls through to the LOCAL side, where it gets stat'd and fails loudly if it
# is not there. The costly direction of a misclassification is the other one:
# anything routed to the cross-repo side is skipped, and a wrongly-skipped ref
# is precisely the unverified-declaration gap this check exists to close. If a
# new estate org appears, adding it here is a deliberate act.
ESTATE_ORGS = frozenset({"SocioProphet"})
CROSS_REPO_REF = re.compile(r"^(?P<org>[A-Za-z0-9._-]+)/[A-Za-z0-9._-]+:.+$")


def is_cross_repo_ref(ref: str) -> bool:
    """True for refs that name another estate repo, e.g. `SocioProphet/x:path`.

    Cross-repo refs point outside this checkout, so their target cannot be
    stat'd from here -- see require_declared_paths_exist().
    """
    match = CROSS_REPO_REF.match(ref)
    return match is not None and match.group("org") in ESTATE_ORGS


def require_declared_paths_exist(required: set[str], label: str) -> int:
    """Stat the in-repo evidence this manifest claims alignment against.

    require_set_contains() only proves the manifest *lists* a path. Listing is
    a declaration about the world; this function checks the world. Without it
    the manifest can claim contract alignment against files that were deleted
    or never existed, and the tool still prints its OK banner and exits 0.

    Cross-repo refs (`SocioProphet/<repo>:<path>`) resolve into peer repos that
    are not present in this checkout, so they CANNOT be verified here and are
    skipped deliberately. The skip is printed rather than silent: an unreported
    skip is how a declared-but-unverified ref creeps back in. Verifying those
    belongs to the owning repo's own validator.
    """
    local_refs = sorted(r for r in required if not is_cross_repo_ref(r))
    skipped = sorted(r for r in required if is_cross_repo_ref(r))

    if skipped:
        print(
            f"SKIP: {label}: {len(skipped)} cross-repo ref(s) not stat-able from this "
            f"checkout, not verified here: {skipped}"
        )

    missing = [ref for ref in local_refs if not (ROOT / ref).exists()]
    if missing:
        for ref in missing:
            print(
                f"ERR: {label} declares {ref!r} but that path does not exist in this repo",
                file=sys.stderr,
            )
        return 1

    print(f"OK: {label}: {len(local_refs)} in-repo evidence path(s) exist on disk")
    return 0


def main() -> int:
    if not MANIFEST.exists():
        return fail(f"missing {MANIFEST.relative_to(ROOT)}")

    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    if not expect_mapping(data, "manifest"):
        return 2
    # `data` is a mapping from here on, and that is enforced above rather than
    # asserted. expect_mapping() is a plain isinstance test that prints ERR and
    # returns False, so `python -O` cannot strip it -- unlike the bare
    # `assert isinstance(data, dict)` that used to sit on this line. That assert
    # was a narrowing hint for a type checker this repo does not run, and it
    # could never fire: a non-mapping manifest has already returned 2 one line
    # up. Removing it closes the "assert evaporates under -O" finding here
    # without changing behaviour on any input. The -O behaviour of all three
    # shape guards in this function is now pinned by
    # tools/tests/test_professional_intelligence_manifest_shape.py.

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
    # Both branches leave a dict behind -- expect_mapping() proved one, the
    # fallback assigned the other -- so the removed `assert isinstance(...)`
    # here was unreachable-with-a-false-condition, not a check. The real
    # rejection is the `bad += 1` above, which survives -O. Normalising to {}
    # rather than returning is deliberate: it lets the run keep accumulating
    # every downstream error instead of stopping at the first one.

    workspace_os = capabilities.get("workspaceOS")
    if not expect_mapping(workspace_os, "capabilities.workspaceOS"):
        bad += 1
        workspace_os = {}
    # Same shape as the capabilities guard above: enforced by expect_mapping()
    # plus the {} fallback, so the removed assert added nothing at runtime.

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

    # The two require_set_contains() calls above only prove the manifest LISTS
    # these refs. Stat the in-repo ones so "contract-aligned" cannot be claimed
    # against files that are no longer there. Driven off the same constants the
    # listing checks use, so the two can never drift apart.
    bad += require_declared_paths_exist(REQUIRED_WORKSPACE_OS_CONTRACTS, "workspaceOS.contractPaths")
    bad += require_declared_paths_exist(REQUIRED_WORKSPACE_OS_CONTROLS, "workspaceOS.controlRefs")
    bad += require_set_contains(workspace_os.get("recoveredSubstrateRefs", []), REQUIRED_RECOVERED_REFS, "workspaceOS.recoveredSubstrateRefs")

    claim_boundary = data.get("claimBoundary", [])
    bad += require_set_contains(claim_boundary, set(CLAIM_BOUNDARY_REQUIREMENTS), "claimBoundary")

    # Route the shape check through expect_mapping() like every other field.
    # The old inline ternary collapsed a non-mapping demoAcceptance to None and
    # then blamed "demoAcceptance.required", naming a field that is not the
    # problem. Same fail-closed outcome, correct diagnosis.
    demo_acceptance = data.get("demoAcceptance")
    if not expect_mapping(demo_acceptance, "demoAcceptance"):
        bad += 1
    elif not expect_nonempty_list(demo_acceptance.get("required"), "demoAcceptance.required"):
        bad += 1

    if bad:
        return 2

    print("OK: professional-intelligence.manifest.yaml structure valid")
    print("OK: workspaceOS contract-aligned evidence present")
    print("OK: workroom update runtime boundary refs present")
    print("OK: workroom update invalid fixture is registered")
    print("OK: claim boundaries present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
