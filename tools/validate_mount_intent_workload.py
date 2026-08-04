#!/usr/bin/env python3
"""Enforce the directional mount-intent invariants on workload manifests.

A workload declares its mounts' intents via the annotation
`mount-intent.socioprophet.io/mounts: <vol>=<intent>[,<vol>=<intent>...]`, and pins the
verity root hash for any verified-immutable mount via
`mount-intent.socioprophet.io/verity.<vol>: <64-hex>`.

This gate enforces, by construction, two invariants that keep isolation from drifting:

  1. SINGLE EGRESS CHOKEPOINT — at most one egress-direction mount per workload (the only
     mount whose contents survive the pod, so egress attestation has one home).
  2. VERIFIED CORPUS IS PINNED — every curated_corpus (verified-immutable) mount must pin a
     dm-verity root hash in the manifest, so corpus integrity is a signature check, not a
     `readOnly: true` trust assertion.

Fail-closed: an unknown intent, a bad verity hash, or a verified-immutable mount with no
pinned hash is an error. Workloads that declare no mount-intent annotation are skipped (the
egress-sync gate covers the device boundary separately).
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "libs" / "python" / "mount-intent" / "src"))
from mount_intent import MountIntent, check_single_egress, verified_immutable  # noqa: E402

MOUNTS_ANN = "mount-intent.socioprophet.io/mounts"
VERITY_PREFIX = "mount-intent.socioprophet.io/verity."
SCAN_DIR = _ROOT / "infra" / "k8s"
WORKLOAD_KINDS = {"Pod", "Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "ReplicaSet"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _docs(path: pathlib.Path):
    try:
        return [d for d in yaml.safe_load_all(path.read_text()) if isinstance(d, dict)]
    except yaml.YAMLError:
        return []


def validate_doc(doc: dict, where: str) -> list[str]:
    meta = doc.get("metadata", {}) or {}
    anns = meta.get("annotations", {}) or {}
    raw = anns.get(MOUNTS_ANN)
    if not raw:
        return []  # not intent-annotated — device-egress gate covers it separately
    name = meta.get("name", "<unnamed>")
    errors: list[str] = []

    pairs: list[tuple[str, MountIntent]] = []
    for tok in [s.strip() for s in raw.split(",") if s.strip()]:
        if "=" not in tok:
            errors.append(f"{where}: {name} mount decl '{tok}' must be <vol>=<intent>")
            continue
        vol, intent_raw = (p.strip() for p in tok.split("=", 1))
        try:
            pairs.append((vol, MountIntent(intent_raw)))
        except ValueError:
            errors.append(f"{where}: {name} declares unknown intent '{intent_raw}' for '{vol}'")

    # 1. single egress chokepoint
    errors += [f"{where}: {name}: {v}" for v in check_single_egress([i for _, i in pairs])]

    # 2. verified-immutable mounts must pin a valid verity root hash
    for vol, intent in pairs:
        if verified_immutable(intent):
            h = anns.get(VERITY_PREFIX + vol)
            if not h:
                errors.append(f"{where}: {name}: '{vol}' is {intent.value} (verified-immutable) but "
                              f"pins no `{VERITY_PREFIX}{vol}` root hash")
            elif not _HEX64.match(h):
                errors.append(f"{where}: {name}: `{VERITY_PREFIX}{vol}` must be a 64-hex sha256 digest")
    return errors


def main() -> int:
    if not SCAN_DIR.exists():
        print(f"no k8s dir at {SCAN_DIR} — nothing to validate")
        return 0
    errors: list[str] = []
    checked = 0
    for path in sorted(SCAN_DIR.rglob("*.yaml")):
        for doc in _docs(path):
            if doc.get("kind") not in WORKLOAD_KINDS:
                continue
            if not ((doc.get("metadata", {}) or {}).get("annotations", {}) or {}).get(MOUNTS_ANN):
                continue
            checked += 1
            errors += validate_doc(doc, path.name)
    if errors:
        print("mount-intent workload invariants VIOLATED:")
        for e in errors:
            print("  ✗ " + e)
        return 1
    print(f"mount-intent workload invariants OK ({checked} intent-annotated workload(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
