#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "repo-governance-mvp"
MANIFEST = BUILD / "repo-governance-replay-manifest.json"
FINDINGS = BUILD / "repo-governance-findings.json"
POLICY_REQUESTS = BUILD / "repo-governance-policy-requests.json"
RDF = BUILD / "repo-governance-observations.ttl"
LEDGER = BUILD / "repo-governance-replay-ledger.jsonl"
SIGNATURE_ENVELOPE = BUILD / "repo-governance-replay-signature-envelope.json"


def read_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_digest(obj: object) -> str:
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ledger_record() -> dict:
    manifest = load_json(MANIFEST)
    record = {
        "schema_version": "0.1",
        "kind": "repo_governance_replay_ledger_record",
        "replay_id": manifest["replay_id"],
        "observation_digest": manifest["observation_digest"],
        "artifacts": {
            "manifest_sha256": sha256_file(MANIFEST),
            "findings_sha256": sha256_file(FINDINGS),
            "policy_requests_sha256": sha256_file(POLICY_REQUESTS),
            "rdf_sha256": sha256_file(RDF),
        },
        "mutation_authorized": False,
        "infrastructure_required": False,
    }
    record["record_digest"] = canonical_digest(record)
    return record


def signature_envelope(record: dict) -> dict:
    return {
        "schema_version": "0.1",
        "kind": "repo_governance_replay_signature_envelope",
        "replay_id": record["replay_id"],
        "record_digest": record["record_digest"],
        "signature_status": "unsigned-local-placeholder",
        "signature_algorithm": "none",
        "signing_key_id": None,
        "mutation_authorized": False,
        "note": "This envelope is deterministic and ready for future ed25519 signing, but this local MVP does not create cryptographic signatures.",
    }


def main() -> int:
    BUILD.mkdir(parents=True, exist_ok=True)
    record = ledger_record()
    LEDGER.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    SIGNATURE_ENVELOPE.write_text(json.dumps(signature_envelope(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: wrote {LEDGER.relative_to(ROOT)}")
    print(f"OK: wrote {SIGNATURE_ENVELOPE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
