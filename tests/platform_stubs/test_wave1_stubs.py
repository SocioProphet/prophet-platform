from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_app(relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.app


def test_identity_policy_app_title():
    app = load_app('apps/identity-policy/main.py')
    assert app.title == 'identity-policy'


def test_dashboard_bff_app_title():
    app = load_app('apps/dashboard-bff/main.py')
    assert app.title == 'dashboard-bff'


def test_deepdive_orchestrator_app_title():
    app = load_app('apps/deepdive-orchestrator/main.py')
    assert app.title == 'deepdive-orchestrator'
