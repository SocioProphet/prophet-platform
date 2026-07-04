#!/usr/bin/env python3
"""Enforce the mount-intent egress policy against edge→cloud-twin sync manifests.

Any Job/CronJob that pushes data to the cloud twin must declare, via the annotation
`mount-intent.socioprophet.io/egress: <intent>[,<intent>...]`, which mount intents it egresses —
and every declared intent MUST be egress-allowed (mount_intent.may_egress). This turns the
sovereignty rule ("derived indexes, secrets, scratch, config, ipc never leave the device") into a
build-time gate: adding e.g. `derived_index` or `secrets` to a sync job fails CI.

Fail-closed: a sync manifest under infra/k8s/edge-twin-sync that has NO egress annotation is an
error too — egress must be declared, not implicit.
"""
from __future__ import annotations

import pathlib
import sys

import yaml

# import the library from libs/python/mount-intent/src without installing it
_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "libs" / "python" / "mount-intent" / "src"))
from mount_intent import EGRESSABLE_INTENTS, MountIntent  # noqa: E402

ANNOTATION = "mount-intent.socioprophet.io/egress"
SYNC_DIR = _ROOT / "infra" / "k8s" / "edge-twin-sync"
EGRESS_KINDS = {"Job", "CronJob"}


def _docs(path: pathlib.Path):
    try:
        return [d for d in yaml.safe_load_all(path.read_text()) if isinstance(d, dict)]
    except yaml.YAMLError:
        return []


def main() -> int:
    if not SYNC_DIR.exists():
        print(f"no sync dir at {SYNC_DIR} — nothing to validate")
        return 0

    errors: list[str] = []
    checked = 0
    for path in sorted(SYNC_DIR.rglob("*.yaml")):
        for doc in _docs(path):
            if doc.get("kind") not in EGRESS_KINDS:
                continue
            checked += 1
            name = doc.get("metadata", {}).get("name", "<unnamed>")
            ann = (doc.get("metadata", {}).get("annotations") or {}).get(ANNOTATION)
            if not ann:
                errors.append(f"{path.name}: {doc['kind']}/{name} egresses to the twin but declares "
                              f"no `{ANNOTATION}` annotation (egress must be declared)")
                continue
            for raw in [s.strip() for s in ann.split(",") if s.strip()]:
                try:
                    intent = MountIntent(raw)
                except ValueError:
                    errors.append(f"{path.name}: {name} declares unknown intent '{raw}'")
                    continue
                if intent not in EGRESSABLE_INTENTS:
                    errors.append(
                        f"{path.name}: {doc['kind']}/{name} declares egress of '{intent.value}', "
                        f"which is NOT egress-allowed — it must never leave the device"
                    )

    if errors:
        print("mount-intent egress policy VIOLATED:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print(f"mount-intent egress policy OK ({checked} sync job(s) checked; "
          f"egress-allowed intents: {sorted(i.value for i in EGRESSABLE_INTENTS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
