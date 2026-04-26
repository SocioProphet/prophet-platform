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
    raise SystemExit("ERR: jsonschema is required to validate SourceOS lifecycle proof artifacts") from exc

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "contracts" / "sourceos"
DEFAULT_OUT = ROOT / "artifacts" / "sourceos" / "m2-lifecycle-proof"
STAMP = "2026-04-26T15:30:00Z"
NLBOOT_MANIFEST_ID = "urn:srcos:boot-manifest:m2-demo-recovery"
NLBOOT_BOOT_RELEASE_SET_ID = "urn:srcos:boot-release-set:m2-demo-recovery-2026-04-26"
NLBOOT_BASE_RELEASE_SET_REF = "urn:srcos:release-set:m2-demo-2026-04-26"
NLBOOT_TOKEN_ID = "urn:srcos:enrollment-token:m2-demo-recovery"
NLBOOT_SIGNER_REF = "urn:srcos:key:sourceos-demo-signing-key-v0"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def sha256_ref(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate(schema_name: str, document: dict[str, Any]) -> None:
    schema = load_json(SCHEMA_DIR / schema_name)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(document), key=lambda err: list(err.path))
    if errors:
        for err in errors:
            loc = ".".join(str(part) for part in err.path) or "<root>"
            print(f"{schema_name}: {loc}: {err.message}")
        raise SystemExit(1)


