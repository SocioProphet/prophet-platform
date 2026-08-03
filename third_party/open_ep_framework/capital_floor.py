"""R-Cap vs E-Cap with the Basel regulatory floor (RFL-1).

Two capital numbers must be stated for every node in the estate omnirisk/EP spine:
the regulator's (**R-Cap**, Basel ``8% x RWA``) and the bank's own diversified
economic capital (**E-Cap**, the coherent-tail Euler contribution the kernel already
produces). This contract carries them as PARALLEL per-node measures, forms the
**E-Cap/R-Cap ratio**, and enforces the **regulatory floor**::

    allocated_capital = max(economic_capital_contribution, regulatory_floor)

with the divergence flagged. The teeth make the McKinsey Working Papers on Risk #38
footnote enforceable: *diversification can lower a node's economic capital, but it
can never lower it below the regulatory minimum silently.*

Consume, do NOT reinvent
------------------------
  * ``regulatory_capital`` (economic-prophet #42) -- the genuine Basel IRB-Advanced
    corporate risk-weight function. R-Cap here is ``target_capital_ratio x RWA`` with
    RWA from ``irb_regulatory_capital``; the standardized path takes RWA directly.
  * ``risk_measures`` (RM-1, #43/#44) -- ``euler_allocation`` supplies the diversified
    E-Cap contribution per node (coherent ES/spectral, so contributions conserve). It
    is given to this layer as a labelled node input, exactly as the GBRG walker takes
    its node inputs (see ``KERNEL_*`` / ``OMNIRISK_WALKER_REF`` soft references).
  * ``settlement`` (IC-1, #39) -- the FIPS SHA-256 ``sha256:`` receipt spine.

Teeth (verdicts)
----------------
  * VERIFIED -- E-Cap contribution >= R-Cap floor (economic binds); ratio reconciles.
  * FLAGGED  -- the regulatory floor binds (E-Cap < R-Cap): allocated at the floor,
        divergence recorded. The floor did its job; the node is over-diversified.
  * REJECTED (raises) --
        a node whose diversified E-Cap is below its regulatory minimum but whose
            ``declared_allocated_capital`` is that sub-floor E-Cap figure (silent
            sub-floor diversification -- the #38 footnote);
        the E-Cap/R-Cap ratio does not reconcile to its inputs;
        the 8% target-ratio assumption is absent, non-positive, or inconsistent with
            R-Cap = target_ratio x RWA;
        a non-positive regulatory floor (no denominator for the ratio).

Measurement, simulation and audit only. Deterministic + stdlib.
"""
from __future__ import annotations

import json
from pathlib import Path

from .regulatory_capital import irb_regulatory_capital
from .settlement import _canonical, _sha256
from .validation import validate_json_file

_SCHEMA = "schemas/capital_floor.schema.json"

# Basel minimum total-capital ratio. Asserted, never assumed silently.
BASEL_CAPITAL_RATIO = 0.08
_TOL = 1e-6

# Soft references (consumed by reference, not re-implemented).
KERNEL_REGCAP_REF = "economic-prophet:src/open_ep_framework/regulatory_capital.py"
KERNEL_EULER_REF = "economic-prophet:src/open_ep_framework/risk_measures.py#euler_allocation"
OMNIRISK_WALKER_REF = "sociosphere:gbrg/governance/omnirisk_allocation.py (OMNI-1)"


class CapitalFloorError(ValueError):
    """Raised when a node cannot be allocated under the regulatory floor (REJECTED)."""


