#!/usr/bin/env python3
"""JIT review gate — independently verify a proposed effect before it rolls out, and seal the verdict.

The Review stage of the vendor-freshness loop. sociosphere detects, the membrane decides, the
executor acts — and THIS reviews what the executor produced before sourceos-continuum promotes it.
It is deliberately cheap and scale-to-zero: invoked on an effect event, it runs a handful of
deterministic checks that do the real work, adds one thin model judgment on top, seals a verdict,
and exits. There is no always-on reviewer to keep warm.

The design echoes the executor on purpose. The deterministic checks are fail-closed and carry the
weight; the model is a thin, PLUGGABLE judgment layer (a right-sized code model) invoked lazily —
only when the deterministic checks already pass — so the expensive backend runs rarely and never
gates on its own. It re-proves the executor's claims against the actual repo rather than trusting
the receipt: the marker is re-asserted from the tarball on disk, the floors and pins re-read.

A reviewer that cannot say no is worse than none, so the verdict is fail-closed: any deterministic
check that does not hold → REJECT, whatever the model thinks. All hold + model approves → APPROVE.
All hold + model raises a concern → NEEDS_HUMAN. Every check has a tested REJECT path.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, _HERE / f"{mod_name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod  # dataclasses in revendor_engine resolve via sys.modules
    spec.loader.exec_module(mod)
    return mod


# Re-use the verified primitives rather than reimplement them (single source of truth):
# the executor's receipt seal, and the marker byte-read.
revendor = _load("revendor_engine")
marker_tool = _load("assert_vendored_engine_marker")

APPROVE, REJECT, NEEDS_HUMAN = "APPROVE", "REJECT", "NEEDS_HUMAN"
_PROMOTABLE_STATUS = {"applied", "noop"}


# ── deterministic checks: each returns (ok, evidence); none mutate anything ───────────

def check_receipt_well_formed(receipt: dict) -> tuple[bool, dict]:
    problems = []
    if receipt.get("tool") != "prophet-platform.revendor_engine.v1":
        problems.append(f"unexpected tool {receipt.get('tool')!r}")
    if receipt.get("status") not in _PROMOTABLE_STATUS:
        problems.append(f"status {receipt.get('status')!r} is not promotable (want one of {sorted(_PROMOTABLE_STATUS)})")
    if not isinstance(receipt.get("steps"), list):
        problems.append("steps missing or not a list")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(receipt.get("to_version", ""))):
        problems.append(f"to_version {receipt.get('to_version')!r} is not a semver")
    return (not problems), {"problems": problems}


def check_seal_intact(receipt: dict) -> tuple[bool, dict]:
    """Recompute the executor's seal over the receipt body; a tampered step or evidence
    field changes the digest. Uses the executor's own seal function, not a copy."""
    claimed = receipt.get("receipt_digest")
    recomputed = revendor._seal(dict(receipt))["receipt_digest"]
    return (claimed == recomputed), {"claimed": claimed, "recomputed": recomputed}


def check_all_steps_passed(receipt: dict) -> tuple[bool, dict]:
    steps = receipt.get("steps", [])
    failed = [s.get("step") for s in steps if not s.get("ok")]
    return (not failed), {"failed_steps": failed, "step_count": len(steps)}


def check_marker_reproven(receipt: dict, root: Path) -> tuple[bool, dict]:
    """Independently re-assert the discriminating marker against the tarball on disk for
    every consumer — do NOT trust the receipt's assert_marker claim. The expected markers
    are taken from the receipt (which sourced them from the register), the proof is redone."""
    to_version = receipt.get("to_version")
    expected = _expected_markers(receipt)
    if not expected:
        return False, {"reason": "receipt carries no expected markers to re-prove"}
    consumers = receipt.get("consumers", [])
    per_consumer = {}
    ok = True
    for consumer in consumers:
        tgz = root / "apps" / consumer / "vendor" / f"socioprophet-hellgraph-{to_version}.tgz"
        if not tgz.exists():
            per_consumer[consumer] = {"ok": False, "reason": f"tarball absent: {tgz.name}"}
            ok = False
            continue
        try:
            raw = marker_tool.read_member(tgz, marker_tool.DEFAULT_MEMBER)
        except SystemExit as exc:
            per_consumer[consumer] = {"ok": False, "reason": str(exc)}
            ok = False
            continue
        missing = [m for m in expected if m.encode("utf-8") not in raw]
        per_consumer[consumer] = {"ok": not missing, "missing": missing,
                                  "tarball_digest": f"sha256:{marker_tool.sha256_file(tgz)}"}
        ok = ok and not missing
    return ok, {"expected": expected, "consumers": per_consumer}


def check_consumers_atomic(receipt: dict, root: Path) -> tuple[bool, dict]:
    """Every declared consumer must actually ship to_version now — pin AND floor — re-read
    from the repo. Catches a re-vendor that moved one consumer and not the other."""
    to_version = receipt.get("to_version")
    tv = tuple(int(p) for p in to_version.split("."))
    per_consumer = {}
    ok = True
    for consumer in receipt.get("consumers", []):
        spec, ver = revendor._vendored_ref(root, consumer)
        floor = revendor._current_floor(root, consumer)
        c_ok = ver == to_version and floor is not None and tuple(int(p) for p in floor.split(".")) >= tv
        per_consumer[consumer] = {"ok": c_ok, "pinned": ver, "floor": floor}
        ok = ok and c_ok
    return ok, {"to_version": to_version, "consumers": per_consumer}


