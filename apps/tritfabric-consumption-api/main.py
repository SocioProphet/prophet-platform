from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "integrations" / "tritfabric-consumption.v0.json"


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _surface(surface_id: str) -> dict[str, Any]:
    contract = _load_contract()
    for surface in contract.get("surfaces", []):
        if surface.get("id") == surface_id:
            return surface
    raise KeyError(f"unknown TritFabric surface: {surface_id}")


def _base(surface_id: str) -> dict[str, Any]:
    contract = _load_contract()
    return {
        "ok": True,
        "integration_id": contract["integration_id"],
        "surface": _surface(surface_id),
        "authority_boundaries": contract["authority_boundaries"],
        "non_claims": contract["non_claims"],
        "mutation_authorized": False,
        "runtime_execution_authorized": False,
        "claim_boundary": contract["claim_boundary"],
    }


def community_learning_intake() -> dict[str, Any]:
    """Describe Community Learning intake gates without ingesting events."""
    out = _base("community-learning-intake")
    out.update({
        "mode": "intake-readiness",
        "event_ingestion": False,
        "workflow_execution": False,
        "model_mutation": False,
        "artifact_promotion": False,
    })
    return out


def framework_catalog() -> dict[str, Any]:
    """Describe Network Atlas catalog consumption without adapter validation."""
    out = _base("network-atlas-framework-catalog")
    out.update({
        "mode": "catalog-readiness",
        "adapter_validation": False,
        "runtime_support_claim": False,
    })
    return out


def promotion_evidence() -> dict[str, Any]:
    """Describe model-card promotion evidence requirements without executing promotion."""
    out = _base("model-card-promotion-evidence")
    out.update({
        "mode": "evidence-readiness",
        "promotion_execution": False,
        "required_status_semantics": ["TRUE", "MID", "FALSE"],
    })
    return out


def serve_readiness() -> dict[str, Any]:
    """Describe Serve readiness reporting without enabling Serve runtime behavior."""
    out = _base("serve-readiness")
    out.update({
        "mode": "serve-readiness-reporting",
        "serve_deployment": False,
        "autoscaler_active_loop": False,
        "production_readiness_claim": False,
    })
    return out


def summary() -> dict[str, Any]:
    return {
        "ok": True,
        "surfaces": [
            community_learning_intake(),
            framework_catalog(),
            promotion_evidence(),
            serve_readiness(),
        ],
        "mutation_authorized": False,
        "runtime_execution_authorized": False,
    }


try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]


if FastAPI is not None:
    app = FastAPI(title="Prophet Platform TritFabric Consumption API", version="0.1")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"ok": True, "mode": "local-pre-infrastructure", "mutation_authorized": False}

    @app.get("/tritfabric")
    def summary_endpoint() -> dict[str, Any]:
        return summary()

    @app.get("/tritfabric/community-learning")
    def community_learning_endpoint() -> dict[str, Any]:
        return community_learning_intake()

    @app.get("/tritfabric/framework-catalog")
    def framework_catalog_endpoint() -> dict[str, Any]:
        return framework_catalog()

    @app.get("/tritfabric/promotion-evidence")
    def promotion_evidence_endpoint() -> dict[str, Any]:
        return promotion_evidence()

    @app.get("/tritfabric/serve-readiness")
    def serve_readiness_endpoint() -> dict[str, Any]:
        return serve_readiness()


def main() -> int:
    print(json.dumps(summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