# --------------------------------------------------------------------------- #
# regulatory capital (R-Cap) per node
# --------------------------------------------------------------------------- #
def _regulatory_capital(reg: dict, target_ratio: float) -> tuple[float, float, dict]:
    """Return (r_cap, rwa, readout). R-Cap = target_ratio x RWA.

    Standardized: RWA is given directly. IRB: RWA comes from the Basel corporate
    risk-weight function (``irb_regulatory_capital``); we then apply the DECLARED
    target ratio so the 8% assumption is used, not buried inside the kernel call.
    """
    if "rwa" in reg and reg["rwa"] is not None:
        rwa = float(reg["rwa"])
        readout = {"approach": "standardized", "rwa": round(rwa, 4)}
    elif {"pd", "lgd", "ead"} <= set(reg):
        irb = irb_regulatory_capital(
            float(reg["pd"]), float(reg["lgd"]), float(reg["ead"]),
            float(reg.get("maturity", 2.5)),
        )
        rwa = float(irb["rwa"])
        readout = {"approach": irb["approach"], "rwa": irb["rwa"],
                   "capital_requirement_K": irb["capital_requirement_K"],
                   "expected_loss": irb["expected_loss"]}
    else:
        raise CapitalFloorError(
            "REJECTED: node.regulatory needs either 'rwa' (standardized) or "
            "'pd'/'lgd'/'ead' (IRB) to form a regulatory floor"
        )
    r_cap = target_ratio * rwa
    return r_cap, rwa, readout


