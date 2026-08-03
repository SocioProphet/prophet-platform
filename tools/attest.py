#!/usr/bin/env python3
"""Emit externally-verifiable SLSA provenance for a governed action — with our governance inside it.

The competitive research was blunt: our hash-sealed receipts are self-issued and self-verified,
whereas the industry standard (Sigstore/SLSA/in-toto) is EXTERNALLY verifiable with off-the-shelf
tooling (cosign, slsa-verifier) against a public root of trust. This tool repairs that — and turns
the weakness into a lead — by emitting a standards-conformant **in-toto v1 statement carrying a
SLSA v1 provenance predicate, wrapped in a DSSE envelope** (exactly what cosign signs and verifies)
for a re-vendor action, with our fail-closed governance (the sealed verdict, the marker proof, the
receipt digest) embedded in the predicate.

The result: a third party verifies the provenance with standard tooling, AND sees the governance
evidence no competitor pairs with it. Production signing is keyless cosign against our own zot (the
`--cosign` invocation is printed); the built-in HMAC signer is a dependency-free, verifiable default
for CI/tests so the format is exercised end-to-end without a live Fulcio.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
SLSA_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
BUILD_TYPE = "https://socioprophet.org/slsa/revendor/v1"


def build_statement(subject_name: str, subject_digest: str, revendor_receipt: dict) -> dict:
    """A conformant in-toto v1 statement + SLSA v1 provenance predicate, with our governance
    embedded. `subject_digest` is 'sha256:<hex>' (as the executor's receipts carry it)."""
    algo, _, hexd = subject_digest.partition(":")
    if not hexd:
        raise ValueError(f"subject_digest must be '<algo>:<hex>', got {subject_digest!r}")

    steps = {s.get("step"): s for s in revendor_receipt.get("steps", [])}
    marker = (steps.get("assert_marker") or {}).get("evidence", {})
    # Our governance, embedded in the standard predicate — the pairing no competitor has.
    governance = {
        "receipt_tool": revendor_receipt.get("tool"),
        "receipt_digest": revendor_receipt.get("receipt_digest"),
        "status": revendor_receipt.get("status"),
        "idempotency_key": revendor_receipt.get("idempotency_key"),
        "fail_closed": True,
        "marker_proof": {"expected_present": marker.get("expected_present"),
                         "member": marker.get("member")},
        "requires_human_approval": revendor_receipt.get("requires_human_approval", False),
    }
    return {
        "_type": IN_TOTO_STATEMENT_TYPE,
        "subject": [{"name": subject_name, "digest": {algo: hexd}}],
        "predicateType": SLSA_PREDICATE_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": BUILD_TYPE,
                "externalParameters": {
                    "toVersion": revendor_receipt.get("to_version"),
                    "consumers": revendor_receipt.get("consumers"),
                    "requestedByEventRef": revendor_receipt.get("requested_by_event_ref"),
                },
                "internalParameters": {"governance": governance},
                "resolvedDependencies": [{"uri": "sovereign-registry:zot", "digest": {algo: hexd}}],
            },
            "runDetails": {
                "builder": {"id": "https://socioprophet.org/prophet-platform/revendor_engine.v1"},
                "metadata": {"invocationId": revendor_receipt.get("idempotency_key")},
                "byproducts": [{"name": "revendor-receipt.receipt_digest",
                                "content": revendor_receipt.get("receipt_digest")}],
            },
        },
    }


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (the exact bytes that get signed), per the DSSE spec:
    "DSSEv1" SP LEN(type) SP type SP LEN(payload) SP payload."""
    t = payload_type.encode("utf-8")
    return (b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" "
            + str(len(payload)).encode() + b" " + payload)


def sign_envelope(statement: dict, signer, keyid: str = "") -> dict:
    """Wrap a statement in a signed DSSE envelope. `signer(pae_bytes) -> signature_bytes`."""
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = signer(dsse_pae(DSSE_PAYLOAD_TYPE, payload))
    return {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": base64.standard_b64encode(payload).decode("ascii"),
        "signatures": [{"keyid": keyid, "sig": base64.standard_b64encode(signature).decode("ascii")}],
    }


def verify_envelope(envelope: dict, verifier) -> bool:
    """Verify a DSSE envelope. `verifier(pae_bytes, signature_bytes) -> bool`. Every signature
    must verify against the PAE recomputed from the payload — a tampered payload fails."""
    payload = base64.standard_b64decode(envelope["payload"])
    pae = dsse_pae(envelope.get("payloadType", DSSE_PAYLOAD_TYPE), payload)
    sigs = envelope.get("signatures") or []
    return bool(sigs) and all(verifier(pae, base64.standard_b64decode(s["sig"])) for s in sigs)


def hmac_signer(key: bytes):
    return lambda pae: hmac.new(key, pae, hashlib.sha256).digest()


def hmac_verifier(key: bytes):
    return lambda pae, sig: hmac.compare_digest(hmac.new(key, pae, hashlib.sha256).digest(), sig)


def _cosign_hint(statement_path: Path) -> str:
    return (f"cosign attest-blob --predicate {statement_path} "
            f"--type slsaprovenance --yes <artifact>   # keyless via Fulcio, pushed to zot")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Emit SLSA/in-toto/DSSE provenance for a re-vendor, governance embedded.")
    ap.add_argument("--receipt", type=Path, required=True, help="the executor's sealed re-vendor receipt JSON")
    ap.add_argument("--subject-name", required=True, help="artifact name (e.g. socioprophet-hellgraph-0.4.45.tgz)")
    ap.add_argument("--subject-digest", required=True, help="'sha256:<hex>' of the artifact")
    ap.add_argument("--out", type=Path, help="write the DSSE envelope here (default stdout)")
    ap.add_argument("--statement-only", action="store_true", help="emit the unsigned in-toto statement (for `cosign attest-blob`)")
    args = ap.parse_args(argv)

    receipt = json.loads(args.receipt.read_text())
    statement = build_statement(args.subject_name, args.subject_digest, receipt)

    if args.statement_only:
        out = json.dumps(statement, indent=2, sort_keys=True)
        print(f"# sign this with cosign for external verifiability:\n# {_cosign_hint(args.out or Path('statement.json'))}", file=sys.stderr)
    else:
        key = os.environ.get("ATTEST_HMAC_KEY", "").encode() or os.urandom(32)
        envelope = sign_envelope(statement, hmac_signer(key), keyid="hmac-sha256:local")
        if not os.environ.get("ATTEST_HMAC_KEY"):
            print("# note: ATTEST_HMAC_KEY unset — used an ephemeral key (not reproducibly verifiable). "
                  "For external verifiability sign with cosign (--statement-only).", file=sys.stderr)
        out = json.dumps(envelope, indent=2, sort_keys=True)

    if args.out:
        args.out.write_text(out + "\n")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
