#!/usr/bin/env python3
"""Validate a frozen release-train manifest against the deploy-wave invariants
(docs/standards/deploy-wave-invariants-v0.md). Fail-closed: any violation exits non-zero.

This is the gate that a wave-promote run calls BEFORE it advances any wave, and that CI
calls on every change to a ``releases/manifests/release-train.*.manifest.json``. It proves
the frozen set is legal to promote:

  INV-DEP-1  every component ``pinned_ref`` is ``<image>@sha256:<64hex>`` — a digest, and
             the image part carries NO moving tag. (Build-once-promote-many is meaningless
             if a "frozen" entry is actually a moving tag that can change under the train.)
  INV-DEP-2  exactly ONE digest per image — the manifest cannot freeze the same image at
             two different digests (that would mean a per-wave rebuild snuck in).
  INV-DEP-3  ``wave_order`` is non-empty and gate references are present.
  INV-DEP-4  ``kind == release-train-frozen-image-set`` (a deploy set only reaches prod as
             a frozen train, never as a raw per-merge push).

Usage:  validate_release_train_manifest.py releases/manifests/release-train.<label>.manifest.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
MOVING_TAG_RE = re.compile(r":[^@/]+$")


def validate(manifest: dict) -> list[str]:
    errors: list[str] = []

    if manifest.get("kind") != "release-train-frozen-image-set":
        errors.append("INV-DEP-4: kind must be 'release-train-frozen-image-set' "
                      f"(got {manifest.get('kind')!r})")

    wave_order = manifest.get("wave_order") or []
    if not isinstance(wave_order, list) or not wave_order:
        errors.append("INV-DEP-3: wave_order must be a non-empty list")

    gates = manifest.get("gates") or {}
    if not gates.get("per_wave"):
        errors.append("INV-DEP-3: gates.per_wave must list the between-wave gates")
    if gates.get("fail_closed") is not True:
        errors.append("INV-DEP-3: gates.fail_closed must be true (a gate that cannot fail is no gate)")

    components = manifest.get("components") or []
    if not components:
        errors.append("INV-DEP-2: manifest freezes zero components")

    seen_image_digest: dict[str, str] = {}
    for c in components:
        image = str(c.get("image", ""))
        digest = str(c.get("digest", ""))
        pinned_ref = str(c.get("pinned_ref", ""))
        tag = c.get("id") or image or "<unknown>"

        if not DIGEST_RE.match(digest):
            errors.append(f"INV-DEP-1: {tag}: digest {digest!r} is not sha256:<64hex>")
        if "@sha256:" not in pinned_ref:
            errors.append(f"INV-DEP-1: {tag}: pinned_ref {pinned_ref!r} is not digest-pinned")
        else:
            ref_image = pinned_ref.split("@", 1)[0]
            if MOVING_TAG_RE.search(ref_image):
                errors.append(f"INV-DEP-1: {tag}: pinned_ref image part {ref_image!r} carries a moving tag")
            if pinned_ref != f"{image}@{digest}":
                errors.append(f"INV-DEP-1: {tag}: pinned_ref != image@digest")

        # INV-DEP-2: one image must not appear at two digests in the same frozen set.
        if image in seen_image_digest and seen_image_digest[image] != digest:
            errors.append(f"INV-DEP-2: {image} frozen at two digests "
                          f"({seen_image_digest[image]} and {digest}) — a per-wave rebuild leaked in")
        seen_image_digest.setdefault(image, digest)

    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("manifest", type=Path)
    args = p.parse_args(argv)

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        print(f"::error::release-train manifest {args.manifest} FAILED validation:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {args.manifest} — {data.get('component_count', len(data.get('components', [])))} "
          f"component(s), all digest-pinned, one digest per image")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
