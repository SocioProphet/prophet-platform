"""Tests for L5 artifact enrolment (issue #1048) and the Sovereign Retention Doctrine.

The producer's job is to turn the warden's empty governed set into a real one,
correctly classified. The risks worth testing are all about being WRONG in a way
that looks fine: mis-classifying an object into the shortest retention, letting a
re-run double-enrol, letting the default policy silently egress data off-sovereign,
or aborting a whole sweep because one object failed. Each has a test.
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from compute_gateway import governance_enroll as ge
from compute_gateway import persistence


@pytest.fixture
def store():
    """A real temp gateway store seeded with one blob per epistemic class."""
    prev = os.environ.get("GATEWAY_STORE_DIR")
    d = tempfile.mkdtemp()
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


def test_policy_passes_its_own_validator():
    import tools.validate_retention_policy as v  # noqa: E402
    assert v.main() == 0


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
