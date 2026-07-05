#!/usr/bin/env python3
"""Emit an AutonomyAdmissionReceipt at the channel-governed runtime gate.

This turns the AutonomyAdmissionReceipt contract from a static schema into a
live emitter on the evidence spine. At a channel-governed runtime gate (where
an L4 conductor-orchestrated solution wants a high-consequence sink), the
platform computes the autonomy admission decision from the canonical ladder
and emits a hashed, self-validated receipt.

Single source of truth: the ladder is the vendored canonical export from
SocioProphet/prophet-mesh (contracts/prophet-mesh/ai-driven-development.ladder.json),
NOT a hand-maintained map. Decision semantics mirror prophet_mesh.autonomy:
authorize by role ceiling, then admit by evidence, demoting toward L0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

# Self-validate before emit, using the contract validator that sits beside us.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_autonomy_admission_receipt import validate_receipt  # noqa: E402

# The capability-membrane kernel governs the admission when an operation context
# (surface/action) is supplied. Absent that, we stay the legacy autonomy-only
# gate and emit a v0.1 receipt.
from capability_membrane import CapabilityRequest, resolve_capability  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LADDER = ROOT / "contracts" / "prophet-mesh" / "ai-driven-development.ladder.json"
DEFAULT_OUTPUT_DIR = ROOT / "build" / "autonomy-admission"
TRUST_KERNEL_GATE_ORDER = ["identity", "policy", "evidence", "attestation", "revocation", "audit"]
_NO_EVIDENCE = {"none", ""}


# --------------------------------------------------------------------------- #
# Decision engine (data-driven from the canonical ladder)
# --------------------------------------------------------------------------- #
def _rank(level: str) -> int:
    try:
        return int(str(level).lstrip("Ll"))
    except (ValueError, TypeError):
        return -1


class Ladder:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.by_rank: dict[int, dict[str, Any]] = {}
        for lvl in doc.get("levels", []):
            r = lvl.get("rank", _rank(lvl.get("level", "")))
            self.by_rank[int(r)] = lvl
        if 0 not in self.by_rank:
            self.by_rank[0] = {"level": "L0", "roles": [], "gate": "none", "evidence_required": "none"}

    @classmethod
    def load(cls, path: Path) -> "Ladder":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def role_ceiling(self, role: str) -> int:
        ceiling = 0
        for rank, lvl in self.by_rank.items():
            if role in (lvl.get("roles") or []) and rank > ceiling:
                ceiling = rank
        return ceiling

    def _satisfied(self, rank: int, available: set[str]) -> bool:
        req = self.by_rank[rank].get("evidence_required", "none")
        return req in _NO_EVIDENCE or req in available

    def evaluate(self, role: str, requested_level: str, evidence: Iterable[str]) -> dict[str, Any]:
        available = set(evidence)
        requested = max(_rank(requested_level), 0)
        ceiling = self.role_ceiling(role)
        capped = min(requested, ceiling)
        reasons: list[str] = []
        if requested > ceiling:
            reasons.append(f"role '{role}' not authorized above L{ceiling}; capped from L{requested}")
        granted = 0
        for rank in range(capped, -1, -1):
            if rank not in self.by_rank:
                continue
            if self._satisfied(rank, available):
                granted = rank
                break
            lvl = self.by_rank[rank]
            reasons.append(
                f"L{rank} gate '{lvl.get('gate')}' needs evidence "
                f"'{lvl.get('evidence_required')}' (absent) -> demote"
            )
        g = self.by_rank[granted]
        decision = "admit" if granted == requested else "deny" if granted == 0 and requested > 0 else "demote"
        if decision == "admit" and not reasons:
            reasons.append(f"granted at requested level L{granted}")
        return {
            "role": role,
            "requested_level": f"L{requested}",
            "granted_level": f"L{granted}",
            "role_ceiling": f"L{ceiling}",
            "decision": decision,
            "gate": g.get("gate", "none"),
            "evidence_required": g.get("evidence_required", "none"),
            "reason": "; ".join(reasons),
        }


# --------------------------------------------------------------------------- #
# Receipt assembly + emit
# --------------------------------------------------------------------------- #
def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_receipt(
    decision: dict[str, Any],
    *,
    subject_ref: str,
    receipt_id: str,
    created_at: str,
    evidence_refs: list[str],
    envelope_ref: str | None = None,
    policy_refs: list[str] | None = None,
    membrane: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "version": "0.2" if membrane else "0.1",
        "receipt_id": receipt_id,
        "created_at": created_at,
        "service_ref": "svc.platform.autonomy-admission",
        "role": decision["role"],
        "requested_level": decision["requested_level"],
        "granted_level": decision["granted_level"],
        "role_ceiling": decision["role_ceiling"],
        "decision": decision["decision"],
        "gate": decision["gate"],
        "evidence_required": decision["evidence_required"],
        "evidence_refs": list(evidence_refs),
        "reason": decision["reason"],
        "trust_kernel_gate_order": list(TRUST_KERNEL_GATE_ORDER),
        "subject_ref": subject_ref,
    }
    if envelope_ref:
        receipt["envelope_ref"] = envelope_ref
    if policy_refs:
        receipt["policy_refs"] = list(policy_refs)
    if membrane:
        receipt["membrane"] = membrane
    receipt["hash_algo"] = "sha256"
    receipt["hash"] = "sha256:" + hashlib.sha256(_canonical_bytes(receipt)).hexdigest()
    return receipt


def _from_channel_gate(path: Path) -> dict[str, Any]:
    """Pull binding context from a channel-governed runtime-gate record."""
    gate = json.loads(path.read_text(encoding="utf-8"))
    return {
        "subject_ref": gate.get("operation_ref", ""),
        "envelope_ref": gate.get("gate_id"),
        "evidence_refs": list(gate.get("evidence_refs", []) or []),
        "policy_refs": list(gate.get("policy_decision_refs", []) or []),
        # Operation context for the capability membrane (all optional).
        "surface": gate.get("surface"),
        "action": gate.get("action"),
        "access_level": gate.get("access_level"),
        "tension_members": list(gate.get("tension_members", []) or []),
        "membrane_decision": gate.get("membrane_decision"),
        "scope": gate.get("scope"),
    }


def _gate_capability(
    *,
    surface: str,
    action: str,
    access_level: str,
    subject_ref: str,
    scope: str,
    owned: bool,
    tension_members: list[str],
    requested_level: str,
    evidence: set[str],
    membrane_decision: str,
    policy_refs: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the capability-membrane kernel over the operation this admission is for.

    Returns (membrane_block, sealed_agent_machine_receipt). The membrane's
    collapsed ExecutionDecision is the fail-closed outer gate: a non-allow value
    denies the admission regardless of what the autonomy ladder alone would grant.
    """
    request = CapabilityRequest(
        surface=surface,
        action=action,
        access_level=access_level,
        subject_ref=subject_ref or "urn:srcos:subject:unspecified",
        scope=scope,
        owned=owned,
        tension_members=tuple(tension_members),
        requested_autonomy_level=requested_level,
        autonomy_evidence=tuple(sorted(evidence)),
        membrane_decision=membrane_decision,
        policy_refs=tuple(policy_refs),
    )
    res = resolve_capability(request)
    membrane_block = {
        "execution_decision": res.execution_decision,
        "verdict": res.verdict,
        "capability_radius": res.radius,
        "missing_tension": list(res.missing_tension),
        "membrane_decision": res.membrane_decision,
        "enforced": res.enforced,
        "seal_hash": res.sealed["sealHash"],
        "agent_machine_receipt_ref": res.sealed["id"],
    }
    return membrane_block, res.sealed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Emit an AutonomyAdmissionReceipt at a channel-governed gate.")
    parser.add_argument("--role", required=True)
    parser.add_argument("--level", required=True, help="requested autonomy level, e.g. L4")
    parser.add_argument("--evidence", default="", help="comma-separated evidence tokens present")
    parser.add_argument("--evidence-refs", default="", help="comma-separated evidence artifact refs")
    parser.add_argument("--subject-ref", default="", help="subject (overridden by --channel-gate operation_ref)")
    parser.add_argument("--channel-gate", help="bind to a channel-governed runtime-gate record")
    parser.add_argument("--ladder", default=str(DEFAULT_LADDER))
    parser.add_argument("--receipt-id", default=None)
    parser.add_argument("--out", help="output path (default build/autonomy-admission/<receipt_id>.json)")
    # Operation context — supplying a surface engages the capability-membrane
    # kernel as the fail-closed outer gate and emits a v0.2 receipt.
    parser.add_argument("--surface", help="operation surface (e.g. shell|computer|browser); engages the membrane")
    parser.add_argument("--action", help="dotted action, e.g. shell.exec")
    parser.add_argument("--access-level", default="scopedRead", help="ConnectorActionScope accessLevel")
    parser.add_argument("--tension-members", default="", help="comma-separated present governance members")
    parser.add_argument("--membrane-decision", default="ALLOW", help="upstream membrane verdict")
    parser.add_argument("--scope", default="user_local", help="user_local | global_platform")
    parser.add_argument("--unowned", action="store_true", help="surface we do not own → observe-only")
    args = parser.parse_args(argv[1:])

    ladder = Ladder.load(Path(args.ladder))
    evidence = {t.strip() for t in args.evidence.split(",") if t.strip()}
    decision = ladder.evaluate(args.role, args.level, evidence)

    evidence_refs = [r.strip() for r in args.evidence_refs.split(",") if r.strip()]
    subject_ref = args.subject_ref
    envelope_ref = None
    policy_refs: list[str] = []
    ctx: dict[str, Any] = {}
    if args.channel_gate:
        ctx = _from_channel_gate(Path(args.channel_gate))
        subject_ref = subject_ref or ctx["subject_ref"]
        envelope_ref = ctx["envelope_ref"]
        evidence_refs = list(dict.fromkeys(evidence_refs + ctx["evidence_refs"]))
        policy_refs = ctx["policy_refs"]
    policy_refs = list(dict.fromkeys(policy_refs + ["prophet-mesh:specs/ai-driven-development.yaml"]))

    if not subject_ref:
        print("ERROR: subject_ref required (pass --subject-ref or --channel-gate)", file=sys.stderr)
        return 2

    # If an operation surface is supplied (CLI or channel gate), the capability
    # membrane governs the admission as a fail-closed outer gate.
    membrane_block: dict[str, Any] | None = None
    sealed: dict[str, Any] | None = None
    surface = args.surface or ctx.get("surface")
    if surface:
        tension = [t.strip() for t in args.tension_members.split(",") if t.strip()] or list(ctx.get("tension_members") or [])
        membrane_block, sealed = _gate_capability(
            surface=surface,
            action=args.action or ctx.get("action") or f"{surface}.invoke",
            access_level=args.access_level or ctx.get("access_level") or "scopedRead",
            subject_ref=subject_ref,
            scope=args.scope or ctx.get("scope") or "user_local",
            owned=not args.unowned,
            tension_members=tension,
            requested_level=decision["requested_level"],
            evidence=evidence,
            membrane_decision=args.membrane_decision or ctx.get("membrane_decision") or "ALLOW",
            policy_refs=list(policy_refs),
        )
        # Fail-closed composition: a non-allow membrane denies the admission at L0,
        # overriding whatever the autonomy ladder alone would have granted.
        if membrane_block["execution_decision"] != "allow":
            note = f"capability membrane {membrane_block['execution_decision']} (radius {membrane_block['capability_radius']}"
            if membrane_block["missing_tension"]:
                note += f", missing tension {membrane_block['missing_tension']}"
            note += ")"
            decision = dict(decision)
            decision["granted_level"] = "L0"
            decision["decision"] = "deny"
            decision["reason"] = "; ".join(x for x in (decision.get("reason", ""), note) if x)

    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    receipt_id = args.receipt_id or f"aar-{int(time.time())}"
    receipt = build_receipt(
        decision,
        subject_ref=subject_ref,
        receipt_id=receipt_id,
        created_at=created_at,
        evidence_refs=evidence_refs,
        envelope_ref=envelope_ref,
        policy_refs=policy_refs,
        membrane=membrane_block,
    )

    # Fail-closed: never emit a receipt that does not validate against the contract.
    try:
        validate_receipt(receipt)
    except Exception as exc:  # ValidationError
        print(f"ERROR: emitted receipt failed self-validation: {exc}", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else DEFAULT_OUTPUT_DIR / f"{receipt_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Emit the sealed AgentMachineReceipt alongside so the membrane decision is
    # independently verifiable (its sealHash is bound into the receipt above).
    sealed_out = None
    if sealed is not None:
        sealed_out = out.parent / f"{out.stem}.agent-machine-receipt.json"
        sealed_out.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "ok": True,
        "out": str(out),
        "decision": decision["decision"],
        "granted_level": decision["granted_level"],
        "hash": receipt["hash"],
    }
    if membrane_block is not None:
        summary["membrane_execution_decision"] = membrane_block["execution_decision"]
        summary["sealed_receipt"] = str(sealed_out)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
