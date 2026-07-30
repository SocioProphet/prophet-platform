"""Coverage for tools/review_gate.py — the JIT review gate.

The gate reviews a REAL executor receipt: a 0.4.40→0.4.45 re-vendor is run on a temp copy
of the two consumers, then the gate verifies the result against the repo. Approve on a
faithful re-vendor; reject on a tampered seal, a failed step, a broken marker on disk, a
non-atomic move, or an out-of-scope diff; needs-human when the model raises a concern the
deterministic checks cannot. Every check has a red path here — a gate that cannot say no
is worthless.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REAL_045 = ROOT / "apps" / "hellgraph-service" / "vendor" / "socioprophet-hellgraph-0.4.45.tgz"
REAL_GUARD = ROOT / "apps" / "hellgraph-service" / "scripts" / "check-engine-version.mjs"
MARKER = 'PROP_NS = "prop:"'
CONSUMERS = ["hellgraph-service", "lifecycle-warden"]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


review_gate = _load("review_gate")
eng = _load("revendor_engine")


def _engine_tarball(path: Path, version: str, with_marker: bool) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in (
            ("package/package.json", json.dumps({"name": "@socioprophet/hellgraph", "version": version}).encode()),
            ("package/ts/dist/index.js", ((MARKER + "\n") if with_marker else "").encode() + b'const d = "prop:";'),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def _fixture(root: Path, start: str = "0.4.40", floor: str = "0.4.40") -> Path:
    guard = REAL_GUARD.read_text().replace("const MIN_ENGINE = '0.4.45'", f"const MIN_ENGINE = '{floor}'")
    for c in CONSUMERS:
        app = root / "apps" / c
        (app / "scripts").mkdir(parents=True, exist_ok=True)
        (app / "vendor").mkdir(parents=True, exist_ok=True)
        (app / "package.json").write_text(json.dumps({
            "name": c,
            "dependencies": {"@socioprophet/hellgraph": f"file:vendor/socioprophet-hellgraph-{start}.tgz"},
            "scripts": {"check:engine": "node scripts/check-engine-version.mjs"},
        }, indent=2) + "\n")
        (app / "scripts" / "check-engine-version.mjs").write_text(guard)
        _engine_tarball(app / "vendor" / f"socioprophet-hellgraph-{start}.tgz", start, with_marker=False)
    return root


@pytest.fixture(autouse=True)
def _no_net(monkeypatch):
    monkeypatch.setenv("HELLGRAPH_ENGINE_REMOTE", "file:///nonexistent")


def _applied(root: Path) -> dict:
    plan = eng.RevendorPlan(to_version="0.4.45", tarball=REAL_045, expect_markers=[MARKER], consumers=CONSUMERS)
    receipt = eng.execute(plan, root, apply=True)
    assert receipt["status"] == "applied", json.dumps(receipt, indent=2)
    return receipt


def _check(v, name):
    return next(c for c in v["checks"] if c["check"] == name)


def test_faithful_revendor_is_approved(tmp_path):
    root = _fixture(tmp_path)
    v = review_gate.review(_applied(root), root)
    assert v["verdict"] == review_gate.APPROVE, json.dumps(v, indent=2)
    assert all(c["ok"] for c in v["checks"])
    assert v["review_digest"].startswith("sha256:")


def test_tampered_seal_is_rejected(tmp_path):
    root = _fixture(tmp_path)
    receipt = _applied(root)
    receipt["steps"][0]["ok"] = "tampered"  # breaks the executor's seal without failing all_steps
    v = review_gate.review(receipt, root)
    assert v["verdict"] == review_gate.REJECT
    assert not _check(v, "seal_intact")["ok"]
    assert v["model"]["verdict"] == "skipped"  # fail-closed: model not consulted


def test_failed_step_is_rejected(tmp_path):
    root = _fixture(tmp_path)
    receipt = _applied(root)
    receipt["steps"].append({"step": "verify_guard", "ok": False, "evidence": {}})
    eng._seal(receipt)  # re-seal so seal_intact passes and all_steps_passed is what fails
    v = review_gate.review(receipt, root)
    assert v["verdict"] == review_gate.REJECT
    assert _check(v, "seal_intact")["ok"] and not _check(v, "all_steps_passed")["ok"]


def test_broken_marker_on_disk_is_rejected(tmp_path):
    root = _fixture(tmp_path)
    receipt = _applied(root)
    # swap the applied tarballs for marker-less ones — the receipt still claims the marker held
    for c in CONSUMERS:
        _engine_tarball(root / "apps" / c / "vendor" / "socioprophet-hellgraph-0.4.45.tgz", "0.4.45", with_marker=False)
    v = review_gate.review(receipt, root)
    assert v["verdict"] == review_gate.REJECT
    assert not _check(v, "marker_reproven")["ok"]


def test_non_atomic_consumers_rejected(tmp_path):
    root = _fixture(tmp_path)
    receipt = _applied(root)
    g = root / "apps" / "lifecycle-warden" / "scripts" / "check-engine-version.mjs"
    g.write_text(g.read_text().replace("const MIN_ENGINE = '0.4.45'", "const MIN_ENGINE = '0.4.40'"))
    v = review_gate.review(receipt, root)
    assert v["verdict"] == review_gate.REJECT
    assert not _check(v, "consumers_atomic")["ok"]


def test_out_of_scope_diff_rejected(tmp_path):
    root = _fixture(tmp_path)
    receipt = _applied(root)
    changed = ["apps/hellgraph-service/vendor/socioprophet-hellgraph-0.4.45.tgz",
               "apps/hellgraph-service/src/secret_backdoor.ts"]
    v = review_gate.review(receipt, root, changed_paths=changed)
    assert v["verdict"] == review_gate.REJECT
    assert "secret_backdoor.ts" in _check(v, "scope_contained")["evidence"]["out_of_scope"][0]


def test_scope_allows_the_real_revendor_paths(tmp_path):
    root = _fixture(tmp_path)
    receipt = _applied(root)
    changed = [f"apps/{c}/vendor/socioprophet-hellgraph-0.4.45.tgz" for c in CONSUMERS] \
        + [f"apps/{c}/package.json" for c in CONSUMERS] \
        + [f"apps/{c}/scripts/check-engine-version.mjs" for c in CONSUMERS]
    v = review_gate.review(receipt, root, changed_paths=changed)
    assert _check(v, "scope_contained")["ok"]


def test_model_concern_needs_human(tmp_path):
    root = _fixture(tmp_path)
    receipt = _applied(root)

    class Concerned(review_gate.ReviewModel):
        def judge(self, receipt, findings):
            return {"verdict": "concern", "rationale": "a semantic smell the checks can't see"}

    v = review_gate.review(receipt, root, model=Concerned())
    assert v["deterministic_ok"] is True
    assert v["verdict"] == review_gate.NEEDS_HUMAN


def test_review_seal_is_tamper_evident(tmp_path):
    root = _fixture(tmp_path)
    v = review_gate.review(_applied(root), root)
    sealed = v["review_digest"]
    v["verdict"] = "APPROVE-tampered"
    assert review_gate._seal_review(dict(v))["review_digest"] != sealed