def build_objects() -> dict[str, dict[str, Any]]:
    config_source = {
        "schema_version": "sourceos.config-source/v0",
        "kind": "SourceOSConfigSource",
        "id": "scfg-m2-demo-local",
        "source_type": "git",
        "location": {
            "canonical_ref": "git:local/sourceos-m2-demo#main",
            "local_path": "~/dev/sourceos-m2-demo",
            "remote_url": "https://github.com/SocioProphet/sourceos-workspace.git",
        },
        "nix": {
            "entry_kind": "flake",
            "entry_ref": "flake.nix",
            "lock_ref": "flake.lock",
            "outputs": [
                "packages.aarch64-linux.sourceosM2System",
                "packages.aarch64-linux.macosLikeUserProfile",
                "packages.aarch64-linux.agentBaseTools",
            ],
        },
        "refs": {
            "allowed_refs": ["main", "feature/*", "release/*", "refs/tags/*"],
            "stable_ref": "main",
            "branch_channel_map": {"main": "stable", "feature/*": "dev", "release/*": "candidate"},
        },
        "update_policy": {
            "mode": "pull",
            "requires_signature_verification": False,
            "required_status_checks": [],
            "build_trigger": "manual",
        },
        "token_policy": {
            "token_ref": "secret:none",
            "token_kind": "none",
            "storage_rule": "not_applicable",
            "redaction_required": True,
            "allowed_ref_writes": [],
        },
        "cache_policy": {"local_cache": True, "remote_cache": False, "trusted_cache_keys": []},
    }

    release_set = {
        "schema_version": "sourceos.release-set/v0",
        "kind": "SourceOSReleaseSet",
        "id": "srset-m2-demo-0001",
        "description": "M2 demo release set for SourceOS system/user/agent lifecycle proof.",
        "created_at": STAMP,
        "channel": "dev",
        "support_state": "experimental",
        "system": {
            "base_kind": "ostree",
            "base_ref": NLBOOT_BASE_RELEASE_SET_REF,
            "architecture": "aarch64",
            "platform_targets": ["apple_silicon_m2"],
            "host_integration_surface": "hisc-sourceos-m2-v0",
            "rollback_refs": ["urn:srcos:release-set:m2-demo-rollback-2026-04-26"],
        },
        "user": {
            "experience_profile": "xp-macos-like-gnome-v0",
            "ux_archetype": "macos_like",
            "desktop": "gnome",
            "closure_refs": ["nix:closure:user/macos-like-gnome/0001"],
            "degraded_parity_notes": [],
        },
        "agent": {
            "default_isolation": "container",
            "environment_refs": ["nix:closure:agent/base-tools/0001"],
            "capability_policy_ref": "policy:sourceos-agent-standard-v0",
            "risk_policy_ref": "policy:sourceos-risk-isolation-v0",
        },
        "policy": {"policy_bundle_ref": "policy:sourceos-m2-demo-v0", "crypto_profile": "standard", "required_signatures": 1},
        "assignment": {"scope_kind": "device", "scope_id": "device:m2-demo"},
        "provenance": {
            "config_sources": ["scfg-m2-demo-local"],
            "bom_ref": "bom:sourceos-m2-demo-0001",
            "build_ref": "build:sourceos-m2-demo-0001",
            "sbom_refs": ["sbom:sourceos-m2-demo-0001"],
            "evidence_refs": ["evidence:sourceos-m2-demo-build-0001"],
        },
        "signatures": [{"key_id": "sourceos-demo-signing-key-v0", "algorithm": "ed25519", "signature_ref": "sig:sourceos-m2-demo-0001"}],
    }

    boot_release_set = {
        "schema_version": "sourceos.boot-release-set/v0",
        "kind": "SourceOSBootReleaseSet",
        "id": "sbrs-m2-demo-recovery-0001",
        "description": "M2 demo SourceOS recovery/install/live boot release set aligned to SociOS-Linux/nlboot examples/m2-demo.",
        "created_at": STAMP,
        "channel": "dev",
        "parent_release_set_ref": "srset-m2-demo-0001",
        "boot_modes": ["live", "installer", "recovery", "rollback"],
        "platform_entrypoints": [
            {"platform": "apple_silicon", "entry_kind": "asahi_installer_entry", "entry_ref": "installer-tree:sourceos/m2/recovery/0001", "notes": "Boot-picker-visible installer/recovery entry via Apple Silicon/Asahi-compatible path."},
            {"platform": "uefi", "entry_kind": "ipxe", "entry_ref": "ipxe:sourceos/recovery/0001", "notes": "Generic parity path for later PC/Purism support."},
        ],
        "artifacts": [
            {"name": "sourceos-recovery-kernel", "artifact_kind": "kernel", "uri": "urn:srcos:artifact:m2-demo-kernel", "digest": "sha256:" + "0" * 64, "size_bytes": 0},
            {"name": "sourceos-recovery-initrd", "artifact_kind": "initrd", "uri": "urn:srcos:artifact:m2-demo-initrd", "digest": "sha256:" + "1" * 64, "size_bytes": 0},
            {"name": "sourceos-recovery-rootfs", "artifact_kind": "rootfs", "uri": "urn:srcos:artifact:m2-demo-rootfs", "digest": "sha256:" + "2" * 64, "size_bytes": 0},
            {"name": "nlboot-recovery-manifest", "artifact_kind": "manifest", "uri": NLBOOT_MANIFEST_ID, "digest": "sha256:" + "3" * 64, "size_bytes": 0},
        ],
        "authorization": {"mode": "single_use_code", "token_binding": "device_claim", "ttl_seconds": 900, "requires_online_redemption": True},
        "capabilities": {"disk_write": "scoped", "network": "restricted", "kexec": "allowed", "rollback": "allowed", "enrollment": "allowed"},
        "proof_requirements": {"emit_fingerprint": True, "emit_manifest_hashes": True, "emit_boot_log_ref": True, "required_report_endpoint": "tritrpc:sourceos.boot.proof.report"},
        "offline_fallback": {"allowed": True, "last_known_good_ref": "sbrs-m2-demo-recovery-0000", "max_age_seconds": 604800},
        "signatures": [{"key_id": "sourceos-demo-signing-key-v0", "algorithm": "ed25519", "signature_ref": "sig:sourceos-m2-demo-recovery-0001"}],
    }

    nlboot_crosswalk = {
        "schema_version": "sourceos.nlboot-crosswalk/v0",
        "kind": "SourceOSNlbootCrosswalk",
        "id": "snx-m2-demo-0001",
        "created_at": STAMP,
        "source_repo": "SociOS-Linux/nlboot",
        "fixture_path": "examples/m2-demo",
        "nlboot_manifest_id": NLBOOT_MANIFEST_ID,
        "nlboot_token_id": NLBOOT_TOKEN_ID,
        "nlboot_signer_ref": NLBOOT_SIGNER_REF,
        "release_set": {"sourceos_id": release_set["id"], "nlboot_ref": NLBOOT_BASE_RELEASE_SET_REF},
        "boot_release_set": {"sourceos_id": boot_release_set["id"], "nlboot_ref": NLBOOT_BOOT_RELEASE_SET_ID},
        "artifact_map": [
            {"sourceos_name": "sourceos-recovery-kernel", "nlboot_ref": "urn:srcos:artifact:m2-demo-kernel"},
            {"sourceos_name": "sourceos-recovery-initrd", "nlboot_ref": "urn:srcos:artifact:m2-demo-initrd"},
            {"sourceos_name": "sourceos-recovery-rootfs", "nlboot_ref": "urn:srcos:artifact:m2-demo-rootfs"},
        ],
        "safety_boundary": [
            "nlboot fixture remains side-effect-free",
            "no artifact fetching",
            "no host mutation",
            "no disk writes",
            "no kexec execution",
            "plans remain execute=false",
        ],
    }

    fingerprint = {
        "schema_version": "sourceos.fingerprint/v0",
        "kind": "SourceOSFingerprint",
        "id": "sfp-m2-demo-0001",
        "observed_at": STAMP,
        "subject": {"subject_kind": "device", "subject_id": "device:m2-demo", "device_claim": "device-claim:m2-demo-public-key-fingerprint"},
        "system": {"architecture": "aarch64", "kernel": "sourceos-demo-kernel", "boot_mode": "normal", "system_base_ref": release_set["system"]["base_ref"], "rollback_available": True},
        "runtime": {"isolation": "host", "libc": "glibc", "shell": "bash", "tool_dialect": "gnu", "pid1": "systemd"},
        "lsm": {"selinux_visible": False, "selinux_mode": "not_visible", "apparmor_visible": False, "landlock_visible": False, "host_enforced_possible": True},
        "policy": {"policy_bundle_ref": release_set["policy"]["policy_bundle_ref"], "release_set_ref": release_set["id"], "boot_release_set_ref": boot_release_set["id"], "capability_manifest_ref": "capabilities:sourceos-m2-demo-0001", "network_scope": "restricted", "filesystem_scope": "scoped"},
        "provenance": {"config_source_refs": [config_source["id"]], "closure_refs": release_set["user"]["closure_refs"] + release_set["agent"]["environment_refs"], "artifact_digests": [boot_release_set["artifacts"][0]["digest"], boot_release_set["artifacts"][1]["digest"]], "evidence_refs": ["evidence:sourceos-m2-demo-fingerprint-0001"]},
        "compliance": {"status": "compliant", "reasons": ["Observed release, policy, architecture, and rollback state match assigned demo release."]},
    }

    compliance_result = {
        "schema_version": "sourceos.compliance-result/v0",
        "kind": "SourceOSComplianceResult",
        "id": "scr-m2-demo-0001",
        "evaluated_at": STAMP,
        "subject": {"subject_kind": "device", "subject_id": "device:m2-demo"},
        "expected": {"release_set_ref": release_set["id"], "boot_release_set_ref": boot_release_set["id"], "policy_bundle_ref": release_set["policy"]["policy_bundle_ref"]},
        "observed": {"fingerprint_ref": fingerprint["id"], "release_set_ref": fingerprint["policy"]["release_set_ref"], "boot_release_set_ref": fingerprint["policy"]["boot_release_set_ref"], "policy_bundle_ref": fingerprint["policy"]["policy_bundle_ref"]},
        "status": "compliant",
        "checks": [
            {"name": "release-set-match", "status": "pass", "expected": release_set["id"], "observed": fingerprint["policy"]["release_set_ref"]},
            {"name": "policy-bundle-match", "status": "pass", "expected": release_set["policy"]["policy_bundle_ref"], "observed": fingerprint["policy"]["policy_bundle_ref"]},
            {"name": "rollback-available", "status": "pass", "expected": "true", "observed": str(fingerprint["system"]["rollback_available"]).lower()},
        ],
        "evidence_refs": ["evidence:sourceos-m2-demo-compliance-0001"],
    }

    return {
        "config-source.json": config_source,
        "release-set.json": release_set,
        "boot-release-set.json": boot_release_set,
        "nlboot-crosswalk.json": nlboot_crosswalk,
        "fingerprint.json": fingerprint,
        "compliance-result.json": compliance_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic local SourceOS M2 lifecycle proof bundle")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    objects = build_objects()
    schema_by_file = {
        "config-source.json": "config-source.v0.schema.json",
        "release-set.json": "release-set.v0.schema.json",
        "boot-release-set.json": "boot-release-set.v0.schema.json",
        "fingerprint.json": "fingerprint.v0.schema.json",
        "compliance-result.json": "compliance-result.v0.schema.json",
    }

    if not args.no_validate:
        for name, document in objects.items():
            if name in schema_by_file:
                validate(schema_by_file[name], document)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, document in objects.items():
        write_json(args.output_dir / name, document)

    kind_by_file = {
        "config-source.json": "SourceOSConfigSource",
        "release-set.json": "SourceOSReleaseSet",
        "boot-release-set.json": "SourceOSBootReleaseSet",
        "nlboot-crosswalk.json": "SourceOSNlbootCrosswalk",
        "fingerprint.json": "SourceOSFingerprint",
        "compliance-result.json": "SourceOSComplianceResult",
    }
    artifacts = []
    for name in objects:
        path = args.output_dir / name
        artifacts.append({"name": name.removesuffix(".json"), "kind": kind_by_file[name], "path": name, "schema_ref": f"contracts/sourceos/{schema_by_file[name]}" if name in schema_by_file else "docs/SOURCEOS_NLBOOT_CROSSWALK.md", "digest": sha256_ref(path)})

    proof_index = {
        "schema_version": "sourceos.proof-index/v0",
        "kind": "SourceOSProofIndex",
        "id": "spi-m2-demo-0001",
        "created_at": STAMP,
        "proof_kind": "m2_lifecycle_demo",
        "summary": "Deterministic local SourceOS M2 lifecycle proof bundle covering ConfigSource, ReleaseSet, BootReleaseSet, nlboot fixture crosswalk, Fingerprint, and ComplianceResult.",
        "artifacts": artifacts,
        "sociosphere_registration_ref": "SocioProphet/sociosphere#196",
        "notes": ["This is a deterministic local proof fixture, not a live boot execution record.", "The nlboot crosswalk maps prophet-platform SourceOS contracts to SociOS-Linux/nlboot examples/m2-demo."],
    }
    if not args.no_validate:
        validate("proof-index.v0.schema.json", proof_index)
    write_json(args.output_dir / "proof-index.json", proof_index)

    print(f"SourceOS M2 lifecycle proof bundle written to {args.output_dir}")
    print("SourceOS M2 lifecycle proof passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
