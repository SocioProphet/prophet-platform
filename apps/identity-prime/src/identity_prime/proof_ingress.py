from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

ProofSource = Literal[
    "first_party_passkey",
    "enterprise_oidc",
    "enterprise_saml",
    "workload_identity",
    "recovery_flow",
]

ProofResult = Literal["accepted", "rejected", "inconclusive"]

_ALLOWED_PROOF_SOURCES = {
    "first_party_passkey",
    "enterprise_oidc",
    "enterprise_saml",
    "workload_identity",
    "recovery_flow",
}

_ALLOWED_RESULTS = {"accepted", "rejected", "inconclusive"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit_proof_ingress_record(
    *,
    proof_source: ProofSource,
    tenant_id: str,
    result: ProofResult,
    subject_id: str | None = None,
    issuer_ref: str | None = None,
    upstream_subject: str | None = None,
    assurance_context: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
    correlation_id: str | None = None,
    proof_record_id: str | None = None,
    received_at: str | None = None,
) -> dict[str, Any]:
    """Emit an IdentityProofIngressRecord v0.1 payload.

    This helper only shapes a contract-conformant record. It does not verify an
    upstream authenticator, issue a session, mutate gateway behavior, or persist
    the record.
    """

    if proof_source not in _ALLOWED_PROOF_SOURCES:
        raise ValueError(f"unsupported proof_source: {proof_source}")
    if result not in _ALLOWED_RESULTS:
        raise ValueError(f"unsupported result: {result}")
    if not tenant_id:
        raise ValueError("tenant_id is required")

    record: dict[str, Any] = {
        "version": "0.1",
        "proof_record_id": proof_record_id or f"proof_{uuid4()}",
        "proof_source": proof_source,
        "tenant_id": tenant_id,
        "received_at": received_at or utc_now_iso(),
        "result": result,
    }

    optional_fields: dict[str, Any | None] = {
        "subject_id": subject_id,
        "issuer_ref": issuer_ref,
        "upstream_subject": upstream_subject,
        "assurance_context": assurance_context,
        "evidence_refs": evidence_refs,
        "correlation_id": correlation_id,
    }
    for key, value in optional_fields.items():
        if value is not None:
            record[key] = value

    return record
