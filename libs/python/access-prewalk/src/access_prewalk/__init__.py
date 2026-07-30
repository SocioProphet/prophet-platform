"""Graded, receipt-bound access decisions for any Python service on the mesh.

The failure this replaces: access as a BOOLEAN the caller checked in-line. Zurich's E-RDA2
diagram shows it plainly — a T/F marker per data source, resolved once, with no time bound,
no revocation trail, and no artefact the caller can present later to show it was entitled.
A boolean answers "may I?" and forgets. A receipt answers "I was entitled, here is the proof,
it expires at T, and here is how it can be revoked."

Three grades, not two:

===================  ==========================================================
``granted``          entitled now; a live consent receipt exists or none is needed
``requires-consent`` not entitled YET — and here is the signed request to fix that
``denied``           not entitled, and no self-service path exists
===================  ==========================================================

``requires-consent`` is what a boolean cannot express, and it is the grade that carries the
product value: Michael can tell Eve "you don't have billing access — want me to request it?"
and hand her a prefilled, signed URL, instead of failing with "permission denied".

Why this lives in ``libs/python`` rather than inside one app: the same reasoning that moved
``lawful-verdict`` here. Access grading that lives inside Noetica is grading no other service
can perform, and prophet-workspace, agora and ops-fabric-api all need it. See
prophet-platform#1065 for the precedent.

Composes with:
  - ``lawful_verdict`` — an access decision is a Law factor; ``granted`` maps to POS,
    ``requires-consent`` to ZERO (unestablished, not refused), ``denied`` to NEG.
  - Noetica ``a2a-trust`` — the graded 0..1 trust score, with ``TRUST_FLOOR = 0.45``.
  - ``ArtifactConsentRecord`` (sourceos-spec) — what a signed request returns on approval.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

__all__ = [
    "Grade", "TRUST_FLOOR", "AccessDecision", "Remediation", "Subject", "Resource",
    "compute_access_decision", "signed_consent_url", "verify_consent_url",
    "grade_to_law_factor",
]

Grade = Literal["granted", "requires-consent", "denied"]

#: Mirrors Noetica ``a2a-trust.TRUST_FLOOR``. Below this a subject cannot be granted
#: regardless of policy — the trust ledger is the floor, policy is the ceiling.
#: Kept as a module constant, not a magic number, so a policy change is one edit and the
#: test pinning it is the change-notice.
TRUST_FLOOR = 0.45


@dataclass(frozen=True)
class Subject:
    """Who is asking. ``trust_score`` comes from the a2a-trust ledger; ``groups`` and
    ``roles`` from the directory. All three are inputs to the decision — none is the
    decision itself."""

    subject_id: str
    trust_score: float
    roles: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class Resource:
    """What is being asked for.

    ``required_roles`` empty means no role gates it (still subject to the trust floor).
    ``consentable`` is the difference between ``requires-consent`` and ``denied``: a
    resource nobody can request access to is denied, full stop — offering a request URL
    for it would be a dead end dressed as a path forward.
    """

    resource_id: str
    required_roles: tuple[str, ...] = ()
    min_trust: float = TRUST_FLOOR
    consentable: bool = True
    #: Human-readable why-denied, surfaced when consentable is False. Without it a `denied`
    #: is indistinguishable from a misconfiguration.
    denial_reason: str | None = None


@dataclass(frozen=True)
class Remediation:
    """The self-service path out of ``requires-consent``."""

    url: str
    expected_return: str = "ArtifactConsentRecord"
    expires_at_epoch: int = 0


@dataclass(frozen=True)
class AccessDecision:
    """The result. Note what is NOT here: a bare boolean. Every consumer must read `grade`,
    and the three-way shape makes 'requires-consent' impossible to accidentally collapse
    into 'denied' — which is what a boolean API forces."""

    grade: Grade
    subject_id: str
    resource_id: str
    trust_score: float
    #: WHY. A decision without a reason is unauditable, and 'denied' with no reason is
    #: indistinguishable from a bug. Always populated, for every grade.
    reason: str
    remediation: Remediation | None = None
    consent_receipt_ref: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "grade": self.grade,
            "subjectId": self.subject_id,
            "resourceId": self.resource_id,
            "trustScore": self.trust_score,
            "reason": self.reason,
        }
        if self.consent_receipt_ref:
            out["consentReceiptRef"] = self.consent_receipt_ref
        if self.remediation:
            out["remediation"] = {
                "url": self.remediation.url,
                "expectedReturn": self.remediation.expected_return,
                "expiresAtEpoch": self.remediation.expires_at_epoch,
            }
        return out


def compute_access_decision(
    subject: Subject,
    resource: Resource,
    *,
    live_consent_ref: str | None = None,
    consent_base_url: str = "https://consent.socioprophet.io/request",
    signing_key: bytes | None = None,
    ttl_seconds: int = 604800,
    now_epoch: int | None = None,
) -> AccessDecision:
    """Resolve access to a graded, receipt-bound decision.

    Order of checks is deliberate and each is stated in the returned ``reason``:

    1. **Live consent** short-circuits to ``granted`` — an existing receipt is the strongest
       evidence, stronger than role membership, because it was explicitly issued for this
       subject and resource.
    2. **Trust floor** is checked BEFORE roles. A subject below the floor cannot be rescued
       by having the right role: the trust ledger records observed behaviour, and a role is
       an assertion about intent. Behaviour beats assertion.
    3. **Roles** gate the rest. Missing role ⇒ ``requires-consent`` when the resource is
       consentable, ``denied`` when it is not.

    That ordering is the substance. Checking roles first would let a revoked-trust subject
    with a stale role pass — which is exactly the fail-open shape a2a-trust hardening
    (Noetica#579, #592) was built to close.
    """
    now = int(time.time()) if now_epoch is None else now_epoch

    if live_consent_ref:
        return AccessDecision(
            grade="granted", subject_id=subject.subject_id, resource_id=resource.resource_id,
            trust_score=subject.trust_score, consent_receipt_ref=live_consent_ref,
            reason=f"live consent receipt {live_consent_ref} covers this subject and resource",
        )

    if subject.trust_score < resource.min_trust:
        # Below the floor is DENIED, not requires-consent. Offering a consent path to a
        # subject the trust ledger has downgraded would let a request form launder a
        # revocation — the fail-open shape a2a-trust hardening exists to prevent.
        return AccessDecision(
            grade="denied", subject_id=subject.subject_id, resource_id=resource.resource_id,
            trust_score=subject.trust_score,
            reason=(
                f"trust score {subject.trust_score:.2f} is below the resource floor "
                f"{resource.min_trust:.2f}. Consent cannot lift a trust denial — the ledger "
                f"records observed behaviour, and a request form must not launder it."
            ),
        )

    missing = [r for r in resource.required_roles if r not in subject.roles]
    if not missing:
        return AccessDecision(
            grade="granted", subject_id=subject.subject_id, resource_id=resource.resource_id,
            trust_score=subject.trust_score,
            reason=(
                f"trust {subject.trust_score:.2f} >= floor {resource.min_trust:.2f}"
                + (f" and subject holds all required roles {list(resource.required_roles)}"
                   if resource.required_roles else " and the resource gates on no role")
            ),
        )

    if not resource.consentable:
        return AccessDecision(
            grade="denied", subject_id=subject.subject_id, resource_id=resource.resource_id,
            trust_score=subject.trust_score,
            reason=(
                resource.denial_reason
                or f"missing roles {missing} and the resource is not consentable — "
                   "no self-service path exists"
            ),
        )

    expires = now + ttl_seconds
    url = signed_consent_url(
        base_url=consent_base_url, subject_id=subject.subject_id,
        resource_id=resource.resource_id, missing_roles=missing,
        expires_at_epoch=expires, signing_key=signing_key,
    )
    return AccessDecision(
        grade="requires-consent", subject_id=subject.subject_id,
        resource_id=resource.resource_id, trust_score=subject.trust_score,
        reason=(
            f"trust {subject.trust_score:.2f} clears the floor but subject is missing "
            f"roles {missing}; a signed request is available"
        ),
        remediation=Remediation(url=url, expires_at_epoch=expires),
    )


def signed_consent_url(
    *,
    base_url: str,
    subject_id: str,
    resource_id: str,
    missing_roles: Sequence[str],
    expires_at_epoch: int,
    signing_key: bytes | None = None,
) -> str:
    """Build a prefilled consent-request URL, signed when a key is supplied.

    The signature binds subject + resource + roles + expiry. Without it, an intercepted URL
    could be edited to request a DIFFERENT resource or a longer expiry and still look
    legitimate — the URL is a capability, and an unsigned capability is a bearer token with
    the scope left blank.

    Unsigned URLs are permitted (``signing_key=None``) for local development, and they carry
    NO ``sig`` parameter at all rather than an empty one. That distinction matters:
    ``verify_consent_url`` can then tell "never signed" from "signed and tampered", and only
    the second is an attack.
    """
    params = {
        "subject": subject_id,
        "resource": resource_id,
        "roles": ",".join(missing_roles),
        "exp": str(expires_at_epoch),
    }
    canonical = _canonical_params(params)
    if signing_key is not None:
        params["sig"] = hmac.new(signing_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def verify_consent_url(url: str, signing_key: bytes, *, now_epoch: int | None = None) -> tuple[bool, str]:
    """Verify a consent URL's signature and expiry. Returns ``(ok, reason)``.

    Expiry is checked as well as signature, because a correctly-signed URL that has expired
    is still invalid — and a caller that checked only the signature would honour a
    year-old request form.
    """
    now = int(time.time()) if now_epoch is None else now_epoch
    parsed = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    sig = q.pop("sig", None)
    if sig is None:
        return False, "URL carries no signature — it was never signed, so nothing binds its scope"

    expected = hmac.new(signing_key, _canonical_params(q).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False, "signature does not match — subject, resource, roles or expiry was altered"

    try:
        exp = int(q.get("exp", "0"))
    except ValueError:
        return False, "expiry is not an integer epoch"
    if exp <= now:
        return False, f"request expired at epoch {exp} (now {now}) — a valid signature does not revive it"

    return True, "signature valid and unexpired"


def _canonical_params(params: dict[str, str]) -> str:
    """Deterministic parameter serialisation for signing. Sorted keys, no whitespace — the
    same discipline as canonical JSON in lawful-verdict, for the same reason: two callers
    must produce byte-identical input or the signature is unreproducible."""
    return json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def grade_to_law_factor(grade: Grade) -> str:
    """Map an access grade onto the Law factor of Truth = Law × Evidence.

    ``requires-consent`` is ZERO, not NEG. That is the whole point of the three-grade shape:
    a subject who could be entitled but has not yet asked is UNESTABLISHED, not refused.
    Collapsing it to NEG would report a refusal that never happened, and collapsing it to
    POS would certify access nobody granted.
    """
    return {"granted": "POS", "requires-consent": "ZERO", "denied": "NEG"}[grade]
