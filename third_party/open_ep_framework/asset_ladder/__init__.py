"""Jacob's Ladder of Assets (ALC-1): the governed asset-class ontology.

A total, ordered ladder of value-transformation (natural capital -> extraction /
harvest -> processed goods -> commodity/labor/mercantile markets -> pure service
-> digital asset -> digital service) that replaces the thin
``{credit, equity, market, crypto}`` asset_class enum and binds each rung to a
valuation_model and an RM-1 ``risk_F_family``.
"""
from .ladder import (
    AssetLadderError,
    LADDER_ORDER,
    RENEWABILITY_REGIME,
    check_ladder,
    classify,
    canonical_rung,
    load_ladder,
    run_check,
)

__all__ = [
    "AssetLadderError",
    "LADDER_ORDER",
    "RENEWABILITY_REGIME",
    "check_ladder",
    "classify",
    "canonical_rung",
    "load_ladder",
    "run_check",
]

CONTRACT = "ALC-1"