def check_scope_contained(receipt: dict, changed_paths: list[str] | None) -> tuple[bool, dict]:
    """If a diff of changed paths is supplied, a re-vendor may only touch vendored tarballs,
    the engine dependency pin, and the engine floor. Anything else rides in on the change and
    is rejected. Without a diff this is advisory (the executor is trusted to have that scope)."""
    if changed_paths is None:
        return True, {"note": "no diff supplied; scope check advisory only"}
    allowed = re.compile(r"apps/[^/]+/(vendor/socioprophet-hellgraph-[\d.]+\.tgz|package\.json|scripts/check-engine-version\.mjs)$")
    out_of_scope = [p for p in changed_paths if not allowed.fullmatch(p)]
    return (not out_of_scope), {"out_of_scope": out_of_scope, "changed_count": len(changed_paths)}


def _expected_markers(receipt: dict) -> list[str]:
    for step in receipt.get("steps", []):
        if step.get("step") == "assert_marker":
            return list(step.get("evidence", {}).get("expected_present", []))
    return []


# ── the pluggable, scale-to-zero model judgment ──────────────────────────────────────

class ReviewModel(ABC):
    """The thin judgment layer. A real implementation POSTs the change + the deterministic
    findings to a right-sized code model served scale-to-zero (cold-started on the effect
    event, idle→0 after). It is asked ONLY the semantic question the deterministic checks
    cannot answer, and only after they pass — so it is invoked rarely and never alone gates."""

    @abstractmethod
    def judge(self, receipt: dict, findings: list[dict]) -> dict:
        """Return {'verdict': 'approve'|'concern', 'rationale': str}."""


class StubReviewModel(ReviewModel):
    """Default when no model backend is configured (tests, and CI where the deterministic
    checks are authoritative). Approves — it adds no signal and must not manufacture any."""

    def judge(self, receipt: dict, findings: list[dict]) -> dict:
        return {"verdict": "approve",
                "rationale": "stub model — no semantic review performed; deterministic checks are authoritative"}


def _seal_review(receipt: dict) -> dict:
    body = {k: v for k, v in receipt.items() if k != "review_digest"}
    receipt["review_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return receipt


def review(revendor_receipt: dict, root: Path, model: ReviewModel | None = None,
           changed_paths: list[str] | None = None) -> dict:
    """Review an executor re-vendor receipt against the repo and seal a verdict. Fail-closed:
    the first failing deterministic check makes the verdict REJECT; the model is consulted
    only when all deterministic checks pass."""
    model = model or StubReviewModel()
    checks: list[dict] = []

    def run(name: str, ok: bool, evidence: dict):
        checks.append({"check": name, "ok": ok, "evidence": evidence})

    run("receipt_well_formed", *check_receipt_well_formed(revendor_receipt))
    run("seal_intact", *check_seal_intact(revendor_receipt))
    run("all_steps_passed", *check_all_steps_passed(revendor_receipt))
    run("marker_reproven", *check_marker_reproven(revendor_receipt, root))
    run("consumers_atomic", *check_consumers_atomic(revendor_receipt, root))
    run("scope_contained", *check_scope_contained(revendor_receipt, changed_paths))

    deterministic_ok = all(c["ok"] for c in checks)
    review_receipt: dict = {
        "tool": "prophet-platform.review_gate.v1",
        "reviewed": {"idempotency_key": revendor_receipt.get("idempotency_key"),
                     "to_version": revendor_receipt.get("to_version")},
        "checks": checks,
        "deterministic_ok": deterministic_ok,
    }

    if not deterministic_ok:
        review_receipt["model"] = {"verdict": "skipped",
                                   "rationale": "deterministic checks failed; fail-closed, model not consulted"}
        review_receipt["verdict"] = REJECT
        return _seal_review(review_receipt)

    judgment = model.judge(revendor_receipt, [c for c in checks])
    review_receipt["model"] = judgment
    review_receipt["verdict"] = APPROVE if judgment.get("verdict") == "approve" else NEEDS_HUMAN
    return _seal_review(review_receipt)


_EXIT = {APPROVE: 0, REJECT: 1, NEEDS_HUMAN: 2}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="JIT review gate over an executor re-vendor receipt.")
    ap.add_argument("--receipt", type=Path, required=True, help="the executor's sealed re-vendor receipt JSON")
    ap.add_argument("--root", type=Path, default=_HERE.parent, help="repo root to re-verify against")
    ap.add_argument("--changed-paths", type=Path, help="optional newline-delimited file of changed paths (scope check)")
    args = ap.parse_args(argv)

    receipt = json.loads(args.receipt.read_text())
    changed = args.changed_paths.read_text().split() if args.changed_paths else None
    verdict = review(receipt, args.root, changed_paths=changed)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return _EXIT[verdict["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
