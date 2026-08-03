#!/usr/bin/env python3
"""validate_intelligence_superiority_board — the contract-with-teeth for the estate's
Intelligence-Superiority feature-board (schemas/eval/intelligence-superiority-board.schema.json).

"We can't beat what we haven't benchmarked." The board is a governed competitive-intelligence
dataset: per capability category it declares competitors, the litmus features that decide the
category, and a scored estate-vs-each verdict (BEAT|MEET|PARTIAL|GAP). This validator refuses to
let an unsupported superiority claim ship, then SEALS the board with a SHA-256 receipt so the
cockpit renders exactly the bytes that passed.

TEETH (each is proven both ways in tests/platform_stubs/test_intelligence_superiority_board.py):
  1. A category with NO litmus_features is REJECTED — you cannot score a category you never defined.
  2. A BEAT or MEET verdict with NO evidence_ref is REJECTED — a lead without evidence is a boast.
  3. A score marked externally_certified with NO cert_ref is REJECTED — certification needs a cert.
  4. A score whose feature_id is not a declared litmus_feature, or whose competitor is not in the
     category's competitors[], is REJECTED — no orphan scores.
  5. MIN-N / PROVISIONAL: a BEAT/MEET claim that is thin — maturity=='spec' OR fewer than
     MIN_EVIDENCE_REFS evidence pointers — MUST carry provisional=true, else it is REJECTED. This
     is what keeps "capable, not yet released (a choice)" honestly separated from "battle-tested".

Pure-stdlib and deterministic so it runs as a GitHub-hosted CI gate with no third-party deps; the
JSON-Schema shape check is layered on top by the test suite (jsonschema) and is not required here.

Usage:
    python tools/validate_intelligence_superiority_board.py <board.json> [--seal OUT.receipt.json]
    # exit 0 = VALID (sealed if --seal), exit 1 = REJECTED, exit 2 = malformed input
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# A BEAT/MEET claim backed by a single pointer is "thin" and must be flagged provisional.
MIN_EVIDENCE_REFS = 2
VALID_VERDICTS = {"BEAT", "MEET", "PARTIAL", "GAP"}
LEAD_VERDICTS = {"BEAT", "MEET"}


@dataclass
class Verdict:
    valid: bool
    rejections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tally: dict[str, Any] = field(default_factory=dict)

    def reject(self, msg: str) -> None:
        self.valid = False
        self.rejections.append(msg)


def _evidence_ref(score: dict) -> list:
    ev = score.get("evidence_ref") or []
    return ev if isinstance(ev, list) else []


def validate_board(board: dict) -> Verdict:
    v = Verdict(valid=True)

    for key in ("board_id", "title", "generated_ts", "spec_version", "categories"):
        if key not in board:
            v.reject(f"board is missing required field '{key}'")
    categories = board.get("categories")
    if not isinstance(categories, list) or not categories:
        v.reject("board has no categories")
        return v

    verdict_counts: dict[str, int] = {k: 0 for k in VALID_VERDICTS}
    per_category: dict[str, dict[str, int]] = {}
    n_scores = 0
    n_provisional = 0

    for ci, cat in enumerate(categories):
        cid = cat.get("category_id", f"<index {ci}>")
        loc = f"category '{cid}'"

        features = cat.get("litmus_features") or []
        # TOOTH 1: no litmus features → cannot score the category.
        if not isinstance(features, list) or not features:
            v.reject(f"{loc}: no litmus_features defined (a category with no litmus test is REJECTED)")
            continue
        feature_ids = {f.get("feature_id") for f in features if isinstance(f, dict)}
        for f in features:
            if not (f.get("definition") and f.get("criteria")):
                v.reject(f"{loc}: litmus_feature '{f.get('feature_id')}' missing definition or criteria")

        competitors = set(cat.get("competitors") or [])
        if not competitors:
            v.reject(f"{loc}: no competitors declared")

        cat_counts = {k: 0 for k in VALID_VERDICTS}
        for score in cat.get("scores") or []:
            n_scores += 1
            fid = score.get("feature_id")
            comp = score.get("competitor")
            verdict = score.get("verdict")
            sloc = f"{loc} score [{fid} vs {comp}]"

            if verdict not in VALID_VERDICTS:
                v.reject(f"{sloc}: invalid verdict {verdict!r}")
                continue
            verdict_counts[verdict] += 1
            cat_counts[verdict] += 1

            # TOOTH 4: orphan scores.
            if fid not in feature_ids:
                v.reject(f"{sloc}: feature_id {fid!r} is not a declared litmus_feature")
            if comp not in competitors:
                v.reject(f"{sloc}: competitor {comp!r} is not in the category competitors[]")

            evidence = _evidence_ref(score)
            basis = score.get("assessment_basis")
            maturity = score.get("maturity")
            provisional = bool(score.get("provisional"))
            if provisional:
                n_provisional += 1

            # TOOTH 3: externally_certified needs a cert_ref.
            if basis == "externally_certified" and not score.get("cert_ref"):
                v.reject(f"{sloc}: assessment_basis=externally_certified but no cert_ref")

            if verdict in LEAD_VERDICTS:
                # TOOTH 2: a BEAT/MEET lead with no evidence is a boast.
                if not evidence:
                    v.reject(f"{sloc}: {verdict} claim has no evidence_ref")
                else:
                    # TOOTH 5: thin evidence must be flagged provisional.
                    thin = maturity == "spec" or len(evidence) < MIN_EVIDENCE_REFS
                    if thin and not provisional:
                        reason = "maturity=spec" if maturity == "spec" else f"only {len(evidence)} evidence_ref(s)"
                        v.reject(f"{sloc}: {verdict} claim is thin ({reason}) and must set provisional=true")

        per_category[cid] = cat_counts

    v.tally = {
        "categories": len(categories),
        "scores": n_scores,
        "provisional": n_provisional,
        "verdicts": verdict_counts,
        "per_category": per_category,
    }
    return v


def _canonical_bytes(board: dict) -> bytes:
    """Deterministic serialization for the seal: sorted keys, compact separators, UTF-8."""
    return json.dumps(board, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seal(board: dict, verdict: Verdict) -> dict:
    digest = hashlib.sha256(_canonical_bytes(board)).hexdigest()
    return {
        "board_id": board.get("board_id"),
        "spec_version": board.get("spec_version"),
        "generated_ts": board.get("generated_ts"),
        "sha256": digest,
        "algorithm": "SHA-256 (FIPS 180-4 via stdlib hashlib; not a FIPS 140-validated module)",
        "canonicalization": "json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False) UTF-8",
        "valid": verdict.valid,
        "tally": verdict.tally,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate + seal the Intelligence-Superiority feature-board.")
    ap.add_argument("board", type=Path, help="path to the board dataset JSON")
    ap.add_argument("--seal", type=Path, default=None, help="write a SHA-256 receipt here when VALID")
    args = ap.parse_args(argv)

    try:
        board = json.loads(args.board.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"MALFORMED: cannot read/parse {args.board}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(board, dict):
        print("MALFORMED: board root is not an object", file=sys.stderr)
        return 2

    v = validate_board(board)

    if v.valid:
        t = v.tally
        vc = t["verdicts"]
        print(f"VALID: {t['categories']} categories, {t['scores']} scores "
              f"(BEAT={vc['BEAT']} MEET={vc['MEET']} PARTIAL={vc['PARTIAL']} GAP={vc['GAP']}, "
              f"{t['provisional']} provisional)")
        for w in v.warnings:
            print(f"  warn: {w}")
        if args.seal:
            receipt = seal(board, v)
            args.seal.parent.mkdir(parents=True, exist_ok=True)
            args.seal.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"SEALED: sha256={receipt['sha256']} -> {args.seal}")
        return 0

    print(f"REJECTED: {len(v.rejections)} violation(s):", file=sys.stderr)
    for r in v.rejections:
        print(f"  - {r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
