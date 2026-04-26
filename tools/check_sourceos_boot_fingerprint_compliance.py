#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def check(name: str, expected: Any, observed: Any) -> dict[str, str]:
    passed = expected == observed
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "expected": str(expected),
        "observed": str(observed),
    }


def evaluate(release_set: dict[str, Any], boot_release_set: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    release_id = release_set.get("id")
    boot_release_id = boot_release_set.get("id")
    policy_ref = release_set.get("policy", {}).get("policy_bundle_ref")

    checks = [
        check("release-set-ref", release_id, fingerprint.get("policy", {}).get("release_set_ref")),
        check("boot-release-set-ref", boot_release_id, fingerprint.get("policy", {}).get("boot_release_set_ref")),
        check("policy-bundle-ref", policy_ref, fingerprint.get("policy", {}).get("policy_bundle_ref")),
        check("subject-kind", "boot_environment", fingerprint.get("subject", {}).get("subject_kind")),
        check("runtime-isolation", "boot_env", fingerprint.get("runtime", {}).get("isolation")),
        check("boot-mode", "recovery", fingerprint.get("system", {}).get("boot_mode")),
    ]

    boot_modes = set(boot_release_set.get("boot_modes") or [])
    checks.append(check("rollback-available", "rollback" in boot_modes, fingerprint.get("system", {}).get("rollback_available")))

    expected_network = boot_release_set.get("capabilities", {}).get("network", "restricted")
    checks.append(check("network-scope", expected_network, fingerprint.get("policy", {}).get("network_scope")))

    expected_fs = "scoped" if boot_release_set.get("capabilities", {}).get("disk_write") == "scoped" else "none"
    checks.append(check("filesystem-scope", expected_fs, fingerprint.get("policy", {}).get("filesystem_scope")))

    status = "fail" if any(item["status"] == "fail" for item in checks) else "pass"
    return {
        "schema_version": "sourceos.boot-fingerprint-compliance/v0",
        "kind": "SourceOSBootFingerprintComplianceResult",
        "status": status,
        "release_set_ref": str(release_id),
        "boot_release_set_ref": str(boot_release_id),
        "fingerprint_ref": str(fingerprint.get("id")),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SourceOS boot Fingerprint against assigned ReleaseSet and BootReleaseSet")
    parser.add_argument("--release-set", required=True, type=Path)
    parser.add_argument("--boot-release-set", required=True, type=Path)
    parser.add_argument("--fingerprint", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate(load_json(args.release_set), load_json(args.boot_release_set), load_json(args.fingerprint))
    text = json.dumps(result, indent=2, sort_keys=False) + "\n"
    if args.output:
        write_json(args.output, result)
    else:
        print(text, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
