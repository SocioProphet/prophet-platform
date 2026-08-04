#!/usr/bin/env python3
"""Firewall #2 — the control-of-controls (the meta-meta layer).

Firewall #1 (`adr_dependency_graph`) is the per-decision control: it catches the L0 failure once an
ADR *has* built its graph + waves. But that is exactly the trap the estate already fell into — the
control was *optional*, so its absence was invisible (the L2 meta-meta-failure). Firewall #2 closes
that: it audits EVERY ADR and fails closed on any that lacks its Firewall #1, and it measures the
**second derivative** — whether unguarded decisions are *accelerating away* from their controls, i.e.
whether the estate is minting decisions faster than it is generating their safety.

To stop the regress (who guards Firewall #2?), it is a **fixpoint**: it must appear in its own guarded
set (`self_governed`). A control-of-controls that governs itself needs no third firewall — two suffice.
Fail-closed, sealed, stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

# what a fully-guarded ADR must carry (its Firewall #1 apparatus).
FIREWALL1_REQUIREMENTS = ("dependency_graph", "wave1_prevent", "wave2_heal", "enforcement")
SENTINEL_ID = "adr_conformance_sentinel"


def _seal(body: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_adr(adr_id: str, apparatus: dict) -> dict:
    """Does this ADR have its Firewall #1? `apparatus` records which pieces are present+true."""
    missing = [r for r in FIREWALL1_REQUIREMENTS if not (apparatus or {}).get(r)]
    return {"adr_id": adr_id, "guarded": not missing, "missing": missing}


def audit_registry(adr_registry: list) -> dict:
    """Fail-closed audit over all ADRs. `adr_registry` = [{adr_id, apparatus}]. Any ADR missing a
    Firewall #1 requirement is an L2 violation — the estate is carrying an ungoverned decision."""
    audits = [audit_adr(a.get("adr_id", "?"), a.get("apparatus", {})) for a in adr_registry]
    unguarded = [x for x in audits if not x["guarded"]]
    total = len(audits) or 1
    return {"total": len(audits), "guarded": len(audits) - len(unguarded),
            "coverage": round((len(audits) - len(unguarded)) / total, 4),
            "unguarded": unguarded}


def second_derivative(series: list) -> dict:
    """The meta-meta signal. `series` = time-ordered [{decisions, controls}]. Let unguarded = decisions
    - controls (the gap). The first derivative is how fast the gap moves; the SECOND derivative is
    whether it is accelerating. d2 > 0 => coverage is losing ground faster over time — the alarm."""
    gap = [max(0, p.get("decisions", 0) - p.get("controls", 0)) for p in series]
    if len(gap) < 3:
        return {"points": len(gap), "d1": None, "d2": None, "trend": "insufficient-history"}
    d1 = [gap[i + 1] - gap[i] for i in range(len(gap) - 1)]
    d2 = d1[-1] - d1[-2]
    trend = ("accelerating" if d2 > 0 else "decelerating" if d2 < 0
             else "closing" if d1[-1] < 0 else "steady")
    return {"points": len(gap), "gap_now": gap[-1], "d1": d1[-1], "d2": d2, "trend": trend}


def self_governed(control_registry: list) -> bool:
    """The fixpoint: the sentinel must be a guarded control in its OWN registry. If it exempts itself,
    the control-of-controls is ungoverned and the whole tower is hollow."""
    for c in control_registry or []:
        if c.get("control") == SENTINEL_ID:
            return bool(c.get("guarded"))
    return False


def run(adr_registry: list, series: list = None, control_registry: list = None) -> dict:
    """Full meta-meta pass. Fail-closed: NOT ok if any ADR is unguarded OR the sentinel does not
    govern itself. The accelerating-gap trend is a raised alarm even when nothing is strictly missing."""
    reg = audit_registry(adr_registry)
    deriv = second_derivative(series or [])
    selfgov = self_governed(control_registry or [])
    decision = {
        "firewall": 2, "control": SENTINEL_ID, "audited_at": _now(),
        "coverage": reg["coverage"], "unguarded": reg["unguarded"],
        "second_derivative": deriv, "self_governed": selfgov,
        "ok": (not reg["unguarded"]) and selfgov,
        "alarm": ("meta-meta: unguarded ADRs exist" if reg["unguarded"]
                  else "meta-meta: sentinel not self-governed" if not selfgov
                  else "meta-meta: unguarded-decision gap is ACCELERATING" if deriv.get("trend") == "accelerating"
                  else None),
    }
    decision["receipt_digest"] = _seal({k: v for k, v in decision.items() if k != "receipt_digest"})
    return decision


if __name__ == "__main__":
    # the estate AS-IS: the Nix→Guix ADR has no Firewall #1 yet (this PR adds it), and the sentinel
    # is not yet in the control registry — both L2 failures, correctly caught.
    as_is = run(
        adr_registry=[{"adr_id": "ADR-0001-nix-to-guix", "apparatus": {}}],
        series=[{"decisions": 3, "controls": 3}, {"decisions": 6, "controls": 4},
                {"decisions": 11, "controls": 5}],  # gap 0→2→6: accelerating
        control_registry=[])  # sentinel absent from its own registry
    to_be = run(
        adr_registry=[{"adr_id": "ADR-0001-nix-to-guix",
                       "apparatus": {k: True for k in FIREWALL1_REQUIREMENTS}}],
        series=[{"decisions": 11, "controls": 9}, {"decisions": 12, "controls": 11},
                {"decisions": 13, "controls": 13}],  # gap 2→1→0: closing
        control_registry=[{"control": "adr_conformance_sentinel", "guarded": True}])
    print(json.dumps({"AS_IS": {"ok": as_is["ok"], "alarm": as_is["alarm"],
                                "unguarded": [u["adr_id"] for u in as_is["unguarded"]],
                                "trend": as_is["second_derivative"]["trend"]},
                      "TO_BE": {"ok": to_be["ok"], "alarm": to_be["alarm"],
                                "trend": to_be["second_derivative"]["trend"]}}, indent=2))
