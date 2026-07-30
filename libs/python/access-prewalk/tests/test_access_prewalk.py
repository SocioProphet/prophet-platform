"""access-prewalk contract tests.

The invariants this file pins, each by observing the behaviour rather than asserting it:

  1. Trust floor is checked BEFORE roles — a revoked-trust subject with a stale role must
     not pass. That ordering is the fail-open shape a2a-trust hardening closed.
  2. Below the trust floor is DENIED, never requires-consent — a request form must not be
     able to launder a revocation.
  3. requires-consent maps to ZERO, not NEG — unestablished is not refused.
  4. A signed URL binds subject + resource + roles + expiry; altering ANY of them fails
     verification, and a valid signature does not revive an expired request.
"""

from __future__ import annotations

import time
import urllib.parse

import pytest

from access_prewalk import (
    TRUST_FLOOR,
    AccessDecision,
    Resource,
    Subject,
    compute_access_decision,
    grade_to_law_factor,
    signed_consent_url,
    verify_consent_url,
)

KEY = b"test-signing-key-not-a-real-secret"
NOW = 1_800_000_000


def _subject(**kw) -> Subject:
    return Subject(**{"subject_id": "eve.smith", "trust_score": 0.82, "roles": ("analyst",), **kw})


def _resource(**kw) -> Resource:
    return Resource(**{"resource_id": "local-billing", **kw})


# ── the three grades ───────────────────────────────────────────────────────────

def test_no_role_gate_and_clear_trust_is_granted() -> None:
    d = compute_access_decision(_subject(), _resource(), now_epoch=NOW)
    assert d.grade == "granted"
    assert "gates on no role" in d.reason


def test_holding_every_required_role_is_granted() -> None:
    d = compute_access_decision(
        _subject(roles=("analyst", "billing-reader")),
        _resource(required_roles=("analyst", "billing-reader")),
        now_epoch=NOW,
    )
    assert d.grade == "granted"
    assert "holds all required roles" in d.reason


def test_missing_role_on_a_consentable_resource_is_requires_consent() -> None:
    """The grade a boolean cannot express, and the one that carries the product value:
    Michael can say 'you don't have billing access — want me to request it?'"""
    d = compute_access_decision(
        _subject(), _resource(required_roles=("billing-reader",)), signing_key=KEY, now_epoch=NOW
    )
    assert d.grade == "requires-consent"
    assert d.remediation is not None
    assert "billing-reader" in d.reason
    assert d.remediation.expected_return == "ArtifactConsentRecord"


def test_missing_role_on_a_non_consentable_resource_is_denied() -> None:
    """Offering a request URL for a resource nobody can request is a dead end dressed as a
    path forward."""
    d = compute_access_decision(
        _subject(),
        _resource(required_roles=("regulator",), consentable=False,
                  denial_reason="regulator access is granted out-of-band only"),
        signing_key=KEY, now_epoch=NOW,
    )
    assert d.grade == "denied"
    assert d.remediation is None
    assert "out-of-band" in d.reason


# ── the ordering that closes the fail-open shape ───────────────────────────────

def test_trust_floor_is_checked_BEFORE_roles() -> None:
    """A revoked-trust subject holding the right role must NOT pass.

    Checking roles first would let a stale role rescue a downgraded subject — precisely the
    fail-open shape a2a-trust hardening (Noetica#579, #592) was built to close. The trust
    ledger records observed BEHAVIOUR; a role is an assertion about INTENT. Behaviour wins.
    """
    d = compute_access_decision(
        _subject(trust_score=0.20, roles=("billing-reader",)),   # has the role, lost the trust
        _resource(required_roles=("billing-reader",)),
        signing_key=KEY, now_epoch=NOW,
    )
    assert d.grade == "denied", "a stale role must not rescue a revoked-trust subject"
    assert "below the resource floor" in d.reason


def test_below_trust_floor_is_denied_NOT_requires_consent() -> None:
    """Consent cannot lift a trust denial. If it could, a request form would launder a
    revocation — the subject asks, an approver rubber-stamps, and the ledger's judgement is
    silently overridden."""
    d = compute_access_decision(
        _subject(trust_score=0.10), _resource(), signing_key=KEY, now_epoch=NOW
    )
    assert d.grade == "denied"
    assert d.remediation is None, "no self-service path out of a trust denial"
    assert "must not launder" in d.reason


def test_live_consent_receipt_short_circuits_to_granted() -> None:
    """An existing receipt is stronger evidence than role membership — it was explicitly
    issued for this subject and this resource."""
    d = compute_access_decision(
        _subject(roles=()), _resource(required_roles=("billing-reader",)),
        live_consent_ref="urn:srcos:consent:2026-07-30:0001", now_epoch=NOW,
    )
    assert d.grade == "granted"
    assert d.consent_receipt_ref == "urn:srcos:consent:2026-07-30:0001"


def test_trust_floor_default_matches_a2a_trust() -> None:
    """Pinned so a drift between this lib and Noetica's a2a-trust is a failing test, not a
    silent policy divergence between two services that both think they gate at the floor."""
    assert TRUST_FLOOR == 0.45
    assert Resource(resource_id="x").min_trust == TRUST_FLOOR


# ── every decision carries a reason ────────────────────────────────────────────

