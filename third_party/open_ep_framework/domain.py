from dataclasses import dataclass

@dataclass
class FTPStack:
    matched_maturity_base_bps: float
    term_premium_bps: float
    liquidity_premium_bps: float
    optionality_charge_bps: float
    contingent_draw_charge_bps: float
    stress_surcharge_bps: float
    stable_funding_credit_bps: float
    franchise_credit_bps: float

@dataclass
class ExpectedLossInputs:
    pd: float
    lgd: float
    ead: float

@dataclass
class RecoverySurfaceInputs:
    seniority: float
    collateral_quality: float
    jurisdiction_score: float
    macro_regime: str
    liquidity_regime: str
    workout_horizon_days: int
    market_state_price: float

@dataclass
class CapitalStack:
    total: float
    credit: float
    market: float
    operational: float
    business: float

@dataclass
class PricingContext:
    balance: float
    fee_income: float
    expense: float
    tax_rate: float
    funding_credits: float
    horizon_years: float
