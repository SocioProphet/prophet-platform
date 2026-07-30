"""Coverage for tools/revendor_engine.py.

The re-vendor is exercised end-to-end on a temp copy of the two consumers: a synthesized
0.4.40 is re-vendored to the REAL 0.4.45 tarball, and success is judged by the consumers'
OWN check-engine-version.mjs guard — the executor does not grade its own work. Idempotency,
fail-closed (bad marker; refusing to lower a floor), and the tamper-evident seal are pinned
because each corresponds to a way this has gone wrong before.
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
TOOL = ROOT / "tools" / "revendor_engine.py"
REAL_045 = ROOT / "apps" / "hellgraph-service" / "vendor" / "socioprophet-hellgraph-0.4.45.tgz"
REAL_GUARD = ROOT / "apps" / "hellgraph-service" / "scripts" / "check-engine-version.mjs"
MARKER = 'PROP_NS = "prop:"'
CONSUMERS = ["hellgraph-service", "lifecycle-warden"]


def _load():
    spec = importlib.util.spec_from_file_location("revendor_engine", TOOL)
    mod = importlib.util.module_from_spec(spec)
    # @dataclass resolves its own module via sys.modules during class creation; register
    # before exec so the importlib-loaded module is findable.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


eng = _load()


def _engine_tarball(path: Path, version: str, with_marker: bool) -> Path:
    """A minimal engine tarball: internal package.json version + a packed dist. The decoy
    'prop:' is always present, so only the full PROP_NS assignment discriminates."""
    with tarfile.open(path, "w:gz") as tar:
        for name, data in (
            ("package/package.json", json.dumps({"name": "@socioprophet/hellgraph", "version": version}).encode()),
            ("package/ts/dist/index.js",
             ((MARKER + "\n") if with_marker else "").encode() + b'const decoy = "prop:";\n'),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def _fixture(root: Path, start_version: str = "0.4.40", floor: str = "0.4.40") -> Path:
    """Two consumers pinned to start_version with the real guard (floor patched down)."""
    guard_src = REAL_GUARD.read_text().replace("const MIN_ENGINE = '0.4.45'", f"const MIN_ENGINE = '{floor}'")
    for consumer in CONSUMERS:
        app = root / "apps" / consumer
        (app / "scripts").mkdir(parents=True, exist_ok=True)
        (app / "vendor").mkdir(parents=True, exist_ok=True)
        (app / "package.json").write_text(json.dumps({
            "name": consumer,
            "dependencies": {"@socioprophet/hellgraph": f"file:vendor/socioprophet-hellgraph-{start_version}.tgz"},
            "scripts": {"check:engine": "node scripts/check-engine-version.mjs"},
        }, indent=2) + "\n")
        (app / "scripts" / "check-engine-version.mjs").write_text(guard_src)
        _engine_tarball(app / "vendor" / f"socioprophet-hellgraph-{start_version}.tgz", start_version, with_marker=False)
    return root


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # The guard's best-effort "is a newer tag out?" call must not reach the network in tests.
    monkeypatch.setenv("HELLGRAPH_ENGINE_REMOTE", "file:///nonexistent-engine-remote")


def _plan(to="0.4.45", tarball=REAL_045, expect=(MARKER,)):
    return eng.RevendorPlan(to_version=to, tarball=Path(tarball), expect_markers=list(expect), consumers=CONSUMERS)


def test_full_revendor_040_to_045_passes_the_real_guard(tmp_path):
    root = _fixture(tmp_path)
    receipt = eng.execute(_plan(), root, apply=True)
    assert receipt["status"] == "applied", json.dumps(receipt, indent=2)
    steps = {s["step"]: s for s in receipt["steps"]}
    # every discipline step present and green, including the consumers' own guard
    assert set(steps) >= {"assert_marker", "precheck", "place_tarball", "bump_floor", "verify_guard"}
    assert all(s["ok"] for s in receipt["steps"])
    for consumer in CONSUMERS:
        app = root / "apps" / consumer
        assert (app / "vendor" / "socioprophet-hellgraph-0.4.45.tgz").exists()
        assert not (app / "vendor" / "socioprophet-hellgraph-0.4.40.tgz").exists()
        pkg = json.loads((app / "package.json").read_text())
        assert pkg["dependencies"]["@socioprophet/hellgraph"] == "file:vendor/socioprophet-hellgraph-0.4.45.tgz"
        assert "const MIN_ENGINE = '0.4.45'" in (app / "scripts" / "check-engine-version.mjs").read_text()
        assert steps["verify_guard"]["evidence"]["consumers"][consumer]["exit"] == 0


def test_idempotent_second_run_is_a_noop(tmp_path):
    root = _fixture(tmp_path)
    assert eng.execute(_plan(), root, apply=True)["status"] == "applied"
    again = eng.execute(_plan(), root, apply=True)
    assert again["status"] == "noop"
    # a no-op re-vendor recorded no mutating step
    assert [s["step"] for s in again["steps"]] == ["assert_marker"]


def test_fail_closed_on_unproven_marker_mutates_nothing(tmp_path):
    root = _fixture(tmp_path)
    before = {c: sorted(p.name for p in (root / "apps" / c / "vendor").iterdir()) for c in CONSUMERS}
    # a 0.4.46 tarball whose dist lacks the marker — claims a version it cannot prove
    bad = _engine_tarball(tmp_path / "bad-0.4.46.tgz", "0.4.46", with_marker=False)
    receipt = eng.execute(_plan(to="0.4.46", tarball=bad), root, apply=True)
    assert receipt["status"] == "failed"
    assert receipt["steps"][0]["step"] == "assert_marker" and receipt["steps"][0]["ok"] is False
    after = {c: sorted(p.name for p in (root / "apps" / c / "vendor").iterdir()) for c in CONSUMERS}
    assert after == before, "a failed marker proof must not have touched any vendor dir"


def test_refuses_to_lower_a_floor_before_any_mutation(tmp_path):
    root = _fixture(tmp_path, floor="0.4.45")  # floor already ahead of the target
    good_044 = _engine_tarball(tmp_path / "e-0.4.44.tgz", "0.4.44", with_marker=True)
    before = {c: (root / "apps" / c / "package.json").read_text() for c in CONSUMERS}
    receipt = eng.execute(_plan(to="0.4.44", tarball=good_044), root, apply=True)
    assert receipt["status"] == "failed"
    failed = [s for s in receipt["steps"] if not s["ok"]][0]
    assert failed["step"] == "precheck" and "lower a floor" in failed["evidence"]["reason"]
    assert not any(s["step"] in ("place_tarball", "bump_floor") for s in receipt["steps"])
    after = {c: (root / "apps" / c / "package.json").read_text() for c in CONSUMERS}
    assert after == before, "the floor guard must fire before any package.json is rewritten"


def test_dry_run_touches_nothing_but_plans(tmp_path):
    root = _fixture(tmp_path)
    snapshot = {c: sorted(p.name for p in (root / "apps" / c / "vendor").iterdir()) for c in CONSUMERS}
    receipt = eng.execute(_plan(), root, apply=False)
    assert receipt["status"] == "planned"
    assert {c: sorted(p.name for p in (root / "apps" / c / "vendor").iterdir()) for c in CONSUMERS} == snapshot


def test_receipt_seal_is_tamper_evident(tmp_path):
    receipt = eng.execute(_plan(), _fixture(tmp_path), apply=True)
    sealed = receipt["receipt_digest"]
    receipt["steps"][0]["ok"] = "tampered"
    assert eng._seal(dict(receipt))["receipt_digest"] != sealed


def test_from_effect_request_maps_the_contract(tmp_path):
    tgz = _engine_tarball(tmp_path / "e.tgz", "0.4.46", with_marker=True)
    doc = {
        "type": "EffectRequest", "capability": "vendor.revendor",
        "requestedByEventRef": "evt-123",
        "parameters": {"toVersion": "0.4.46", "tarball": str(tgz), "versionMarker": MARKER},
    }
    plan = eng.RevendorPlan.from_effect_request(doc)
    assert plan.to_version == "0.4.46" and plan.expect_markers == [MARKER]
    assert plan.idempotency_key == "engine@0.4.46" and plan.requested_by_event_ref == "evt-123"


def test_wrong_capability_is_rejected():
    with pytest.raises(ValueError, match="vendor.revendor"):
        eng.RevendorPlan.from_effect_request({"capability": "something.else", "parameters": {}})
