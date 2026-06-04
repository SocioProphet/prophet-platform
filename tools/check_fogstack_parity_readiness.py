#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SUMMARY_ARTIFACTS = {
    "local_demo_summary",
    "local_demo_markdown",
    "local_demo_html",
    "artifact_index",
    "deploy_summary",
    "node_inventory_record",
    "immutable_update_readiness_record",
    "deploy_plan",
    "agent_corps_plan",
    "cluster_readiness_record",
    "gitops_bundle",
    "gitops_application",
    "gitops_kustomization",
    "gitops_readiness_record",
    "live_cluster_preflight_record",
    "live_apply_plan_record",
    "runtime_adapter",
    "runtime_dry_run_record",
}
REQUIRED_INDEX_IDS = {
    "deploy_node_profile",
    "deploy_node_inventory_record",
    "deploy_immutable_update_readiness_record",
    "deploy_agent_corps_plan",
    "deploy_plan",
    "deploy_kubernetes_configmap",
    "deploy_kubernetes_deployment",
    "deploy_kubernetes_service",
    "deploy_kubernetes_manifest_check_record",
    "deploy_cluster_readiness_record",
    "deploy_gitops_bundle",
    "deploy_gitops_application",
    "deploy_gitops_kustomization",
    "deploy_gitops_configmap",
    "deploy_gitops_deployment",
    "deploy_gitops_service",
    "deploy_gitops_readiness_record",
    "deploy_live_cluster_preflight_record",
    "deploy_live_apply_plan_record",
    "deploy_runtime_adapter",
    "deploy_runtime_dry_run_record",
    "deploy_summary",
}


