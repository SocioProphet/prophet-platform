#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "apps" / "tritfabric-consumption-api" / "main.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("tritfabric_consumption_api", MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load TritFabric consumption API stub module: {MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_false(payload: dict[str, Any], key: str) -> None:
    if payload.get(key) is not False:
        raise AssertionError(f"expected {key}=False")


def validate_summary(summary: dict[str, Any]) -> None:
    if summary.get("ok") is not True:
        raise AssertionError("summary must be ok")
    _assert_false(summary, "mutation_authorized")
    _assert_false(summary, "runtime_execution_authorized")
    surface_ids = {surface["surface"]["id"] for surface in summary.get("surfaces", [])}
    expected = {
        "community-learning-intake",
        "network-atlas-framework-catalog",
        "model-card-promotion-evidence",
        "serve-readiness",
    }
    if surface_ids != expected:
        raise AssertionError(f"unexpected TritFabric surfaces: {sorted(surface_ids)}")


def validate_module(module: Any) -> dict[str, Any]:
    summary = module.summary()
    validate_summary(summary)

    community = module.community_learning_intake()
    for key in ("event_ingestion", "workflow_execution", "model_mutation", "artifact_promotion"):
        _assert_false(community, key)
    for gate in ("consent", "license", "lineage", "rubric", "manual-review-before-promotion"):
        if gate not in community["surface"].get("required_gates", []):
            raise AssertionError(f"community surface missing gate {gate}")

    catalog = module.framework_catalog()
    _assert_false(catalog, "adapter_validation")
    _assert_false(catalog, "runtime_support_claim")

    promotion = module.promotion_evidence()
    _assert_false(promotion, "promotion_execution")
    if promotion.get("required_status_semantics") != ["TRUE", "MID", "FALSE"]:
        raise AssertionError("promotion evidence must expose TRUE/MID/FALSE status semantics")

    serve = module.serve_readiness()
    for key in ("serve_deployment", "autoscaler_active_loop", "production_readiness_claim"):
        _assert_false(serve, key)

    return summary


def main() -> int:
    module = _load_module()
    summary = validate_module(module)
    print(json.dumps({"ok": True, "validated_surfaces": [s["surface"]["id"] for s in summary["surfaces"]]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
