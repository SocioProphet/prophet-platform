#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Fog Stack release seal signature metadata")
    parser.add_argument("--seal", required=True, type=Path)
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    seal = load_json(args.seal)
    signed = seal.get("signed")
    signature = seal.get("signature")
    checks = []

    def record(rule_id: str, status: str, message: str) -> None:
        checks.append({"id": rule_id, "status": status, "message": message})

    if signed is True:
        record("SEALSIG-001", "pass", "seal marked signed")
    elif signed is False:
        if args.require_signed:
            record("SEALSIG-001", "fail", "seal is not marked signed")
        else:
            record("SEALSIG-001", "warn", "seal is unsigned")
    else:
        record("SEALSIG-001", "fail", "seal missing boolean 'signed' field")

    if signed is True:
        if not isinstance(signature, dict):
            record("SEALSIG-002", "fail", "signed seal missing signature object")
        else:
            sig_type = signature.get("type")
            sig_ref = signature.get("ref")
            if sig_type in {"cosign", "sigstore", "other"}:
                record("SEALSIG-002", "pass", f"signature type present: {sig_type}")
            else:
                record("SEALSIG-002", "fail", f"invalid signature type: {sig_type!r}")
            if isinstance(sig_ref, str) and sig_ref.strip():
                record("SEALSIG-003", "pass", "signature reference present")
            else:
                record("SEALSIG-003", "fail", "signature reference missing or empty")
    else:
        record("SEALSIG-002", "skip", "signature object not required for unsigned seal")
        record("SEALSIG-003", "skip", "signature reference not required for unsigned seal")

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
        "tool": "fogstack verify-seal-signature",
        "subject": str(args.seal),
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
        print(f"{args.seal} status={overall} checks={len(checks)}")
        for item in checks:
            print(f"- {item['status'].upper():5s} {item['id']} {item['message']}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
