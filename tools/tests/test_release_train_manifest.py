"""Prove the release-train freeze + validate enforce the deploy-wave invariants both ways.

Positive: a digest-pinned lock freezes and validates. Negatives: a moving-tag lock is REFUSED
at freeze (INV-DEP-1), and a manifest that freezes one image at two digests is REFUSED at
validate (INV-DEP-2, a per-wave rebuild leaked in). Also proves the queue-vs-cancel concurrency
contract (COST GUARD 2 / INV-DEP-5) is actually declared in the shipped workflow YAML.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FREEZE = _load("freeze_release_train_manifest")
VALIDATE = _load("validate_release_train_manifest")

IMAGE = "ghcr.io/socioprophet/prophet-platform/search-orchestrator"
GOOD_DIGEST = "sha256:" + ("b" * 64)


def _write_lock(path: Path, digest: str, pinned_ref: str) -> None:
    path.write_text(json.dumps({
        "image_lock_id": "x", "component": "services/search-orchestrator",
        "image": IMAGE, "source_sha": "abc", "digest": digest,
        "pinned_ref": pinned_ref, "status": "pinned",
    }), encoding="utf-8")


def test_freeze_accepts_digest_pinned_lock(tmp_path) -> None:
    _write_lock(tmp_path / "a.image-lock.json", GOOD_DIGEST, f"{IMAGE}@{GOOD_DIGEST}")
    manifest = FREEZE.freeze(str(tmp_path / "*.image-lock.json"),
                             tmp_path / "no-inventory.yaml", ["dev", "canary", "prod"], "t")
    assert manifest["component_count"] == 1
    assert manifest["components"][0]["pinned_ref"] == f"{IMAGE}@{GOOD_DIGEST}"
    assert VALIDATE.validate(manifest) == [], "a clean frozen set must validate"


def test_freeze_refuses_moving_tag(tmp_path) -> None:
    # A moving tag (:latest) is exactly the estate trap — must be refused at freeze (INV-DEP-1).
    _write_lock(tmp_path / "a.image-lock.json", GOOD_DIGEST, f"{IMAGE}:latest")
    try:
        FREEZE.freeze(str(tmp_path / "*.image-lock.json"),
                      tmp_path / "no-inv.yaml", ["dev"], "t")
    except SystemExit as exc:
        assert "INV-DEP-1" in str(exc)
    else:
        raise AssertionError("a moving-tag pinned_ref must be REFUSED at freeze")


def test_validate_refuses_two_digests_for_one_image() -> None:
    other = "sha256:" + ("c" * 64)
    manifest = {
        "kind": "release-train-frozen-image-set",
        "wave_order": ["dev", "prod"],
        "gates": {"per_wave": ["preflight-deploy-contract"], "fail_closed": True},
        "components": [
            {"id": "s", "image": IMAGE, "digest": GOOD_DIGEST, "pinned_ref": f"{IMAGE}@{GOOD_DIGEST}"},
            {"id": "s", "image": IMAGE, "digest": other, "pinned_ref": f"{IMAGE}@{other}"},
        ],
    }
    errors = VALIDATE.validate(manifest)
    assert any("INV-DEP-2" in e for e in errors), "two digests for one image = leaked rebuild"


def test_validate_refuses_non_failclosed_gates() -> None:
    manifest = {
        "kind": "release-train-frozen-image-set",
        "wave_order": ["dev"],
        "gates": {"per_wave": ["preflight-deploy-contract"], "fail_closed": False},
        "components": [
            {"id": "s", "image": IMAGE, "digest": GOOD_DIGEST, "pinned_ref": f"{IMAGE}@{GOOD_DIGEST}"},
        ],
    }
    errors = VALIDATE.validate(manifest)
    assert any("fail_closed" in e for e in errors), "a gate that cannot fail is no gate"


def test_committed_manifest_validates() -> None:
    committed = ROOT / "releases/manifests/release-train.2026-08-02.manifest.json"
    data = json.loads(committed.read_text(encoding="utf-8"))
    assert VALIDATE.validate(data) == [], "the shipped example manifest must be legal"


def test_image_workflows_queue_on_main_cancel_on_feature() -> None:
    """COST GUARD 2 / INV-DEP-5 — the per-component image workflows must QUEUE main builds
    (cancel-in-progress != true on main) and CANCEL feature builds. Asserted against the
    shipped YAML text so the contract can't silently regress."""
    import yaml
    for wf in ["socioprophet-api-image", "tritrpc-gateway-image", "search-orchestrator-image"]:
        doc = yaml.safe_load((ROOT / ".github/workflows" / f"{wf}.yml").read_text(encoding="utf-8"))
        conc = doc["concurrency"]
        # The expression evaluates to false on refs/heads/main (queue) and true elsewhere (cancel).
        assert conc["cancel-in-progress"] == "${{ github.ref != 'refs/heads/main' }}", wf
        assert "changes" in doc["jobs"], f"{wf} must have a change-detection preflight job"


def test_release_and_wave_workflows_never_cancel() -> None:
    import yaml
    for wf in ["release-train", "wave-promote"]:
        doc = yaml.safe_load((ROOT / ".github/workflows" / f"{wf}.yml").read_text(encoding="utf-8"))
        assert doc["concurrency"]["cancel-in-progress"] is False, \
            f"{wf} must QUEUE, never cancel a promotion mid-flight"
