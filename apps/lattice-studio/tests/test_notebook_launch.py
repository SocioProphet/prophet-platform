import json

from lattice_studio.notebook_launch import demo_launch_plans, launch_plan_evidence, launch_plan_set_to_platform_record
from lattice_studio.notebook_launch_cli import main


def test_launch_plans_cover_all_notebook_adapters_and_backends() -> None:
    plans = demo_launch_plans()
    by_adapter = {plan.adapter: plan for plan in plans}

    assert set(by_adapter) == {"jupyterlab", "zeppelin", "observable", "plutojl", "quarto"}
    assert by_adapter["jupyterlab"].backend == "jupyter-server"
    assert by_adapter["zeppelin"].backend == "zeppelin-server"
    assert by_adapter["observable"].backend == "browser-runtime"
    assert by_adapter["plutojl"].backend == "julia-process"
    assert by_adapter["quarto"].backend == "quarto-renderer"

    assert by_adapter["jupyterlab"].command[:2] == ["jupyter", "lab"]
    assert by_adapter["zeppelin"].command[0] == "zeppelin-daemon.sh"
    assert by_adapter["observable"].command[:2] == ["observable", "preview"]
    assert by_adapter["plutojl"].command[0] == "julia"
    assert by_adapter["quarto"].command[:2] == ["quarto", "render"]


def test_launch_plans_bind_runtime_catalog_workspace_and_policy() -> None:
    for plan in demo_launch_plans():
        doc = plan.to_dict()
        assert doc["kind"] == "NotebookSurfaceLaunchPlan"
        assert doc["dryRun"] is True
        assert doc["environment"]["LATTICE_RUNTIME_ASSET_ID"] == "runtime-asset:prophet-python-ml:0.1.0"
        assert doc["environment"]["LATTICE_POLICY_REF"] == "policy://lattice-studio/demo"
        assert "catalog://datasets/demo-csv@0.1.0" in doc["mountedCatalogInputs"]
        assert doc["localWorkspaceRef"] == "workspace://demo"


def test_launch_plan_evidence_and_platform_record() -> None:
    plans = demo_launch_plans()
    evidence = launch_plan_evidence(plans)
    record = launch_plan_set_to_platform_record(plans)

    assert evidence["kind"] == "NotebookSurfaceLaunchEvidence"
    assert evidence["launchPlanCount"] == 5
    assert "zeppelin-server" in evidence["backends"]
    assert "quarto-renderer" in evidence["backends"]
    assert "adapter-specific-launch-plan" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "notebook-launch-plan-set"
    assert "zeppelin" in record["compatibilitySurfaces"]
    assert "quarto" in record["compatibilitySurfaces"]


def test_notebook_launch_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "launch"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    plans = json.loads((output_dir / "notebook-launch-plans.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "notebook-launch-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "notebook-launch-platform-record.json").read_text(encoding="utf-8"))

    assert plans["kind"] == "NotebookSurfaceLaunchPlanSet"
    assert len(plans["plans"]) == 5
    assert evidence["kind"] == "NotebookSurfaceLaunchEvidence"
    assert record["kind"] == "PlatformAssetRecord"
