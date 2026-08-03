"""Jacob's Ladder of Assets -- the governed asset-class ontology (ALC-1).

A contract-with-teeth for the estate omnirisk ``asset_class`` axis. It grounds
asset classes in the real economy as a TOTAL, ORDERED ladder of value-
transformation, from tangible extraction (rung 0) up to pure digital services
(rung 8), and it REPLACES the thin ``{credit, equity, market, crypto}`` enum.

Why a ladder and not a flat enum
--------------------------------
``credit``/``equity``/``market``/``crypto`` are all *financial claims* -- they
name what a balance sheet holds after value already exists. They cannot say
where Revenue comes from. The ladder does: extraction (rungs 1 / 1') and
labor-mixing (rung 2) are the value-GENESIS the economic-prophet kernel needs
before anything becomes a financial claim (rungs 3+). Each rung binds:

  * a ``valuation_model`` -- how value is measured at that rung
    (real-option / Hotelling / sustainable-yield / Lockean labor-value-add /
    spot-futures-vol / human-capital-wage / spatiotemporal-arbitrage / DCF /
    network-memetic / Economia-Mentium); and
  * a ``risk_F_family`` -- the RM-1 risk kernel that scores that rung's loss
    distribution F (sharpe / sortino / kappa / var / expected_shortfall /
    spectral / stddev).

The renewability axis is bound to a stochastic-process regime (TC-1 crosswalk):

    depleting_stock   <-> monotone_absorbing   (drift to an absorbing barrier
                                                 at zero reserves; Hotelling)
    regenerating_flow <-> mean_reverting_ou     (OU reversion to a sustainable
                                                 yield; TC-1 persistence)
    non_physical      <-> non_physical          (a claim / service / digital
                                                 asset; no physical stock)

Teeth (both directions)
-----------------------
VERIFIES  the ladder is total + ordered; every rung carries every axis; farming
          classifies ``regenerating_flow``; mining classifies
          ``depleting_stock``; a digital_service classifies ``non_rival``.
REJECTS   a renewable_harvest tagged ``depleting_stock`` (or mining as
          ``regenerating_flow``); a digital_asset priced by SCARCITY as if rival
          (non-rival economics: value is network / attention, not scarcity);
          a non-renewable with NO depletion / Hotelling model; a rung missing
          any required axis; a value_stage ordering that is not monotone
          tangible -> digital.

Deterministic and stdlib-only. Measurement, simulation and audit only.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..risk_measures import KNOWN_KERNELS
from ..validation import validate_json_file

_SCHEMA = "schemas/asset_class_ladder.schema.json"

# --------------------------------------------------------------------------- #
# controlled vocabularies (the checker is the authority; the schema documents)
# --------------------------------------------------------------------------- #
REQUIRED_AXES = (
    "value_stage",
    "key",
    "label",
    "tangibility",
    "rivalry",
    "renewability",
    "labor_content",
    "process_regime",
    "valuation_model",
    "risk_F_family",
)

TANGIBILITY_ORDER = {"tangible": 3, "semi_tangible": 2, "intangible": 1}
RIVALRY = {"rival", "non_rival"}
RENEWABILITY = {"depleting_stock", "regenerating_flow", "non_physical"}
PROCESS_REGIME = {"monotone_absorbing", "mean_reverting_ou", "non_physical"}
LABOR_CONTENT = {"none", "low", "moderate", "high"}
VALUATION_MODELS = {
    "real_option",
    "hotelling_rent",
    "sustainable_yield",
    "labor_value_add",
    "spot_futures_vol",
    "human_capital_wage",
    "spatiotemporal_arbitrage",
    "dcf",
    "network_memetic",
    "economia_mentium",
}

# renewability <-> process-regime crosswalk (total function on RENEWABILITY).
RENEWABILITY_REGIME = {
    "depleting_stock": "monotone_absorbing",
    "regenerating_flow": "mean_reverting_ou",
    "non_physical": "non_physical",
}

# Class-defining axes. renewability and rivalry are DEFINITIONAL for an asset
# class (mining is by definition a depleting stock; a digital asset is by
# definition non-rival), so the ladder must bind them exactly. valuation_model,
# risk_F_family and labor_content may vary within these constraints.
CANONICAL_RENEWABILITY = {
    "natural_capital": "depleting_stock",
    "extractive_nonrenewable": "depleting_stock",
    "renewable_harvest": "regenerating_flow",
    "processed_goods": "regenerating_flow",
    "commodity_market": "non_physical",
    "labor_market": "non_physical",
    "mercantile_trade": "non_physical",
    "pure_service": "non_physical",
    "digital_asset": "non_physical",
    "digital_service": "non_physical",
}
CANONICAL_RIVALRY = {
    "natural_capital": "rival",
    "extractive_nonrenewable": "rival",
    "renewable_harvest": "rival",
    "processed_goods": "rival",
    "commodity_market": "rival",
    "labor_market": "rival",
    "mercantile_trade": "rival",
    "pure_service": "rival",
    "digital_asset": "non_rival",
    "digital_service": "non_rival",
}

# The canonical ordered rung keys (0 .. 8, with 1' as the renewable sibling).
LADDER_ORDER = (
    "natural_capital",
    "extractive_nonrenewable",
    "renewable_harvest",
    "processed_goods",
    "commodity_market",
    "labor_market",
    "mercantile_trade",
    "pure_service",
    "digital_asset",
    "digital_service",
)

# Depletion-aware valuation models: any depleting_stock rung MUST use one of
# these (a non-renewable priced without a Hotelling / depletion model is silent
# infinite-reserve pricing and is REJECTED).
DEPLETION_MODELS = {"real_option", "hotelling_rent"}

# Scarcity / cash-flow models: asserting one of these on a NON-RIVAL digital
# asset is the wrong model (copying is free -> no scarcity rent, no cash flow to
# discount). Value there is network / memetic.
SCARCITY_OR_CASHFLOW_MODELS = {"real_option", "hotelling_rent", "dcf"}
NONRIVAL_VALUATION_MODELS = {"network_memetic", "economia_mentium"}


class AssetLadderError(ValueError):
    """Raised when the ladder or a descriptor violates the contract (REJECTED)."""


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def load_ladder(path: str) -> dict:
    return json.loads(Path(path).read_text())


# --------------------------------------------------------------------------- #
# per-rung teeth
# --------------------------------------------------------------------------- #
def _check_rung_axes(rung: dict, where: str) -> None:
    for axis in REQUIRED_AXES:
        if axis not in rung or rung[axis] in (None, ""):
            raise AssetLadderError(f"{where}: missing required axis {axis!r}")

    if rung["tangibility"] not in TANGIBILITY_ORDER:
        raise AssetLadderError(f"{where}: unknown tangibility {rung['tangibility']!r}")
    if rung["rivalry"] not in RIVALRY:
        raise AssetLadderError(f"{where}: unknown rivalry {rung['rivalry']!r}")
    if rung["renewability"] not in RENEWABILITY:
        raise AssetLadderError(f"{where}: unknown renewability {rung['renewability']!r}")
    if rung["process_regime"] not in PROCESS_REGIME:
        raise AssetLadderError(f"{where}: unknown process_regime {rung['process_regime']!r}")
    if rung["labor_content"] not in LABOR_CONTENT:
        raise AssetLadderError(f"{where}: unknown labor_content {rung['labor_content']!r}")
    if rung["valuation_model"] not in VALUATION_MODELS:
        raise AssetLadderError(f"{where}: unknown valuation_model {rung['valuation_model']!r}")
    if rung["risk_F_family"] not in KNOWN_KERNELS:
        raise AssetLadderError(
            f"{where}: risk_F_family {rung['risk_F_family']!r} is not a known RM-1 kernel "
            f"({sorted(KNOWN_KERNELS)})"
        )


def _check_renewability_regime(rung: dict, where: str) -> None:
    expected = RENEWABILITY_REGIME[rung["renewability"]]
    if rung["process_regime"] != expected:
        raise AssetLadderError(
            f"{where}: renewability {rung['renewability']!r} requires process_regime "
            f"{expected!r}, got {rung['process_regime']!r} "
            f"(depleting_stock<->monotone_absorbing, "
            f"regenerating_flow<->mean_reverting_ou, non_physical<->non_physical)"
        )


def _check_class_invariants(rung: dict, where: str) -> None:
    key = rung["key"]
    want_ren = CANONICAL_RENEWABILITY.get(key)
    if want_ren is not None and rung["renewability"] != want_ren:
        raise AssetLadderError(
            f"{where}: asset class {key!r} is defined as renewability={want_ren!r}, "
            f"got {rung['renewability']!r} "
            f"(e.g. mining is a depleting_stock; farming is a regenerating_flow)"
        )
    want_riv = CANONICAL_RIVALRY.get(key)
    if want_riv is not None and rung["rivalry"] != want_riv:
        raise AssetLadderError(
            f"{where}: asset class {key!r} is defined as rivalry={want_riv!r}, "
            f"got {rung['rivalry']!r} "
            f"(digital assets/services are NON-RIVAL: copying is free)"
        )


def _check_valuation_binding(rung: dict, where: str) -> None:
    # A depleting (non-renewable) stock must be priced with a depletion-aware
    # model (Hotelling / real option) -- never as an infinite reserve.
    if rung["renewability"] == "depleting_stock" and rung["valuation_model"] not in DEPLETION_MODELS:
        raise AssetLadderError(
            f"{where}: depleting_stock rung must use a depletion/Hotelling model "
            f"{sorted(DEPLETION_MODELS)}, got {rung['valuation_model']!r}"
        )
    # The extractive non-renewable rung is specifically the Hotelling rung.
    if rung["key"] == "extractive_nonrenewable" and rung["valuation_model"] != "hotelling_rent":
        raise AssetLadderError(
            f"{where}: extractive_nonrenewable must be priced by hotelling_rent, "
            f"got {rung['valuation_model']!r}"
        )
    # A renewable flow must be priced by sustainable yield.
    if rung["key"] == "renewable_harvest" and rung["valuation_model"] != "sustainable_yield":
        raise AssetLadderError(
            f"{where}: renewable_harvest must be priced by sustainable_yield, "
            f"got {rung['valuation_model']!r}"
        )
    # Non-rival digital assets are NOT priced by scarcity or cash flow.
    if rung["rivalry"] == "non_rival" and rung["valuation_model"] in SCARCITY_OR_CASHFLOW_MODELS:
        raise AssetLadderError(
            f"{where}: non_rival asset priced by scarcity/cash-flow model "
            f"{rung['valuation_model']!r}; non-rival value is network/attention "
            f"(one of {sorted(NONRIVAL_VALUATION_MODELS)}), not scarcity"
        )


# --------------------------------------------------------------------------- #
# ladder-level teeth: totality + ordering
# --------------------------------------------------------------------------- #
def _check_totality_and_order(rungs: list) -> None:
    keys = [r.get("key") for r in rungs]
    if keys != list(LADDER_ORDER):
        raise AssetLadderError(
            f"ladder is not total/ordered: expected keys {list(LADDER_ORDER)}, got {keys}"
        )

    prev_stage = None
    prev_tang = None
    for idx, rung in enumerate(rungs):
        where = f"rung[{idx}] {rung.get('key')!r}"
        stage = rung["value_stage"]
        if prev_stage is not None and stage <= prev_stage:
            raise AssetLadderError(
                f"{where}: value_stage {stage} is not strictly increasing "
                f"(previous {prev_stage}); the ladder must be monotone tangible->digital"
            )
        tang = TANGIBILITY_ORDER[rung["tangibility"]]
        if prev_tang is not None and tang > prev_tang:
            raise AssetLadderError(
                f"{where}: tangibility {rung['tangibility']!r} is more tangible than the "
                f"rung below it; tangibility must be monotone non-increasing tangible->digital"
            )
        prev_stage = stage
        prev_tang = tang

    # The top of the ladder must be non-rival digital (value beyond scarcity).
    if rungs[-1]["rivalry"] != "non_rival":
        raise AssetLadderError("top rung (digital_service) must be non_rival")


def check_ladder(ladder: dict) -> dict:
    """Validate the whole ladder against every tooth. Raise on violation.

    Returns a deterministic receipt describing the verified ladder.
    """
    if "rungs" not in ladder or not isinstance(ladder["rungs"], list) or not ladder["rungs"]:
        raise AssetLadderError("ladder has no rungs")

    rungs = ladder["rungs"]
    for idx, rung in enumerate(rungs):
        where = f"rung[{idx}] {rung.get('key')!r}"
        _check_rung_axes(rung, where)
        _check_class_invariants(rung, where)
        _check_renewability_regime(rung, where)
        _check_valuation_binding(rung, where)

    _check_totality_and_order(rungs)

    return {
        "contract": "ALC-1",
        "ladder_id": ladder.get("ladder_id"),
        "rung_count": len(rungs),
        "total": True,
        "ordered": True,
        "replaces_enum": ladder.get("replaces_enum", []),
        "rungs": [
            {
                "value_stage": r["value_stage"],
                "key": r["key"],
                "tangibility": r["tangibility"],
                "rivalry": r["rivalry"],
                "renewability": r["renewability"],
                "process_regime": r["process_regime"],
                "valuation_model": r["valuation_model"],
                "risk_F_family": r["risk_F_family"],
            }
            for r in rungs
        ],
    }


def run_check(ladder_path: str, schema_path: str = _SCHEMA) -> dict:
    """Schema-validate then apply the teeth. Returns the receipt."""
    validate_json_file(ladder_path, schema_path)
    return check_ladder(load_ladder(ladder_path))


# --------------------------------------------------------------------------- #
# classification: bind a real-world asset descriptor to its rung
# --------------------------------------------------------------------------- #
def canonical_rung(key: str, ladder: dict) -> dict:
    for rung in ladder["rungs"]:
        if rung.get("key") == key:
            return rung
    raise AssetLadderError(f"unknown asset-class key {key!r}")


def classify(descriptor: dict, ladder: dict) -> dict:
    """Classify an asset descriptor onto the ladder.

    ``descriptor`` must carry a ``key``; any axes it also asserts
    (renewability, rivalry, ...) are checked against the canonical rung. A
    contradiction (e.g. farming asserted as ``depleting_stock``) is REJECTED.
    Returns the canonical rung.
    """
    key = descriptor.get("key")
    if not key:
        raise AssetLadderError("descriptor has no asset-class key")
    rung = canonical_rung(key, ladder)
    for axis in ("tangibility", "rivalry", "renewability", "process_regime", "valuation_model"):
        if axis in descriptor and descriptor[axis] != rung[axis]:
            raise AssetLadderError(
                f"{key!r} classified {axis}={descriptor[axis]!r} but the ladder binds "
                f"{axis}={rung[axis]!r}"
            )
    return rung


# --------------------------------------------------------------------------- #
# CLI: emit a deterministic receipt for CI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Check the Jacob's Ladder of Assets contract (ALC-1).")
    parser.add_argument("--ladder", default="examples/asset_class_ladder.json")
    parser.add_argument("--schema", default=_SCHEMA)
    parser.add_argument("--receipt", default=None, help="Optional path to write the receipt JSON.")
    args = parser.parse_args(argv)

    receipt = run_check(args.ladder, args.schema)
    text = json.dumps(receipt, indent=2, sort_keys=True)
    if args.receipt:
        Path(args.receipt).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
