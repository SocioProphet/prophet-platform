#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a Fog Stack manifest promotion set against policy")
    parser.add_argument("--publication-set", required=True, type=Path)
    parser.add_argument("--policy-catalog", required=True, type=Path)
    args = parser.parse_args()

    publication = load_json(args.publication_set)
    policy = yaml.safe_load(args.policy_catalog.read_text(encoding="utf-8")) or {}
    defaults = policy.get("defaults") or {}
    transitions = policy.get("allowed_transitions") or {}

    promotion = publication.get("promotion") or {}
    manifests = publication.get("manifests") or []
    if not isinstance(manifests, list):
        raise SystemExit("ERR: manifests list missing or malformed")

    require_channel = bool(defaults.get("require_explicit_target_channel"))
    require_support = bool(defaults.get("require_explicit_target_support_state"))

    if require_channel and not promotion.get("channel"):
        raise SystemExit("ERR: promotion.channel is required by policy")
    if require_support and not promotion.get("support_state"):
        raise SystemExit("ERR: promotion.support_state is required by policy")

    violations: list[str] = []
    for item in manifests:
        if not isinstance(item, dict):
            violations.append("manifest entry is not an object")
            continue
        bundle_id = item.get("bundle_id")
        prev_channel = item.get("previous_channel")
        prev_support = item.get("previous_support_state")
        target_channel = item.get("channel")
        target_support = item.get("support_state")

        allowed_supports = (((transitions.get(prev_channel) or {}).get(prev_support) or {}).get(target_channel))
        if not isinstance(allowed_supports, list) or target_support not in allowed_supports:
            violations.append(
                f"{bundle_id}: disallowed transition {prev_channel}/{prev_support} -> {target_channel}/{target_support}"
            )

    if violations:
        for item in violations:
            print(item)
        raise SystemExit(1)

    print("FogStack manifest promotion policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
