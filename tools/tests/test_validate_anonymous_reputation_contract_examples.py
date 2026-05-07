from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_validator_module(repo_root: Path) -> ModuleType:
    module_path = repo_root / "tools" / "validate_anonymous_reputation_contract_examples.py"
    spec = importlib.util.spec_from_file_location("validate_anonymous_reputation_contract_examples", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_anonymous_reputation_contract_examples_validate() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    module = load_validator_module(repo_root)
    module.validate_all(repo_root)
