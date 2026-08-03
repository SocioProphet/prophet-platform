"""Crypto as a distinct asset class for Economic Prophet (CAV-1 / BR-1 / MS-1).

Crypto is NOT credit and NOT equity: most tokens have no cash flows, exhibit
extreme reflexivity, and derive value from network, narrative and psychology. The
credit/equity DCF machinery therefore does NOT apply. This package supplies crypto
its own valuation criteria (network / fee / memetic) and its own reflexive loss
distribution F, while REUSING the estate's risk kernel and receipt spine by
reference rather than forking them.

Three contracts, one asset class:

  * ``valuation``          -- CAV-1 CryptoAssetValuation. Tokenomics + on-chain +
                              Metcalfe/NVT network value + a modified economic profit
                              (fee_revenue - security_cost - emission_dilution -
                              risk_capital) + an evidence-bound memetic/information
                              value. Guards against the wrong (DCF) model.
  * ``behavioral_regime``  -- BR-1 BehavioralRegime. A 2-state greed/fear Markov
                              regime-switching overlay (Hamilton filter) plus a
                              prospect-theory value/probability distortion.
  * ``manipulation``       -- MS-1 ManipulationSignal. Adverse selection
                              (Glosten-Milgrom / Kyle) extended with concentration
                              (whale/Gini), wash-trade and MEV indicators, emitted in
                              a GBRG-governance-plane shape.

Consume-by-reference hooks (do NOT fork):
  * risk kernel      -- ``open_ep_framework.risk_measures`` (RM-1): the reflexive
                        fat-tailed F is shaped for the kernel's LPM / Expected
                        Shortfall, which supplies ``risk_capital``.
  * memory-regime    -- the BR-1 regime carries the memory-mesh characterizer's
                        arrival-regime taxonomy label (reflexive/self-exciting ==
                        the Hawkes / long-memory arrival regime).
  * GBRG plane       -- MS-1 emits a governed-blast-radius-graph-shaped signal for
                        the governance/containment plane.
  * microstructure   -- the MS-1 adverse-selection block is shaped to consume the
                        in-flight order-flow contract (feat/microstructure-order-flow).

Deterministic and stdlib-only (analytic where possible, seeded PRNG otherwise), so
CI is reproducible. Measurement, simulation and audit only: no live on-chain feeds,
token issuance, custody, or trading.
"""
from .behavioral_regime import BehavioralRegimeError, evaluate_behavioral_regime, run_behavioral_regime
from .manipulation import ManipulationError, evaluate_manipulation, run_manipulation
from .valuation import CryptoValuationError, evaluate_valuation, run_valuation

__all__ = [
    "CryptoValuationError",
    "evaluate_valuation",
    "run_valuation",
    "BehavioralRegimeError",
    "evaluate_behavioral_regime",
    "run_behavioral_regime",
    "ManipulationError",
    "evaluate_manipulation",
    "run_manipulation",
]
