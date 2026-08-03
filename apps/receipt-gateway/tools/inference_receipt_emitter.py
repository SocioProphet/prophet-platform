#!/usr/bin/env python3
"""InferenceReceipt emitter + hash-chained ledger (reference implementation).

This is the emitter side of the Model Plane: when an inference completes, it writes a
schema-conformant, hash-chained InferenceReceipt to an append-only ledger (SEAM-011:
no local-only ledger; the chain makes it tamper-evident). The receipt/ledger machinery
is REAL and self-proven here; wiring it to a live model is one call to `emit_receipt`.

HONEST BOUNDARY: no local model runs (no weights present), so `--selftest` exercises the
emitter with clearly-labelled synthetic completions (task "selftest"). It proves the
emitter produces conformant receipts and an unbroken, tamper-evident chain — NOT that a
real LLM completion occurred. Point `emit_receipt` at a real provider to emit real receipts.

exit 0 ok; 1 = conformance/chain failure; 2 = usage error.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl  # POSIX advisory locking (Linux/macOS)
except ImportError:  # pragma: no cover
    fcntl = None

try:
    import jsonschema
except ImportError:
    print("ERR: jsonschema not installed", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "model-plane" / "InferenceReceipt.schema.json"

_UNSET = object()  # distinguishes "estimate it" from an explicit None (record null)


def sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _last_entry(f) -> dict | None:
    """Last non-blank ledger entry, constant memory (deque(maxlen=1) over the file)."""
    f.seek(0)
    tail = deque((line for line in f if line.strip()), maxlen=1)
    return json.loads(tail[0]) if tail else None


def emit_receipt(ledger: Path, *, base_model_digest: str, task: str, input_text: str,
                 output_text: str, provider_daemon: str = "inferenced", tier: str = "T1",
                 tokenizer_digest: str | None = None, compute_device: str = "cpu",
                 input_token_count=_UNSET, output_token_count=_UNSET) -> dict:
    """Append one on-device InferenceReceipt to the hash-chained ledger, return it.

    Read-tail + append happen under an exclusive advisory lock so concurrent emitters
    cannot race into duplicate ledgerSeq or a broken chain (single-writer per entry).
    """
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a+", encoding="utf-8") as f:
        if fcntl is not None:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            prev = _last_entry(f)
            seq = (prev["ledgerSeq"] + 1) if prev else 0
            receipt = {
                "id": f"urn:srcos:inference-receipt:{task}-{seq}",
                "type": "InferenceReceipt",
                "specVersion": "2.1.0",
                "issuedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "providerDaemon": provider_daemon,
                "tier": tier,
                "baseModelDigest": base_model_digest,
                "tokenizerDigest": tokenizer_digest,
                "task": task,
                "inputHash": sha256(input_text),
                # real provider token counts when supplied; explicit None -> null (e.g.
                # embeddings have no output tokens); _UNSET -> a whitespace estimate.
                "inputTokenCount": len(input_text.split()) if input_token_count is _UNSET else input_token_count,
                "outputHash": sha256(output_text),
                "outputTokenCount": len(output_text.split()) if output_token_count is _UNSET else output_token_count,
                "dataResidencyClass": "on_device_only",
                "escalatedFrom": None,
                "escalationChain": [],
                "computeDevice": compute_device,
                "ledgerSeq": seq,
            }
            if seq >= 1:
                # hash-chain: bind this entry to the canonical prior entry (SEAM-011)
                receipt["ledgerPrevHash"] = sha256(canonical(prev))
            f.write(canonical(receipt) + "\n")
            f.flush()
        finally:
            if fcntl is not None:
                fcntl.flock(f, fcntl.LOCK_UN)
    return receipt


def verify_ledger(ledger: Path, validator: "jsonschema.Draft202012Validator") -> tuple[bool, str]:
    if not ledger.exists():
        return False, f"ledger not found: {ledger}"
    try:
        lines = [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError as exc:
        return False, f"cannot read ledger: {exc}"
    prev = None
    for i, line in enumerate(lines):
        try:
            r = json.loads(line)
        except json.JSONDecodeError as exc:
            return False, f"entry {i} is not valid JSON: {exc}"
        errs = sorted(validator.iter_errors(r), key=lambda e: list(e.path))
        if errs:
            return False, f"entry {i} schema-invalid: {errs[0].message}"
        if r["ledgerSeq"] != i:
            return False, f"entry {i} has ledgerSeq {r['ledgerSeq']} (expected {i})"
        if i >= 1:
            expect = sha256(canonical(prev))
            if r.get("ledgerPrevHash") != expect:
                return False, f"entry {i} chain broken: ledgerPrevHash != hash(entry {i-1})"
        prev = r
    return True, f"{len(lines)} receipts: schema-conformant + unbroken hash-chain"


def _selftest() -> int:
    import tempfile
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    # A REAL model content-address (from the local ollama manifest); the completion is
    # synthetic self-test data — no model is run here.
    digest = "sha256:aabd4debf0c8f08881923f2c25fc0fdeed24435271c2b3e92c4af36704040dbc"
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "ledger.jsonl"
        for i in range(3):
            emit_receipt(ledger, base_model_digest=digest, task="selftest",
                         input_text=f"selftest prompt {i}", output_text=f"selftest completion {i}")
        ok, msg = verify_ledger(ledger, validator)
        if not ok:
            print(f"FAIL selftest: {msg}", file=sys.stderr)
            return 1
        print(f"OK emitter: {msg}")
        # Tamper-evidence (teeth both ways): mutate entry 1, chain must break.
        lines = ledger.read_text(encoding="utf-8").splitlines()
        e1 = json.loads(lines[1]); e1["outputHash"] = sha256("tampered")
        lines[1] = canonical(e1); ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, msg = verify_ledger(ledger, validator)
        if ok:
            print("FAIL selftest: tamper NOT detected — chain has no teeth", file=sys.stderr)
            return 1
        print(f"OK tamper-evidence: mutation detected — {msg}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--selftest":
        return _selftest()
    print("usage: inference_receipt_emitter.py --selftest", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
