#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

PACKS: dict[str, dict[str, str]] = {
    "access": {
        "bundle_id": "fogstack.access",
        "version": "0.1.0",
        "bundle": "bundles/fogstack.access-v0.1.yaml",
        "manifest": "releases/manifests/fogstack.access-v0.1.manifest.json",
    }
}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run(cmd: list[str], *, stdout: Path | None = None) -> None:
    if stdout:
        stdout.parent.mkdir(parents=True, exist_ok=True)
        with stdout.open("w", encoding="utf-8") as handle:
            subprocess.run(cmd, cwd=ROOT, check=True, stdout=handle)
    else:
        subprocess.run(cmd, cwd=ROOT, check=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_demo(pack: str, output_dir: Path, clean: bool) -> dict[str, Any]:
    if pack not in PACKS:
        raise SystemExit(f"ERR: unsupported FogStack local demo pack: {pack}")

    cfg = PACKS[pack]
    bundle_id = cfg["bundle_id"]
    version = cfg["version"]
    bundle = ROOT / cfg["bundle"]
    manifest = ROOT / cfg["manifest"]
    support_catalog = ROOT / "catalog" / "fogstack-support-states-v0.1.yaml"
    promotion_policy = ROOT / "catalog" / "fogstack-manifest-promotion-policy-v0.1.yaml"
    approver_policy = ROOT / "catalog" / "fogstack-manifest-promotion-approver-policy-v0.1.yaml"
    publication_gate_policy = ROOT / "catalog" / "fogstack-release-publication-gate-policy-v0.1.yaml"

    required = [bundle, manifest, support_catalog, promotion_policy, approver_policy, publication_gate_policy]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise SystemExit("ERR: missing local demo inputs: " + ", ".join(rel(path) for path in missing))

    output_dir = output_dir if output_dir.is_absolute() else ROOT / output_dir
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    validation_dir = output_dir / "validation"
    publication_dir = output_dir / "publication"
    promoted_dir = output_dir / "promoted"
    approval_dir = output_dir / "approval"
    gate_dir = output_dir / "gate"
    registry_publication_dir = output_dir / "registry-publication"
    registry_root_dir = output_dir / "registry"
    lifecycle_dir = output_dir / "lifecycle"
    root_dir = output_dir / "root"

    verify_json = validation_dir / f"{bundle_id}.verify.json"
    validation_record = validation_dir / f"{bundle_id}.validation.record.json"

    run([
        sys.executable,
        "tools/fogstack_verify.py",
        str(bundle),
        "--json",
    ], stdout=verify_json)

    run([
        sys.executable,
        "tools/emit_fogstack_validation_record.py",
        "--verifier-json", str(verify_json),
        "--bundle-id", bundle_id,
        "--version", version,
        "--source", "local",
        "--evidence-ref", rel(verify_json),
        "--output", str(validation_record),
    ])

    run([
        sys.executable,
        "tools/build_fogstack_manifest_publication_set.py",
        "--output-dir", str(publication_dir),
        "--manifest", str(manifest),
        "--signature-type", "other",
        "--signature-ref-prefix", "artifact://local-demo/signatures",
    ])

    run([
        sys.executable,
        "tools/promote_fogstack_manifest_publication_set.py",
        "--input-dir", str(publication_dir),
        "--output-dir", str(promoted_dir),
        "--support-catalog", str(support_catalog),
        "--target-channel", "candidate",
        "--target-support-state", "supported",
    ])

    promoted_set = promoted_dir / "manifest-publication-set.json"
    run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_policy.py",
        "--publication-set", str(promoted_set),
        "--policy-catalog", str(promotion_policy),
    ])

    approval_record = approval_dir / "fogstack.manifest-promotion.approval.record.json"
    approval_sig = approval_dir / "fogstack.manifest-promotion.approval.sig"
    approval_private = approval_dir / "private.pem"
    approval_public = approval_dir / "public.pem"
    approval_verification = approval_dir / "fogstack.manifest-promotion.approval.signature-verification.json"

    run([
        sys.executable,
        "tools/emit_fogstack_manifest_promotion_approval_record.py",
        "--promotion-set", str(promoted_set),
        "--required-approvals", "2",
        "--approval", "release-manager:release-manager:approved local demo candidate promotion",
        "--approval", "security-reviewer:security-reviewer:approved local demo release evidence",
        "--signature-type", "other",
        "--signature-ref", str(approval_sig),
        "--output", str(approval_record),
    ])

    run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_approval_record.py",
        "--approval-record", str(approval_record),
        "--promotion-set", str(promoted_set),
        "--require-signed",
    ])
    run([
        sys.executable,
        "tools/check_fogstack_manifest_promotion_approver_policy.py",
        "--approval-record", str(approval_record),
        "--approver-policy", str(approver_policy),
    ])

    approval_dir.mkdir(parents=True, exist_ok=True)
    run(["openssl", "genpkey", "-algorithm", "RSA", "-out", str(approval_private)])
    run(["openssl", "pkey", "-in", str(approval_private), "-pubout", "-out", str(approval_public)])
    run([
        "openssl", "dgst", "-sha256",
        "-sign", str(approval_private),
        "-out", str(approval_sig),
        str(approval_record),
    ])
    run([
        sys.executable,
        "tools/run_openssl_fogstack_manifest_promotion_approval_verifier.py",
        "--approval-record", str(approval_record),
        "--signature", str(approval_sig),
        "--public-key", str(approval_public),
        "--key-ref", str(approval_public),
        "--output", str(approval_verification),
    ])

    release_identity = gate_dir / "release-identity.json"
    write_json(release_identity, {
        "kind": "FogStackReleaseIdentity",
        "schema_version": "v0.1",
        "id": "github-actions",
        "issuer": "github-actions",
        "subject": "SocioProphet/prophet-platform/.github/workflows/fogstack-manifest-promotion.yml",
    })

    publication_gate = gate_dir / "fogstack.release-publication-gate.record.json"
    run([
        sys.executable,
        "tools/emit_fogstack_release_publication_gate_record.py",
        "--publication-set", str(promoted_set),
        "--approval-record", str(approval_record),
        "--approval-signature-verification", str(approval_verification),
        "--release-identity", str(release_identity),
        "--policy-catalog", str(publication_gate_policy),
        "--output", str(publication_gate),
    ])

    registry_index = registry_publication_dir / "registry-publication.index.json"
    run([
        sys.executable,
        "tools/build_fogstack_registry_publication_index.py",
        "--registry-uri", f"file://{rel(registry_root_dir)}",
        "--publication-set", str(promoted_set),
        "--publication-gate-record", str(publication_gate),
        "--artifact", "manifest-publication-set", str(promoted_set),
        "--artifact", "approval-record", str(approval_record),
        "--artifact", "approval-signature-verification", str(approval_verification),
        "--artifact", "release-publication-gate", str(publication_gate),
        "--artifact", "validation-record", str(validation_record),
        "--notes", "local demo filesystem registry publication",
        "--output", str(registry_index),
    ])

    run([
        sys.executable,
        "tools/publish_fogstack_filesystem_registry.py",
        "--index", str(registry_index),
        "--registry-root", str(registry_root_dir),
        "--bundle-id", bundle_id,
        "--version", version,
    ], stdout=registry_publication_dir / "release-pointer.json")
    run([
        sys.executable,
        "tools/check_fogstack_filesystem_registry.py",
        "--registry-root", str(registry_root_dir),
        "--bundle-id", bundle_id,
        "--version", version,
    ])

    revocation_index = lifecycle_dir / "registry-revocation-index.json"
    run([
        sys.executable,
        "tools/build_fogstack_registry_revocation_index.py",
        "--output", str(revocation_index),
    ])
    run([
        sys.executable,
        "tools/check_fogstack_registry_revocation_index.py",
        "--index", str(revocation_index),
    ])

    registry_root_metadata = root_dir / "registry-root-metadata.json"
    release_root = registry_root_dir / bundle_id / version
    run([
        sys.executable,
        "tools/build_fogstack_registry_root_metadata.py",
        "--registry-uri", f"file://{rel(registry_root_dir)}",
        "--release", bundle_id, version, str(release_root),
        "--revocation-index", str(revocation_index),
        "--signature-type", "other",
        "--signature-ref", "artifact://local-demo/registry-root.sig",
        "--output", str(registry_root_metadata),
    ])
    run([
        sys.executable,
        "tools/check_fogstack_registry_root_metadata.py",
        "--root", str(registry_root_metadata),
        "--require-signed",
    ])

    summary = {
        "kind": "FogStackLocalDemoRun",
        "schema_version": "v0.1",
        "bundle_id": bundle_id,
        "version": version,
        "registry_uri": f"file://{rel(registry_root_dir)}",
        "channel": "candidate",
        "support_state": "supported",
        "artifacts": {
            "verify_json": rel(verify_json),
            "validation_record": rel(validation_record),
            "publication_set": rel(publication_dir / "manifest-publication-set.json"),
            "promoted_publication_set": rel(promoted_set),
            "approval_record": rel(approval_record),
            "approval_signature_verification": rel(approval_verification),
            "publication_gate": rel(publication_gate),
            "registry_publication_index": rel(registry_index),
            "filesystem_release_pointer": rel(release_root / "release-pointer.json"),
            "revocation_index": rel(revocation_index),
            "registry_root_metadata": rel(registry_root_metadata),
        },
        "checks": [
            "bundle_verified",
            "validation_record_emitted",
            "publication_set_built",
            "promotion_policy_passed",
            "approval_record_checked",
            "approval_signature_verified",
            "publication_gate_passed",
            "registry_index_built",
            "filesystem_registry_published",
            "filesystem_registry_checked",
            "revocation_index_checked",
            "registry_root_checked",
        ],
    }
    summary_path = output_dir / "fogstack-local-demo.summary.json"
    write_json(summary_path, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local FogStack release/registry demo end to end")
    parser.add_argument("--pack", choices=sorted(PACKS), default="access")
    parser.add_argument("--output-dir", type=Path, default=Path("build/fogstack-local-demo"))
    parser.add_argument("--no-clean", action="store_true", help="Do not remove the output directory before running")
    args = parser.parse_args()

    summary = build_demo(args.pack, args.output_dir, clean=not args.no_clean)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
