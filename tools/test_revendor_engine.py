"""Coverage for tools/revendor_engine.py.

The re-vendor is exercised end-to-end on a temp copy of the two consumers: a synthesized
0.4.40 is re-vendored to the REAL 0.4.45 tarball, and success is judged by the consumers'
OWN check-engine-version.mjs guard — the executor does not grade its own work. Idempotency,
fail-closed (bad marker; refusing to lower a floor), and the tamper-evident seal are pinned
because each corresponds to a way this has gone wrong before.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
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


def _real_effect_request(to="0.4.46", consumer="hellgraph-service", crossings=False):
    """Shaped exactly as sociosphere tools/detect_vendor_freshness.py emits it (the merged
    EffectRequest.json 0.1.0): versionMarker is an OBJECT, the consumer rides in consumerApp,
    idempotencyKey/requiresHumanApproval are top-level, and there is NO tarball field."""
    return {
        "type": "EffectRequest", "specVersion": "0.1.0", "effectKind": "update",
        "capability": "vendor.revendor",
        "target": {"kind": "vendor-pin", "identifier": f"hellgraph-engine@{consumer}",
                   "location": f"prophet-platform/apps/{consumer}/vendor"},
        "idempotencyKey": f"hellgraph-engine@{consumer}@0.4.40->{to}",
        "requestedByEventRef": "vendor-freshness-observation/2026-07-30/hellgraph-engine",
        "requiresHumanApproval": crossings,
        "riskLabels": ["contract-crossing"] if crossings else [],
        "parameters": {
            "artifactId": f"hellgraph-engine@{consumer}", "consumerApp": consumer,
            "toVersion": to, "fromVersion": "0.4.40",
            "versionMarker": {"marker": MARKER, "presentIn": to, "absentIn": "0.4.40",
                              "assertInside": "package/ts/dist/index.js", "note": None},
        },
    }


def test_from_effect_request_maps_the_real_contract(tmp_path):
    tgz = _engine_tarball(tmp_path / "e.tgz", "0.4.46", with_marker=True)
    plan = eng.RevendorPlan.from_effect_request(_real_effect_request(), tgz)
    assert plan.to_version == "0.4.46"
    assert plan.expect_markers == [MARKER]                        # versionMarker.marker (object), not the object
    assert plan.consumers == ["hellgraph-service"]                # consumerApp — one per request, not both
    assert plan.member == "package/ts/dist/index.js"             # versionMarker.assertInside
    assert plan.idempotency_key == "hellgraph-engine@hellgraph-service@0.4.40->0.4.46"  # request's own key
    assert plan.requires_human_approval is False
    assert plan.tarball == tgz                                    # supplied separately (not in the request)


def test_from_effect_request_rejects_a_bare_string_marker(tmp_path):
    # The old bug: treating parameters.versionMarker as a string. The real field is an object.
    tgz = _engine_tarball(tmp_path / "e.tgz", "0.4.46", with_marker=True)
    doc = _real_effect_request()
    doc["parameters"]["versionMarker"] = MARKER
    with pytest.raises(ValueError, match="versionMarker.marker"):
        eng.RevendorPlan.from_effect_request(doc, tgz)


def test_from_effect_request_requires_consumer_app(tmp_path):
    tgz = _engine_tarball(tmp_path / "e.tgz", "0.4.46", with_marker=True)
    doc = _real_effect_request()
    del doc["parameters"]["consumerApp"]
    with pytest.raises(ValueError, match="consumerApp"):
        eng.RevendorPlan.from_effect_request(doc, tgz)


def test_wrong_capability_is_rejected(tmp_path):
    tgz = _engine_tarball(tmp_path / "e.tgz", "0.4.46", with_marker=True)
    with pytest.raises(ValueError, match="vendor.revendor"):
        eng.RevendorPlan.from_effect_request({"capability": "something.else", "parameters": {}}, tgz)


def test_requires_human_approval_blocks_apply_until_approved(tmp_path):
    root = _fixture(tmp_path)
    plan = eng.RevendorPlan.from_effect_request(_real_effect_request(to="0.4.45", crossings=True), REAL_045)
    blocked = eng.execute(plan, root, apply=True)
    assert blocked["status"] == "blocked_pending_human_approval" and blocked["requires_human_approval"] is True
    # nothing was touched — the old 0.4.40 tarball is still in place for the targeted consumer
    assert (root / "apps" / "hellgraph-service" / "vendor" / "socioprophet-hellgraph-0.4.40.tgz").exists()
    # an approving EffectDecision (human_approved) lets it proceed
    approved = eng.execute(plan, root, apply=True, human_approved=True)
    assert approved["status"] in ("applied", "noop")


# ── resolve_tarball: pull the digest-pinned artifact the request only names ──────────

def _fake_registry(tarball_bytes, media="application/vnd.oci.image.layer.v1.tar+gzip"):
    """An injectable http_get that serves a one-layer OCI manifest + the blob."""
    digest = "sha256:" + hashlib.sha256(tarball_bytes).hexdigest()

    def http_get(url, headers):
        if "/manifests/" in url:
            return json.dumps({"layers": [{"mediaType": media, "digest": digest,
                                           "size": len(tarball_bytes)}]}).encode()
        if url.endswith(digest):
            return tarball_bytes
        raise AssertionError(f"unexpected url: {url}")

    return http_get, digest


def test_resolve_tarball_pulls_and_verifies(tmp_path):
    data = b"pretend-this-is-a-gzipped-tar"
    http_get, _ = _fake_registry(data)
    doc = {"parameters": {"toVersion": "0.4.46", "packageName": "hellgraph"}}
    out = eng.resolve_tarball(doc, tmp_path, http_get=http_get)
    assert out.read_bytes() == data
    assert out.name == "socioprophet-hellgraph-0.4.46.tgz"


def test_resolve_tarball_refuses_a_digest_mismatch(tmp_path):
    # The manifest attests a digest the returned blob does NOT hash to — never vendor it.
    wrong_digest = "sha256:" + hashlib.sha256(b"a different artifact").hexdigest()

    def http_get(url, headers):
        if "/manifests/" in url:
            return json.dumps({"layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                                           "digest": wrong_digest}]}).encode()
        return b"the actual bytes, which do not match wrong_digest"

    with pytest.raises(ValueError, match="digest mismatch"):
        eng.resolve_tarball({"parameters": {"toVersion": "0.4.46"}}, tmp_path, http_get=http_get)


def test_resolve_tarball_requires_exactly_one_tar_layer(tmp_path):
    with pytest.raises(ValueError, match="one tarball layer"):
        eng.resolve_tarball({"parameters": {"toVersion": "0.4.46"}}, tmp_path,
                            http_get=lambda url, headers: json.dumps({"layers": []}).encode())


def test_resolve_tarball_requires_to_version(tmp_path):
    with pytest.raises(ValueError, match="toVersion"):
        eng.resolve_tarball({"parameters": {}}, tmp_path, http_get=lambda url, headers: b"")


# ── Copilot #1062 round 2: fail-closed AND receipt-producing ──────────────────

def test_corrupt_tarball_yields_a_sealed_failed_receipt_not_a_raise(tmp_path):
    """A tarball that is not a readable gzip trips marker_tool into raising
    SystemExit. Pre-fix, step_assert_marker let it escape past execute()'s
    `except RevendorAbort` and the run tore down WITHOUT a sealed receipt —
    the exact opposite of the fail-closed-AND-receipt-producing contract.
    Post-fix, execute() returns a sealed failed receipt naming assert_marker."""
    root = _fixture(tmp_path)
    corrupt = tmp_path / "corrupt-0.4.99.tgz"
    corrupt.write_bytes(b"this is not a gzip stream")  # tarfile.open will raise
    receipt = eng.execute(_plan(to="0.4.99", tarball=corrupt), root, apply=True)
    # The whole point: NO exception escaped execute(); we got a receipt.
    assert receipt["status"] == "failed"
    failed = receipt["steps"][0]
    assert failed["step"] == "assert_marker" and failed["ok"] is False
    # The reader's own error text rides through as evidence — an operator sees
    # what specifically was wrong with the artifact, not just "it failed".
    assert "packed dist" in failed["evidence"]["reason"] \
        or "readable gzip" in failed["evidence"]["reason"]
    # And the receipt is sealed, so tamper detection still works.
    assert receipt["receipt_digest"].startswith("sha256:")


def test_open_pr_failure_still_prints_a_sealed_receipt_and_exits_nonzero(
        tmp_path, monkeypatch, capsys):
    """If --open-pr is used and open_pr() raises (any of RevendorAbort,
    subprocess.CalledProcessError, OSError), main() must still print the
    receipt as JSON on stdout — the receipt is the deliverable, and automation
    downstream parses stdout to learn the final status. Pre-fix, the exception
    propagated past the print() call and stdout was empty."""
    root = _fixture(tmp_path)
    # Stub open_pr so we do not actually run git/gh in this test.
    def boom(plan, receipt, root):
        raise subprocess.CalledProcessError(1, ["git", "push", "-u", "origin", "revendor/engine-0.4.45"])
    monkeypatch.setattr(eng, "open_pr", boom)
    rc = eng.main([
        "--to-version", "0.4.45",
        "--tarball", str(REAL_045),
        "--expect", MARKER,
        "--root", str(root),
        "--open-pr",
    ])
    assert rc == 1, "an open_pr failure must exit non-zero"
    out = capsys.readouterr().out
    assert out.strip(), "stdout must carry the receipt even when open_pr failed"
    receipt = json.loads(out)
    assert receipt["status"] == "failed"
    open_pr_step = [s for s in receipt["steps"] if s["step"] == "open_pr"][0]
    assert open_pr_step["ok"] is False
    # The subprocess argv rides through as evidence — an operator can see which
    # git/gh call actually broke, not just "open_pr failed".
    assert "git" in open_pr_step["evidence"]["argv"][0]
    assert open_pr_step["evidence"]["returncode"] == 1
    # And the receipt was re-sealed after the failure was recorded.
    assert receipt["receipt_digest"].startswith("sha256:")
# ── open_pr stages the new tarball; a post-mutation failure rolls back ────────────────

def _git(root: Path, *args: str):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _snapshot_tree(root: Path) -> dict:
    """Byte-level snapshot of everything the re-vendor can touch, for an exact-equality
    'nothing changed' assertion."""
    out: dict[str, object] = {}
    for consumer in CONSUMERS:
        app = root / "apps" / consumer
        out[str(app / "package.json")] = (app / "package.json").read_bytes()
        out[str(app / "scripts" / "check-engine-version.mjs")] = \
            (app / "scripts" / "check-engine-version.mjs").read_bytes()
        vd = app / "vendor"
        out[str(vd) + ":listing"] = sorted(f.name for f in vd.iterdir())
        for f in vd.iterdir():
            if f.is_file():
                out[str(f)] = f.read_bytes()
    return out


def test_open_pr_commit_contains_the_new_tarball(tmp_path, monkeypatch):
    """Copilot #1062: `git commit -a` does NOT stage the freshly-copied (untracked) tgz, so
    the opened PR deleted the old tarball and bumped package.json but never carried the new
    bytes it points at. Inspect the COMMIT (not the working tree) — the tool checks the file
    on disk, so only the commit itself proves the artifact ships."""
    root = _fixture(tmp_path)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")

    plan = _plan()
    receipt = eng.execute(plan, root, apply=True)
    assert receipt["status"] == "applied"

    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        # Run local git for real (switch/add/commit); stub the remote-facing calls so the
        # test needs no network, no origin remote and no gh auth.
        if isinstance(cmd, list) and cmd:
            if cmd[0] == "gh":
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if "ls-remote" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")   # branch does not exist remotely
            if "push" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(eng.subprocess, "run", fake_run)

    result = eng.open_pr(plan, receipt, root)
    assert result["opened"] is True

    committed = real_run(["git", "-C", str(root), "show", "--name-only", "--format=", "HEAD"],
                         capture_output=True, text=True).stdout.split()
    for consumer in CONSUMERS:
        newtgz = f"apps/{consumer}/vendor/socioprophet-hellgraph-0.4.45.tgz"
        assert newtgz in committed, f"new tarball missing from the commit for {consumer}: {committed}"
        # It is a real, non-empty blob in the committed tree, not just a deletion of the old one.
        size = real_run(["git", "-C", str(root), "cat-file", "-s", f"HEAD:{newtgz}"],
                        capture_output=True, text=True)
        assert size.returncode == 0 and int(size.stdout.strip()) > 0, f"empty/absent tgz blob for {consumer}"


def test_a_failed_verify_guard_rolls_back_all_mutations(tmp_path, monkeypatch):
    """Copilot #1062: verify_guard runs AFTER place_tarball/bump_floor mutate, so its failure
    must undo them — otherwise the receipt says 'failed' while the tree is left half-applied
    (new tarball copied, old one deleted, package.json + guard bumped). Force the guard to
    reject and assert the tree is byte-identical to before the run."""
    root = _fixture(tmp_path)
    before = _snapshot_tree(root)

    def boom(plan, root):
        raise eng.RevendorAbort("verify_guard", "forced guard rejection")
    monkeypatch.setattr(eng, "step_verify_guard", boom)

    receipt = eng.execute(_plan(), root, apply=True)
    assert receipt["status"] == "failed"
    assert receipt["steps"][-1]["step"] == "verify_guard"
    assert receipt["steps"][-1]["evidence"].get("rolled_back") is True

    assert _snapshot_tree(root) == before, "a post-mutation failure left the tree half-applied"
    for consumer in CONSUMERS:
        vd = root / "apps" / consumer / "vendor"
        assert not (vd / "socioprophet-hellgraph-0.4.45.tgz").exists(), "new tarball not removed on rollback"
        assert (vd / "socioprophet-hellgraph-0.4.40.tgz").exists(), "old tarball not restored on rollback"


# ── advisory gate wired into execute: don't re-vendor a known-vulnerable version ────

def test_advisory_gate_blocks_a_vulnerable_version_before_mutating(tmp_path):
    root = _fixture(tmp_path)
    plan = eng.RevendorPlan(to_version="0.4.45", tarball=REAL_045, expect_markers=[MARKER], consumers=CONSUMERS)
    block = lambda v: {"recommendation": "block", "reason": f"known advisory for {v}",
                       "advisories": [{"id": "GHSA-x"}]}
    r = eng.execute(plan, root, apply=True, advisory_assessor=block)
    assert r["status"] == "failed"
    gate = next(s for s in r["steps"] if s["step"] == "advisory_gate")
    assert gate["ok"] is False and "advisory" in gate["evidence"]["reason"]
    for c in CONSUMERS:  # fail-closed: nothing mutated
        assert (root / "apps" / c / "vendor" / "socioprophet-hellgraph-0.4.40.tgz").exists()


def test_advisory_gate_allows_a_clean_version(tmp_path):
    root = _fixture(tmp_path)
    plan = eng.RevendorPlan(to_version="0.4.45", tarball=REAL_045, expect_markers=[MARKER], consumers=CONSUMERS)
    allow = lambda v: {"recommendation": "allow", "reason": "no known advisories", "advisories": []}
    r = eng.execute(plan, root, apply=True, advisory_assessor=allow)
    assert r["status"] in ("applied", "noop")
    assert any(s["step"] == "advisory_gate" and s["ok"] for s in r["steps"])
