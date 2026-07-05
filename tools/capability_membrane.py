"""Capability membrane — the unified capability-decision kernel (design "C").

One decision point every capability call routes through, composing FOUR
already-shipped kernels rather than reinventing them:

  1. Surface taxonomy   — sourceos-spec ConnectorActionScope.connectorKind
                          (filesystem|shell|computer|browser|deployment|...),
                          i.e. the same native surfaces a desktop agent exposes.
  2. Capability radius   — agentplane R0..R5 (docs/specs/capability-radius-v0):
                          each tier lists REQUIRED tension members; a work
                          (compression) member never executes without its
                          policy tension member (Tensegrity Invariant 1) →
                          fail-closed QUARANTINE when a required member is absent.
  3. Membrane decision   — slash-topics Membrane_Decision v0.2 /
                          prophet-platform contracts/MembraneDecision.v0.1
                          (ALLOW|DENY|QUARANTINE|REDACT|REQUIRE_SIGNATURE)
                          × scope (user_local|global_platform).
  4. Autonomy ladder     — tritfabric atlas/autonomy_gate L0..L5, fail-closed:
                          a level is admitted only if its evidence is present;
                          promotion BLOCKS rather than silently under-granting.

The kernel collapses those into ONE sourceos-spec ExecutionDecision
(allow|deny|ask|defer|rewrite) and emits ONE sealed AgentMachineReceipt whose
`verdict` carries the honest enforce-vs-observe distinction:

  * OWNED surface (ours)      → we enforce; verdict ∈ {allowed,denied,deferred}.
  * FOREIGN surface (e.g. a  → we cannot enforce inside another process, so we
    frontier client's           OBSERVE + receipt only; verdict = "observed",
    computer_use)               enforced = False. Being explicit about this is
                                the difference between a real membrane and a
                                false one.

Pure and local-first: no network, stdlib only. A membrane in the hot path of
every capability call must not take a cloud round-trip.

Conformance notes
-----------------
* Hashes are ``sha256:<lowercase-hex>`` over a JCS-style canonical form
  (RFC 8785 subset: sorted keys, compact separators, UTF-8). Adequate for the
  string/int/bool/array/object payloads here; floats are not used.
* Seal binding follows agentplane seal_reasoning_receipt:
  ``seal_hash = sha256( receipt_canonical || run_trace_hash || events_sha )``.
* The autonomy ladder is loaded as DATA from the canonical
  ``tritfabric/configs/autonomy-ladder.yaml`` when reachable, else the embedded
  copy below (kept byte-equal to the canonical export). The kernel never forks
  the ladder logic — it mirrors autonomy_gate.evaluate exactly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SPEC_VERSION = "2.0.0"

# --------------------------------------------------------------------------- #
# 1. Surface taxonomy — mirrors sourceos-spec ConnectorActionScope.connectorKind
# --------------------------------------------------------------------------- #

# connectorKinds we treat as "actuating" (side-effecting on the world). The list
# mirrors the spec enum; the classification here only drives the default radius.
CONNECTOR_KINDS = (
    "filesystem", "github", "gitlab", "email", "calendar", "drive", "slack",
    "linear", "notion", "browser", "computer", "httpApi", "kafka", "rdbms",
    "objectStore", "lakehouse", "shell", "ci", "deployment", "observability",
    "custom",
)

# sourceos-spec ConnectorActionScope.accessLevel
ACCESS_LEVELS = (
    "none", "readOnly", "draftOnly", "commentOnly", "scopedWrite",
    "send", "publish", "merge", "destructive", "control",
)

# --------------------------------------------------------------------------- #
# 2. Capability radius — agentplane R0..R5 + required tension members
#    (docs/specs/capability-radius-v0.md). Fail-closed if a required member
#    is absent (Tensegrity Invariant 1).
# --------------------------------------------------------------------------- #

R_TIERS = ("R0", "R1", "R2", "R3", "R4", "R5")

# Cumulative required tension members per radius, verbatim from capability-radius-v0.
TENSION_REQUIRED: Dict[str, Tuple[str, ...]] = {
    "R0": ("policy", "identity"),
    "R1": ("policy", "identity", "provenance"),
    "R2": ("policy", "identity", "provenance", "evidence", "replay"),
    "R3": ("policy", "identity", "provenance", "evidence", "replay", "revocation"),
    "R4": ("policy", "identity", "provenance", "evidence", "replay", "revocation", "audit"),
    "R5": ("policy", "identity", "provenance", "evidence", "replay", "revocation", "audit", "post_authority_ref"),
}

# Map an accessLevel to its minimum capability radius. Reading is R0/R1; writing
# to governed state is R3; deploy is R4; host/prod control is R5.
ACCESS_TO_RADIUS: Dict[str, str] = {
    "none": "R0",
    "readOnly": "R1",
    "commentOnly": "R1",
    "draftOnly": "R2",
    "scopedWrite": "R3",
    "send": "R3",
    "publish": "R3",
    "merge": "R3",
    "destructive": "R5",
    "control": "R5",
}

# A few connector kinds float the floor up regardless of access level: driving
# the OS or a browser session, or mutating a deployment, is never below these.
CONNECTOR_RADIUS_FLOOR: Dict[str, str] = {
    "computer": "R3",     # synthesises input into the live OS
    "shell": "R3",        # spawns real processes
    "deployment": "R4",   # stages/mutates environments
    "ci": "R4",
}

# Reserved / internal handler namespaces (gapi §8 "handler namespace collision":
# only registered services are callable; reserved lifecycle handlers like
# _g_connect / __cb must not be reachable by ordinary callers). Any action in a
# reserved namespace floors to R5, so it is admissible only with an explicit
# post_authority_ref tension member — a normal caller is denied fail-closed.
RESERVED_ACTION_PREFIXES = ("_", "__", "internal.", "gapi._", "rpc._", "_g_")

# --------------------------------------------------------------------------- #
# 3. Membrane decision domain — slash-topics v0.2 (superset of platform v0.1)
# --------------------------------------------------------------------------- #

MEMBRANE_DECISIONS = ("ALLOW", "DENY", "QUARANTINE", "REDACT", "REQUIRE_SIGNATURE")
MEMBRANE_SCOPES = ("user_local", "global_platform")

# --------------------------------------------------------------------------- #
# 4. Autonomy ladder — mirrors tritfabric atlas/autonomy_gate (fail-closed).
#    Embedded copy of configs/autonomy-ladder.yaml (canonical export from
#    prophet-mesh:specs/ai-driven-development.yaml). evidence_required "none"
#    is always satisfied; otherwise the token must be present.
# --------------------------------------------------------------------------- #

AUTONOMY_LADDER: List[Dict[str, str]] = [
    {"level": "L0", "label": "manual", "evidence_required": "none"},
    {"level": "L1", "label": "assisted", "evidence_required": "trail_log"},
    {"level": "L2", "label": "automated_unit", "evidence_required": "test_result_or_review_receipt"},
    {"level": "L3", "label": "automated_design", "evidence_required": "evidence_dossier"},
    {"level": "L4", "label": "automated_solution", "evidence_required": "conductor_response_envelope"},
    {"level": "L5", "label": "autonomous_governed", "evidence_required": "continuous_attestation_with_revocation"},
]
_LEVEL_RANK = {row["level"]: i for i, row in enumerate(AUTONOMY_LADDER)}


@dataclass
class AutonomyDecision:
    """Mirror of tritfabric atlas.autonomy_gate.AutonomyDecision."""
    ok: bool
    requested_level: str
    granted_level: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "requested_level": self.requested_level,
            "granted_level": self.granted_level,
            "reason": self.reason,
        }


def evaluate_autonomy(requested_level: str, evidence: Iterable[str]) -> AutonomyDecision:
    """Fail-closed admission, byte-for-byte semantics of autonomy_gate.evaluate.

    The requested level is admitted only if its required evidence token is
    present. The reason reports the highest level the evidence actually
    supports (the ceiling), so a caller can see how far short it fell.
    """
    have = set(evidence or ())
    requested = requested_level if requested_level in _LEVEL_RANK else "L0"

    def satisfied(row: Dict[str, str]) -> bool:
        need = row["evidence_required"]
        return need in ("none", "", None) or need in have

    # Ceiling = highest contiguous-independent level whose evidence is present.
    ceiling = "L0"
    for row in AUTONOMY_LADDER:
        if satisfied(row):
            ceiling = row["level"]
    requested_row = AUTONOMY_LADDER[_LEVEL_RANK[requested]]
    ok = satisfied(requested_row)
    if ok:
        reason = f"evidence satisfies gate for {requested} ({requested_row['label']})"
    else:
        reason = (
            f"blocked: {requested} requires '{requested_row['evidence_required']}'; "
            f"evidence supports at most {ceiling}"
        )
    return AutonomyDecision(ok=ok, requested_level=requested, granted_level=ceiling, reason=reason)


# --------------------------------------------------------------------------- #
# Request / resolution model
# --------------------------------------------------------------------------- #

@dataclass
class CapabilityRequest:
    """A single capability call arriving at a surface."""
    surface: str                       # connectorKind, e.g. "shell" | "computer" | "browser"
    action: str                        # dotted action, e.g. "shell.exec", "computer.screencapture"
    access_level: str                  # ConnectorActionScope.accessLevel
    subject_ref: str                   # urn:srcos:agent:... or user
    scope: str = "user_local"          # user_local | global_platform
    owned: bool = True                 # do WE control this surface? False => observe-only
    object_ref: Optional[str] = None
    tension_members: Sequence[str] = field(default_factory=tuple)  # present governance members
    requested_autonomy_level: str = "L0"
    autonomy_evidence: Sequence[str] = field(default_factory=tuple)
    membrane_decision: str = "ALLOW"   # upstream policy verdict (from policyMembrane.membraneRef)
    policy_refs: Sequence[str] = field(default_factory=tuple)
    risk_level: str = "low"            # low|medium|high|critical
    may_transmit_content: bool = False  # ConnectorActionScope.dataExposure.mayTransmitContent
    machine_ref: str = "urn:srcos:agent-machine:local"

    def required_radius(self) -> str:
        if any(self.action.startswith(p) for p in RESERVED_ACTION_PREFIXES):
            return "R5"       # reserved/internal handler — top authority only
        floor = CONNECTOR_RADIUS_FLOOR.get(self.surface, "R0")
        base = ACCESS_TO_RADIUS.get(self.access_level, "R0")
        return floor if _rank(floor) >= _rank(base) else base


@dataclass
class CapabilityResolution:
    request: CapabilityRequest
    radius: str
    required_tension: Tuple[str, ...]
    missing_tension: Tuple[str, ...]
    membrane_decision: str
    autonomy: AutonomyDecision
    execution_decision: str            # allow|deny|ask|defer|rewrite (sourceos ExecutionDecision)
    verdict: str                       # allowed|denied|deferred|failed|observed (AgentMachineReceipt)
    enforced: bool
    obligations: List[Dict[str, str]]
    reasons: List[str]
    receipt: Dict[str, Any]
    sealed: Dict[str, Any]

    @property
    def allowed(self) -> bool:
        return self.execution_decision == "allow" and self.enforced


# --------------------------------------------------------------------------- #
# Canonicalization + sealing (conforms to FOG_ENVELOPE_CANONICALIZATION + agentplane)
# --------------------------------------------------------------------------- #

def _canonical(obj: Any) -> bytes:
    """JCS-style canonical bytes: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _rank(tier: str) -> int:
    return R_TIERS.index(tier) if tier in R_TIERS else 0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seal_receipt(receipt: Dict[str, Any], run_trace_hash: str = "", events_hash: str = "") -> Dict[str, Any]:
    """agentplane seal_reasoning_receipt binding:
    seal_hash = sha256( receipt_canonical || run_trace_hash || events_sha ).
    """
    preimage = _canonical(receipt) + run_trace_hash.encode("utf-8") + events_hash.encode("utf-8")
    seal_hash = _sha256(preimage)
    local = seal_hash.split(":", 1)[1][:32]
    return {
        "id": f"urn:srcos:evidence:sealed-reasoning:{local}",
        "type": "SealedReasoningEvidence",
        "specVersion": SPEC_VERSION,
        "sealedAt": _now(),
        "sealingAuthority": "urn:srcos:authority:capability-membrane",
        "sealHash": seal_hash,
        "binding": {
            "receiptHash": _sha256(_canonical(receipt)),
            "runTraceHash": run_trace_hash,
            "eventsHash": events_hash,
        },
        "receipt": receipt,
        "verifyHint": "recompute sealHash over receipt||runTraceHash||eventsHash",
    }


