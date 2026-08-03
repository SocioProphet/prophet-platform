from .domain import CapitalStack

def capital_charge(capital: CapitalStack, hurdle_rate: float) -> float:
    return capital.total * hurdle_rate
