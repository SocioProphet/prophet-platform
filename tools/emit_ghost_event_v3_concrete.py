#!/usr/bin/env python3
"""Concrete GhostEventV3 emitter.

This script emits a minimal GhostEventV3 JSON artifact with canonical hash
binding. It is intentionally self-contained so the V3 runtime lane is no
longer wrapper-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_canonical_hash(event: dict) -> str:
    clone = dict(event)
    clone.pop("canonical_hash", None)
    return "sha256:" + hashlib.sha256(canonical_json(clone).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", default="evt_v3_runtime_0001")
    parser.add_argument("--event-type", default="layer_touch")
    parser.add_argument("--run-id", default="run_v3_runtime_0001")
    parser.add_argument("--trace-id", default="trace_v3_runtime_0001")
    parser.add_argument("--span-id", default="span_v3_runtime_0001")
    parser.add_argument("--timestamp", default="1970-01-01T00:00:00Z")
    parser.add_argument("--layer-id", default="S1")
    parser.add_argument("--prime-registry-ref", default="sp.prime_topic_registry.v1@1.1.0")
    parser.add_argument("--prime-registry-state-hash", default="sha256:REGISTRYSTATE")
    parser.add_argument("--event-ir-hash", default="sha256:EVENTIR")
    parser.add_argument("--output", default="ghost_event_v3.json")
    args = parser.parse_args()

    event = {
        "event_id": args.event_id,
        "event_type": args.event_type,
        "run_id": args.run_id,
        "trace_id": args.trace_id,
        "span_id": args.span_id,
        "timestamp": args.timestamp,
        "layer_id": args.layer_id,
        "theta_ref": None,
        "scope_ref": None,
        "policy_ref": None,
        "registry_ref": None,
        "prime_registry_ref": args.prime_registry_ref,
        "prime_registry_state_hash": args.prime_registry_state_hash,
        "event_ir_hash": args.event_ir_hash,
        "prime_vector": [],
        "artifact_refs": [],
        "canonical_hash": None,
        "payload": {
            "step_name": "runtime",
            "state_ref": "state:runtime",
            "confidence": 1.0
        }
    }

    event["canonical_hash"] = compute_canonical_hash(event)
    Path(args.output).write_text(json.dumps(event, indent=2) + "\n")
    print(json.dumps({"ok": True, "output": args.output, "canonical_hash": event["canonical_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
