from pathlib import Path

from tools.validate_identity_contract_examples import validate_all


def test_identity_contract_examples_validate() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    validate_all(repo_root)
