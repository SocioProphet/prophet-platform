"""ManipulationSignal contract (MS-1) -- predatory-cartel / information asymmetry.

The honesty/governance layer for the crypto asset class. It extends the classic
adverse-selection microstructure models with crypto-native manipulation indicators
and emits a governed signal shaped for the GBRG (governed-blast-radius-graph)
governance plane.

Adverse selection (consume the microstructure order-flow contract by reference)
-------------------------------------------------------------------------------
  * Glosten-Milgrom -- the adverse-selection spread an honest market maker must quote
    given a probability of informed trading (PIN):
        gm_spread = 2 * pin * (value_high - value_low).
  * Kyle -- price impact / inverse depth of a market with an informed trader:
        kyle_lambda = sigma_v / (2 * sigma_u)
    (higher lambda == thinner, more exploitable market). These blocks are shaped to
    consume the in-flight order-flow contract (feat/microstructure-order-flow).

Crypto-native manipulation indicators
--------------------------------------
  * Concentration -- whale risk via the Gini coefficient of holdings and the top-1
    holder share (a cartel can move price at will).
  * Wash trading -- self-trade share of reported volume and a volume-inflation ratio
    (reported vs on-chain-settled volume).
  * MEV -- maximal extractable value intensity = MEV extracted / volume (sandwiching,
    front-running: predation on ordinary flow).

Teeth (both directions)
-----------------------
  * VERIFIES -- a high-concentration + wash-trade fixture raises a ManipulationSignal
    with a non-empty evidence list and a non-clean verdict.
  * REJECTS  -- an ``attested_clean`` claim on a fixture whose concentration is above
    threshold is a contradiction and is REJECTED (an attestation cannot override the
    on-chain evidence).

Deterministic and stdlib-only. Measurement, simulation and audit only.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..settlement import _canonical, _sha256
from ..validation import validate_json_file

_SCHEMA = "schemas/manipulation_signal.schema.json"

# Detection thresholds (documented, tunable). Above threshold == an indicator fires.
GINI_THRESHOLD = 0.90
TOP_HOLDER_SHARE_THRESHOLD = 0.50
WASH_SELF_TRADE_THRESHOLD = 0.30
VOLUME_INFLATION_THRESHOLD = 3.0
MEV_INTENSITY_THRESHOLD = 0.02


class ManipulationError(ValueError):
    """Raised when a manipulation claim is inadmissible / contradicted (REJECTED)."""


# --------------------------------------------------------------------------- #
# concentration
# --------------------------------------------------------------------------- #
def gini(balances: list) -> float:
    """Gini coefficient of a holdings distribution (0 == equal, ->1 == one whale)."""
    xs = sorted(float(b) for b in balances if float(b) >= 0)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total <= 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(xs, start=1):
        cum += i * x
    return (2.0 * cum) / (n * total) - (n + 1.0) / n


def _concentration(spec: dict) -> dict:
    holders = spec.get("holders")
    if holders:
        g = gini(holders)
        total = sum(float(b) for b in holders)
        top = max(float(b) for b in holders) / total if total > 0 else 0.0
    else:
        g = float(spec.get("gini", 0.0))
        top = float(spec.get("top_holder_share", 0.0))
    return {
        "gini": g,
        "top_holder_share": top,
        "flag": bool(g > GINI_THRESHOLD or top > TOP_HOLDER_SHARE_THRESHOLD),
    }


# --------------------------------------------------------------------------- #
# wash trading + MEV
# --------------------------------------------------------------------------- #
def _wash(spec: dict) -> dict:
    reported = float(spec.get("reported_volume", 0.0))
    settled = float(spec.get("onchain_settled_volume", reported))
    self_trade = float(spec.get("self_trade_volume", 0.0))
    self_share = self_trade / reported if reported > 0 else 0.0
    inflation = reported / settled if settled > 0 else float("inf")
    return {
        "self_trade_share": self_share,
        "volume_inflation": inflation,
        "flag": bool(
            self_share > WASH_SELF_TRADE_THRESHOLD or inflation > VOLUME_INFLATION_THRESHOLD
        ),
    }


def _mev(spec: dict) -> dict:
    extracted = float(spec.get("mev_extracted", 0.0))
    volume = float(spec.get("block_volume", spec.get("reported_volume", 0.0)))
    intensity = extracted / volume if volume > 0 else 0.0
    return {
        "mev_extracted": extracted,
        "mev_intensity": intensity,
        "flag": bool(intensity > MEV_INTENSITY_THRESHOLD),
    }


# --------------------------------------------------------------------------- #
# adverse selection (Glosten-Milgrom / Kyle)
# --------------------------------------------------------------------------- #
def _adverse_selection(spec: dict) -> dict:
    pin = float(spec.get("pin", 0.0))  # probability of informed trading
    value_high = float(spec.get("value_high", 0.0))
    value_low = float(spec.get("value_low", 0.0))
    gm_spread = 2.0 * pin * (value_high - value_low)

    sigma_v = float(spec.get("sigma_v", 0.0))  # fundamental value volatility
    sigma_u = float(spec.get("sigma_u", 0.0))  # noise (uninformed) order flow
    kyle_lambda = sigma_v / (2.0 * sigma_u) if sigma_u > 0 else float("inf")
    return {
        "pin": pin,
        "glosten_milgrom_spread": gm_spread,
        "kyle_lambda": kyle_lambda,
        # Shaped to consume the in-flight microstructure order-flow contract.
        "consumes": "feat/microstructure-order-flow-contract",
        "flag": bool(pin > 0.4 or (sigma_u > 0 and kyle_lambda > 1.0)),
    }


# --------------------------------------------------------------------------- #
# signal
# --------------------------------------------------------------------------- #
_WEIGHTS = {"concentration": 0.35, "wash": 0.30, "mev": 0.20, "adverse_selection": 0.15}


def evaluate_manipulation(spec: dict) -> dict:
    """Evaluate MS-1: build indicators, assemble evidence, emit a GBRG signal."""
    subject = spec.get("subject", "crypto-asset")
    concentration = _concentration(spec.get("concentration", {}))
    wash = _wash(spec.get("volume", {}))
    mev = _mev(spec.get("mev", {}))
    adverse = _adverse_selection(spec.get("adverse_selection", {}))

    indicators = {
        "concentration": concentration,
        "wash": wash,
        "mev": mev,
        "adverse_selection": adverse,
    }

    evidence = []
    if concentration["flag"]:
        evidence.append({
            "indicator": "concentration",
            "gini": concentration["gini"],
            "top_holder_share": concentration["top_holder_share"],
            "thresholds": {"gini": GINI_THRESHOLD, "top_holder_share": TOP_HOLDER_SHARE_THRESHOLD},
        })
    if wash["flag"]:
        evidence.append({
            "indicator": "wash_trade",
            "self_trade_share": wash["self_trade_share"],
            "volume_inflation": wash["volume_inflation"],
            "thresholds": {"self_trade_share": WASH_SELF_TRADE_THRESHOLD, "volume_inflation": VOLUME_INFLATION_THRESHOLD},
        })
    if mev["flag"]:
        evidence.append({
            "indicator": "mev",
            "mev_intensity": mev["mev_intensity"],
            "threshold": MEV_INTENSITY_THRESHOLD,
        })
    if adverse["flag"]:
        evidence.append({
            "indicator": "adverse_selection",
            "glosten_milgrom_spread": adverse["glosten_milgrom_spread"],
            "kyle_lambda": adverse["kyle_lambda"],
            "pin": adverse["pin"],
        })

    severity = sum(_WEIGHTS[k] for k, ind in indicators.items() if ind["flag"])
    flagged = bool(evidence)

    # Teeth: an attestation of cleanliness cannot override on-chain evidence.
    if bool(spec.get("attested_clean", False)) and concentration["flag"]:
        raise ManipulationError(
            "REJECTED: attested_clean contradicts on-chain evidence -- concentration is "
            f"above threshold (gini={concentration['gini']:.4f}, "
            f"top_holder_share={concentration['top_holder_share']:.4f}); a manipulation-free "
            "claim on a whale-concentrated asset must be flagged, not attested away"
        )

    if not flagged:
        verdict = "clean"
    elif severity >= 0.5:
        verdict = "manipulated"
    else:
        verdict = "flagged"

    body = {
        "signal_id": spec.get("signal_id", f"ms1:{subject}"),
        "as_of": spec.get("as_of", ""),
        "subject": subject,
        "indicators": indicators,
        "severity": severity,
        "verdict": verdict,
        "evidence": evidence,
        # GBRG governance-plane shape (consumed by reference).
        "gbrg": {
            "signal_id": spec.get("signal_id", f"ms1:{subject}"),
            "subject": subject,
            "severity": severity,
            "verdict": verdict,
            "evidence_count": len(evidence),
            "blast_radius": spec.get("blast_radius", ["price_discovery", "counterparties", "index_inclusion"]),
            "containment": "quarantine_pending_review" if verdict == "manipulated" else (
                "monitor" if flagged else "none"
            ),
        },
    }
    receipt = dict(body)
    receipt["output_hash"] = _sha256(_canonical(body))
    receipt["receipt_hash"] = _sha256(_canonical(receipt))
    return receipt


def run_manipulation(path: str) -> dict:
    """Load, schema-validate and evaluate a ManipulationSignal fixture."""
    validate_json_file(path, _SCHEMA)
    spec = json.loads(Path(path).read_text())
    return evaluate_manipulation(spec)
