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
    raise SystemExit("ERR: jsonschema is required to validate SourceOS Truth Plane artifacts") from exc

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "contracts" / "sourceos"
DEFAULT_PROOF_DIR = ROOT / "artifacts" / "sourceos" / "m2-lifecycle-proof"
STAMP = "2026-04-26T15:30:00Z"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ERR: required proof artifact is missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


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


def digest_entry(proof_dir: Path, filename: str, object_ref: str) -> dict[str, str]:
    artifact_path = proof_dir / filename
    return {"object_ref": object_ref, "path": filename, "digest": sha256_ref(artifact_path)}


def build_truth_manifest(proof_dir: Path) -> dict[str, Any]:
    config_source = load_json(proof_dir / "config-source.json")
    release_set = load_json(proof_dir / "release-set.json")
    boot_release_set = load_json(proof_dir / "boot-release-set.json")
    nlboot_crosswalk = load_json(proof_dir / "nlboot-crosswalk.json")
    fingerprint = load_json(proof_dir / "fingerprint.json")
    compliance_result = load_json(proof_dir / "compliance-result.json")
    proof_index = load_json(proof_dir / "proof-index.json")

    compliance_status = compliance_result.get("status", "unknown")
    eligible = compliance_status == "compliant"

    manifest = {
        "schema_version": "sourceos.truth-current-manifest/v0",
        "kind": "SourceOSTruthCurrentManifest",
        "id": "stm-m2-demo-current-0001",
        "generated_at": STAMP,
        "subject": fingerprint["subject"],
        "current": {
            "release_set_ref": release_set["id"],
            "boot_release_set_ref": boot_release_set["id"],
            "fingerprint_ref": fingerprint["id"],
            "compliance_result_ref": compliance_result["id"],
            "proof_index_ref": proof_index["id"],
            "previous_boot_receipt_ref": "boot-receipt:m2-demo-0000",
            "current_boot_receipt_ref": "boot-receipt:m2-demo-0001",
        },
        "truth_plane": {
            "service_shape": "fixture",
            "endpoints": [
                {"name": "current-manifest", "method": "GET", "path": "/truth/current-manifest", "returns": "SourceOSTruthCurrentManifest", "notes": "Primary node trust summary consumed by web, Agentplane, GAIA, and Sherlock gates."},
                {"name": "current-release-set", "method": "GET", "path": "/truth/boot-release-set/current", "returns": "SourceOSBootReleaseSet", "notes": "Current bootable release assignment and rollback companion set."},
                {"name": "current-fingerprint", "method": "GET", "path": "/truth/fingerprint/current", "returns": "SourceOSFingerprint", "notes": "Observed runtime state used for drift detection."},
                {"name": "current-compliance", "method": "GET", "path": "/truth/compliance/current", "returns": "SourceOSComplianceResult", "notes": "Comparison of observed state against assigned ReleaseSet and policy."}
            ]
        },
        "integrity": {
            "hash_algorithm": "sha256",
            "object_digests": [
                digest_entry(proof_dir, "config-source.json", config_source["id"]),
                digest_entry(proof_dir, "release-set.json", release_set["id"]),
                digest_entry(proof_dir, "boot-release-set.json", boot_release_set["id"]),
                digest_entry(proof_dir, "nlboot-crosswalk.json", nlboot_crosswalk["id"]),
                digest_entry(proof_dir, "fingerprint.json", fingerprint["id"]),
                digest_entry(proof_dir, "compliance-result.json", compliance_result["id"]),
            ],
            "signature_state": "unsigned_fixture",
            "signature_ref": "sig:fixture-only",
            "crypto_profile": release_set.get("policy", {}).get("crypto_profile", "standard"),
        },
        "status": {
            "compliance": compliance_status,
            "agentplane_eligible": eligible,
            "gaia_ingest_eligible": eligible,
            "sherlock_evidence_eligible": eligible,
            "reasons": [
                "Deterministic fixture links ReleaseSet, BootReleaseSet, Fingerprint, ComplianceResult, and ProofIndex.",
                "Eligibility is true only when the compliance result is compliant.",
                "This fixture is not a live boot execution record and does not claim hardware-root attestation.",
            ],
        },
        "notes": [
            "Truth Plane v0 is represented here as a generated fixture artifact.",
            "The endpoint paths are the intended local service surface for the next implementation tranche.",
        ],
    }
    return manifest


def update_proof_index(proof_dir: Path, truth_path: Path) -> None:
    proof_index_path = proof_dir / "proof-index.json"
    proof_index = load_json(proof_index_path)
    artifacts = proof_index.setdefault("artifacts", [])
    artifacts = [item for item in artifacts if item.get("path") != truth_path.name]
    artifacts.append({
        "name": "truth-current-manifest",
        "kind": "SourceOSTruthCurrentManifest",
        "path": truth_path.name,
        "schema_ref": "contracts/sourceos/truth-current-manifest.v0.schema.json",
        "digest": sha256_ref(truth_path),
    })
    proof_index["artifacts"] = artifacts
    notes = proof_index.setdefault("notes", [])
    note = "Truth Plane current manifest fixture emitted for Agentplane, GAIA, Sherlock, and web trust-panel consumption."
    if note not in notes:
        notes.append(note)
    validate("proof-index.v0.schema.json", proof_index)
    write_json(proof_index_path, proof_index)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SourceOS Truth Plane current manifest fixture from an M2 lifecycle proof bundle")
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--no-update-proof-index", action="store_true")
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args()

    manifest = build_truth_manifest(args.proof_dir)
    if not args.no_validate:
        validate("truth-current-manifest.v0.schema.json", manifest)

    truth_path = args.proof_dir / "truth-current-manifest.json"
    write_json(truth_path, manifest)

    if not args.no_update_proof_index:
        update_proof_index(args.proof_dir, truth_path)

    print(f"SourceOS Truth Plane current manifest written to {truth_path}")
    print("SourceOS Truth Plane fixture passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
