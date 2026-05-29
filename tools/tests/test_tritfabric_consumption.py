from tools.validate_tritfabric_consumption import load_contract, validate_contract


def test_tritfabric_consumption_contract():
    validate_contract(load_contract())
