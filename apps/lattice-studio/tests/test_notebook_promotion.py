import json

from lattice_studio.notebook_promotion import (
    demo_notebook_promotion_bundle,
    promotion_evidence,
    promotion_to_platform_record,
)
from lattice_studio.notebook_promotion_cli import main


def test_notebook_promotion_bundle_targets_clean_deployable_units() -> None:
    bundle = demo_notebook_promotion_bundle()

    assert bundle["kind"] == "NotebookPromotionBundle"
    targets = {candidate["target"] for candidate in bundle["promotionCandidates"]}
    assert targets == {
        "ray-train-job",
        "ray-serve-service",
        "beam-pipeline",
        "paas-service",
        "observable-app",
        "plutojl-job",
        "quarto-publication",
    }
    assert bundle["extractionReport"]["checks"]["hidden_state_removed"] is True
    assert bundle["extractionReport"]["checks"]["secrets_absent"] is True
    assert "stale-cell-outputs" in bundle["extractionReport"]["removedArtifacts"]


def test_build_and_deployment_plans_cover_ray_beam_paas_and_publishing() -> None:
    bundle = demo_notebook_promotion_bundle()
    build_plans = bundle["containerBuildPlans"]
    deployment_plans = bundle["deploymentTargetPlans"]

    assert len(build_plans) == 7
    assert all(plan["sbomRequired"] is True for plan in build_plans)
    assert all(plan["signatureRequired"] is True for plan in build_plans)
    target_runtimes = {plan["targetRuntime"] for plan in deployment_plans}
    assert target_runtimes == {
        "kuberay-rayjob",
        "kuberay-rayservice",
        "beam-runner",
        "kubernetes-paas",
        "browser-static-app",
        "julia-container-job",
        "quarto-render-publish",
    }


def test_promotion_evidence_and_platform_record() -> None:
    bundle = demo_notebook_promotion_bundle()
    evidence = promotion_evidence(bundle)
    record = promotion_to_platform_record(bundle)

    assert evidence["kind"] == "NotebookPromotionEvidence"
    assert evidence["candidateCount"] == 7
    assert "container-build-plans" in evidence["evidenceReports"]
    assert "deployment-target-plans" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "notebook-promotion-bundle"
    assert "ray-train" in record["compatibilitySurfaces"]
    assert "beam" in record["compatibilitySurfaces"]
    assert "quarto" in record["compatibilitySurfaces"]


def test_notebook_promotion_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "promotion"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    bundle = json.loads((output_dir / "notebook-promotion-bundle.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "notebook-promotion-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "notebook-promotion-platform-record.json").read_text(encoding="utf-8"))

    assert bundle["kind"] == "NotebookPromotionBundle"
    assert evidence["kind"] == "NotebookPromotionEvidence"
    assert record["kind"] == "PlatformAssetRecord"