# --------------------------------------------------------------------------- #
# The kernel
# --------------------------------------------------------------------------- #

# How a membrane decision collapses into a sourceos ExecutionDecision outcome,
# assuming the surface is owned/enforceable and radius+autonomy are satisfied.
_MEMBRANE_TO_EXECUTION = {
    "ALLOW": "allow",
    "DENY": "deny",
    "QUARANTINE": "deny",
    "REDACT": "rewrite",           # proceed, but mask fields (obligation)
    "REQUIRE_SIGNATURE": "ask",     # proceed only once a signature is attached
}

_EXECUTION_TO_VERDICT = {
    "allow": "allowed",
    "deny": "denied",
    "ask": "deferred",
    "defer": "deferred",
    "rewrite": "allowed",
}


def resolve_capability(request: CapabilityRequest,
                       run_trace_hash: str = "",
                       events_hash: str = "",
                       signer: Any = None) -> CapabilityResolution:
    """Compose the four kernels into one decision + one sealed receipt.

    If `signer` (a membrane_identity.IdentityRoot) is supplied, the sealed
    receipt is additionally signed (detached Ed25519 over the FOG preimage),
    threading the sovereign DID through the receipt. Absent a signer the kernel
    stays pure/stdlib-only and emits a valid unsigned receipt.
    """
    reasons: List[str] = []
    obligations: List[Dict[str, str]] = []

    if request.membrane_decision not in MEMBRANE_DECISIONS:
        raise ValueError(f"unknown membrane decision: {request.membrane_decision!r}")
    if request.scope not in MEMBRANE_SCOPES:
        raise ValueError(f"unknown scope: {request.scope!r}")

    # (2) Capability radius + tension-member fail-closed (Tensegrity Invariant 1).
    radius = request.required_radius()
    required = TENSION_REQUIRED[radius]
    present = set(request.tension_members or ())
    missing = tuple(m for m in required if m not in present)
    tension_ok = not missing
    if missing:
        reasons.append(
            f"radius {radius} requires tension members {list(required)}; missing {list(missing)}"
        )

    # (4) Autonomy ladder (fail-closed).
    autonomy = evaluate_autonomy(request.requested_autonomy_level, request.autonomy_evidence)
    if not autonomy.ok:
        reasons.append(autonomy.reason)

    # (3) Membrane decision → base execution outcome.
    membrane = request.membrane_decision
    base_outcome = _MEMBRANE_TO_EXECUTION[membrane]
    if membrane == "REDACT":
        obligations.append({"name": "mask_fields", "when": "runtime"})
        reasons.append("membrane REDACT → rewrite with mask_fields obligation")
    elif membrane == "REQUIRE_SIGNATURE":
        reasons.append("membrane REQUIRE_SIGNATURE → ask (signature required before release)")
    elif membrane in ("DENY", "QUARANTINE"):
        reasons.append(f"membrane {membrane} → deny")

    # Collapse: any fail-closed condition dominates ALLOW/REDACT/REQUIRE_SIGNATURE.
    if base_outcome == "deny":
        execution = "deny"
    elif not tension_ok:
        execution = "deny"          # fail-closed on missing governance
    elif not autonomy.ok:
        execution = "deny"          # over-claimed autonomy
    else:
        execution = base_outcome    # allow | rewrite | ask

    # Enforce-vs-observe: on a foreign surface we cannot prevent the action; we
    # record the decision we WOULD make and mark it advisory.
    if request.owned:
        enforced = True
        verdict = _EXECUTION_TO_VERDICT[execution]
    else:
        enforced = False
        verdict = "observed"
        reasons.append(
            "foreign surface: membrane cannot enforce inside another process — "
            "decision is advisory (observe + receipt only)"
        )

    # Emit a sourceos-spec AgentMachineReceipt (+ embedded PolicyDecision hash).
    decision_body = {
        "surface": request.surface,
        "action": request.action,
        "accessLevel": request.access_level,
        "scope": request.scope,
        "radius": radius,
        "requiredTension": list(required),
        "missingTension": list(missing),
        "membraneDecision": membrane,
        "autonomy": autonomy.to_dict(),
        "executionDecision": execution,
        "obligations": obligations,
        "riskLevel": request.risk_level,
    }
    decision_hash = _sha256(_canonical(decision_body))

    receipt: Dict[str, Any] = {
        "id": "urn:srcos:agent-machine-receipt:" + decision_hash.split(":", 1)[1][:24],
        "type": "AgentMachineReceipt",
        "specVersion": SPEC_VERSION,
        "machineRef": request.machine_ref,
        "receiptClass": "execution" if request.owned else "probe",
        "issuedAt": _now(),
        "subjectRef": request.subject_ref,
        "objectRef": request.object_ref,
        "verdict": verdict,
        "enforced": enforced,
        "policyDecisionRef": list(request.policy_refs),
        "decisionHash": decision_hash,
        "evidenceHash": decision_hash,
        "decision": decision_body,
        "reasons": reasons,
    }

    sealed = seal_receipt(receipt, run_trace_hash=run_trace_hash, events_hash=events_hash)
    if signer is not None:
        sealed = signer.sign_sealed(sealed)

    return CapabilityResolution(
        request=request,
        radius=radius,
        required_tension=required,
        missing_tension=missing,
        membrane_decision=membrane,
        autonomy=autonomy,
        execution_decision=execution,
        verdict=verdict,
        enforced=enforced,
        obligations=obligations,
        reasons=reasons,
        receipt=receipt,
        sealed=sealed,
    )


