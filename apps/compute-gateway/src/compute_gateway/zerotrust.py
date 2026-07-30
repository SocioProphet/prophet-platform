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
gateway performs the CHECK and emits conforming evidence.

── VENDORED SCHEMAS: provenance and integrity (see schemas/PROVENANCE.md) ────
Six schemas are VENDORED into this package (`src/compute_gateway/schemas/`, so
they ship in the image the Dockerfile builds from `COPY src`) — sovereign,
self-contained, validated at runtime and in tests against the exact kernel
contract:

    repo    SocioProphet/mcp-a2a-zero-trust
    commit  0399e8ae84f0be8194ce57e56b14ba4bbb807f47  (2026-05-21, "Bind MCP/A2A
            interop to Operation Plane trust boundaries")
    files   mcp/registry/capability_registry.schema.json
            schemas/canonical/{attestation_bundle,grant,policy_decision,quorum_proof}.schema.json
            schemas/interop/tool_grant_check.schema.json

All six are byte-identical to that commit (re-verified against upstream
2026-07-29, and still byte-identical to the kernel's `main` — the pin is current,
not merely recorded). The per-file sha256 table below is ASSERTED AT IMPORT
(nugget-extractor contract.py precedent), together with the exact FILE SET: an
unexpected schema appearing in this directory is refused too, because
`_registry()` globs the directory and would otherwise hand an unvendored
document authority over what this gateway accepts.

The prior version of this docstring named the vendored path as
`apps/compute-gateway/schemas/`, which does not exist — the real location is
`src/compute_gateway/schemas/`. A provenance note pointing at the wrong
directory is how "vendored from nowhere identifiable" starts.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import registry, signing
from .contract import Receipt

log = logging.getLogger("compute_gateway.zerotrust")

# ── env flags: one spelling convention, and "off" is never silent ─────────────
# The estate spells truthy at least three ways: "1" is dominant (NOETICA_SHACL_ENFORCE,
# BROKER_REQUIRE_KEY, SERVICE_REGISTER_STRICT, PREMERGE_STRICT), memoryd/main.py accepts
# {'1','true','yes'}, and hellgraph-service uses 'on'. This module used to accept the literal
# "true" and nothing else, so ZEROTRUST_ENFORCE=1 — the estate's OWN dominant spelling — parsed
# as False. An operator who set it believed the gate was on; grant_check silently skipped every
# grant-store validation. A flag with three spellings, one of which quietly means "off", is a
# worse failure than no flag at all.
TRUTHY = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, default: str = "false") -> bool:
    """Parse a boolean env var — THE one way this package parses them.

    Other apps in the estate still carry their own variants (memoryd, hellgraph-service,
    device-service, openai-research-mcp, osm-map-api). Consolidating those is a separate
    change; this at least stops the gateway from adding a fourth convention. Note that
    engine.py's GATEWAY_MEMOIZE / GATEWAY_WRITE_PROVENANCE still use `== "true"` — they
    default to ON, so the same bug there turns a feature off rather than a gate, but they
    should adopt this helper too.
    """
    return os.getenv(name, default).strip().lower() in TRUTHY


ZEROTRUST_ENFORCE = env_flag("ZEROTRUST_ENFORCE")
TRUST_BOUNDARY_ID = os.getenv("ZEROTRUST_BOUNDARY_ID", "tb-compute-gateway")
TRUST_DOMAIN = os.getenv("ZEROTRUST_TRUST_DOMAIN", "socioprophet.dev")


def warn_if_unenforced(warn: Callable[[str], None] | None = None) -> bool:
    """Announce a DISABLED zero-trust gate loudly at startup. Returns True if it warned.

    Matches the discipline hellgraph-service already applies in auth.ts (`initAuth`) and
    membrane.ts (`initMembrane`): off is a legitimate rollout state, but it is a passthrough,
    and a passthrough must be stated out loud exactly once rather than inferred from silence.

    The default is deliberately NOT flipped to on here. `deploy/values/compute-gateway.yaml`
    does not set ZEROTRUST_ENFORCE at all, so the deployed default is off, and turning it on
    is a deployment decision with a live blast radius — not something to slip in under a
    parsing fix. Making "off" audible is the fix; choosing "on" is Michael's call.
    """
    if ZEROTRUST_ENFORCE:
        return False
    (warn or log.warning)(
        "[zerotrust] WARN ZEROTRUST_ENFORCE is OFF — grant validation is a PASSTHROUGH. "
        "grant_check() never checks a presented grant_id against the grant store, so a "
        "REVOKED or EXPIRED grant returns valid=True on entitlement alone, and a user-code "
        "kind dispatches with no capability grant at all. Set ZEROTRUST_ENFORCE to one of "
        f"{sorted(TRUTHY)} to fail closed."
    )
    return True


# Import IS startup for this module (the vendored-schema provenance assertion below already
# relies on that), and the gateway's entrypoint is `uvicorn compute_gateway.server:app`, which
# imports this module rather than calling an init hook we could hang the warning off.
warn_if_unenforced()

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"   # ships inside the package (src/)

