"""Going-concern / gone-concern confidence ladder == capital waterfall (CLD-1).

A bank's survival is a *ladder of confidence levels*, and each rung is absorbed by a
*layer of the capital waterfall* in subordination order:

  * Early-Warning   alpha 0.80  (30/250d)  <- hidden reserves        (going-concern)
  * Severe-Stress   alpha 0.95  (250d)     <- retained earnings/Tier1 (going-concern)
  * Liquidation     alpha 0.9998/1.00      <- Tier2/subordinated/debt  (gone-concern)

Going-concern (the firm SURVIVES) vs gone-concern (LIQUIDATION / creditor
protection) is exactly the alpha range: below the going->gone boundary the firm is a
going concern; at/above it, it is being resolved. **CoCos convert at that boundary.**

Loss absorbs in subordination order -- equity/first-loss -> ... -> senior debt -- and
this contract reuses the kernel's securitization waterfall to prove it, rather than
re-deriving one:

Consume, do NOT reinvent
------------------------
  * ``risk_measures.structural_transform`` (RM-1, economic-prophet #43/#44) -- the
    seniority/tranche waterfall: a [attach, detach] layer absorbs
    ``clip(pool_loss - attach, 0, detach - attach)``. A contiguous partition of the
    loss sums back to the pool loss (conservation), which is precisely "loss hits
    equity, then the next layer, ... in order". The capital stack here IS such a
    partition; each layer's absorbed loss is computed by ``structural_transform``.
  * ``risk_measures.expected_loss`` / ``LossDistribution`` -- the pool F.
  * ``settlement`` (IC-1, #39) -- the FIPS SHA-256 ``sha256:`` receipt spine.
  * ``sociosphere:gbrg/governance/omnirisk_allocation.py`` (OMNI-1) -- soft ref; the
    ladder's per-layer absorbed capital is a node input the cross-cut walker consumes.

Teeth (verdicts)
----------------
  * VERIFIED -- alphas strictly increase; every scenario is booked to the marginal
        layer its loss actually reaches (subordination-correct); coverage holds; the
        concern label matches the alpha range; CoCos convert at the boundary.
  * FLAGGED  -- a scenario whose absorbing capital is LESS than its loss at alpha
        (under-capitalized -- loss punches through the booked layer); a concern label
        inconsistent with the boundary; CoCo conversion off the boundary.
  * REJECTED (raises) --
        alphas not strictly increasing down the ladder (non-monotone);
        a loss booked against a SENIOR layer while junior layers are unpierced
            (out of subordination order);
        a gone-concern scenario mapped to a going-concern soft layer (e.g. hidden
            reserves cannot absorb a liquidation loss).

Measurement, simulation and audit only. Deterministic + stdlib.
"""
from __future__ import annotations

import json
from pathlib import Path

from .risk_measures import LossDistribution, expected_loss, structural_transform
from .settlement import _canonical, _sha256
from .validation import validate_json_file

_SCHEMA = "schemas/concern_ladder.schema.json"
_TOL = 1e-6

# Soft references (consumed by reference).
KERNEL_WATERFALL_REF = "economic-prophet:src/open_ep_framework/risk_measures.py#structural_transform"
OMNIRISK_WALKER_REF = "sociosphere:gbrg/governance/omnirisk_allocation.py (OMNI-1)"

GOING = "going"
GONE = "gone"


class ConcernLadderError(ValueError):
    """Raised when the ladder violates monotonicity or subordination (REJECTED)."""


