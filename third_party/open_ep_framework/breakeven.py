from .capital import capital_charge
from .domain import CapitalStack, ExpectedLossInputs, FTPStack, PricingContext, RecoverySurfaceInputs
from .expected_loss import expected_loss_amount
from .ftp import ftp_rate
from .recovery import recovery_wedge


def economic_profit_for_rate(
    customer_rate: float,
    context: PricingContext,
    ftp_stack: FTPStack,
    expected_loss: ExpectedLossInputs,
    capital: CapitalStack,
    recovery_surface: RecoverySurfaceInputs,
    hurdle_rate: float,
) -> float:
    """Compute a conservative one-period forward EP estimate for a customer rate.

    This is the first reference implementation of the zero-EP pricing surface.
    It intentionally remains simple: revenue is customer_rate * balance plus fee
    income, FTP is a balance charge, expected loss is PD * LGD * EAD, and the
    recovery wedge increases required return when market-implied recovery is
    below planning recovery.
    """
    revenue = customer_rate * context.balance * context.horizon_years + context.fee_income
    el_amount = expected_loss_amount(expected_loss)
    funding_cost = ftp_rate(ftp_stack) * context.balance * context.horizon_years
    cap_charge = capital_charge(capital, hurdle_rate) * context.horizon_years
    recovery_wedge_charge = -recovery_wedge(recovery_surface) * el_amount
    pre_tax = (
        revenue
        - el_amount
        - context.expense
        - funding_cost
        + context.funding_credits
        - cap_charge
        - recovery_wedge_charge
    )
    tax = max(pre_tax, 0.0) * context.tax_rate
    return pre_tax - tax


def solve_break_even_rate(
    context: PricingContext,
    ftp_stack: FTPStack,
    expected_loss: ExpectedLossInputs,
    capital: CapitalStack,
    recovery_surface: RecoverySurfaceInputs,
    hurdle_rate: float,
    lower: float = 0.0,
    upper: float = 0.50,
    tolerance: float = 1e-8,
    max_iterations: int = 100,
) -> float:
    """Solve for the customer rate where forward EP is approximately zero."""
    lo = lower
    hi = upper
    f_lo = economic_profit_for_rate(lo, context, ftp_stack, expected_loss, capital, recovery_surface, hurdle_rate)
    f_hi = economic_profit_for_rate(hi, context, ftp_stack, expected_loss, capital, recovery_surface, hurdle_rate)

    if f_lo >= 0.0:
        return lo
    if f_hi <= 0.0:
        raise ValueError("upper bound does not produce positive EP; raise upper bound")

    for _ in range(max_iterations):
        mid = (lo + hi) / 2.0
        f_mid = economic_profit_for_rate(mid, context, ftp_stack, expected_loss, capital, recovery_surface, hurdle_rate)
        if abs(f_mid) <= tolerance:
            return mid
        if f_mid > 0.0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0