def path_from_ref(ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_artifact_files(artifacts: dict[str, Any], errors: list[str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for artifact_id in sorted(REQUIRED_SUMMARY_ARTIFACTS):
        ref = artifacts.get(artifact_id)
        if not isinstance(ref, str):
            errors.append(f"missing summary artifact: {artifact_id}")
            continue
        path = path_from_ref(ref)
        paths[artifact_id] = path
        require(path.exists() and path.is_file(), f"summary artifact missing on disk: {artifact_id} {ref}", errors)
    return paths


def check_index(index: dict[str, Any], errors: list[str]) -> None:
    require(index.get("kind") == "FogStackLocalDemoArtifactIndex", "artifact index kind mismatch", errors)
    entries = {entry.get("id"): entry for entry in index.get("artifacts", []) if isinstance(entry, dict)}
    for artifact_id in sorted(REQUIRED_INDEX_IDS):
        entry = entries.get(artifact_id)
        if not entry:
            errors.append(f"artifact index missing id: {artifact_id}")
            continue
        ref = entry.get("ref")
        digest = entry.get("digest")
        if not isinstance(ref, str):
            errors.append(f"artifact index missing ref: {artifact_id}")
            continue
        path = path_from_ref(ref)
        require(path.exists() and path.is_file(), f"artifact index file missing: {artifact_id} {ref}", errors)
        if path.exists() and path.is_file():
            require(digest == sha256_file(path), f"artifact index digest mismatch: {artifact_id}", errors)


def check_svf_signadot_adapter_readiness(errors: list[str]) -> dict[str, str] | None:
    proc = subprocess.run(
        [sys.executable, "tools/validate_fogstack_svf_signadot_adapter_readiness.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
        errors.append(f"SVF Signadot adapter readiness validator failed: {detail}")
        return None
    return {
        "id": "svf_signadot_adapter_readiness",
        "status": "passed",
        "mode": "contract-fixture-only",
    }


def check_records(paths: dict[str, Path], errors: list[str]) -> list[dict[str, str]]:
    checked: list[dict[str, str]] = []

    node_inventory = load_json(paths["node_inventory_record"])
    require(node_inventory.get("kind") == "FogStackAgentMachineNodeInventoryRecord", "node inventory kind mismatch", errors)
    require(node_inventory.get("status") == "passed", "node inventory did not pass", errors)
    require(node_inventory.get("storage", {}).get("topolvm_required") is True, "node inventory does not require TopoLVM for default SourceOS node", errors)
    require(node_inventory.get("storage", {}).get("persistent_storage") == "topolvm", "node inventory persistent storage is not TopoLVM", errors)
    surfaces = {surface.get("id"): surface for surface in node_inventory.get("agent_machine", {}).get("use_surfaces", []) if isinstance(surface, dict)}
    for surface_id, expected_ref in {
        "turtleterm": "github://SourceOS-Linux/TurtleTerm",
        "bearbrowser": "github://SourceOS-Linux/BearBrowser",
    }.items():
        surface = surfaces.get(surface_id)
        require(isinstance(surface, dict), f"missing required use surface: {surface_id}", errors)
        if surface:
            require(surface.get("repo_ref") == expected_ref, f"wrong repo ref for surface: {surface_id}", errors)
            require(surface.get("agentplane_visible") is True, f"surface not AgentPlane-visible: {surface_id}", errors)
            require(surface.get("policyplane_guarded") is True, f"surface not PolicyPlane-guarded: {surface_id}", errors)
    checked.append({"id": "node_inventory", "status": "passed"})

    immutable_update = load_json(paths["immutable_update_readiness_record"])
    require(immutable_update.get("kind") == "FogStackImmutableUpdateReadinessRecord", "immutable update kind mismatch", errors)
    require(immutable_update.get("status") == "passed", "immutable update readiness did not pass", errors)
    require(all(immutable_update.get("readiness", {}).values()), "immutable update readiness flags are not all true", errors)
    require(immutable_update.get("policy", {}).get("live_update_allowed") is False, "immutable update allows live update", errors)
    checked.append({"id": "immutable_update_readiness", "status": "passed"})

    cluster = load_json(paths["cluster_readiness_record"])
    require(cluster.get("kind") == "FogStackClusterReadinessRecord", "cluster readiness kind mismatch", errors)
    require(cluster.get("status") == "passed", "cluster readiness did not pass", errors)
    checked.append({"id": "cluster_readiness", "status": "passed"})

    gitops = load_json(paths["gitops_readiness_record"])
    require(gitops.get("kind") == "FogStackGitOpsReadinessRecord", "GitOps readiness kind mismatch", errors)
    require(gitops.get("status") == "passed", "GitOps readiness did not pass", errors)
    require(gitops.get("validation_result", {}).get("bundle_validated") is True, "GitOps bundle was not validated", errors)
    checked.append({"id": "gitops_readiness", "status": "passed"})

    live_preflight = load_json(paths["live_cluster_preflight_record"])
    require(live_preflight.get("kind") == "FogStackLiveClusterPreflightRecord", "live cluster preflight kind mismatch", errors)
    require(live_preflight.get("status") in {"passed", "blocked"}, "live cluster preflight must pass or block safely", errors)
    require(live_preflight.get("mode") == "read-only-live-preflight", "live cluster preflight mode mismatch", errors)
    safety = live_preflight.get("safety", {})
    require(safety.get("mutated_cluster") is False, "live cluster preflight mutated cluster", errors)
    require(safety.get("live_apply_allowed") is False, "live cluster preflight allows live apply", errors)
    require(safety.get("human_approval_required_for_apply") is True, "live cluster preflight does not require human approval", errors)
    checked.append({"id": "live_cluster_preflight", "status": str(live_preflight.get("status"))})

    apply_plan = load_json(paths["live_apply_plan_record"])
    require(apply_plan.get("kind") == "FogStackLiveApplyPlanRecord", "live apply plan kind mismatch", errors)
    require(apply_plan.get("status") in {"passed", "blocked"}, "live apply plan must pass or block safely", errors)
    require(apply_plan.get("mode") == "plan-only", "live apply plan mode mismatch", errors)
    apply_safety = apply_plan.get("safety", {})
    require(apply_safety.get("plan_only") is True, "live apply plan is not plan-only", errors)
    require(apply_safety.get("run_performed") is False, "live apply plan performed a run", errors)
    require(apply_safety.get("mutated_cluster") is False, "live apply plan mutated cluster", errors)
    require(apply_safety.get("live_apply_allowed") is False, "live apply plan allows live apply", errors)
    require(apply_safety.get("future_approval_record_required") is True, "live apply plan does not require future approval", errors)
    require(apply_safety.get("rollback_plan_required") is True, "live apply plan does not require rollback plan", errors)
    require(apply_plan.get("agentplane", {}).get("agentplane_ref") == "github://SocioProphet/agentplane", "live apply plan AgentPlane ref mismatch", errors)
    require(apply_plan.get("policyplane", {}).get("policyplane_ref") == "github://SocioProphet/policy-fabric", "live apply plan PolicyPlane ref mismatch", errors)
    require(apply_plan.get("policyplane", {}).get("decision") == "allow-plan-deny-run", "live apply plan PolicyPlane decision mismatch", errors)
    checked.append({"id": "live_apply_plan", "status": str(apply_plan.get("status"))})

    runtime_adapter = load_json(paths["runtime_adapter"])
    require(runtime_adapter.get("kind") == "FogStackLocalClusterRuntimeAdapter", "runtime adapter kind mismatch", errors)
    require(runtime_adapter.get("runtime_policy", {}).get("live_apply_allowed") is False, "runtime adapter allows live apply", errors)
    checked.append({"id": "runtime_adapter", "status": "passed"})

    runtime = load_json(paths["runtime_dry_run_record"])
    require(runtime.get("kind") == "FogStackRuntimeDryRunRecord", "runtime dry-run kind mismatch", errors)
    require(runtime.get("status") == "passed", "runtime dry-run did not pass", errors)
    require(runtime.get("dry_run_result", {}).get("mutated_cluster") is False, "runtime dry-run mutated cluster", errors)
    require(runtime.get("dry_run_result", {}).get("validation_path") == "contract-and-digest-only", "runtime dry-run validation path mismatch", errors)
    require(runtime.get("runtime_policy", {}).get("live_apply_allowed") is False, "runtime dry-run allows live apply", errors)
    agentplane = runtime.get("agentplane_run", {})
    require(agentplane.get("agentplane_ref") == "github://SocioProphet/agentplane", "AgentPlane ref mismatch", errors)
    require(agentplane.get("approval_state") == "live-apply-requires-human-approval", "AgentPlane approval state mismatch", errors)
    policy = runtime.get("policyplane_decision", {})
    require(policy.get("policyplane_ref") == "github://SocioProphet/policy-fabric", "PolicyPlane ref mismatch", errors)
    require(policy.get("effect") == "allow-dry-run-deny-live-apply", "PolicyPlane effect mismatch", errors)
    require(policy.get("live_apply_allowed") is False, "PolicyPlane allows live apply", errors)
    require(policy.get("human_approval_required") is True, "PolicyPlane does not require human approval", errors)
    checked.append({"id": "runtime_dry_run", "status": "passed"})

    svf_lane = check_svf_signadot_adapter_readiness(errors)
    if svf_lane is not None:
        checked.append(svf_lane)

    for artifact_id in ["deploy_plan", "agent_corps_plan", "gitops_bundle", "gitops_application", "gitops_kustomization"]:
        require(paths[artifact_id].exists(), f"required artifact missing: {artifact_id}", errors)
        checked.append({"id": artifact_id, "status": "present"})

    return checked


def build_record(summary_path: Path, index_path: Path, output_path: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    index = load_json(index_path)
    errors: list[str] = []
    require(summary.get("kind") == "FogStackLocalDemoFullRun", "full summary kind mismatch", errors)
    require(summary.get("status") == "passed", "full summary status is not passed", errors)
    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("ERR: full summary artifacts must be an object")
    paths = check_artifact_files(artifacts, errors)
    check_index(index, errors)
    checked = check_records(paths, errors) if not errors else []
    record = {
        "kind": "FogStackParityReadinessRecord",
        "schema_version": "v0.1",
        "status": "failed" if errors else "passed",
        "parity_target": "credible-mvp-ibm-style-parity",
        "turn_counter": "31/32",
        "summary_ref": str(summary_path.relative_to(ROOT)) if summary_path.is_relative_to(ROOT) else str(summary_path),
        "summary_digest": sha256_file(summary_path),
        "artifact_index_ref": str(index_path.relative_to(ROOT)) if index_path.is_relative_to(ROOT) else str(index_path),
        "artifact_index_digest": sha256_file(index_path),
        "checked_lanes": checked,
        "required_summary_artifacts": sorted(REQUIRED_SUMMARY_ARTIFACTS),
        "required_index_ids": sorted(REQUIRED_INDEX_IDS),
        "errors": errors,
    }
    write_json(output_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Check FogStack credible-MVP parity readiness from full local demo evidence")
    parser.add_argument("--summary", type=Path, default=Path("build/fogstack-local-demo/fogstack-local-demo.full.summary.json"))
    parser.add_argument("--index", type=Path, default=Path("build/fogstack-local-demo/demo-artifacts.index.json"))
    parser.add_argument("--output", type=Path, default=Path("build/fogstack-local-demo/fogstack-parity-readiness.record.json"))
    parser.add_argument("--summary-text", action="store_true")
    args = parser.parse_args()

    summary_path = path_from_ref(str(args.summary))
    index_path = path_from_ref(str(args.index))
    output_path = path_from_ref(str(args.output))
    record = build_record(summary_path, index_path, output_path)
    if args.summary_text:
        print(f"FogStack parity readiness: {record['status']}")
        print(f"Parity target: {record['parity_target']}")
        print(f"Checked lanes: {len(record['checked_lanes'])}")
        print(f"Output: {args.output}")
    else:
        print(json.dumps(record, indent=2))
    if record["status"] != "passed":
        for error in record["errors"]:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
