"""Sovereignty-aware leaderboard + notebook fixture over the InferenceGateway board.

Ranks the cloud catalog entries the same way the cockpit surface does — not on raw
capability but on **sovereignty and locality** (privacy_profile) plus the latency/cost
bands the catalog entry already carries. This is the cloud lattice face of the board:
one leaderboard across foundation + business models, cloud ∩ local, ranked by the thesis.
No new fields are invented — scoring reads only `model-catalog-entry.v0` properties.
"""
from __future__ import annotations

from typing import Any, Dict, List

from lattice_studio.inference_gateway_board import board_catalog_entries

_SOV = {"sovereign-local": 3.0, "sovereign-both": 3.0, "vendor-cloud": 1.0}
_LAT = {"low": 1.0, "mid": 0.5, "high": 0.0}
_COST = {"minimal": 1.0, "low": 0.5, "mid": 0.0, "high": -0.5}


def score(entry: Dict[str, Any]) -> float:
    return round(
        _SOV.get(entry.get("privacy_profile"), 0.0)
        + _LAT.get(entry.get("latency_band"), 0.0)
        + _COST.get(entry.get("cost_band"), 0.0),
        2,
    )


def leaderboard() -> List[Dict[str, Any]]:
    ranked = sorted(board_catalog_entries(), key=score, reverse=True)
    return [
        {"rank": i + 1, "model_id": e["model_id"], "provider_id": e["provider_id"],
         "privacy_profile": e["privacy_profile"], "score": score(e)}
        for i, e in enumerate(ranked)
    ]


def notebook_fixture() -> Dict[str, Any]:
    """A lattice notebook artifact rendering the board — kind-tagged like the model-zoo fixtures."""
    entries = board_catalog_entries()
    mix: Dict[str, int] = {}
    for e in entries:
        mix[e["privacy_profile"]] = mix.get(e["privacy_profile"], 0) + 1
    return {
        "kind": "ModelBoardNotebook",
        "generatedBy": "lattice_studio.inference_gateway_leaderboard",
        "entryCount": len(entries),
        "sovereigntyMix": mix,
        "leaderboard": leaderboard(),
        "note": "One board across foundation + business models, cloud ∩ local, ranked by sovereignty × locality. Reads the shared InferenceGateway catalog + GatewayCallAudit stream.",
    }
