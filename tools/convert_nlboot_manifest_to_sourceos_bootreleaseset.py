#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover
    raise SystemExit("ERR: jsonschema is required to validate SourceOS BootReleaseSet output") from exc

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts" / "sourceos" / "boot-release-set.v0.schema.json"

BOOT_MODE_MAP = {
    "recovery": "recovery",
    "installer": "installer",
    "ephemeral": "live",
    "bootstrap": "live",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def digest_for_ref(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"ERR: {key} must be a non-empty string")
    return value


def convert(manifest: dict[str, Any], token: dict[str, Any]) -> dict[str, Any]:
    boot_mode = require_string(manifest, "boot_mode")
    if boot_mode not in BOOT_MODE_MAP:
        raise SystemExit(f"ERR: unsupported nlboot boot_mode={boot_mode!r}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("ERR: manifest.artifacts must be an object")
    for required in ("kernel_ref", "initrd_ref", "rootfs_ref"):
        if not isinstance(artifacts.get(required), str) or not artifacts[required]:
            raise SystemExit(f"ERR: manifest.artifacts.{required} is required")

    token_boot_ref = require_string(token, "boot_release_set_ref")
    manifest_boot_ref = require_string(manifest, "boot_release_set_id")
    if token_boot_ref != manifest_boot_ref:
        raise SystemExit("ERR: token boot_release_set_ref does not match manifest boot_release_set_id")
    token_release_ref = require_string(token, "release_set_ref")
    manifest_release_ref = require_string(manifest, "base_release_set_ref")
    if token_release_ref != manifest_release_ref:
        raise SystemExit("ERR: token release_set_ref does not match manifest base_release_set_ref")

    signature_algorithm = require_string(manifest, "signature_algorithm")
    crypto_profile = require_string(manifest, "crypto_profile")
    if signature_algorithm != "rsa-pss-sha256":
        raise SystemExit("ERR: only rsa-pss-sha256 nlboot manifests are accepted")
    if crypto_profile != "fips-140-3-compatible":
        raise SystemExit("ERR: only fips-140-3-compatible nlboot manifests are accepted")

    source_artifacts = [
        ("kernel", artifacts["kernel_ref"]),
        ("initrd", artifacts["initrd_ref"]),
        ("rootfs", artifacts["rootfs_ref"]),
        ("manifest", require_string(manifest, "manifest_id")),
    ]

    sourceos_mode = BOOT_MODE_MAP[boot_mode]
    boot_modes = [sourceos_mode]
    if sourceos_mode == "recovery":
        boot_modes.append("rollback")

    return {
        "schema_version": "sourceos.boot-release-set/v0",
        "kind": "SourceOSBootReleaseSet",
        "id": "sbrs-nlboot-m2-demo-recovery-0001",
        "description": "SourceOS BootReleaseSet generated from nlboot signed M2 recovery manifest metadata.",
        "created_at": "2026-04-26T19:30:00Z",
        "channel": "dev",
        "parent_release_set_ref": manifest_release_ref,
        "boot_modes": boot_modes,
        "platform_entrypoints": [
            {
                "platform": "apple_silicon",
                "entry_kind": "asahi_installer_entry",
                "entry_ref": manifest_boot_ref,
                "notes": "Generated from nlboot signed manifest; actual Apple Silicon packaging remains a PAL-Mac tranche.",
            },
            {
                "platform": "generic",
                "entry_kind": "disk_image",
                "entry_ref": manifest_boot_ref,
                "notes": "Generic side-effect-free adapter path for nlboot bootstrap media.",
            },
        ],
        "artifacts": [
            {
                "name": f"nlboot-{kind}",
                "artifact_kind": kind,
                "uri": ref,
                "digest": digest_for_ref(ref),
                "size_bytes": 0,
            }
            for kind, ref in source_artifacts
        ],
        "authorization": {
            "mode": "single_use_code" if token.get("one_time_use") is True else "device_claim",
            "token_binding": "device_claim",
            "ttl_seconds": 900,
            "requires_online_redemption": True,
        },
        "capabilities": {
            "disk_write": "scoped" if sourceos_mode in {"installer", "recovery", "rollback"} else "denied",
            "network": "restricted",
            "kexec": "denied",
            "rollback": "allowed" if "rollback" in boot_modes else "denied",
            "enrollment": "allowed",
        },
        "proof_requirements": {
            "emit_fingerprint": True,
            "emit_manifest_hashes": True,
            "emit_boot_log_ref": True,
            "required_report_endpoint": "tritrpc:sourceos.boot.proof.report",
        },
        "offline_fallback": {
            "allowed": True,
            "last_known_good_ref": "sbrs-m2-demo-recovery-0000",
            "max_age_seconds": 604800,
        },
        "signatures": [
            {
                "key_id": require_string(manifest, "signer_ref"),
                "algorithm": "x509",
                "signature_ref": require_string(manifest, "signature_ref"),
            }
        ],
    }


def validate_output(document: dict[str, Any]) -> None:
    schema = load_json(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(document), key=lambda err: list(err.path))
    if errors:
        for err in errors:
            loc = ".".join(str(part) for part in err.path) or "<root>"
            print(f"{loc}: {err.message}")
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert nlboot signed manifest metadata into SourceOS BootReleaseSet")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--token", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    document = convert(load_json(args.manifest), load_json(args.token))
    if not args.no_validate:
        validate_output(document)
    write_json(args.output, document)
    print(f"SourceOS BootReleaseSet written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
