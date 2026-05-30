import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "apps" / "tritfabric-consumption-api" / "main.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tritfabric_consumption_api", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_exposes_all_surfaces_without_mutation():
    api = _load_module()
    out = api.summary()

    assert out["ok"] is True
    assert out["mutation_authorized"] is False
    assert out["runtime_execution_authorized"] is False
    assert {surface["surface"]["id"] for surface in out["surfaces"]} == {
        "community-learning-intake",
        "network-atlas-framework-catalog",
        "model-card-promotion-evidence",
        "serve-readiness",
    }


def test_community_learning_stub_preserves_gates_and_non_execution():
    api = _load_module()
    out = api.community_learning_intake()

    assert out["mode"] == "intake-readiness"
    assert out["event_ingestion"] is False
    assert out["workflow_execution"] is False
    assert out["model_mutation"] is False
    assert out["artifact_promotion"] is False
    for gate in ("consent", "license", "lineage", "rubric", "manual-review-before-promotion"):
        assert gate in out["surface"]["required_gates"]


def test_framework_catalog_stub_does_not_claim_adapter_validation():
    api = _load_module()
    out = api.framework_catalog()

    assert out["mode"] == "catalog-readiness"
    assert out["adapter_validation"] is False
    assert out["runtime_support_claim"] is False
    assert "claim-boundary-visible" in out["surface"]["required_gates"]


def test_promotion_stub_requires_evidence_and_status_semantics_without_execution():
    api = _load_module()
    out = api.promotion_evidence()

    assert out["mode"] == "evidence-readiness"
    assert out["promotion_execution"] is False
    assert out["required_status_semantics"] == ["TRUE", "MID", "FALSE"]
    for field in ("mathType", "calcOps", "ledgerRef", "artifactRef", "tritStatus"):
        assert field in out["surface"]["required_fields"]


def test_serve_readiness_stub_does_not_enable_runtime():
    api = _load_module()
    out = api.serve_readiness()

    assert out["mode"] == "serve-readiness-reporting"
    assert out["serve_deployment"] is False
    assert out["autoscaler_active_loop"] is False
    assert out["production_readiness_claim"] is False