# --------------------------------------------------------------------------- #
# single node: E-Cap vs R-Cap, the floor, and the ratio
# --------------------------------------------------------------------------- #
def evaluate_node(node: dict, target_ratio: float) -> dict:
    node_id = node["node_id"]
    e_cap = float(node["economic_capital_contribution"])
    r_cap, rwa, reg_readout = _regulatory_capital(node["regulatory"], target_ratio)

    if r_cap <= 0.0:
        # No denominator for the ratio, no floor to enforce.
        raise CapitalFloorError(
            f"REJECTED: node {node_id!r} has a non-positive regulatory floor "
            f"(RWA={rwa}); cannot form an E-Cap/R-Cap ratio"
        )

    # The 8% assumption must be self-consistent: R-Cap == target_ratio x RWA.
    if abs(r_cap - target_ratio * rwa) > _TOL:
        raise CapitalFloorError(
            f"REJECTED: node {node_id!r} regulatory capital {r_cap} != "
            f"target_ratio {target_ratio} x RWA {rwa} (the 8% assumption is inconsistent)"
        )

    ratio = e_cap / r_cap  # E-Cap / R-Cap
    # Teeth: the ratio must reconcile to its inputs.
    if abs(ratio * r_cap - e_cap) > _TOL:
        raise CapitalFloorError(
            f"REJECTED: node {node_id!r} E-Cap/R-Cap ratio {ratio} does not "
            f"reconcile (ratio x R-Cap {ratio * r_cap} != E-Cap {e_cap})"
        )

    allocated = max(e_cap, r_cap)          # the regulatory floor
    binding = "economic" if e_cap >= r_cap else "regulatory"
    divergence = e_cap - r_cap
    floor_binds = binding == "regulatory"

    warnings: list[str] = []
    if floor_binds:
        warnings.append(
            f"divergence flagged: diversified E-Cap {e_cap} is below the regulatory "
            f"floor {r_cap}; allocated at the floor (E-Cap/R-Cap={ratio:.4f} < 1)"
        )

    # Teeth: a declared allocation BELOW the floor is silent sub-floor diversification.
    declared = node.get("declared_allocated_capital")
    if declared is not None:
        declared = float(declared)
        if declared < r_cap - _TOL:
            raise CapitalFloorError(
                f"REJECTED: node {node_id!r} declares allocated capital {declared} "
                f"below its regulatory floor {r_cap}. You cannot diversify under the "
                f"regulatory minimum silently (McKinsey WP #38). "
                f"allocated_capital must be max(E-Cap {e_cap}, R-Cap {r_cap}) = {allocated}"
            )
        if abs(declared - allocated) > _TOL:
            warnings.append(
                f"declared allocated capital {declared} != floored allocation {allocated}; "
                "using the floored allocation"
            )

    verdict = "flagged" if floor_binds else "verified"
    return {
        "node_id": node_id,
        "economic_capital": e_cap,
        "regulatory_capital": r_cap,
        "regulatory_detail": reg_readout,
        "ecap_rcap_ratio": ratio,
        "allocated_capital": allocated,
        "binding_constraint": binding,
        "divergence_economic_minus_regulatory": divergence,
        "floor_binds": floor_binds,
        "verdict": verdict,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# portfolio: roll up the floored allocations
# --------------------------------------------------------------------------- #
def evaluate_contract(spec: dict) -> dict:
    contract_id = spec.get("contract_id", "rfl")
    as_of = spec.get("as_of", "")
    approach = spec.get("approach", "IRB-Advanced")

    assumptions = spec.get("assumptions") or {}
    if "target_capital_ratio" not in assumptions:
        raise CapitalFloorError(
            "REJECTED: assumptions.target_capital_ratio is required "
            "(the 8% Basel ratio must be asserted, not assumed silently)"
        )
    target_ratio = float(assumptions["target_capital_ratio"])
    if target_ratio <= 0.0:
        raise CapitalFloorError("REJECTED: target_capital_ratio must be positive")

    nodes = [evaluate_node(n, target_ratio) for n in spec["nodes"]]

    sum_ecap = sum(n["economic_capital"] for n in nodes)
    sum_rcap = sum(n["regulatory_capital"] for n in nodes)
    sum_allocated = sum(n["allocated_capital"] for n in nodes)
    portfolio_ratio = sum_ecap / sum_rcap if sum_rcap > 0 else None

    warnings: list[str] = []
    # The floor is applied per node, so the portfolio allocation can never fall below
    # either the summed economic OR the summed regulatory capital -- the floor cannot
    # be diversified away at the portfolio level either.
    if sum_allocated < sum_rcap - _TOL or sum_allocated < sum_ecap - _TOL:
        raise CapitalFloorError(
            "REJECTED: floored portfolio allocation fell below a summed capital total "
            "(floor conservation violated)"
        )
    if abs((portfolio_ratio or 0.0) * sum_rcap - sum_ecap) > _TOL and sum_rcap > 0:
        raise CapitalFloorError(
            "REJECTED: portfolio E-Cap/R-Cap ratio does not reconcile to summed inputs"
        )

    flagged = [n["node_id"] for n in nodes if n["verdict"] == "flagged"]
    if flagged:
        warnings.append(f"regulatory floor binds on nodes: {flagged}")

    body = {
        "contract_id": contract_id,
        "as_of": as_of,
        "approach": approach,
        "assumptions": {"target_capital_ratio": target_ratio,
                        "basel_minimum": BASEL_CAPITAL_RATIO,
                        "asserted": abs(target_ratio - BASEL_CAPITAL_RATIO) <= _TOL},
        "nodes": nodes,
        "portfolio": {
            "sum_economic_capital": sum_ecap,
            "sum_regulatory_capital": sum_rcap,
            "sum_allocated_capital": sum_allocated,
            "ecap_rcap_ratio": portfolio_ratio,
            "binding_constraint": "economic" if sum_ecap >= sum_rcap else "regulatory",
            "floor_uplift": sum_allocated - sum_ecap,
        },
        "soft_references": {
            "regulatory_capital_kernel": KERNEL_REGCAP_REF,
            "euler_allocation_kernel": KERNEL_EULER_REF,
            "omnirisk_walker": OMNIRISK_WALKER_REF,
        },
        "warnings": warnings,
    }
    receipt = dict(body)
    receipt["input_hash"] = _sha256(_canonical(spec))
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_capital_floor(path: str) -> dict:
    """Load, schema-validate and evaluate a RegulatoryCapitalFloor contract fixture."""
    validate_json_file(path, _SCHEMA)
    spec = json.loads(Path(path).read_text())
    return evaluate_contract(spec)