def test_every_grade_carries_a_substantive_reason() -> None:
    """A decision without a reason is unauditable, and 'denied' with no reason is
    indistinguishable from a misconfiguration."""
    cases = [
        compute_access_decision(_subject(), _resource(), now_epoch=NOW),
        compute_access_decision(_subject(), _resource(required_roles=("x",)), signing_key=KEY, now_epoch=NOW),
        compute_access_decision(_subject(trust_score=0.1), _resource(), now_epoch=NOW),
        compute_access_decision(_subject(), _resource(required_roles=("x",), consentable=False), now_epoch=NOW),
    ]
    seen = set()
    for d in cases:
        assert len(d.reason) > 25, f"{d.grade}: reason too thin — {d.reason!r}"
        seen.add(d.grade)
    assert seen == {"granted", "requires-consent", "denied"}, "all three grades exercised"


# ── the Law-factor mapping ─────────────────────────────────────────────────────

def test_requires_consent_maps_to_ZERO_not_NEG() -> None:
    """The whole point of the three-grade shape. A subject who could be entitled but has not
    yet asked is UNESTABLISHED, not refused. Collapsing to NEG reports a refusal that never
    happened; collapsing to POS certifies access nobody granted."""
    assert grade_to_law_factor("granted") == "POS"
    assert grade_to_law_factor("requires-consent") == "ZERO"
    assert grade_to_law_factor("denied") == "NEG"


def test_law_factor_mapping_covers_every_grade() -> None:
    """A grade with no mapping would raise at dispatch time, in production, on the one
    request that hit it."""
    for g in ("granted", "requires-consent", "denied"):
        assert grade_to_law_factor(g) in {"POS", "ZERO", "NEG"}


# ── signed consent URLs ────────────────────────────────────────────────────────

def test_signed_url_verifies() -> None:
    url = signed_consent_url(
        base_url="https://consent.example/request", subject_id="eve.smith",
        resource_id="local-billing", missing_roles=["billing-reader"],
        expires_at_epoch=NOW + 3600, signing_key=KEY,
    )
    ok, reason = verify_consent_url(url, KEY, now_epoch=NOW)
    assert ok, reason


@pytest.mark.parametrize("field_,tampered", [
    ("subject", "mallory"),
    ("resource", "all-billing"),
    ("roles", "admin"),
    ("exp", str(NOW + 999_999_999)),
])
def test_altering_ANY_signed_field_fails_verification(field_: str, tampered: str) -> None:
    """The signature binds subject + resource + roles + expiry. Without that binding, an
    intercepted URL could be edited to request a DIFFERENT resource, or grant ADMIN, or
    never expire — a capability with the scope left blank."""
    url = signed_consent_url(
        base_url="https://consent.example/request", subject_id="eve.smith",
        resource_id="local-billing", missing_roles=["billing-reader"],
        expires_at_epoch=NOW + 3600, signing_key=KEY,
    )
    parsed = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parsed.query))
    q[field_] = tampered
    tampered_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urllib.parse.urlencode(q)}"

    ok, reason = verify_consent_url(tampered_url, KEY, now_epoch=NOW)
    assert not ok, f"altering {field_} must fail verification"
    assert "altered" in reason or "expired" in reason


def test_expired_url_fails_even_with_a_valid_signature() -> None:
    """A correctly-signed URL that has expired is still invalid. A caller checking only the
    signature would honour a year-old request form."""
    url = signed_consent_url(
        base_url="https://consent.example/request", subject_id="eve.smith",
        resource_id="local-billing", missing_roles=["billing-reader"],
        expires_at_epoch=NOW - 1, signing_key=KEY,
    )
    ok, reason = verify_consent_url(url, KEY, now_epoch=NOW)
    assert not ok
    assert "expired" in reason
    assert "does not revive" in reason


def test_unsigned_url_carries_no_sig_param_at_all() -> None:
    """'Never signed' and 'signed then tampered' must be distinguishable — only the second
    is an attack, and conflating them would either cry wolf on dev URLs or stay silent on
    real tampering."""
    url = signed_consent_url(
        base_url="https://consent.example/request", subject_id="eve.smith",
        resource_id="local-billing", missing_roles=["billing-reader"],
        expires_at_epoch=NOW + 3600, signing_key=None,
    )
    assert "sig=" not in url, "an unsigned URL must omit sig entirely, not send an empty one"
    ok, reason = verify_consent_url(url, KEY, now_epoch=NOW)
    assert not ok
    assert "never signed" in reason


def test_signature_is_reproducible_across_calls() -> None:
    """Two callers building the same request must produce byte-identical signatures, or
    verification is a coin flip. Same discipline as canonical JSON in lawful-verdict."""
    kwargs = dict(
        base_url="https://consent.example/request", subject_id="eve.smith",
        resource_id="local-billing", missing_roles=["billing-reader", "analyst"],
        expires_at_epoch=NOW + 3600, signing_key=KEY,
    )
    assert signed_consent_url(**kwargs) == signed_consent_url(**kwargs)


def test_decision_serialises_without_a_bare_boolean() -> None:
    """The JSON shape must force a consumer to read `grade`. A `granted: true/false` field
    would let 'requires-consent' silently collapse into 'denied' at every call site."""
    d = compute_access_decision(
        _subject(), _resource(required_roles=("billing-reader",)), signing_key=KEY, now_epoch=NOW
    )
    j = d.to_json()
    assert j["grade"] == "requires-consent"
    assert "granted" not in j, "no boolean field — the three-way grade is the only answer"
    assert j["remediation"]["expectedReturn"] == "ArtifactConsentRecord"
    assert j["reason"]