# --------------------------------------------------------------------------- #
# Reference wiring — compose over the owned prophet-platform policy-fabric surface
# (schemas/external/policy-fabric/prophet_operations_action_decision_v1). The
# policy-fabric produces the ABAC outcome; the membrane then unifies it with
# radius + tension + autonomy + seal into ONE enforced decision + receipt.
# --------------------------------------------------------------------------- #

# ProphetOperationsActionDecision.decision.outcome → Membrane decision domain.
# `unknown` is treated fail-closed (QUARANTINE), never as a silent allow.
POLICY_FABRIC_OUTCOME_TO_MEMBRANE = {
    "allow": "ALLOW",
    "deny": "DENY",
    "manual_review": "REQUIRE_SIGNATURE",
    "defer": "REQUIRE_SIGNATURE",
    "unknown": "QUARANTINE",
}


def request_from_operation_decision(
    decision: Dict[str, Any],
    *,
    surface: str,
    access_level: str,
    subject_ref: Optional[str] = None,
    scope: str = "user_local",
    owned: bool = True,
    tension_members: Sequence[str] = (),
    requested_autonomy_level: str = "L0",
    autonomy_evidence: Sequence[str] = (),
    machine_ref: str = "urn:srcos:agent-machine:local",
) -> CapabilityRequest:
    """Map a policy-fabric ProphetOperationsActionDecision into a CapabilityRequest.

    This is the seam that lets the membrane enforce OVER the existing owned
    surface rather than replace it: the policy-fabric outcome becomes the
    membrane decision input, then radius/tension/autonomy compose on top.
    """
    d = decision.get("decision", {}) or {}
    outcome = d.get("outcome", "unknown")
    membrane = POLICY_FABRIC_OUTCOME_TO_MEMBRANE.get(outcome, "QUARANTINE")

    controls = decision.get("controls", {}) or {}
    if membrane == "ALLOW" and controls.get("requires_human_approval"):
        membrane = "REQUIRE_SIGNATURE"

    action_obj = decision.get("proposed_action", {}) or {}
    action = action_obj.get("type") or action_obj.get("intent") or "operation.execute"
    subject = subject_ref or (decision.get("subject", {}) or {}).get("id") or "urn:srcos:subject:unknown"
    basis = decision.get("basis", {}) or {}

    return CapabilityRequest(
        surface=surface,
        action=action,
        access_level=access_level,
        subject_ref=subject,
        scope=scope,
        owned=owned,
        tension_members=tuple(tension_members),
        requested_autonomy_level=requested_autonomy_level,
        autonomy_evidence=tuple(autonomy_evidence),
        membrane_decision=membrane,
        policy_refs=tuple(basis.get("policy_refs", []) or []),
        risk_level=d.get("risk_level") or "low",
        machine_ref=machine_ref,
    )