# ── vendored kernel schemas: the pinned manifest ──────────────────────────────
# The authority kernel the compute plane conforms to. A branch name would be a moving
# reference; this is the commit the bytes came from.
KERNEL_REPO = "SocioProphet/mcp-a2a-zero-trust"
KERNEL_COMMIT = "0399e8ae84f0be8194ce57e56b14ba4bbb807f47"
KERNEL_REF = f"{KERNEL_REPO}@{KERNEL_COMMIT}"

# vendored filename -> (upstream path at KERNEL_COMMIT, sha256 of the bytes)
# The upstream path matters as much as the digest: it is what makes a re-vendor mechanical
# instead of a search, and it is precisely what was missing when these six were described as
# "vendored" from nowhere identifiable.
SCHEMA_PROVENANCE: dict[str, tuple[str, str]] = {
    "capability_registry.schema.json": (
        "mcp/registry/capability_registry.schema.json",
        "f3e793394baee2c4782762de565e988b4fc527639b41839aa859d2f9cbb3d73d"),
    "attestation_bundle.schema.json": (
        "schemas/canonical/attestation_bundle.schema.json",
        "485d0ed689cc1b3184a18d555bb3eba75c4110f7087d0c3c6c54c575447a4272"),
    "grant.schema.json": (
        "schemas/canonical/grant.schema.json",
        "2aac20b5fc9ce2ef72c0609bc1687f2b4b17a2167ef3148fa8ad3c4c1494f0b1"),
    "policy_decision.schema.json": (
        "schemas/canonical/policy_decision.schema.json",
        "fa836113aeda2b1d65b9a3868cb692e266fa51d516bb3a3f248e58e74d6dfc89"),
    "quorum_proof.schema.json": (
        "schemas/canonical/quorum_proof.schema.json",
        "d3ceec20d3268c30c1f0fda17f0981654a850ad39073ac5b1ff4aff62a0b2bb2"),
    "tool_grant_check.schema.json": (
        "schemas/interop/tool_grant_check.schema.json",
        "360c5c98c43742aa7f930a472fd8662eff28bba32eca9b20dd8e76d3077c923c"),
}


def verify_vendored_schemas(schema_dir: Path | None = None) -> dict[str, str]:
    """Fail-closed integrity gate over the vendored kernel schemas. Returns {file: sha256}.

    Three ways to fail, all raising RuntimeError, because all three mean this gateway would be
    enforcing a contract other than the one it declares:

      missing   — a pinned schema is absent; validation would raise at first use, deep inside a
                  request, rather than at boot.
      drifted   — a pinned schema's bytes changed. These documents decide what a ToolGrantCheck
                  and an AttestationBundle ARE; a loosened `required` or a widened enum silently
                  admits evidence the kernel would reject, and nothing downstream can tell.
      unpinned  — an EXTRA *.schema.json in the directory. `_registry()` globs this directory and
                  registers every document it finds by $id, so an unvendored file can satisfy a
                  canonical $ref and quietly become the contract. Vendoring is a closed set or it
                  is not vendoring.
    """
    d = _SCHEMA_DIR if schema_dir is None else schema_dir
    found = {p.name for p in d.glob("*.schema.json")}
    pinned = set(SCHEMA_PROVENANCE)

    if missing := sorted(pinned - found):
        raise RuntimeError(
            f"vendored kernel schemas MISSING: {', '.join(missing)} (expected in {d}); "
            f"re-vendor from {KERNEL_REF}")
    if extra := sorted(found - pinned):
        raise RuntimeError(
            f"UNPINNED schema(s) in the vendored kernel directory: {', '.join(extra)}. Every "
            f"schema here is registered by $id and can satisfy a canonical $ref, so an unvendored "
            f"document would silently become part of the contract. Add it to SCHEMA_PROVENANCE "
            f"with its upstream path + sha256, or remove it.")

    digests: dict[str, str] = {}
    for name, (upstream_path, expected) in sorted(SCHEMA_PROVENANCE.items()):
        actual = hashlib.sha256((d / name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"vendored kernel schema DRIFTED: {name} sha256 {actual} != pinned {expected}; "
                f"re-vendor from {KERNEL_REF} ({upstream_path}) and update SCHEMA_PROVENANCE + "
                f"schemas/PROVENANCE.md. Refusing to enforce a contract this gateway cannot name.")
        digests[name] = actual
    return digests


# THE GATE. Asserted at import — a provenance table nothing verifies is decoration.
SCHEMA_DIGESTS = verify_vendored_schemas()

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

    With enforcement OFF this function validates NOTHING against the grant store: a
    presented grant_id is echoed into the evidence and `valid` tracks `entitled` alone,
    so a REVOKED or EXPIRED grant still reads valid=True. That is the passthrough
    warn_if_unenforced() announces at startup — it is a real state, not a theoretical one.
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
