#!/usr/bin/env python3
"""Validate the internal-models register — the teeth.

A register entry is trusted only if it is internally honest:
  1. conforms to analytic-model-catalog-entry.v0 (jsonschema);
  2. `verified: true` REQUIRES both an eval_fixture AND a realizing_component
     (effect-canary — a model card is never trusted without a passing fixture);
  3. `status: GAP` must NOT name a realizing_component (else it is mislabeled);
  4. `status: HAVE|PARTIAL` MUST name a realizing_component;
  5. `output_contract_exists: true` requires the contract file to actually exist on disk.

Exit non-zero on any violation. `--selftest` proves the teeth bite both ways.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/crystal-atlas/schemas/analytic-model-catalog-entry.v0.schema.json"
REGISTER = ROOT / "contracts/crystal-atlas/registry/internal-models.v0.json"
CONTRACTS = ROOT / "contracts"


def _contract_exists(name: str) -> bool:
    if not name:
        return False
    stem = name[:-3] if name.endswith(".v0") else name
    hits = list(CONTRACTS.rglob(f"{stem}.v0.schema.json")) + list(CONTRACTS.rglob(f"{stem}.v0.json"))
    return bool(hits)


def check_entry(e: dict) -> list[str]:
    errs: list[str] = []
    status = e.get("status")
    rc = e.get("realizing_component")
    if e.get("verified") and not (e.get("eval_fixture") and rc):
        errs.append(f"{e['model_id']}: verified=true but missing eval_fixture and/or realizing_component (effect-canary)")
    if status == "GAP" and rc:
        errs.append(f"{e['model_id']}: status GAP but names realizing_component {rc!r}")
    if status in ("HAVE", "PARTIAL") and not rc:
        errs.append(f"{e['model_id']}: status {status} but no realizing_component")
    if e.get("output_contract_exists") and not _contract_exists(e.get("output_contract")):
        errs.append(f"{e['model_id']}: output_contract_exists=true but {e.get('output_contract')!r} not found in contracts/")
    return errs


def validate(register: dict, schema: dict) -> list[str]:
    errs: list[str] = []
    try:
        from jsonschema import Draft202012Validator
        v = Draft202012Validator(schema)
    except Exception:
        v = None
    ids = set()
    for e in register["models"]:
        if v is not None:
            for err in v.iter_errors(e):
                errs.append(f"{e.get('model_id','?')}: schema: {err.message}")
        if e["model_id"] in ids:
            errs.append(f"duplicate model_id {e['model_id']}")
        ids.add(e["model_id"])
        errs.extend(check_entry(e))
    return errs


def _selftest() -> int:
    schema = json.loads(SCHEMA.read_text())
    good = json.loads(REGISTER.read_text())
    errs = validate(good, schema)
    assert not errs, f"clean register must pass, got: {errs}"
    # teeth both ways: each tamper MUST be caught
    import copy
    t1 = copy.deepcopy(good); t1["models"][0]["verified"] = True
    assert validate(t1, schema), "tamper 1 (verified without fixture) not caught"
    t2 = copy.deepcopy(good); t2["models"][0]["realizing_component"] = "ghost-svc"  # a GAP row
    assert validate(t2, schema), "tamper 2 (GAP with realizing_component) not caught"
    t3 = copy.deepcopy(good)
    for m in t3["models"]:
        if m["status"] in ("HAVE", "PARTIAL"):
            m["realizing_component"] = None; break
    assert validate(t3, schema), "tamper 3 (HAVE without realizing_component) not caught"
    t4 = copy.deepcopy(good); t4["models"][0]["output_contract"] = "does.not.exist"; t4["models"][0]["output_contract_exists"] = True
    assert validate(t4, schema), "tamper 4 (missing contract) not caught"
    print("selftest OK — teeth bite both ways")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    schema = json.loads(SCHEMA.read_text())
    register = json.loads(REGISTER.read_text())
    errs = validate(register, schema)
    n = len(register["models"])
    have = sum(m["status"] == "HAVE" for m in register["models"])
    partial = sum(m["status"] == "PARTIAL" for m in register["models"])
    gap = sum(m["status"] == "GAP" for m in register["models"])
    verified = sum(m["verified"] for m in register["models"])
    print(f"internal-models register: {n} models — HAVE={have} PARTIAL={partial} GAP={gap} verified={verified}")
    if errs:
        print("FAIL:")
        for e in errs:
            print("  -", e)
        return 1
    print("OK — register is internally honest (no verified-without-fixture, no mislabeled GAP/HAVE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
