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


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Fog Stack signed-manifest metadata")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    signed = manifest.get("signed")
    signature = manifest.get("signature")
    checks: list[dict[str, Any]] = []

    def record(rule_id: str, status: str, message: str) -> None:
        checks.append({"id": rule_id, "status": status, "message": message})

    if signed is True:
        record("SIG-001", "pass", "manifest marked signed")
    elif signed is False:
        if args.require_signed:
            record("SIG-001", "fail", "manifest is not marked signed")
        else:
            record("SIG-001", "warn", "manifest is unsigned")
    else:
        record("SIG-001", "fail", "manifest missing boolean 'signed' field")

    if signed is True:
        if not isinstance(signature, dict):
            record("SIG-002", "fail", "signed manifest missing signature object")
        else:
            sig_type = signature.get("type")
            sig_ref = signature.get("ref")
            if sig_type in {"cosign", "sigstore", "other"}:
                record("SIG-002", "pass", f"signature type present: {sig_type}")
            else:
                record("SIG-002", "fail", f"invalid signature type: {sig_type!r}")
            if isinstance(sig_ref, str) and sig_ref.strip():
                record("SIG-003", "pass", "signature reference present")
            else:
                record("SIG-003", "fail", "signature reference missing or empty")
    else:
        record("SIG-002", "skip", "signature object not required for unsigned manifest")
        record("SIG-003", "skip", "signature reference not required for unsigned manifest")

    statuses = [c["status"] for c in checks]
    if "fail" in statuses:
        overall = "fail"
        exit_code = 2
    elif "warn" in statuses:
        overall = "warn"
        exit_code = 0
    else:
        overall = "pass"
        exit_code = 0

    result = {
        "tool": "fogstack verify-signature",
        "subject": str(args.manifest),
        "summary": {
            "status": overall,
            "exit_code": exit_code,
            "checks_run": len(checks)
        },
        "checks": checks
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{args.manifest} status={overall} checks={len(checks)}")
        for item in checks:
            print(f"- {item['status'].upper():5s} {item['id']} {item['message']}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
