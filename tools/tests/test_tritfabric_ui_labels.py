from tools.validate_tritfabric_ui_labels import load_contract, validate_contract


def test_tritfabric_ui_label_contract():
    validate_contract(load_contract())
