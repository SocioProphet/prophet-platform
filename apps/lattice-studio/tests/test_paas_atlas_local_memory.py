import json
from pathlib import Path

from lattice_studio.atlas import atlas_evidence, atlas_to_platform_record, demo_atlas_context
from lattice_studio.cli import main
from lattice_studio.local_dev import create_local_dev_session, local_dev_to_platform_record
from lattice_studio.memory import memory_event, memory_event_set
from lattice_studio.paas import create_deployment_plan, deployment_evidence, deployment_to_platform_record


def test_atlas_context_covers_service_studies_workflows_and_autopilot() -> None:
    context = demo_atlas_context()
    doc = context.to_dict()
    evidence = atlas_evidence(context)
    record = atlas_to_platform_record(context)

    assert doc["kind"] == "AtlasContext"
    assert "SocioProphet/atlas_os_service_full" in doc["sourceRepos"]
    assert doc["rayRunnerRef"] == "atlas://os-service/ray-runner"
    assert doc["autopilotRolloutRef"] == "atlas://autopilot/promotion-rollout"
    assert evidence["kind"] == "AtlasContextEvidence"
    assert record["assetKind"] == "atlas-context"
    assert "beam" in record["compatibilitySurfaces"]


def test_paas_deployment_plan_models_cf_over_kubernetes_lane() -> None:
    plan = create_deployment_plan(
        name="demo-inference-service",
        kind="service",
        source_ref="git://SocioProphet/demo-inference-service#main",
        build_mode="buildpack",
        runtime_asset_id="runtime-asset:prophet-python-ml:0.1.0",
        catalog_asset_refs=["catalog://services/demo-inference-service@0.1.0"],
        environment="preview",
        target_platform="kubernetes",
        route="https://demo-inference.preview.example.invalid",
        policy_ref="policy://lattice-studio/paas-demo",
    )
    evidence = deployment_evidence(plan)
    record = deployment_to_platform_record(plan)

    assert plan.to_dict()["kind"] == "PaaSDeploymentPlan"
    assert plan.target_platform == "kubernetes"
    assert "preview-environment" in plan.to_dict()["capabilities"]
    assert evidence["kind"] == "PaaSDeploymentEvidence"
    assert record["assetKind"] == "paas-service"
    assert "porter-paas-devops" in record["compatibilitySurfaces"]


def test_local_dev_session_covers_notebook_terminal_browser_and_agents() -> None:
    session = create_local_dev_session(
        workspace_ref="workspace://demo",
        atlas_context_ref="atlas-context:demo",
        paas_deployment_ref="paas-deployment:demo",
    )
    doc = session.to_dict()
    record = local_dev_to_platform_record(session)

    assert doc["kind"] == "LocalDevSession"
    assert doc["notebookEndpoint"].startswith("http://localhost")
    assert doc["terminalEndpoint"].startswith("local://terminal")
    assert doc["browserEndpoint"].startswith("http://localhost")
    assert "openclaw://workflows/default" in doc["codingAgentRefs"]
    assert record["assetKind"] == "local-dev-session"
    assert "sourceos-local" in record["compatibilitySurfaces"]


def test_memory_events_bind_studio_activity_to_subjects() -> None:
    event = memory_event(
        subject_ref="notebook-session:demo",
        event_type="lattice-studio.activity",
        summary="Recorded demo notebook session.",
        links=["catalog://datasets/demo-csv@0.1.0"],
    )
    payload = memory_event_set([event])

    assert event.to_dict()["kind"] == "MemoryEvent"
    assert payload["kind"] == "MemoryEventSet"
    assert payload["events"][0]["links"] == ["catalog://datasets/demo-csv@0.1.0"]


def test_cli_emits_atlas_paas_local_dev_and_memory_artifacts(tmp_path) -> None:
    atlas_dir = tmp_path / "atlas"
    paas_dir = tmp_path / "paas"
    local_dir = tmp_path / "local"
    memory_path = tmp_path / "memory" / "memory-events.json"

    assert main(["emit-atlas-context", "--output-dir", str(atlas_dir)]) == 0
    assert main([
        "emit-paas-plan",
        "--name",
        "demo-inference-service",
        "--kind",
        "service",
        "--source-ref",
        "git://SocioProphet/demo-inference-service#main",
        "--build-mode",
        "buildpack",
        "--runtime-asset-id",
        "runtime-asset:prophet-python-ml:0.1.0",
        "--catalog-asset-ref",
        "catalog://services/demo-inference-service@0.1.0",
        "--environment",
        "preview",
        "--target-platform",
        "kubernetes",
        "--route",
        "https://demo-inference.preview.example.invalid",
        "--policy-ref",
        "policy://lattice-studio/paas-demo",
        "--output-dir",
        str(paas_dir),
    ]) == 0
    assert main([
        "emit-local-dev",
        "--workspace-ref",
        "workspace://demo",
        "--atlas-context-ref",
        "atlas-context:demo",
        "--paas-deployment-ref",
        "paas-deployment:demo",
        "--output-dir",
        str(local_dir),
    ]) == 0
    assert main([
        "emit-memory",
        "--subject",
        "workspace://demo",
        "--subject",
        "atlas-context:demo",
        "--link",
        "catalog://datasets/demo-csv@0.1.0",
        "--output",
        str(memory_path),
    ]) == 0

    assert (atlas_dir / "atlas-context.json").exists()
    assert (atlas_dir / "atlas-platform-record.json").exists()
    assert (paas_dir / "paas-deployment-plan.json").exists()
    assert (paas_dir / "paas-platform-record.json").exists()
    assert (local_dir / "local-dev-session.json").exists()
    assert (local_dir / "local-dev-platform-record.json").exists()
    assert json.loads(memory_path.read_text(encoding="utf-8"))["kind"] == "MemoryEventSet"
