"""Register the InferenceGateway intersection board into the cloud model catalog.

The sovereign model plane is defined once at the intersection seam (sourceos-spec
`inference-gateway-intersection.md`); this projects that board — foundation models AND
business-target champions (fraud/churn/credit/AML) — into the prophet-platform / lattice
model catalog as `model-catalog-entry.v0` entries. Sovereignty is carried in
`privacy_profile` (sovereign-local / sovereign-both / vendor-cloud) so the cloud catalog,
notebooks, and leaderboards rank on the same sovereignty-aware board the cockpit surfaces do.

Foundation and business models sit in ONE catalog — the differentiator watsonx.ai /
SageMaker / Seldon split across separate products.
"""
from __future__ import annotations

from typing import Any, Dict, List

_CREATED = "2026-08-03T00:00:00Z"


def _entry(model_id: str, provider_id: str, privacy: str, *, modalities: List[str],
           structured: bool, tool_use: bool, vision: bool = False,
           latency: str = "mid", cost: str = "mid") -> Dict[str, Any]:
    return {
        "model_id": model_id,
        "provider_id": provider_id,
        "modalities": modalities,
        "supports_structured_output": structured,
        "supports_tool_use": tool_use,
        "supports_vision": vision,
        "latency_band": latency,
        "cost_band": cost,
        "privacy_profile": privacy,
        "created_at": _CREATED,
    }


def foundation_entries() -> List[Dict[str, Any]]:
    return [
        _entry("claude-opus-4-8", "anthropic", "vendor-cloud",
               modalities=["text", "vision"], structured=True, tool_use=True, vision=True,
               latency="low", cost="high"),
        _entry("llama-3.3-70b", "meta-open-weight", "sovereign-both",
               modalities=["text"], structured=True, tool_use=True, latency="mid", cost="low"),
        _entry("deepseek-v3", "deepseek-open-weight", "sovereign-both",
               modalities=["text"], structured=True, tool_use=True, latency="mid", cost="low"),
        _entry("gemma-2-9b-it", "google-open-weight", "sovereign-local",
               modalities=["text"], structured=True, tool_use=False, latency="low", cost="minimal"),
    ]


def business_champion_entries() -> List[Dict[str, Any]]:
    # Each business target's production champion, as a catalog entry. Champion/challenger
    # promotion lineage lives in the model-zoo promotion layer; this is the catalog face.
    return [
        _entry("gbm-fraud-v4", "socioprophet-fraud", "sovereign-local",
               modalities=["tabular"], structured=True, tool_use=False, latency="low", cost="low"),
        _entry("xgb-churn-v7", "socioprophet-churn", "sovereign-local",
               modalities=["tabular"], structured=True, tool_use=False, latency="low", cost="low"),
        _entry("scorecard-v12", "socioprophet-credit", "sovereign-local",
               modalities=["tabular"], structured=True, tool_use=False, latency="low", cost="low"),
        _entry("rules-gbm-aml-v3", "socioprophet-aml", "sovereign-local",
               modalities=["tabular", "graph"], structured=True, tool_use=False, latency="low", cost="low"),
    ]


def board_catalog_entries() -> List[Dict[str, Any]]:
    """The full intersection board projected as cloud catalog entries."""
    return foundation_entries() + business_champion_entries()
