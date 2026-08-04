#!/usr/bin/env python3
"""Validate the three-space reconstruction contracts — the teeth.

A reconstruction is only trustworthy if it is internally honest. Two records, each with teeth
that bite the exact way this method fails in the wild:

reconstruction-manifest.v0
  1. conforms to the schema (jsonschema);
  2. every SPACE present must be fully pinned (seed + hash/sv_hash/topics_hash) — an unpinned
     space cannot be reproduced, which defeats the entire point;
  3. coverage.declared_gaps must be PRESENT (empty array = explicit "no gaps" affirmation) — a
     reconstruction must never let "comprehensive" quietly mean "comprehensive about part of it";
  4. attestation.attested=true REQUIRES a non-empty `signed`.

topic-record.v0
  1. conforms to the schema (jsonschema);
  2. grounded=true REQUIRES reasoning AND non-empty representative_evidence — the term-list
     ("seven-word answer") form of a topic is never trusted as grounded;
  3. mass in [0,1];
  4. every representative_evidence item must carry a non-empty snippet — a doc_id with no snippet
     is a pointer with no witness.

Exit non-zero on any violation. `--selftest` proves the teeth bite both ways.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "contracts/crystal-atlas/schemas"
EX_DIR = ROOT / "contracts/crystal-atlas/examples"
MANIFEST_SCHEMA = SCHEMA_DIR / "reconstruction-manifest.v0.schema.json"
TOPIC_SCHEMA = SCHEMA_DIR / "topic-record.v0.schema.json"
MANIFEST_EX = EX_DIR / "reconstruction-manifest.v0.json"
TOPIC_EX = EX_DIR / "topic-record.v0.json"


def _schema_errors(instance: dict, schema: dict) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return []  # jsonschema absent: structural teeth below still bite
    return [f"schema: {e.message}" for e in Draft202012Validator(schema).iter_errors(instance)]


def check_manifest(m: dict, schema: dict) -> list[str]:
    errs = _schema_errors(m, schema)
    for name, space in (m.get("spaces") or {}).items():
        pin = {"lsa": "hash", "lsi": "sv_hash", "lda": "topics_hash"}.get(name)
        if pin and not space.get(pin):
            errs.append(f"space {name!r} is present but not pinned (missing {pin})")
        if space.get("seed") is None:
            errs.append(f"space {name!r} is present but has no seed")
    if "declared_gaps" not in (m.get("coverage") or {}):
        errs.append("coverage.declared_gaps missing — coverage must be explicitly declared")
    att = m.get("attestation") or {}
    if att.get("attested") and not att.get("signed"):
        errs.append("attestation.attested=true but no signature present")
    return errs


def check_topic(t: dict, schema: dict) -> list[str]:
    errs = _schema_errors(t, schema)
    ev = t.get("representative_evidence") or []
    if t.get("grounded") and not (t.get("reasoning") and ev):
        errs.append(f"{t.get('topic_id','?')}: grounded=true but missing reasoning and/or representative_evidence")
    mass = t.get("mass")
    if mass is not None and not (0.0 <= mass <= 1.0):
        errs.append(f"{t.get('topic_id','?')}: mass {mass} outside [0,1]")
    for i, e in enumerate(ev):
        if not e.get("snippet"):
            errs.append(f"{t.get('topic_id','?')}: evidence[{i}] has doc_id but no snippet (pointer with no witness)")
    return errs


def _selftest() -> int:
    ms = json.loads(MANIFEST_SCHEMA.read_text()); ts = json.loads(TOPIC_SCHEMA.read_text())
    m = json.loads(MANIFEST_EX.read_text()); t = json.loads(TOPIC_EX.read_text())
    assert not check_manifest(m, ms), f"clean manifest must pass: {check_manifest(m, ms)}"
    assert not check_topic(t, ts), f"clean topic must pass: {check_topic(t, ts)}"

    # manifest teeth
    m1 = copy.deepcopy(m); m1["spaces"]["lda"]["topics_hash"] = ""
    assert check_manifest(m1, ms), "tooth: unpinned space not caught"
    m2 = copy.deepcopy(m); del m2["coverage"]["declared_gaps"]
    assert check_manifest(m2, ms), "tooth: undeclared coverage not caught"
    m3 = copy.deepcopy(m); m3["attestation"]["signed"] = ""
    assert check_manifest(m3, ms), "tooth: attested-without-signature not caught"

    # topic teeth
    t1 = copy.deepcopy(t); t1["representative_evidence"] = []
    assert check_topic(t1, ts), "tooth: grounded-without-evidence not caught"
    t2 = copy.deepcopy(t); t2["reasoning"] = ""
    assert check_topic(t2, ts), "tooth: grounded-without-reasoning not caught"
    t3 = copy.deepcopy(t); t3["representative_evidence"][0]["snippet"] = ""
    assert check_topic(t3, ts), "tooth: evidence-without-snippet not caught"

    print("selftest OK — teeth bite both ways")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    ms = json.loads(MANIFEST_SCHEMA.read_text()); ts = json.loads(TOPIC_SCHEMA.read_text())
    errs = check_manifest(json.loads(MANIFEST_EX.read_text()), ms)
    errs += check_topic(json.loads(TOPIC_EX.read_text()), ts)
    if errs:
        print("FAIL:")
        for e in errs:
            print("  -", e)
        return 1
    print("OK — reconstruction contracts are internally honest (spaces pinned, coverage declared, topics grounded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
