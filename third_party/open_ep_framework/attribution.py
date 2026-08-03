def single_period_attribution(old: dict, new: dict) -> dict:
    """Simple EP attribution template.

    This is intentionally conservative. A production implementation should
    decompose EP movement by price, volume, utilization, funding/FTP, expected
    loss, recovery, capital, tax, expense, and hedge transfer.
    """
    keys = [
        "revenue",
        "expected_loss",
        "expense",
        "funding_costs",
        "funding_credits",
        "taxes",
        "capital_charge",
        "economic_profit",
    ]
    delta = {k: new.get(k, 0.0) - old.get(k, 0.0) for k in keys}
    return {
        "price": delta.get("revenue", 0.0),
        "expected_loss": -delta.get("expected_loss", 0.0),
        "expense": -delta.get("expense", 0.0),
        "funding": -delta.get("funding_costs", 0.0) + delta.get("funding_credits", 0.0),
        "tax": -delta.get("taxes", 0.0),
        "capital": -delta.get("capital_charge", 0.0),
        "unexplained": delta.get("economic_profit", 0.0)
        - (delta.get("revenue", 0.0)
           - delta.get("expected_loss", 0.0)
           - delta.get("expense", 0.0)
           - delta.get("funding_costs", 0.0)
           + delta.get("funding_credits", 0.0)
           - delta.get("taxes", 0.0)
           - delta.get("capital_charge", 0.0)),
    }