# --------------------------------------------------------------------------- #
# Callable gate seam
#
# The stable entrypoint a runtime (an agent-machine, a connector dispatcher, a
# service) calls immediately BEFORE executing a tool/connector action. Describe
# the call as a CapabilityRequest-shaped dict; if the returned decision is not
# `allowed`, the caller MUST NOT execute the action (fail-closed). The sealed
# AgentMachineReceipt travels back for the caller's evidence spine.
# --------------------------------------------------------------------------- #

_REQUEST_FIELDS = set(CapabilityRequest.__dataclass_fields__)


def gate(request: Dict[str, Any]) -> Dict[str, Any]:
    """Gate one tool/connector call. Fail-closed: execute only if ``allowed``.

    >>> gate({"surface": "shell", "action": "shell.exec", "access_level": "scopedWrite",
    ...       "subject_ref": "urn:srcos:agent:x",
    ...       "tension_members": ["policy", "identity"]})["allowed"]
    False
    """
    unknown = set(request) - _REQUEST_FIELDS
    if unknown:
        raise ValueError(f"unknown CapabilityRequest fields: {sorted(unknown)}")
    resolution = resolve_capability(CapabilityRequest(**request))
    return {
        "allowed": resolution.allowed,
        "execution_decision": resolution.execution_decision,
        "verdict": resolution.verdict,
        "enforced": resolution.enforced,
        "radius": resolution.radius,
        "missing_tension": list(resolution.missing_tension),
        "obligations": resolution.obligations,
        "reasons": resolution.reasons,
        "sealed_receipt": resolution.sealed,
    }


