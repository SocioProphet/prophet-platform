#!/usr/bin/env python3
"""Minimal GhostEventV3 validator scaffold.

This validator is intentionally dependency-light and checks the load-bearing
runtime invariants for the V3 event envelope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_TOP = [
    "event_id",
    "event_type",
    "run_id",
    "trace_id",
    "span_id",
    "timestamp",
    "layer_id",
    "prime_registry_ref",
    "prime_registry_state_hash",
    "event_ir_hash",
    "prime_vector",
    "payload",
]


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_canonical_hash(event: dict) -> str:
    clone = dict(event)
    clone.pop("canonical_hash", None)
    return "sha256:" + hashlib.sha256(canonical_json(clone).encode("utf-8")).hexdigest()


def validate(event: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for key in REQUIRED_TOP:
        if key not in event:
            errors.append(f"missing:{key}")

    pv = event.get("prime_vector")
    if not isinstance(pv, list):
        errors.append("prime_vector:not_list")
    else:
        seen = set()
        last = -1
        for idx, entry in enumerate(pv):
            if not isinstance(entry, dict):
                errors.append(f"prime_vector[{idx}]:not_object")
                continue
            for k in ("basis_index", "topic_id", "prime", "exponent"):
                if k not in entry:
                    errors.append(f"prime_vector[{idx}]:missing:{k}")
            bi = entry.get("basis_index")
            ex = entry.get("exponent")
            if isinstance(bi, int):
                if bi in seen:
                    errors.append("prime_vector:duplicate_basis_index")
                seen.add(bi)
                if bi < last:
                    errors.append("prime_vector:not_sorted")
                last = bi
            else:
                errors.append(f"prime_vector[{idx}]:basis_index_type")
            if isinstance(ex, int):
                if ex < 0:
                    errors.append(f"prime_vector[{idx}]:negative_exponent")
                if ex == 0:
                    errors.append(f"prime_vector[{idx}]:zero_exponent_forbidden")
            else:
                errors.append(f"prime_vector[{idx}]:exponent_type")

    if event.get("canonical_hash") is not None:
        expected = compute_canonical_hash(event)
        if event.get("canonical_hash") != expected:
            errors.append("canonical_hash:mismatch")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event_file")
    args = parser.parse_args()

    data = json.loads(Path(args.event_file).read_text())
    ok, errors = validate(data)
    print(json.dumps({"ok": ok, "errors": errors}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
