"""Tests for L5 artifact enrolment (issue #1048) and the Sovereign Retention Doctrine.

The producer's job is to turn the warden's empty governed set into a real one,
correctly classified. The risks worth testing are all about being WRONG in a way
that looks fine: mis-classifying an object into the shortest retention, letting a
re-run double-enrol, letting the default policy silently egress data off-sovereign,
or aborting a whole sweep because one object failed. Each has a test.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from compute_gateway import governance_enroll as ge
from compute_gateway import persistence

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def store():
    """A real temp gateway store seeded with one blob per epistemic class."""
    prev = os.environ.get("GATEWAY_STORE_DIR")
    d = tempfile.mkdtemp()   # removed in teardown below — see shutil.rmtree
    os.environ["GATEWAY_STORE_DIR"] = d
    persistence._reset_connection()

    seq = [0]

    def seed(receipt_id, epistemic_status, digest, blob):
        seq[0] += 1  # (project, seq) is the receipts PK — distinct seq per receipt
        persistence.save_receipt("p", seq[0], receipt_id,
                                 json.dumps({"id": receipt_id, "kind": "materialize",
                                             "epistemic_status": epistemic_status}))
        persistence.save_blob(digest, blob)
        persistence.save_index(receipt_id, [digest])

    seed("r-derived", "derived", "sha256:d1", {"data": {"nodes": 1}, "mime": None})
    seed("r-observed", "observed", "sha256:o1", {"data": "telemetry"})
    seed("r-asserted", "asserted", "sha256:a1", {"data": "canonical source"})
    seed("r-unknown", None, "sha256:u1", {"data": "no epistemic status"})
    yield
    persistence._reset_connection()
    if prev is None:
        os.environ.pop("GATEWAY_STORE_DIR", None)
    else:
        os.environ["GATEWAY_STORE_DIR"] = prev
    persistence._reset_connection()
    shutil.rmtree(d, ignore_errors=True)   # mkdtemp does not clean up after itself


class RecordingWarden:
    """Fake POST /v1/objects. Enforces the warden's real idempotency contract:
    a second ingest of the same id is a 409, not a silent overwrite."""

    def __init__(self):
        self.enrolled: dict[str, dict] = {}
        self.calls = 0

    def post(self, path, body):
        self.calls += 1
        assert path == "/v1/objects"
        if body["id"] in self.enrolled:
            return 409, {"ok": False, "error": f"object already governed: {body['id']}"}
        self.enrolled[body["id"]] = body
        return 201, {"ok": True}


_DELETE = object()


def _validator():
    """Load tools/validate_retention_policy.py by path.

    Not `import tools.validate_retention_policy`: that needs the repo root on
    sys.path, which the dedicated governance workflow supplies via PYTHONPATH but
    the generic app-test-diagnostics job does not — so this test passed in one CI
    job and failed with ModuleNotFoundError in the other. Loading by path makes it
    independent of who runs it and from where.
    """
    path = REPO_ROOT / "tools" / "validate_retention_policy.py"
    spec = importlib.util.spec_from_file_location("validate_retention_policy", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load the retention validator at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_policy_passes_its_own_validator():
    assert _validator().main() == 0


# ── The validator must be shown to REJECT, not only to accept ─────────────
#
# test_policy_passes_its_own_validator was the ONLY thing exercising the
# validator, and it asserts the shipped policy passes. That assertion survives
# `errors()` being replaced with `return []` — so the entire enforcement of the
# Sovereign Retention Doctrine could be deleted with nothing going red. Verified:
# stubbing errors() to return [] leaves the original suite fully green.
#
# The validator's own docstring says these are "precisely the changes that would
# look harmless in review, so they are asserted here rather than trusted". Each
# therefore gets a case proving the assertion actually refuses it.

def _mutate(**overrides):
    """The real shipped policy with targeted damage applied."""
    policy = copy.deepcopy(json.loads(
        (REPO_ROOT / "contracts" / "governance" / "retention-policy.v0.json").read_text()))
    for dotted, value in overrides.items():
        node = policy
        parts = dotted.split("__")
        for p in parts[:-1]:
            node = node[p]
        if value is _DELETE:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = value
    return policy


@pytest.mark.parametrize("overrides,expect", [
    ({"universal_invariants__residency": "us-east-1"},      "residency"),
    ({"universal_invariants__residency": _DELETE},          "residency"),
    ({"universal_invariants__vendor_opt_in": True},         "vendor_opt_in"),
    ({"universal_invariants__vendor_opt_in": _DELETE},      "vendor_opt_in"),
    ({"classes__derived__retention_delete_days": None},     "retention_delete_days"),
    ({"classes__derived__retention_delete_days": 0},        "retention_delete_days"),
    ({"classes__derived__ttl_days": 9_999},                 "ttl_days"),
    ({"classes__asserted__retention_delete_days": 30},      "legal_hold"),
    ({"fallback__unknown_epistemic_status": "derived"},     "SHORTEST"),
    ({"fallback__unknown_epistemic_status": "asserted"},    "auto class"),
    ({"fallback__unknown_epistemic_status": "nope"},        "not a defined class"),
    ({"classes": {}},                                       "no classes"),
])
def test_validator_rejects_each_relaxed_invariant(overrides, expect):
    errs = _validator().errors(_mutate(**overrides))
    assert errs, f"validator ACCEPTED {overrides} — that invariant is unenforced"
    assert any(expect in e for e in errs), \
        f"rejected, but for the wrong reason. wanted {expect!r}, got: {errs}"


@pytest.mark.parametrize("policy", [
    "not a dict", ["also", "not"], 42, None,
    {"universal_invariants": [], "classes": {}},
    {"universal_invariants": {}, "classes": "should be an object"},
    {"universal_invariants": {}, "classes": {"x": "not an object"}},
    {"universal_invariants": {}, "classes": {}, "fallback": "not an object"},
])
def test_validator_reports_rather_than_crashes_on_wrong_types(policy):
    """Copilot's third comment. A validator meant to fail safely must report a
    violation, not raise AttributeError — a traceback and a violation report are
    different signals, and only one of them says what is wrong."""
    errs = _validator().errors(policy)
    assert errs and all(isinstance(e, str) for e in errs)


def test_the_shipped_policy_is_what_the_rejection_tests_mutate():
    """Guards the mutation helper itself: if _mutate stopped reading the real
    policy, every rejection case above would be testing a fixture instead."""
    v = _validator()
    assert v.errors(_mutate()) == [], "the unmutated copy must be the passing policy"
    assert v.POLICY.resolve() == (
        REPO_ROOT / "contracts" / "governance" / "retention-policy.v0.json").resolve()


def test_classification_maps_status_to_class(store):
    policy = ge.load_policy()
    plans = {p.digest: p for p in ge.build_plan(policy, now_ms=0)}
    assert plans["sha256:d1"].klass == "derived"
    assert plans["sha256:o1"].klass == "observed"
    assert plans["sha256:a1"].klass == "asserted"
    # The one that matters: unknown must NOT become 'derived' (shortest retention).
    assert plans["sha256:u1"].klass == "observed"


def test_derived_gets_short_window_asserted_gets_none(store):
    policy = ge.load_policy()
    plans = {p.digest: p for p in ge.build_plan(policy, now_ms=0)}
    derived = plans["sha256:d1"].body
    assert derived["ttlAt"] == 14 * ge.DAY_MS
    assert derived["retentionDeleteAt"] == 90 * ge.DAY_MS
    # asserted is legal-hold: no auto-delete is scheduled at all.
    asserted = plans["sha256:a1"].body
    assert "ttlAt" not in asserted and "retentionDeleteAt" not in asserted


def test_every_object_is_sovereign_and_opt_out(store):
    """The inviolable defaults must ride on EVERY enrolment body, all classes."""
    policy = ge.load_policy()
    for p in ge.build_plan(policy, now_ms=0):
        assert p.body["residency"] == "sovereign"
        assert p.body["vendorOptIn"] is False


def test_sensitive_classes_are_marked(store):
    policy = ge.load_policy()
    plans = {p.digest: p for p in ge.build_plan(policy, now_ms=0)}
    assert "sensitiveFields" in plans["sha256:o1"].body   # observed: sensitive
    assert "sensitiveFields" in plans["sha256:a1"].body   # asserted: sensitive
    assert "sensitiveFields" not in plans["sha256:d1"].body  # derived: not


def test_dry_run_contacts_nothing(store):
    policy = ge.load_policy()
    w = RecordingWarden()
    s = ge.enrol(policy, w.post, apply=False, now_ms=0)
    assert s.planned == 4 and s.enrolled == 0 and w.calls == 0


def test_apply_enrols_then_is_idempotent(store):
    policy = ge.load_policy()
    w = RecordingWarden()
    first = ge.enrol(policy, w.post, apply=True, now_ms=0)
    assert first.enrolled == 4 and first.already_governed == 0 and first.failed == 0
    # Re-run: every object is already governed -> 409 -> counted, not errored.
    second = ge.enrol(policy, w.post, apply=True, now_ms=0)
    assert second.enrolled == 0 and second.already_governed == 4 and second.failed == 0


def test_one_failure_does_not_abort_the_sweep(store):
    policy = ge.load_policy()

    calls = {"n": 0}

    def flaky(path, body):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ConnectionError("warden blipped")
        return 201, {"ok": True}

    s = ge.enrol(policy, flaky, apply=True, now_ms=0)
    assert s.enrolled == 3 and s.failed == 1 and len(s.errors) == 1


def test_limit_bounds_the_first_live_batch(store):
    policy = ge.load_policy()
    assert len(ge.build_plan(policy, now_ms=0, limit=2)) == 2


def test_each_blob_enrolled_once_even_if_multiple_receipts_cite_it(store):
    """A digest referenced by two receipts is one governed object, not two."""
    persistence.save_receipt("p", 99, "r-derived-2",
                             json.dumps({"id": "r-derived-2", "epistemic_status": "derived"}))
    persistence.save_index("r-derived-2", ["sha256:d1"])  # same digest as r-derived
    policy = ge.load_policy()
    digests = [p.digest for p in ge.build_plan(policy, now_ms=0)]
    assert digests.count("sha256:d1") == 1


# ── Copilot round-1 ───────────────────────────────────────────────────────

# Both ids are parametrised to sort BEFORE and AFTER the incumbent "r-derived".
# This is not belt-and-braces: the first draft of the legal-hold test used only
# "r-asserted-2", which sorts before "r-derived", so the buggy first-seen
# implementation happened to pick the right answer and the test PASSED against
# the bug it was written to catch. A tie-break test that only exercises one
# iteration order is testing the ordering, not the tie-break.
@pytest.mark.parametrize("rid", ["r-aaa-asserted", "r-zzz-asserted"])
def test_a_digest_cited_by_two_classes_takes_the_LONGER_retention(store, rid):
    """Copilot: dedupe kept whichever receipt was iterated first, so ordering
    could pick the retention window — and in the bad case pick the shorter one.

    One blob cited by both a 'derived' receipt (14d ttl / 90d delete) and an
    'asserted' one (legal hold, never auto-deleted). Enrolling it as derived puts
    a legally-held object on a 90-day hard delete.
    """
    persistence.save_receipt("p", 98, rid,
                             json.dumps({"id": rid, "epistemic_status": "asserted"}))
    persistence.save_index(rid, ["sha256:d1"])   # same blob as r-derived
    policy = ge.load_policy()
    plan = {p.digest: p for p in ge.build_plan(policy, now_ms=0)}["sha256:d1"]
    assert plan.klass == "asserted", "legal hold must win over an auto class"
    assert "retentionDeleteAt" not in plan.body, "a legally-held object must carry no delete date"


@pytest.mark.parametrize("rid", ["r-aaa-observed", "r-zzz-observed"])
def test_among_auto_classes_the_longer_ceiling_wins(store, rid):
    """observed (365d) must beat derived (90d) in either iteration order."""
    persistence.save_receipt("p", 97, rid,
                             json.dumps({"id": rid, "epistemic_status": "observed"}))
    persistence.save_index(rid, ["sha256:d1"])
    policy = ge.load_policy()
    plan = {p.digest: p for p in ge.build_plan(policy, now_ms=0)}["sha256:d1"]
    assert plan.klass == "observed"


def test_retention_rank_is_read_from_the_policy_not_hardcoded():
    """The tie-break must follow the doctrine. If a class's ceiling is raised in
    the contract, the ranking must move with it rather than stay pinned to a
    constant someone wrote once."""
    policy = ge.load_policy()
    assert ge.retention_rank("asserted", policy) > ge.retention_rank("observed", policy)
    assert ge.retention_rank("observed", policy) > ge.retention_rank("derived", policy)
    bumped = copy.deepcopy(policy)
    bumped["classes"]["derived"]["retention_delete_days"] = 10_000
    assert ge.retention_rank("derived", bumped) > ge.retention_rank("observed", bumped), \
        "ranking ignored the policy — it is hardcoded"


def test_enrolled_content_is_the_bytes_the_id_addresses(store):
    """Copilot: `id` is the artifact digest but `content` was a DIFFERENT encoding
    of the same object, so the governed object's declared id did not address the
    bytes the warden ingested. Verified broken before the fix: json.dumps defaults
    differ from the canonical form for every dict blob, not just non-ASCII ones."""
    from compute_gateway import artifacts
    blob = {"note": "café résumé", "items": [1, 2], "z": "a"}
    digest = artifacts.digest(blob)
    persistence.save_blob(digest, blob)
    persistence.save_receipt("p", 96, "r-uni",
                             json.dumps({"id": "r-uni", "epistemic_status": "observed"}))
    persistence.save_index("r-uni", [digest])

    plan = {p.digest: p for p in ge.build_plan(ge.load_policy(), now_ms=0)}[digest]
    rehashed = artifacts.digest(json.loads(plan.body["content"]))
    assert rehashed == plan.body["id"], (
        "content does not hash back to the id it is enrolled under — the governed "
        "object is not content-addressed")
    assert "\\u00e9" not in plan.body["content"], "content must not be ASCII-escaped"


def test_a_limited_enrolment_picks_the_same_objects_every_run(store):
    """Copilot: with --limit set, which objects get enrolled depended on
    load_index() insertion order, so 'the first live batch' was not reproducible.
    A re-run after a partial failure would silently govern a different set.

    The seeding below is the whole test. The default fixture inserts receipts whose
    ids (r-asserted, r-derived, r-observed, r-unknown) happen to sort the same way
    as their digests, so insertion order and sorted order COINCIDE and the fixture
    cannot tell the two apart — the first version of this test passed with
    chosen.items() restored. These pairs invert that deliberately: the receipt
    inserted first carries the digest that sorts LAST.
    """
    persistence.save_receipt("p", 90, "r-aaa-first",
                             json.dumps({"id": "r-aaa-first", "epistemic_status": "observed"}))
    persistence.save_blob("sha256:zzz9", {"data": "sorts last, inserted first"})
    persistence.save_index("r-aaa-first", ["sha256:zzz9"])
    persistence.save_receipt("p", 91, "r-zzz-last",
                             json.dumps({"id": "r-zzz-last", "epistemic_status": "observed"}))
    persistence.save_blob("sha256:aaa0", {"data": "sorts first, inserted last"})
    persistence.save_index("r-zzz-last", ["sha256:aaa0"])

    policy = ge.load_policy()
    everything = [p.digest for p in ge.build_plan(policy, now_ms=0)]
    assert everything == sorted(everything), (
        f"plan order is not deterministic — got {everything}")
    # The discriminating relation: zzz9 was inserted FIRST, aaa0 LAST. Under insertion
    # order zzz9 precedes aaa0; under digest order it cannot. If this ever holds under
    # both, the fixture has stopped discriminating and the assertion above is decorative.
    assert everything.index("sha256:aaa0") < everything.index("sha256:zzz9"), (
        f"ordering still follows insertion, not digest — got {everything}")

    first = [p.digest for p in ge.build_plan(policy, now_ms=0, limit=2)]
    assert first == everything[:2], "the limited batch must be the first N of that order"
    for _ in range(5):
        assert [p.digest for p in ge.build_plan(policy, now_ms=0, limit=2)] == first
