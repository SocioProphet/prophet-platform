#!/usr/bin/env python3
"""CheckCoverSufficiency — runtime tier-aware evidence sufficiency gate.

Implements evidence_cover_registry_spec_v0_1 §CheckCoverSufficiency:

  Given a fully-validated EvidenceCoverGraph for claim_id and an evaluation
  tier T_eval, select covers whose tier is <= T_eval in the tier_policy
  tier_order. If at least one cover passes, the evidence is SUFFICIENT for
  that claim at that tier. If none pass, the verdict is INCONCLUSIVE and a
  content-addressed RepairRequest is emitted describing what upgrade is needed.

  Admissibility floor enforcement: if tier_policy.admissibility_floor_by_claim_class
  specifies a floor tier for the graph's claim class that is STRICTER than T_eval
  (i.e. the floor tier comes later in tier_order than T_eval), the check returns
  INCONCLUSIVE with an upgrade_tier RepairRequest before even inspecting covers.

Verdicts:
  SUFFICIENT   — at least one cover is admissible at T_eval
  INCONCLUSIVE — no admissible cover (need_additional_evidence) or T_eval is
                 below the admissibility floor for this claim class (upgrade_tier)

RepairRequest determinism: the request is content-addressed via SHA-256 of its
canonical JSON (sorted keys, tight separators). Identical inputs MUST produce the
same digest — enforced in the test suite.

Usage:
  python tools/check_cover_sufficiency.py \\
      contracts/evidence/cover/cover-graph.valid.example.json \\
      --tier T2

Exit codes: 0 = SUFFICIENT, 1 = INCONCLUSIVE (repair request printed to stdout).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Canonicalization (project profile — see validate_evidence_cover_graph.py)
# ---------------------------------------------------------------------------

def _canon(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# Tier helpers
# ---------------------------------------------------------------------------

def _tier_index(tier_order: list[str], tier: str) -> int:
    """Return the index of tier in tier_order (lower index = more permissive)."""
    try:
        return tier_order.index(tier)
    except ValueError:
        raise ValueError(f"tier '{tier}' is not in tier_policy.tier_order {tier_order}")


def _admissible_covers(graph: dict, t_eval: str) -> list[dict]:
    """Return covers whose tier is admissible (index <= T_eval index) in tier_order."""
    tier_order: list[str] = graph.get("tier_policy", {}).get("tier_order", [])
    if not tier_order:
        # No tier policy — all covers are admissible (open world).
        return list(graph.get("covers", []))
    t_eval_idx = _tier_index(tier_order, t_eval)
    result = []
    for cover in graph.get("covers", []):
        try:
            if _tier_index(tier_order, cover["tier"]) <= t_eval_idx:
                result.append(cover)
        except ValueError:
            pass  # cover has an unknown tier — not admissible
    return result


# ---------------------------------------------------------------------------
# RepairRequest builders (content-addressed)
# ---------------------------------------------------------------------------

def _repair_need_additional(graph: dict, t_eval: str, tier_order: list[str]) -> dict:
    present_tiers = sorted({c["tier"] for c in graph.get("covers", [])})
    # The coarsest admissible tier the caller could add to become SUFFICIENT.
    return {
        "repair_request_version": 1,
        "claim_id": graph["claim_id"],
        "reason": "cover_sufficiency_gap",
        "requested_actions": [
            {
                "action": "need_additional_evidence",
                "details": {
                    "t_eval": t_eval,
                    "tier_order": tier_order,
                    "covers_present_at_tiers": present_tiers,
                    "required": "at least one cover with tier admissible at T_eval",
                },
            }
        ],
    }


def _repair_upgrade_tier(graph: dict, t_eval: str, floor_tier: str, tier_order: list[str]) -> dict:
    return {
        "repair_request_version": 1,
        "claim_id": graph["claim_id"],
        "reason": "admissibility_floor_not_met",
        "requested_actions": [
            {
                "action": "upgrade_tier",
                "details": {
                    "t_eval": t_eval,
                    "admissibility_floor": floor_tier,
                    "tier_order": tier_order,
                    "instruction": (
                        f"Evaluation at tier '{t_eval}' is not admissible for this "
                        f"claim class; must evaluate at '{floor_tier}' or stricter."
                    ),
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_cover_sufficiency(
    graph: dict,
    t_eval: str,
    claim_class: str | None = None,
) -> tuple[str, dict | None]:
    """CheckCoverSufficiency(graph, T_eval) -> (verdict, repair_request | None).

    verdict in {"SUFFICIENT", "INCONCLUSIVE"}.

    Args:
        graph:        A structurally-valid EvidenceCoverGraph dict.
        t_eval:       The evaluation tier string (must be in tier_policy.tier_order).
        claim_class:  Optional claim class string. When supplied and tier_policy
                      contains an admissibility_floor_by_claim_class entry, the
                      floor is enforced before inspecting covers.
    """
    tier_order: list[str] = graph.get("tier_policy", {}).get("tier_order", [])

    # 1. Admissibility-floor enforcement.
    if tier_order and claim_class:
        floors: dict[str, str] = (
            graph.get("tier_policy", {}).get("admissibility_floor_by_claim_class", {})
        )
        floor_tier = floors.get(claim_class)
        if floor_tier and floor_tier in tier_order:
            t_eval_idx = _tier_index(tier_order, t_eval)
            floor_idx = _tier_index(tier_order, floor_tier)
            if floor_idx < t_eval_idx:
                # Floor is stricter than T_eval — cannot satisfy at this tier.
                repair = _repair_upgrade_tier(graph, t_eval, floor_tier, tier_order)
                return "INCONCLUSIVE", repair

    # 2. Cover selection.
    admissible = _admissible_covers(graph, t_eval)
    if admissible:
        return "SUFFICIENT", None

    # 3. No admissible cover — emit need_additional_evidence.
    repair = _repair_need_additional(graph, t_eval, tier_order)
    return "INCONCLUSIVE", repair


def repair_digest(repair: dict) -> str:
    """Content-address a RepairRequest (determinism law)."""
    return _sha256(_canon(repair))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("graph_path", type=Path, help="Path to EvidenceCoverGraph JSON file.")
    parser.add_argument("--tier", required=True, help="Evaluation tier (T_eval).")
    parser.add_argument("--claim-class", default=None, help="Claim class (for admissibility floor).")
    parser.add_argument("--fixture-dir", type=Path, default=None,
                        help="Run all fixtures in directory (CI mode).")
    args = parser.parse_args(argv)

    if args.fixture_dir:
        return _run_fixtures(args.fixture_dir, args.tier, args.claim_class)

    graph = json.loads(args.graph_path.read_text())
    verdict, repair = check_cover_sufficiency(graph, args.tier, args.claim_class)
    print(json.dumps({"verdict": verdict, "repair_request": repair}, indent=2))
    return 0 if verdict == "SUFFICIENT" else 1


def _run_fixtures(fixture_dir: Path, t_eval: str, claim_class: str | None) -> int:
    """Validate all check_cover_sufficiency_*.json fixtures in fixture_dir."""
    paths = sorted(fixture_dir.glob("check_cover_sufficiency_*.json"))
    if not paths:
        print(f"ERR: no check_cover_sufficiency_*.json fixtures in {fixture_dir}", file=sys.stderr)
        return 1

    passed = 0
    failed = 0
    for p in paths:
        fixture = json.loads(p.read_text())
        graph = fixture["graph"]
        ft_eval = fixture.get("t_eval", t_eval)
        fcc = fixture.get("claim_class", claim_class)
        expected = fixture["expected_verdict"]

        verdict, repair = check_cover_sufficiency(graph, ft_eval, fcc)
        if verdict != expected:
            print(f"FAIL {p.name}: expected {expected} got {verdict}", file=sys.stderr)
            failed += 1
            continue

        if verdict == "INCONCLUSIVE":
            if repair is None:
                print(f"FAIL {p.name}: INCONCLUSIVE verdict must carry a repair request", file=sys.stderr)
                failed += 1
                continue
            # Determinism law: re-running must yield the same digest.
            d1 = repair_digest(repair)
            _, repair2 = check_cover_sufficiency(graph, ft_eval, fcc)
            d2 = repair_digest(repair2)
            if d1 != d2:
                print(f"FAIL {p.name}: repair request is non-deterministic", file=sys.stderr)
                failed += 1
                continue

        print(f"PASS {p.name} verdict={verdict}")
        passed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
