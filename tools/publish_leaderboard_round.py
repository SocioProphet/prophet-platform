"""publish-leaderboard-round — the public ranked/tiered leaderboard round surface.

Turns a set of validated submissions into a versioned, ranked-or-tiered
leaderboard round FOR ONE DIVISION (MLPerf-parity versioned rounds; #1263
feature 4, follow-up #1272), driven by:

  * schemas/eval/leaderboard-round.schema.json — the round contract;
  * tools/validate_submission.py + schemas/eval/division-rules.json (#1271) —
    the SINGLE division-validity verdict. This module does NOT re-implement any
    gate; it runs validate_submission over every entry's embedded submission.

TEETH — a round is PUBLISHABLE iff, for its division:
  1. every entry's submission is in the round's division;
  2. every entry's submission passes validate_submission (all required gates);
  3. every entry's headline metric IS the ranking_rule metric;
  4. any declared `rank` matches the rank computed from ranking_rule
     (a declared rank that lies is REJECTED).
An OPEN round is published but flagged non-comparable; a declared `comparable`
that disagrees with the division is REJECTED.

Usage:
    python tools/publish_leaderboard_round.py <round.json>
    # exit 0 = PUBLISHED (prints the ranked round), 1 = REJECTED, 2 = malformed
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "eval"


def _load_validator():
    """Load tools/validate_submission.py as a module — the single division verdict (#1271)."""
    path = ROOT / "tools" / "validate_submission.py"
    spec = importlib.util.spec_from_file_location("validate_submission", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class EntryVerdict:
    entry_id: str
    candidate_id: str
    value: float
    computed_rank: int | None
    valid: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "candidate_id": self.candidate_id,
            "headline_value": self.value,
            "rank": self.computed_rank,
            "valid": self.valid,
            "reasons": self.reasons,
        }


@dataclass
class RoundVerdict:
    round_id: str
    version: str
    division: str
    comparable: bool
    publishable: bool
    ranking_rule: dict[str, Any]
    entries: list[EntryVerdict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id,
            "version": self.version,
            "division": self.division,
            "comparable": self.comparable,
            "publishable": self.publishable,
            "ranking_rule": self.ranking_rule,
            "ranked_entries": [e.to_dict() for e in sorted(
                self.entries, key=lambda e: (e.computed_rank is None, e.computed_rank or 0))],
            "reasons": self.reasons,
        }


def _rank_entries(entries: list[dict], direction: str) -> dict[str, int]:
    """Assign 1..N ranks over headline value per direction (ties share the higher rank)."""
    reverse = direction == "higher_is_better"
    ordered = sorted(entries, key=lambda e: e["headline"]["value"], reverse=reverse)
    ranks: dict[str, int] = {}
    last_value = None
    last_rank = 0
    for i, e in enumerate(ordered, start=1):
        v = e["headline"]["value"]
        if last_value is not None and v == last_value:
            ranks[e["entry_id"]] = last_rank  # tie -> same rank
        else:
            ranks[e["entry_id"]] = i
            last_rank = i
            last_value = v
    return ranks


def publish_round(rnd: dict, rules: dict | None = None, validator=None) -> RoundVerdict:
    """Compute the round verdict. PUBLISHABLE iff every entry is valid for the division."""
    validator = validator or _load_validator()
    rules = rules or validator.load_division_rules()

    division = rnd.get("division")
    div_spec = (rules.get("divisions") or {}).get(division)
    if div_spec is None:
        raise ValueError(f"unknown division {division!r} (expected one of {list((rules.get('divisions') or {}))})")
    div_comparable = bool(div_spec.get("comparable", False))

    ranking_rule = rnd.get("ranking_rule") or {}
    metric_id = ranking_rule.get("metric_id")
    direction = ranking_rule.get("direction")

    verdict = RoundVerdict(
        round_id=rnd.get("round_id", "?"), version=rnd.get("version", "?"),
        division=division, comparable=div_comparable, publishable=False,
        ranking_rule=ranking_rule,
    )

    # round-level: a declared comparability must match the division's truth
    if "comparable" in rnd and bool(rnd["comparable"]) != div_comparable:
        verdict.reasons.append(
            f"declared comparable={rnd['comparable']} contradicts division {division} (comparable={div_comparable})")
    if not metric_id or direction not in ("higher_is_better", "lower_is_better"):
        verdict.reasons.append("ranking_rule requires a metric_id and a valid direction")

    entries = rnd.get("entries") or []
    if not entries:
        verdict.reasons.append("a round must have at least one entry")

    computed = _rank_entries(entries, direction) if (entries and direction and metric_id) else {}

    for e in entries:
        eid = e.get("entry_id", "?")
        reasons: list[str] = []
        headline = e.get("headline") or {}
        value = headline.get("value")

        # entry must be in the round's division
        sub = e.get("submission") or {}
        if sub.get("division") != division:
            reasons.append(f"entry submission division {sub.get('division')!r} != round division {division!r}")

        # headline metric must be the ranking metric
        if metric_id and headline.get("metric_id") != metric_id:
            reasons.append(f"headline metric {headline.get('metric_id')!r} != ranking metric {metric_id!r}")

        # the single division verdict (#1271) — no gate re-implemented here
        try:
            sub_verdict = validator.validate_submission(sub, rules=rules)
            if not sub_verdict.valid:
                reasons.append(f"submission failed required gates: {sub_verdict.failed_gates()}")
        except ValueError as exc:
            reasons.append(f"submission invalid: {exc}")

        # a declared rank that lies is rejected
        crank = computed.get(eid)
        if "rank" in e and crank is not None and e["rank"] != crank:
            reasons.append(f"declared rank {e['rank']} != computed rank {crank}")

        verdict.entries.append(EntryVerdict(
            entry_id=eid, candidate_id=e.get("candidate_id", "?"),
            value=value if isinstance(value, (int, float)) else float("nan"),
            computed_rank=crank, valid=not reasons, reasons=reasons,
        ))

    verdict.publishable = not verdict.reasons and all(en.valid for en in verdict.entries)
    return verdict


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="publish a ranked/tiered leaderboard round for a division")
    ap.add_argument("round", type=Path, help="path to a leaderboard-round JSON")
    args = ap.parse_args(argv)
    try:
        rnd = json.loads(args.round.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"malformed round: {exc}", file=sys.stderr)
        return 2
    try:
        verdict = publish_round(rnd)
    except ValueError as exc:
        print(f"invalid round: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(verdict.to_dict(), indent=2))
    status = "PUBLISHED" if verdict.publishable else "REJECTED"
    tail = "" if verdict.publishable else (
        " — " + "; ".join(verdict.reasons + [f"{e.entry_id}: {e.reasons}" for e in verdict.entries if not e.valid]))
    comp = "comparable" if verdict.comparable else "NON-COMPARABLE (OPEN)"
    print(f"\n{status}: {verdict.round_id}@{verdict.version} [{verdict.division}, {comp}]{tail}", file=sys.stderr)
    return 0 if verdict.publishable else 1


if __name__ == "__main__":
    raise SystemExit(main())