# --------------------------------------------------------------------------- #
# capital stack -> cumulative attach/detach partition of the loss axis
# --------------------------------------------------------------------------- #
def _layers_with_bounds(stack: list[dict]) -> list[dict]:
    """Turn the ordered stack into a contiguous [attach, detach] partition.

    Layer 0 (most junior) is the first-loss piece [0, amount_0]; each subsequent
    layer attaches where the previous detaches. This is exactly the partition
    ``structural_transform`` treats as a securitization waterfall.
    """
    layers = []
    cursor = 0.0
    for spec in stack:
        amount = float(spec["amount"])
        attach = cursor
        detach = cursor + amount
        layers.append({
            "layer": spec["layer"],
            "concern": spec["concern"],
            "kind": spec.get("kind", ""),
            "amount": amount,
            "attach": attach,
            "detach": detach,
        })
        cursor = detach
    return layers


def _find_layer(layers: list[dict], name: str) -> dict:
    for layer in layers:
        if layer["layer"] == name:
            return layer
    raise ConcernLadderError(
        f"REJECTED: absorbing_capital_layer {name!r} is not in the capital stack"
    )


# --------------------------------------------------------------------------- #
# waterfall demonstration via the kernel's structural_transform
# --------------------------------------------------------------------------- #
def _waterfall_absorption(layers: list[dict], samples: list[float]) -> list[dict]:
    """Per-layer EXPECTED absorbed loss over the pool F, via structural_transform.

    Proves loss hits the layers in order and that the partition conserves: the sum of
    layer expected-absorbed losses equals the pool expected loss capped at the stack.
    """
    F = LossDistribution.from_samples(samples)
    out = []
    for layer in layers:
        tranche = structural_transform(F, layer["attach"], layer["detach"])
        out.append({
            "layer": layer["layer"],
            "attach": layer["attach"],
            "detach": layer["detach"],
            "expected_absorbed_loss": expected_loss(tranche),
        })
    return out


