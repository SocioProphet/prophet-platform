#!/usr/bin/env python3
"""Enforce the reasoning dataset catalogue: licence gate + fixture-family grounding.

Two failures this catches, both of which a prose list cannot:

1. LICENCE GATE (admitted != governed). A dataset may only reach `use.status: adopted` when
   `licence.verified: true`. Cataloguing a benchmark is knowing about it; adopting it means we
   train or evaluate on it, and doing that under unread distribution terms is the actual risk.
   NewsQA is the live example — realistic corpus, blocked on terms, and the block is recorded
   rather than silently re-litigated every few months.

2. FIXTURE GROUNDING. Every `use.fixture_families` entry must name a task_family that actually
   exists in fixtures/reasoning-task-eval/*.json. Without this the catalogue can claim a dataset
   backs a fixture family that was renamed or never existed — a citation to nothing, which is
   exactly the "declared but not grounded" failure the catalogue was written to fix.

Proven able to go red by --selftest (and tools/tests/test_check_reasoning_dataset_catalog.py),
because a gate that has only ever passed proves nothing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "registry" / "reasoning-dataset-catalog.v0.yaml"
FIXTURE_DIR = ROOT / "fixtures" / "reasoning-task-eval"

REQUIRED_DATASET_FIELDS = ("id", "name", "world", "family", "availability", "tests", "use", "licence")
VALID_STATUS = {"adopted", "candidate", "not-adopted"}
VALID_AVAILABILITY = {"public", "restricted", "not-distributed", "public-method", "unresolved"}


def known_fixture_families(fixture_dir: Path) -> set[str]:
    """Every task_family declared by the actual fixture files — the ground truth for citations."""
    families: set[str] = set()
    for path in sorted(fixture_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for task in payload.get("tasks", []):
            if isinstance(task, dict) and task.get("task_family"):
                families.add(str(task["task_family"]))
    return families


def violations(catalogue: dict[str, Any], families: set[str]) -> list[str]:
    out: list[str] = []
    datasets = catalogue.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        return ["catalogue declares no datasets"]

    seen: set[str] = set()
    for entry in datasets:
        if not isinstance(entry, dict):
            out.append("dataset entry is not a mapping")
            continue
        did = entry.get("id", "<unnamed>")

        for field in REQUIRED_DATASET_FIELDS:
            if field not in entry:
                out.append(f"{did}: missing required field '{field}'")
        if did in seen:
            out.append(f"{did}: duplicate dataset id")
        seen.add(did)

        avail = entry.get("availability")
        if avail is not None and avail not in VALID_AVAILABILITY:
            out.append(f"{did}: availability '{avail}' not one of {sorted(VALID_AVAILABILITY)}")

        if not entry.get("tests"):
            out.append(f"{did}: 'tests' is empty — a catalogue entry that does not say what the "
                       f"dataset probes is a name, not a record")

        use = entry.get("use") or {}
        licence = entry.get("licence") or {}
        status = use.get("status")
        if status not in VALID_STATUS:
            out.append(f"{did}: use.status '{status}' not one of {sorted(VALID_STATUS)}")
        if not use.get("rationale"):
            out.append(f"{did}: use.rationale is required — record WHY, or the decision gets "
                       f"re-litigated from scratch")

        # (1) THE LICENCE GATE
        verified = licence.get("verified")
        if verified is not True and status == "adopted":
            out.append(
                f"{did}: use.status=adopted but licence.verified is not true — a dataset cannot "
                f"graduate to adopted under unread distribution terms")

        # (2) FIXTURE GROUNDING
        for fam in use.get("fixture_families") or []:
            if fam not in families:
                out.append(
                    f"{did}: cites fixture family '{fam}', which does not exist in "
                    f"fixtures/reasoning-task-eval — a citation to nothing")
    return out


def _selftest() -> int:
    """Prove both gates bite, on fixtures built to trip them."""
    families = {"complex_qa.abstention"}
    good = {"datasets": [{
        "id": "ok", "name": "ok", "world": "closed", "family": "f", "availability": "public",
        "tests": ["something"], "licence": {"name": "x", "verified": True},
        "use": {"status": "adopted", "rationale": "because", "fixture_families": ["complex_qa.abstention"]},
    }]}
    assert violations(good, families) == [], violations(good, families)

    # licence gate: adopted without a verified licence must fail
    bad_licence = json.loads(json.dumps(good))
    bad_licence["datasets"][0]["licence"]["verified"] = False
    got = violations(bad_licence, families)
    assert any("licence.verified" in v for v in got), f"licence gate did not fire: {got}"

    # fixture grounding: a citation to a family that does not exist must fail
    bad_family = json.loads(json.dumps(good))
    bad_family["datasets"][0]["use"]["fixture_families"] = ["complex_qa.does_not_exist"]
    got = violations(bad_family, families)
    assert any("citation to nothing" in v for v in got), f"grounding check did not fire: {got}"

    # an entry that says nothing about what it tests must fail
    empty_tests = json.loads(json.dumps(good))
    empty_tests["datasets"][0]["tests"] = []
    assert any("'tests' is empty" in v for v in violations(empty_tests, families))

    print("selftest OK — licence gate and fixture grounding both bite")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalogue", type=Path, default=CATALOGUE)
    ap.add_argument("--fixtures", type=Path, default=FIXTURE_DIR)
    ap.add_argument("--selftest", action="store_true", help="prove the checks can fail, then exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    catalogue = yaml.safe_load(args.catalogue.read_text(encoding="utf-8"))
    families = known_fixture_families(args.fixtures)
    found = violations(catalogue, families)
    if found:
        for v in found:
            print(f"::error::{v}")
        print(f"reasoning-dataset-catalog: {len(found)} violation(s)")
        return 1
    n = len(catalogue.get("datasets", []))
    m = len(catalogue.get("methods", []) or [])
    print(f"reasoning-dataset-catalog: OK — {n} datasets, {m} methods, "
          f"every fixture-family citation resolves, licence gate holds.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI glue
    raise SystemExit(main())
