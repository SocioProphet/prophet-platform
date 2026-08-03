from .domain import ExpectedLossInputs

def expected_loss_amount(el: ExpectedLossInputs) -> float:
    return el.pd * el.lgd * el.ead
