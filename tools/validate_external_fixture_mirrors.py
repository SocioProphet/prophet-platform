#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures" / "external" / "mirror-manifest.json"
VALID_MIRROR_STATES = {"current", "pinned", "future", "stale"}
VALID_SOURCE_PLANES = {"AgentPlane", "Sociosphere", "GAIA", "Guardrail Fabric"}


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def all_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def fixture_non_claim_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("non_claims", "nonClaims"):
        parts.extend(all_strings(data.get(key)))
    return "\n".join(parts).lower()


def main() -> int:
    problems: list[str] = []
    manifest = load(MANIFEST)

    if manifest.get("schema_version") != "1.0":
        problems.append("manifest schema_version must be 1.0")
    if not str(manifest.get("manifest_id", "")).startswith("prophet-platform:external-fixture-mirror-manifest:"):
        problems.append("manifest_id shape is invalid")

    mirrors = manifest.get("mirrors", [])
    if not isinstance(mirrors, list) or not mirrors:
        problems.append("manifest mirrors must be non-empty")
        mirrors = []

    seen: set[str] = set()
    state_counts: dict[str, int] = {state: 0 for state in sorted(VALID_MIRROR_STATES)}
    plane_counts: dict[str, int] = {plane: 0 for plane in sorted(VALID_SOURCE_PLANES)}
    for item in mirrors:
        if not isinstance(item, dict):
            problems.append("mirror entry must be object")
            continue
        mirror_path = str(item.get("mirror_path", ""))
        if not mirror_path:
            problems.append("mirror entry missing mirror_path")
            continue
        if mirror_path in seen:
            problems.append(f"duplicate mirror path: {mirror_path}")
        seen.add(mirror_path)

        source_plane = str(item.get("source_plane", ""))
        if source_plane not in VALID_SOURCE_PLANES:
            problems.append(f"{mirror_path}: invalid source_plane")
        else:
            plane_counts[source_plane] += 1
        if not str(item.get("source_repo", "")).startswith("SocioProphet/"):
            problems.append(f"{mirror_path}: source_repo must be SocioProphet/*")
        source_path = str(item.get("source_path", ""))
        if not source_path:
            problems.append(f"{mirror_path}: missing source_path")
        if not item.get("purpose"):
            problems.append(f"{mirror_path}: missing purpose")

        mirror_state = str(item.get("mirror_state", ""))
        if mirror_state not in VALID_MIRROR_STATES:
            problems.append(f"{mirror_path}: mirror_state must be one of {sorted(VALID_MIRROR_STATES)}")
        else:
            state_counts[mirror_state] += 1
        if mirror_state == "future":
            if not source_path.startswith("future/"):
                problems.append(f"{mirror_path}: future mirrors must use future/ source_path")
        if mirror_state == "current":
            if source_path.startswith("future/"):
                problems.append(f"{mirror_path}: current mirrors must not use future/ source_path")
        if mirror_state == "stale":
            problems.append(f"{mirror_path}: stale mirrors must not be present in passing CI")

        fixture_path = ROOT / mirror_path
        if not fixture_path.exists():
            problems.append(f"{mirror_path}: mirror file does not exist")
            continue
        fixture = load(fixture_path)
        text = fixture_non_claim_text(fixture)
        for required in all_strings(item.get("required_non_claims")):
            words = required.lower().split()
            if not all(word in text for word in words):
                problems.append(f"{mirror_path}: missing required non-claim phrase {required!r}")
        if mirror_state == "future" and "future" not in item.get("purpose", "").lower() and "shared receipt" not in item.get("purpose", "").lower():
            problems.append(f"{mirror_path}: future mirrors must explain staged purpose")

    non_claims = manifest.get("non_claims", [])
    if not isinstance(non_claims, list) or not non_claims:
        problems.append("manifest non_claims must be non-empty")

    report = {
        "validator": "prophet-platform.external-fixture-mirrors.validator.v1",
        "passed": not problems,
        "problems": problems,
        "mirror_count": len(mirrors),
        "mirror_state_counts": state_counts,
        "source_plane_counts": plane_counts,
        "non_claims": [
            "Validator checks mirror governance metadata only.",
            "Validator does not compare mirrors to live upstream repositories.",
            "Validator does not execute infrastructure.",
            "Validator does not certify Signadot feature parity."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(("PASS" if not problems else "FAIL") + ": external fixture mirrors")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
