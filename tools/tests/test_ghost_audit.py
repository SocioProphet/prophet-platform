"""Ghost audit tests — prove ghosts are caught and ghostry is measured."""

from __future__ import annotations

from tools.capability_membrane import CapabilityRequest, TENSION_REQUIRED, resolve_capability
from tools.ghost_audit import StateDelta, audit
from tools import membrane_identity as mid
import pytest

FULL_TENSION = TENSION_REQUIRED["R5"]


def enforced_allow_receipt(rid_subject="urn:srcos:agent:worker", signer=None):
    r = resolve_capability(
        CapabilityRequest(surface="filesystem", action="filesystem.write", access_level="scopedWrite",
                          subject_ref=rid_subject, tension_members=FULL_TENSION, membrane_decision="ALLOW"),
        signer=signer,
    )
    return r.sealed, r.receipt["id"]


def observed_receipt():
    r = resolve_capability(
        CapabilityRequest(surface="computer", action="computer.control", access_level="control",
                          subject_ref="urn:srcos:agent:frontier", tension_members=FULL_TENSION,
                          owned=False, membrane_decision="ALLOW"))
    return r.sealed, r.receipt["id"]


def denied_receipt():
    r = resolve_capability(
        CapabilityRequest(surface="filesystem", action="filesystem.write", access_level="scopedWrite",
                          subject_ref="urn:srcos:agent:worker", tension_members=FULL_TENSION,
                          membrane_decision="DENY"))
    return r.sealed, r.receipt["id"]


def test_clean_journal_has_zero_ghostry():
    sealed, rid = enforced_allow_receipt()
    deltas = [StateDelta(id="d1", action="filesystem.write", subject="s", authorized_by=rid)]
    report = audit([sealed], deltas)
    assert report.clean
    assert report.ghostry == 0.0
    assert report.attested == 1


def test_state_change_with_no_receipt_is_a_ghost():
    report = audit([], [StateDelta(id="d1", action="x", subject="s", authorized_by=None)])
    assert not report.clean
    assert report.ghostry == 1.0
    assert report.ghosts[0].reason == "no_receipt"


def test_observed_edge_that_changed_state_is_a_ghost():
    # THE ghostry case: a foreign/observed edge produced a durable change.
    sealed, rid = observed_receipt()
    deltas = [StateDelta(id="d1", action="computer.control", subject="s", authorized_by=rid)]
    report = audit([sealed], deltas)
    assert report.ghosts[0].reason == "not_enforced"
    assert report.ghostry == 1.0


def test_denied_receipt_does_not_authorize():
    sealed, rid = denied_receipt()
    deltas = [StateDelta(id="d1", action="filesystem.write", subject="s", authorized_by=rid)]
    report = audit([sealed], deltas)
    assert report.ghosts[0].reason == "not_allowed"


def test_missing_receipt_reference_is_a_ghost():
    deltas = [StateDelta(id="d1", action="x", subject="s", authorized_by="urn:srcos:agent-machine-receipt:nope")]
    report = audit([], deltas)
    assert report.ghosts[0].reason == "receipt_missing"


def test_ghostry_ratio_is_fraction_of_ghost_deltas():
    sealed, rid = enforced_allow_receipt()
    deltas = [
        StateDelta(id="ok", action="w", subject="s", authorized_by=rid),
        StateDelta(id="ghost1", action="w", subject="s", authorized_by=None),
        StateDelta(id="ghost2", action="w", subject="s", authorized_by=None),
        StateDelta(id="ghost3", action="w", subject="s", authorized_by=None),
    ]
    report = audit([sealed], deltas)
    assert report.total_deltas == 4
    assert report.attested == 1
    assert report.ghostry == 0.75
    assert report.to_dict()["byReason"]["no_receipt"] == 3


@pytest.mark.skipif(not mid.HAVE_CRYPTO, reason="cryptography not installed")
def test_require_signed_flags_unsigned_authorizer():
    unsigned, rid = enforced_allow_receipt()               # enforced allow, but NOT signed
    deltas = [StateDelta(id="d1", action="filesystem.write", subject="s", authorized_by=rid)]
    report = audit([unsigned], deltas, require_signed=True, verify=mid.verify_sealed)
    assert report.ghosts[0].reason == "bad_signature"


@pytest.mark.skipif(not mid.HAVE_CRYPTO, reason="cryptography not installed")
def test_require_signed_accepts_validly_signed_authorizer():
    ident = mid.IdentityRoot.from_seed(bytes(range(32)))
    signed, rid = enforced_allow_receipt(signer=ident)
    deltas = [StateDelta(id="d1", action="filesystem.write", subject="s", authorized_by=rid)]
    report = audit([signed], deltas, require_signed=True, verify=mid.verify_sealed)
    assert report.clean
    assert report.ghostry == 0.0
