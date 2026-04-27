#!/usr/bin/env python3
"""CLI for Lattice Studio governed notebook sessions, catalog assets, and local/PaaS lanes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .atlas import atlas_evidence, atlas_to_platform_record, demo_atlas_context
from .catalog import catalog_evidence, demo_catalog_assets
from .execution import demo_execution_record, execution_evidence, execution_to_platform_record
from .lampstand import (
    context_pack_for_results,
    demo_local_search_results,
    local_search_result_to_platform_record,
    promotion_proposals_for_results,
)
from .local_dev import create_local_dev_session, local_dev_to_platform_record
from .memory import memory_event, memory_event_set
from .notebook_plane import (
    demo_notebook_surface_plane,
    demo_spawn_requests,
    notebook_plane_to_platform_record,
    notebook_surface_evidence,
)
from .ontogenesis import demo_ontogenesis_context, ontogenesis_evidence, ontogenesis_to_platform_record
from .paas import create_deployment_plan, deployment_evidence, deployment_to_platform_record
from .platform_records import catalog_asset_to_platform_record, notebook_session_to_platform_record, platform_record_set
from .session import create_session, load_json, write_session_bundle


def create_notebook_session(args: argparse.Namespace) -> int:
    runtime_asset = load_json(args.runtime_asset)
    catalog_inputs = args.catalog_input or []
    session = create_session(
        project_id=args.project_id,
        user_id=args.user_id,
        runtime_asset=runtime_asset,
        catalog_inputs=catalog_inputs,
        policy_ref=args.policy_ref,
    )
    written = write_session_bundle(session, args.output_dir)
    print(json.dumps({"written": [str(path) for path in written]}, indent=2, sort_keys=True))
    return 0


def emit_demo_catalog(args: argparse.Namespace) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for asset in demo_catalog_assets():
        asset_dir_name = asset.catalog_asset_id.replace("catalog://", "").replace("/", "_")
        asset_dir = args.output_dir / asset_dir_name
        asset_dir.mkdir(parents=True, exist_ok=True)
        asset_path = asset_dir / "catalog-asset.json"
        evidence_path = asset_dir / "catalog-asset-evidence.json"
        asset_path.write_text(json.dumps(asset.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        evidence_path.write_text(json.dumps(catalog_evidence(asset), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.extend([asset_path, evidence_path])
    print(json.dumps({"written": [str(path) for path in written]}, indent=2, sort_keys=True))
    return 0


def emit_platform_records(args: argparse.Namespace) -> int:
    records = []
    for path in args.catalog_asset:
        records.append(catalog_asset_to_platform_record(load_json(path)))
    for path in args.notebook_session:
        records.append(notebook_session_to_platform_record(load_json(path)))
    for path in args.platform_record:
        records.append(load_json(path))
    payload = platform_record_set(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(args.output)], "recordCount": len(records)}, indent=2, sort_keys=True))
    return 0


def emit_atlas_context(args: argparse.Namespace) -> int:
    context = demo_atlas_context()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    context_path = args.output_dir / "atlas-context.json"
    evidence_path = args.output_dir / "atlas-context-evidence.json"
    record_path = args.output_dir / "atlas-platform-record.json"
    context_path.write_text(json.dumps(context.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(atlas_evidence(context), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(atlas_to_platform_record(context), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(context_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def emit_ontogenesis_context(args: argparse.Namespace) -> int:
    context = demo_ontogenesis_context()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    context_path = args.output_dir / "ontogenesis-context.json"
    evidence_path = args.output_dir / "ontogenesis-context-evidence.json"
    record_path = args.output_dir / "ontogenesis-platform-record.json"
    context_path.write_text(json.dumps(context.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(ontogenesis_evidence(context), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(ontogenesis_to_platform_record(context), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(context_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def emit_notebook_plane(args: argparse.Namespace) -> int:
    plane = demo_notebook_surface_plane()
    requests = demo_spawn_requests()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plane_path = args.output_dir / "notebook-surface-plane.json"
    requests_path = args.output_dir / "notebook-spawn-requests.json"
    evidence_path = args.output_dir / "notebook-surface-evidence.json"
    record_path = args.output_dir / "notebook-plane-platform-record.json"
    plane_path.write_text(json.dumps(plane.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    requests_path.write_text(json.dumps({"apiVersion": "studio.socioprophet.dev/v1", "kind": "NotebookSurfaceSpawnRequestSet", "requests": [request.to_dict() for request in requests]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(notebook_surface_evidence(plane, requests), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(notebook_plane_to_platform_record(plane), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(plane_path), str(requests_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def emit_paas_plan(args: argparse.Namespace) -> int:
    plan = create_deployment_plan(
        name=args.name,
        kind=args.kind,
        source_ref=args.source_ref,
        build_mode=args.build_mode,
        runtime_asset_id=args.runtime_asset_id,
        catalog_asset_refs=args.catalog_asset_ref or [],
        environment=args.environment,
        target_platform=args.target_platform,
        route=args.route,
        policy_ref=args.policy_ref,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.output_dir / "paas-deployment-plan.json"
    evidence_path = args.output_dir / "paas-deployment-evidence.json"
    record_path = args.output_dir / "paas-platform-record.json"
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(deployment_evidence(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(deployment_to_platform_record(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(plan_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def emit_local_dev(args: argparse.Namespace) -> int:
    session = create_local_dev_session(
        workspace_ref=args.workspace_ref,
        atlas_context_ref=args.atlas_context_ref,
        paas_deployment_ref=args.paas_deployment_ref,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    session_path = args.output_dir / "local-dev-session.json"
    record_path = args.output_dir / "local-dev-platform-record.json"
    session_path.write_text(json.dumps(session.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(local_dev_to_platform_record(session), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(session_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def emit_memory(args: argparse.Namespace) -> int:
    events = [
        memory_event(
            subject_ref=subject,
            event_type="lattice-studio.activity",
            summary=f"Recorded Lattice Studio activity for {subject}.",
            links=args.link or [],
        )
        for subject in args.subject
    ]
    payload = memory_event_set(events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(args.output)], "eventCount": len(events)}, indent=2, sort_keys=True))
    return 0


def emit_lampstand_demo(args: argparse.Namespace) -> int:
    results = demo_local_search_results()
    context_pack = context_pack_for_results(results, workspace_ref=args.workspace_ref)
    proposals = promotion_proposals_for_results(results)
    platform_records = [local_search_result_to_platform_record(result) for result in results]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "lampstand-local-search-results.json"
    context_path = args.output_dir / "lampstand-context-pack.json"
    proposals_path = args.output_dir / "datahub-promotion-proposals.json"
    records_path = args.output_dir / "lampstand-platform-records.json"

    results_path.write_text(json.dumps({"apiVersion": "studio.socioprophet.dev/v1", "kind": "LampstandLocalSearchResultSet", "results": [result.to_dict() for result in results]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    context_path.write_text(json.dumps(context_pack.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    proposals_path.write_text(json.dumps({"apiVersion": "studio.socioprophet.dev/v1", "kind": "DataHubPromotionProposalSet", "proposals": [proposal.to_dict() for proposal in proposals]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    records_path.write_text(json.dumps(platform_record_set(platform_records), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(results_path), str(context_path), str(proposals_path), str(records_path)]}, indent=2, sort_keys=True))
    return 0


def emit_execution(args: argparse.Namespace) -> int:
    execution = demo_execution_record()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    execution_path = args.output_dir / "execution-record.json"
    evidence_path = args.output_dir / "execution-evidence.json"
    record_path = args.output_dir / "execution-platform-record.json"
    execution_path.write_text(json.dumps(execution.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(json.dumps(execution_evidence(execution), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record_path.write_text(json.dumps(execution_to_platform_record(execution), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"written": [str(execution_path), str(evidence_path), str(record_path)]}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lattice Studio governed notebook sessions, catalog assets, local dev, and PaaS lanes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-session", help="Create a governed NotebookSession bundle")
    create_parser.add_argument("--project-id", required=True)
    create_parser.add_argument("--user-id", required=True)
    create_parser.add_argument("--runtime-asset", type=Path, required=True)
    create_parser.add_argument("--catalog-input", action="append", default=[])
    create_parser.add_argument("--policy-ref")
    create_parser.add_argument("--output-dir", type=Path, required=True)
    create_parser.set_defaults(func=create_notebook_session)

    catalog_parser = subparsers.add_parser("emit-demo-catalog", help="Emit demo CatalogAsset bundles for data, ML, app, and service assets")
    catalog_parser.add_argument("--output-dir", type=Path, required=True)
    catalog_parser.set_defaults(func=emit_demo_catalog)

    records_parser = subparsers.add_parser("emit-platform-records", help="Convert Studio artifacts into PlatformAssetRecordSet")
    records_parser.add_argument("--catalog-asset", type=Path, action="append", default=[])
    records_parser.add_argument("--notebook-session", type=Path, action="append", default=[])
    records_parser.add_argument("--platform-record", type=Path, action="append", default=[])
    records_parser.add_argument("--output", type=Path, required=True)
    records_parser.set_defaults(func=emit_platform_records)

    atlas_parser = subparsers.add_parser("emit-atlas-context", help="Emit demo Atlas integration context")
    atlas_parser.add_argument("--output-dir", type=Path, required=True)
    atlas_parser.set_defaults(func=emit_atlas_context)

    ontogenesis_parser = subparsers.add_parser("emit-ontogenesis-context", help="Emit demo Ontogenesis semantic-governance context")
    ontogenesis_parser.add_argument("--output-dir", type=Path, required=True)
    ontogenesis_parser.set_defaults(func=emit_ontogenesis_context)

    notebook_plane_parser = subparsers.add_parser("emit-notebook-plane", help="Emit Notebook Surface Plane and adapter spawn requests")
    notebook_plane_parser.add_argument("--output-dir", type=Path, required=True)
    notebook_plane_parser.set_defaults(func=emit_notebook_plane)

    paas_parser = subparsers.add_parser("emit-paas-plan", help="Emit Cloud Foundry-style PaaS-over-Kubernetes deployment plan")
    paas_parser.add_argument("--name", required=True)
    paas_parser.add_argument("--kind", choices=["application", "service", "notebook-app", "agent-service"], default="service")
    paas_parser.add_argument("--source-ref", required=True)
    paas_parser.add_argument("--build-mode", choices=["buildpack", "dockerfile", "oci-image", "helm-chart"], default="buildpack")
    paas_parser.add_argument("--runtime-asset-id")
    paas_parser.add_argument("--catalog-asset-ref", action="append", default=[])
    paas_parser.add_argument("--environment", choices=["local-sourceos", "preview", "dev", "staging", "production"], default="preview")
    paas_parser.add_argument("--target-platform", default="kubernetes")
    paas_parser.add_argument("--route")
    paas_parser.add_argument("--policy-ref")
    paas_parser.add_argument("--output-dir", type=Path, required=True)
    paas_parser.set_defaults(func=emit_paas_plan)

    local_parser = subparsers.add_parser("emit-local-dev", help="Emit SourceOS/SociOS local notebook/terminal/browser/agent session")
    local_parser.add_argument("--workspace-ref", required=True)
    local_parser.add_argument("--atlas-context-ref")
    local_parser.add_argument("--paas-deployment-ref")
    local_parser.add_argument("--output-dir", type=Path, required=True)
    local_parser.set_defaults(func=emit_local_dev)

    memory_parser = subparsers.add_parser("emit-memory", help="Emit memory-mesh sidecar events for Studio activity")
    memory_parser.add_argument("--subject", action="append", required=True)
    memory_parser.add_argument("--link", action="append", default=[])
    memory_parser.add_argument("--output", type=Path, required=True)
    memory_parser.set_defaults(func=emit_memory)

    lampstand_parser = subparsers.add_parser("emit-lampstand-demo", help="Emit Lampstand local-search DataHub promotion demo artifacts")
    lampstand_parser.add_argument("--workspace-ref", required=True)
    lampstand_parser.add_argument("--output-dir", type=Path, required=True)
    lampstand_parser.set_defaults(func=emit_lampstand_demo)

    execution_parser = subparsers.add_parser("emit-execution", help="Emit demo ExecutionRecord lineage artifacts")
    execution_parser.add_argument("--output-dir", type=Path, required=True)
    execution_parser.set_defaults(func=emit_execution)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"lattice-studio: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
