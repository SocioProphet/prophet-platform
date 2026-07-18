"""Zero-trust conformance to OUR authority kernel — SocioProphet/mcp-a2a-zero-trust.

We do NOT use the public `mcp` SDK. The estate owns the control-zone security
kernel (mcp-a2a-zero-trust): provider capability registries, MCP tool/server
trust boundaries, ToolGrant request/decision/ledger contracts, and hardware/
supply-chain attestation bundles. The compute-gateway registers as a governed
PROVIDER inside that kernel:

  • capability_registry()  — declares the gateway as an MCP server whose tools
    ARE the compute kinds (one row per registry kind), conforming to
    `mcp/registry/capability_registry.schema.json` ({servers:[{name,side,tools}]}).
  • grant_check()          — every /v1/compute emits a ToolGrantCheck BEFORE
    dispatch (`schemas/interop/tool_grant_check.schema.json`). Under
    ZEROTRUST_ENFORCE a request with no presented grant fails closed.
  • attestation_bundle()   — the signed in-toto/Ed25519 receipt is rendered as
    an AttestationBundle (`schemas/canonical/attestation_bundle.schema.json`):
    the Ed25519 signature over the in-toto Statement IS a cosign-class
    attestation (cosign_valid), with the receipt id as the attested-unit digest.

The full grant DECISION + ledger + quorum live in the kernel/agentplane; the
gateway performs the CHECK and emits conforming evidence. Schemas are VENDORED
(apps/compute-gateway/schemas/) — sovereign, self-contained, validated at runtime
and in tests against the exact kernel contract (pinned mcp-a2a-zero-trust 0399e8a).
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from . import registry, signing
from .contract import Receipt

ZEROTRUST_ENFORCE = os.getenv("ZEROTRUST_ENFORCE", "false").lower() == "true"
TRUST_BOUNDARY_ID = os.getenv("ZEROTRUST_BOUNDARY_ID", "tb-compute-gateway")
TRUST_DOMAIN = os.getenv("ZEROTRUST_TRUST_DOMAIN", "socioprophet.dev")

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"   # ships inside the package (src/)

# compute kind → capability effect (kernel enum: read|write|compute|exec|egress)
_EFFECT = {"notebook": "exec", "spark": "exec", "graph-query": "read",
           "graph-stats": "read", "inference": "compute"}


def _sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _spiffe(*segments: str) -> str:
    path = "/".join(s.strip("/").replace(" ", "-") or "_" for s in segments)
    return f"spiffe://{TRUST_DOMAIN}/{path}"


def _policy_hash() -> str:
    """Full sha256 of the entitlement policy in force (kernel requires 64-hex)."""
    return _sha256("entitlements:" + os.getenv("COMPUTE_ENTITLEMENTS", ""))


# ── capability registry: the gateway as a governed MCP provider ──
def capability_registry() -> dict[str, Any]:
    """Declare the compute plane to the kernel: one MCP tool per compute kind."""
    tools = []
    for kind, d in registry.KINDS.items():
        exec_user = d["executes_user_code"]
        tools.append({
            "name": f"compute.{kind.replace('-', '_')}",
            "capability_ref": f"cap:compute:{kind}",
            "capability_digest": _sha256(f"compute:{kind}:{','.join(sorted(d['backends']))}"),
            "effect": _EFFECT.get(kind, "compute"),
            "side_effect_tags": [f"epistemic:{d['epistemic']}", f"status:{d['status']}"],
            "danger_class_hint": "HIGH" if exec_user else "LOW",
            "schema": {
                "in": {"contract": "ComputeRequest", "kind": kind,
                       "backends": d["backends"]},
                "out": {"contract": "ComputeResult", "epistemic": d["epistemic"]},
            },
            "trustHints": {
                "attestationRequired": True,
                "grantRequired": exec_user,   # user-code kinds always need a grant
                "ledgerMode": "required",
            },
        })
    return {"servers": [{
        "name": "compute-gateway",
        "side": "either",            # reachable from edge and twin planes
        "tools": tools,
    }]}


# ── ToolGrantCheck: fail-closed grant validation before every dispatch ──
def grant_check(*, project: str, kind: str, backend: str, actor: str,
                grant_id: str | None, entitled: bool) -> tuple[dict[str, Any], bool]:
    """Build a conforming ToolGrantCheck and return (check, permitted).

    The uniform entitlement gate has already decided `entitled`. This records the
    kernel-shaped evidence AND, under ZEROTRUST_ENFORCE, tightens the decision:
    a user-code kind presented with no grant_id fails closed regardless of
    entitlement (defence in depth — a paid entitlement is not a capability grant).
    """
    needs_grant = registry.KINDS.get(kind, {}).get("executes_user_code", False)
    gid = grant_id or f"grant-implicit-{project}-{kind}"
    valid = entitled
    reason = "entitled" if entitled else "no entitlement for project"
    expired = revoked = False

    if ZEROTRUST_ENFORCE:
        if grant_id:
            # a presented grant is AUTHORITATIVE — validate it against the grant
            # store (issued? unexpired? unrevoked? operation matches?). Revoked or
            # expired grants fail closed regardless of entitlement.
            from . import grants  # local import avoids a module cycle
            v = grants.validate(grant_id, operation=f"{kind}:{backend}")
            valid, expired, revoked, reason = v["valid"], v["expired"], v["revoked"], v["reason"]
        elif needs_grant:
            valid = False
            reason = "zero-trust: user-code compute requires an explicit capability grant"

    check = {
        "check_id": "check-" + uuid.uuid4().hex,
        "operation": "tool_grant.validate",
        "grant_id": gid,
        "checked_at": _now(),
        "actor": {"spiffe_id": _spiffe("compute-gateway", project, "actor", actor)},
        "result": {"valid": valid, "expired": expired, "revoked": revoked, "reason": reason},
        "trust_boundary_id": TRUST_BOUNDARY_ID,
        "policy_hash": _policy_hash(),
    }
    return check, valid


# ── AttestationBundle: the signed receipt as kernel-consumable attestation ──
def attestation_bundle(receipt: Receipt) -> dict[str, Any]:
    """Render the signed in-toto/Ed25519 receipt as an AttestationBundle.

    cosign_valid ⇔ the receipt carries an Ed25519 signature that verifies over its
    in-toto Statement (cosign's exact model: sign the statement). tpm/fido2 are
    false — this plane has no hardware root of trust (a flagged deepening: bind to
    a TEE/TPM quote for `verified`→`attested` promotion).
    """
    cosign_valid = bool(
        receipt.signature
        and receipt.statement is not None
        and signing.verify_signature(receipt.statement, receipt.signature, receipt.public_key)
    )
    return {
        "subject": {
            "spiffe_id": _spiffe("compute", receipt.kind, receipt.backend),
            "aum_digest": receipt.id,   # receipt id is already sha256:<64hex>
        },
        "results": {
            "tpm_valid": False,
            "cosign_valid": cosign_valid,
            "fido2_valid": False,
        },
        "evidence_refs": {
            "cosign_bundle_ref": receipt.id,
        },
    }


# ── vendored-schema validation (sovereign, self-contained) ──
@functools.lru_cache(maxsize=None)
def _schema(name: str) -> dict[str, Any]:
    return json.loads((_SCHEMA_DIR / f"{name}.schema.json").read_text())


@functools.lru_cache(maxsize=1)
def _registry() -> Any:
    """A referencing registry of every vendored schema (keyed by $id) so canonical
    cross-refs — e.g. grant → quorum_proof.schema.json — resolve locally, sovereignly."""
    from referencing import Registry, Resource  # noqa: PLC0415

    resources = []
    for p in _SCHEMA_DIR.glob("*.schema.json"):
        s = json.loads(p.read_text())
        res = Resource.from_contents(s)
        if "$id" in s:
            resources.append((s["$id"], res))
    return Registry().with_resources(resources)


def validate(payload: dict[str, Any], schema_name: str) -> None:
    """Validate against the vendored kernel schema. Raises jsonschema.ValidationError.

    Import is local so the gateway still boots if jsonschema is absent (validation
    is a conformance guarantee, not a request-path dependency)."""
    import jsonschema  # noqa: PLC0415

    jsonschema.Draft202012Validator(_schema(schema_name), registry=_registry()).validate(payload)
