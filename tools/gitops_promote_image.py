#!/usr/bin/env python3
"""Promote a container image digest across deployment channels (dev→stage→prod),
enforcing the promotion_requirements declared in deployment-profiles.yaml.

The contract (require_digest / require_signature_state / require_sbom /
require_provenance) already exists in contracts/platform/deployment-profiles.yaml
but nothing enforced it. This tool is the gate: given a digest + a verification
summary (produced by cosign verify / verify-attestation in CI), it refuses the
promotion unless every required check is satisfied, then pins the digest into the
target channel's values file.

Usage:
  gitops_promote_image.py \
      --service hellgraph-service --channel prod \
      --digest sha256:<64hex> \
      --values-file deploy/values/hellgraph-service.yaml \
      --profiles contracts/platform/deployment-profiles.yaml \
      --signed --sbom --provenance

Exit 0 = promoted (values file updated); non-zero = refused (requirements unmet).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# promotion_requirements key → the verification field that satisfies it.
REQUIREMENT_TO_CHECK = {
    "require_digest": "digest_pinned",
    "require_signature_state": "signed",
    "require_sbom": "sbom",
    "require_provenance": "provenance",
}


def check_promotion(requirements: dict[str, Any], verification: dict[str, bool], digest: str) -> list[str]:
    """Return a list of unmet-requirement errors ([] means promotion is allowed)."""
    errors: list[str] = []
    if not DIGEST_RE.match(digest or ""):
        errors.append(f"digest {digest!r} is not a pinned sha256:<64hex> reference")
    for req, check in REQUIREMENT_TO_CHECK.items():
        if requirements.get(req) and not verification.get(check):
            errors.append(f"{req} is required but verification.{check} is not satisfied")
    return errors


def apply_digest(values_path: Path, digest: str, channel: str, tag: str | None) -> dict[str, Any]:
    """Pin the digest into the values file's image block; record the channel."""
    values = yaml.safe_load(values_path.read_text(encoding="utf-8")) or {}
    image = values.get("image")
    if not isinstance(image, dict):
        image = {}
    image["digest"] = digest
    if tag:
        image["tag"] = tag
    image["channel"] = channel
    values["image"] = image
    values_path.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote an image digest across channels, enforcing promotion_requirements")
    parser.add_argument("--service", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--values-file", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--tag", default=None)
    # Verification summary (from cosign verify / verify-attestation in CI):
    parser.add_argument("--signed", action="store_true", help="keyless signature verified")
    parser.add_argument("--sbom", action="store_true", help="SBOM attestation present")
    parser.add_argument("--provenance", action="store_true", help="SLSA provenance attestation present")
    args = parser.parse_args()

    profiles = yaml.safe_load(args.profiles.read_text(encoding="utf-8")) or {}
    channels = profiles.get("channels") or []
    if channels and args.channel not in channels:
        print(f"ERR: channel {args.channel!r} not in declared channels {channels}", file=sys.stderr)
        return 2
    requirements = profiles.get("promotion_requirements") or {}

    verification = {
        "digest_pinned": bool(DIGEST_RE.match(args.digest or "")),
        "signed": args.signed,
        "sbom": args.sbom,
        "provenance": args.provenance,
    }
    errors = check_promotion(requirements, verification, args.digest)
    if errors:
        print(f"REFUSED: promotion of {args.service} to {args.channel} blocked:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if not args.values_file.exists():
        print(f"ERR: values file {args.values_file} not found", file=sys.stderr)
        return 2
    apply_digest(args.values_file, args.digest, args.channel, args.tag)
    print(f"OK: promoted {args.service} → {args.channel} at {args.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