# --------------------------------------------------------------------------- #
# evaluate one scenario against the waterfall
# --------------------------------------------------------------------------- #
def _evaluate_scenario(scn: dict, layers: list[dict], boundary: float | None) -> dict:
    name = scn["name"]
    alpha = float(scn["confidence_alpha"])
    loss = float(scn["loss_at_alpha"])
    declared_name = scn["absorbing_capital_layer"]
    concern = scn["concern"]
    layer = _find_layer(layers, declared_name)
    attach, detach = layer["attach"], layer["detach"]

    warnings: list[str] = []

    # Teeth: gone-concern loss cannot be absorbed by a going-concern soft layer.
    if concern == GONE and layer["concern"] == GOING:
        raise ConcernLadderError(
            f"REJECTED: scenario {name!r} is gone-concern but is mapped to going-concern "
            f"soft layer {declared_name!r}; a going-concern buffer cannot absorb a "
            f"liquidation loss (gone-concern must land on Tier2/subordinated/senior debt)"
        )

    # Teeth: loss booked against a SENIOR layer while junior layers are unpierced.
    if attach >= loss + _TOL:
        raise ConcernLadderError(
            f"REJECTED: scenario {name!r} loss {loss} is booked against layer "
            f"{declared_name!r} (attach={attach}) but the loss does not even reach it; "
            f"a more junior layer absorbs it first (out of subordination order)"
        )

    # Coverage: capital up to and including the booked layer must cover the loss.
    covered = detach + _TOL >= loss
    if not covered:
        warnings.append(
            f"under-capitalized: loss {loss} punches through layer {declared_name!r} "
            f"(capital up to it = {detach}); it is not fully absorbed"
        )

    # Concern label vs the going->gone boundary.
    if boundary is not None:
        implied = GOING if alpha < boundary - _TOL else GONE
        if implied != concern:
            warnings.append(
                f"concern label {concern!r} inconsistent with alpha {alpha} vs "
                f"going->gone boundary {boundary} (implies {implied!r})"
            )

    return {
        "name": name,
        "confidence_alpha": alpha,
        "horizon_days": scn.get("horizon_days"),
        "trigger": scn.get("trigger"),
        "concern": concern,
        "loss_at_alpha": loss,
        "absorbing_capital_layer": declared_name,
        "layer_attach": attach,
        "layer_detach": detach,
        "capital_up_to_layer": detach,
        "covered": covered,
        "verdict": "verified" if (covered and not warnings) else "flagged",
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# contract
# --------------------------------------------------------------------------- #
def evaluate_contract(spec: dict) -> dict:
    contract_id = spec.get("contract_id", "cld")
    as_of = spec.get("as_of", "")
    boundary = spec.get("going_gone_boundary_alpha")
    boundary = float(boundary) if boundary is not None else None

    layers = _layers_with_bounds(spec["capital_stack"])

    # Teeth: alphas must strictly increase down the ladder.
    scenarios_in = spec["scenarios"]
    alphas = [float(s["confidence_alpha"]) for s in scenarios_in]
    for i in range(len(alphas) - 1):
        if not (alphas[i + 1] > alphas[i] + _TOL):
            raise ConcernLadderError(
                f"REJECTED: ladder alphas are not strictly increasing at rung {i}: "
                f"{alphas[i]} -> {alphas[i + 1]} (going->gone confidence must climb)"
            )

    scenarios = [_evaluate_scenario(s, layers, boundary) for s in scenarios_in]

    warnings: list[str] = []
    # CoCos convert at the going->gone boundary.
    coco = spec.get("coco_conversion")
    if coco:
        _find_layer(layers, coco["layer"])  # must exist (else REJECT)
        if boundary is not None and abs(float(coco.get("alpha", -1)) - boundary) > _TOL:
            warnings.append(
                f"CoCo conversion alpha {coco.get('alpha')} is not at the going->gone "
                f"boundary {boundary}; convertible capital should trigger at the boundary"
            )

    # Waterfall proof via the kernel's structural_transform (if a pool is supplied).
    waterfall = None
    pool = spec.get("loss_pool_samples")
    if pool:
        losses = [abs(float(x)) for x in pool]
        # LossDistribution stores returns (negative == loss); pass -loss so .losses == loss.
        layer_absorption = _waterfall_absorption(layers, [-x for x in losses])
        total_cap = layers[-1]["detach"]
        el = sum(losses) / len(losses)
        capped_el = sum(min(x, total_cap) for x in losses) / len(losses)
        absorbed_sum = sum(w["expected_absorbed_loss"] for w in layer_absorption)
        conserved = abs(absorbed_sum - capped_el) <= 1e-4
        if not conserved:
            raise ConcernLadderError(
                "REJECTED: waterfall layers do not conserve the pool loss "
                f"(sum absorbed {absorbed_sum} != capped EL {capped_el})"
            )
        waterfall = {
            "layers": layer_absorption,
            "pool_expected_loss": el,
            "capped_expected_loss": capped_el,
            "sum_absorbed": absorbed_sum,
            "conserved": conserved,
        }

    flagged = [s["name"] for s in scenarios if s["verdict"] == "flagged"]

    body = {
        "contract_id": contract_id,
        "as_of": as_of,
        "going_gone_boundary_alpha": boundary,
        "coco_conversion": coco,
        "capital_stack": [
            {k: layer[k] for k in ("layer", "concern", "kind", "amount", "attach", "detach")}
            for layer in layers
        ],
        "total_capital": layers[-1]["detach"],
        "scenarios": scenarios,
        "waterfall": waterfall,
        "flagged_scenarios": flagged,
        "monotone_alphas": True,
        "soft_references": {
            "structural_transform_kernel": KERNEL_WATERFALL_REF,
            "omnirisk_walker": OMNIRISK_WALKER_REF,
        },
        "warnings": warnings,
    }
    receipt = dict(body)
    receipt["input_hash"] = _sha256(_canonical(spec))
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_concern_ladder(path: str) -> dict:
    """Load, schema-validate and evaluate a ConcernLadder contract fixture."""
    validate_json_file(path, _SCHEMA)
    spec = json.loads(Path(path).read_text())
    return evaluate_contract(spec)
