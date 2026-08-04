#!/usr/bin/env python3
"""Sample swarm dispatch through the holography gate — the register's probe made real.

The register entry `swarm-holography-gate` says the bar is "gate decision observable on a
sample swarm dispatch." This is that dispatch: a Tier-2 swarm agent asks for a projection
of a subject's fields; the gate decides per field; the decision is printed (observable) and
its holographic-completeness invariant is asserted. Also the first caller of the gate
library, so the capability is `wired`, not a library nobody imports.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Import the gate library from the monorepo (no install needed for the smoke).
_LIB = Path(__file__).resolve().parents[1] / "libs" / "python" / "holography-gate" / "src"
sys.path.insert(0, str(_LIB))

from holography_gate import Policy, holographic_project, disclosed, denials, Permit  # noqa: E402


def sample_dispatch() -> dict:
    """A swarm agent projecting a person-twin for a marketing intent: name/email are
    disclosable, but HEALTH∧ADS is a hard prohibition and location needs earned trust."""
    policy = Policy(
        hard_prohibitions=frozenset({"health_status", "ad_targeting"}),
        soft_costs={"email": 0.4, "location": 0.9},
        soft_budget=1.0,
        required_readiness={"email": "TRUSTED", "location": "LINKED"},
    )
    fields = ["name", "email", "health_status", "ad_targeting", "location"]
    decision = holographic_project(
        fields,
        trust=0.6,   # a mid-trust agent
        readiness={"name": "DELIVERED", "email": "TRUSTED", "location": "SEEDED"},
        policy=policy,
    )
    # INV-26: the decision's domain is the WHOLE field set — never a photograph crop.
    assert set(decision.keys()) == set(fields), "holographic completeness violated"
    return {
        "dispatch": "swarm-agent:tier2 → project(person-twin, scope=marketing)",
        "disclosed": sorted(disclosed(decision)),
        "withheld": {
            f: {"reason": d.reason, "policy_ref": d.policy_ref, "class": d.cls, "earnable": d.earnable}
            for f, d in denials(decision).items()
        },
        "completeness": {
            "domain_size": len(decision),
            "field_count": len(fields),
            "holographically_complete": set(decision.keys()) == set(fields),
        },
    }


def main() -> int:
    out = sample_dispatch()
    print(json.dumps(out, indent=2))
    # A well-formed, observable gate decision on a sample swarm dispatch.
    ok = out["completeness"]["holographically_complete"] and "name" in out["disclosed"] and "health_status" in out["withheld"]
    print(("OK" if ok else "FAIL") + " swarm-holography-gate: decision observable on a sample dispatch")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
