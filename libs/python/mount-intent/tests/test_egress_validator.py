"""The egress validator must pass on the real repo and fail-closed on violations."""
import importlib.util
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / "tools" / "validate_mount_intent_egress.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("veg", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validator_passes_on_repo():
    assert _load_validator().main() == 0


def test_edge_twin_sync_declares_only_canonical():
    cj = ROOT / "infra/k8s/edge-twin-sync/base/sync-cronjob.yaml"
    doc = next(d for d in yaml.safe_load_all(cj.read_text()) if isinstance(d, dict) and d.get("kind") == "CronJob")
    ann = doc["metadata"]["annotations"]["mount-intent.socioprophet.io/egress"]
    assert ann == "canonical_data"  # only the source of truth crosses


def test_validator_rejects_non_egressable(tmp_path, monkeypatch):
    # a sync job that tries to egress derived_index must be refused
    mod = _load_validator()
    bad = tmp_path / "edge-twin-sync"
    bad.mkdir()
    (bad / "bad.yaml").write_text(
        "apiVersion: batch/v1\nkind: CronJob\nmetadata:\n  name: leaky\n"
        "  annotations:\n    mount-intent.socioprophet.io/egress: derived_index\nspec: {}\n"
    )
    monkeypatch.setattr(mod, "SYNC_DIR", bad)
    assert mod.main() == 1


def test_validator_fails_closed_on_missing_annotation(tmp_path, monkeypatch):
    mod = _load_validator()
    d = tmp_path / "edge-twin-sync"
    d.mkdir()
    (d / "nolabel.yaml").write_text(
        "apiVersion: batch/v1\nkind: CronJob\nmetadata:\n  name: undeclared\nspec: {}\n"
    )
    monkeypatch.setattr(mod, "SYNC_DIR", d)
    assert mod.main() == 1  # egress must be declared, not implicit
