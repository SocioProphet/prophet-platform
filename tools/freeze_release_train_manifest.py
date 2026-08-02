#!/usr/bin/env python3
"""Freeze a *release-train* image-set manifest — the exact immutable digest set that a
single scheduled release train promotes through every wave (dev -> canary -> prod).

This is the heart of build-once-promote-many (INV-DEP-2): the train FREEZES one digest
per component ONCE, and every wave promotes that SAME frozen digest. Nothing downstream
rebuilds; a wave only advances the already-built, already-signed sha256 through the next
env overlay. The frozen manifest is the contract the wave-promote workflow reads.

Inputs
------
  * ``releases/images/*.image-lock.json``  — the per-component immutable digest locks
    written by the Wave-0 build (never the ``*.example.json`` templates).
  * ``releases/images/component-inventory.v1.yaml`` — the component registry, used to
    stamp each frozen entry with its inventory id / source path (advisory; a lock that
    has no inventory entry is still frozen, but flagged).

Invariants enforced at freeze time (fail-closed — a violation aborts the freeze)
--------------------------------------------------------------------------------
  INV-DEP-1  every ``pinned_ref`` MUST be ``<image>@sha256:<64hex>`` — a digest, never a
             moving tag (``:latest`` / ``:main`` / ``:dev`` / ``:sha-...``). A moving tag
             with imagePullPolicy: IfNotPresent never rolls; only a digest is immutable.
  INV-DEP-1b ``pinned_ref`` MUST equal ``<image>@<digest>`` (internal consistency).

Output
------
  ``releases/manifests/release-train.<label>.manifest.json`` — sorted, stable, the frozen
  digest set + wave order + gate references. Re-running with the same locks is idempotent.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import re
from pathlib import Path
from typing import Any

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# A moving tag is anything of the form image:tag (a single ':' segment that is NOT a digest).
MOVING_TAG_RE = re.compile(r":[^@/]+$")

DEFAULT_WAVE_ORDER = ["dev", "canary", "prod"]
DEFAULT_GATES = {
    "per_wave": [
        "preflight-deploy-contract",   # what we deploy references something that exists
        "canary-slo-gate",             # fail-closed Argo Rollouts SLO analysis (no-data aborts)
        "evidence-present",            # a rollout evidence record for the wave
    ],
    "fail_closed": True,
}


def _validate_pinned_ref(image: str, digest: str, pinned_ref: str, lock_id: str) -> None:
    if not DIGEST_RE.match(digest):
        raise SystemExit(f"::error::{lock_id}: digest {digest!r} is not sha256:<64hex> (INV-DEP-1)")
    # A pinned_ref must carry an @sha256 digest, and must NOT be a bare moving tag.
    if "@sha256:" not in pinned_ref:
        raise SystemExit(f"::error::{lock_id}: pinned_ref {pinned_ref!r} is not digest-pinned — "
                         f"moving tags never roll under IfNotPresent (INV-DEP-1)")
    ref_image, _, ref_digest = pinned_ref.partition("@")
    if MOVING_TAG_RE.search(ref_image):
        raise SystemExit(f"::error::{lock_id}: pinned_ref image part {ref_image!r} carries a moving "
                         f"tag as well as a digest (INV-DEP-1)")
    expected = f"{image}@{digest}"
    if pinned_ref != expected:
        raise SystemExit(f"::error::{lock_id}: pinned_ref {pinned_ref!r} != {expected!r} (INV-DEP-1b)")


def _load_inventory(inv_path: Path) -> dict[str, dict[str, Any]]:
    """Map component source_path/image_name -> inventory record (best-effort, advisory)."""
    if not inv_path.exists():
        return {}
    try:
        import yaml  # optional; freeze still works without pyyaml
    except Exception:
        return {}
    try:
        # Advisory only: the inventory stamps ids onto frozen entries. A parse problem
        # (e.g. an unquoted-colon justification string) must NOT abort the freeze — the
        # digest set comes from the locks, not the inventory.
        data = yaml.safe_load(inv_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - advisory best-effort
        print(f"::warning::could not parse inventory {inv_path} ({exc}); "
              f"freezing from locks without inventory stamps")
        return {}
    by_key: dict[str, dict[str, Any]] = {}
    for comp in data.get("components", []) or []:
        for key in (comp.get("source_path"), comp.get("image_name"), comp.get("id")):
            if key:
                by_key[str(key)] = comp
    return by_key


def freeze(lock_glob: str, inventory: Path, wave_order: list[str],
           label: str) -> dict[str, Any]:
    inv = _load_inventory(inventory)
    components: list[dict[str, Any]] = []
    for lock_file in sorted(glob.glob(lock_glob)):
        if lock_file.endswith(".example.json"):
            continue
        lock = json.loads(Path(lock_file).read_text(encoding="utf-8"))
        if lock.get("status") == "example":
            continue
        image = str(lock.get("image", ""))
        digest = str(lock.get("digest", ""))
        pinned_ref = str(lock.get("pinned_ref", ""))
        lock_id = str(lock.get("image_lock_id") or lock_file)
        _validate_pinned_ref(image, digest, pinned_ref, lock_id)

        component = str(lock.get("component", ""))
        inv_rec = inv.get(component) or inv.get(Path(image).name) or {}
        components.append({
            "id": inv_rec.get("id", Path(image).name),
            "component": component,
            "image": image,
            "digest": digest,
            "pinned_ref": pinned_ref,
            "source_sha": lock.get("source_sha", ""),
            "source_content_digest": lock.get("source_content_digest"),
            "lock": lock_file,
            "in_inventory": bool(inv_rec),
        })

    if not components:
        raise SystemExit("::error::no non-example image-locks found — nothing to freeze")

    components.sort(key=lambda c: c["image"])
    return {
        "manifest_id": f"release-train.{label}",
        "schema_version": "v1",
        "kind": "release-train-frozen-image-set",
        "frozen_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_inventory": str(inventory),
        "wave_order": wave_order,
        "gates": DEFAULT_GATES,
        "invariants": ["INV-DEP-1", "INV-DEP-2", "INV-DEP-3", "INV-DEP-4", "INV-DEP-5"],
        "component_count": len(components),
        "components": components,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--locks", default="releases/images/*.image-lock.json",
                   help="glob of per-component image-lock files")
    p.add_argument("--inventory", type=Path,
                   default=Path("releases/images/component-inventory.v1.yaml"))
    p.add_argument("--wave-order", default=",".join(DEFAULT_WAVE_ORDER),
                   help="comma-separated wave order (default: dev,canary,prod)")
    p.add_argument("--label", default=_dt.date.today().isoformat(),
                   help="release-train label (default: today's date)")
    p.add_argument("--output", type=Path, default=None,
                   help="output path (default: releases/manifests/release-train.<label>.manifest.json)")
    p.add_argument("--print", action="store_true", help="also print the frozen manifest to stdout")
    args = p.parse_args(argv)

    wave_order = [w.strip() for w in args.wave_order.split(",") if w.strip()]
    manifest = freeze(args.locks, args.inventory, wave_order, args.label)

    out = args.output or Path(f"releases/manifests/release-train.{args.label}.manifest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    print(f"froze {manifest['component_count']} component(s) -> {out}")
    if args.print:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
