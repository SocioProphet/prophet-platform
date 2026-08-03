from .domain import FTPStack

def ftp_rate(stack: FTPStack) -> float:
    """Return total FTP rate as a decimal annualized rate."""
    bps = (
        stack.matched_maturity_base_bps
        + stack.term_premium_bps
        + stack.liquidity_premium_bps
        + stack.optionality_charge_bps
        + stack.contingent_draw_charge_bps
        + stack.stress_surcharge_bps
        - stack.stable_funding_credit_bps
        - stack.franchise_credit_bps
    )
    return bps / 10000.0