def _cli(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Resolve a capability call through the unified membrane.")
    p.add_argument("--request", type=str,
                   help="path (or - for stdin) to a full CapabilityRequest JSON; gates that call and "
                        "prints the decision. Exit 0 iff allowed. The runtime seam.")
    p.add_argument("--operation", type=str, help="path to a ProphetOperationsActionDecision JSON")
    p.add_argument("--surface", help="connectorKind, e.g. shell|computer|browser|deployment")
    p.add_argument("--access", help="ConnectorActionScope accessLevel")
    p.add_argument("--subject", default=None)
    p.add_argument("--scope", default="user_local", choices=list(MEMBRANE_SCOPES))
    p.add_argument("--foreign", action="store_true", help="surface is NOT ours → observe-only")
    p.add_argument("--tension", default="", help="comma-separated present tension members")
    p.add_argument("--membrane", default="ALLOW", choices=list(MEMBRANE_DECISIONS),
                   help="membrane decision (ignored when --operation is given)")
    p.add_argument("--autonomy-level", default="L0")
    p.add_argument("--evidence", default="", help="comma-separated autonomy evidence tokens")
    p.add_argument("--out", type=str, help="write sealed receipt JSON here (default stdout)")
    args = p.parse_args(argv)

    # Runtime seam: gate a fully-described call and print the decision, fail-closed.
    if args.request:
        import sys as _sys
        raw = _sys.stdin.read() if args.request == "-" else open(args.request, encoding="utf-8").read()
        decision = gate(json.loads(raw))
        out = json.dumps(decision, indent=2, sort_keys=True)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(out + "\n")
        else:
            print(out)
        return 0 if decision["allowed"] else 3

    if not (args.surface and args.access):
        p.error("--surface and --access are required unless --request is given")

    tension = tuple(t for t in args.tension.split(",") if t)
    evidence = tuple(e for e in args.evidence.split(",") if e)

    if args.operation:
        decision = json.loads(open(args.operation, encoding="utf-8").read())
        request = request_from_operation_decision(
            decision, surface=args.surface, access_level=args.access,
            subject_ref=args.subject, scope=args.scope, owned=not args.foreign,
            tension_members=tension, requested_autonomy_level=args.autonomy_level,
            autonomy_evidence=evidence,
        )
    else:
        request = CapabilityRequest(
            surface=args.surface, action=f"{args.surface}.invoke", access_level=args.access,
            subject_ref=args.subject or "urn:srcos:subject:cli", scope=args.scope,
            owned=not args.foreign, tension_members=tension, membrane_decision=args.membrane,
            requested_autonomy_level=args.autonomy_level, autonomy_evidence=evidence,
        )

    resolution = resolve_capability(request)
    out = json.dumps(resolution.sealed, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    else:
        print(out)
    # Exit non-zero when the enforced decision is not an allow, so CI/guards can gate on it.
    return 0 if resolution.allowed else 3


__all__ = [
    "CapabilityRequest",
    "CapabilityResolution",
    "AutonomyDecision",
    "evaluate_autonomy",
    "resolve_capability",
    "gate",
    "request_from_operation_decision",
    "seal_receipt",
    "TENSION_REQUIRED",
    "AUTONOMY_LADDER",
    "MEMBRANE_DECISIONS",
]


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(_cli(_sys.argv[1:]))
