#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest_json(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def bundle_subject_ref(bundle_id: str, version: str) -> str:
    return f"bundle://{bundle_id}@{version}"


def correlation_id(bundle_id: str, version: str) -> str:
    safe = bundle_id.replace(".", "_").replace("/", "_")
    return f"{safe}-{version}"


@dataclass(frozen=True)
class Layout:
    state_root: Path
    service: str

    @property
    def platform_root(self) -> Path:
        return self.state_root / "prophet-platform"

    @property
    def payload_dir(self) -> Path:
        return self.platform_root / "payloads" / self.service

    @property
    def event_dir(self) -> Path:
        return self.platform_root / "events" / self.service

    @property
    def receipt_dir(self) -> Path:
        return self.platform_root / "receipts" / self.service

    @property
    def catalog_file(self) -> Path:
        return self.platform_root / "catalog" / self.service / "receipt_catalog.jsonl"

    def ensure(self) -> None:
        for p in [self.payload_dir, self.event_dir, self.receipt_dir, self.catalog_file.parent]:
            p.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"ERR: expected JSON object in {path}")
    return data


def emit_record(record: dict[str, Any], layout: Layout) -> dict[str, str]:
    bundle_id = str(record["bundle_id"])
    version = str(record["version"])
    corr = correlation_id(bundle_id, version)
    created_at = utc_now()
    subject_ref = bundle_subject_ref(bundle_id, version)

    payload = {
        "kind": "FogStackValidationPayload",
        "record": record,
    }

    payload_path = layout.payload_dir / f"{corr}.payload.json"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload_ref = f"file://{payload_path.resolve()}"

    envelope = {
        "version": "0.1",
        "envelope_id": corr + "-event",
        "created_at": created_at,
        "event_type": "fogstack.validation.record.emitted",
        "producer": "ci://github-actions",
        "subject_ref": subject_ref,
        "payload_ref": payload_ref,
        "scope_ref": "scope://platform/fogstack-release-engineering",
        "correlation_id": corr,
        "classifiers": ["source:ci", "kind:fogstack-validation"],
    }
    env_hash = digest_json(envelope)

    receipt = {
        "version": "0.1",
        "receipt_id": corr + "-receipt",
        "created_at": created_at,
        "service_ref": "ci://github-actions/fogstack-validation",
        "action": "FogStackValidationRecordIngest",
        "status": "succeeded",
        "subject_ref": subject_ref,
        "envelope_ref": f"event://{envelope['envelope_id']}",
        "policy_refs": [],
        "evidence_refs": [str(record.get("evidence_ref")) if record.get("evidence_ref") else payload_ref],
        "output_refs": [payload_ref],
        "metrics": {
            "summary_status": (record.get("summary") or {}).get("status"),
            "exit_code": (record.get("summary") or {}).get("exit_code"),
        },
        "hash": env_hash,
        "hash_algo": "sha256",
        "correlation_id": corr,
    }

    event_path = layout.event_dir / f"{corr}.event.json"
    receipt_path = layout.receipt_dir / f"{corr}.receipt.json"
    event_path.write_text(json.dumps({**envelope, "receipt_ref": f"receipt://{receipt['receipt_id']}"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    catalog_entry = {
        "version": "0.1",
        "entry_id": corr + "-catalog",
        "created_at": created_at,
        "service_ref": layout.service,
        "event_type": envelope["event_type"],
        "status": receipt["status"],
        "subject_ref": subject_ref,
        "scope_ref": envelope["scope_ref"],
        "envelope_ref": f"file://{event_path.resolve()}",
        "receipt_ref": f"file://{receipt_path.resolve()}",
        "payload_ref": payload_ref,
        "correlation_id": corr,
        "classifiers": envelope["classifiers"],
    }
    with layout.catalog_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(catalog_entry, sort_keys=True) + "\n")

    return {
        "correlation_id": corr,
        "payload_ref": payload_ref,
        "event_ref": f"file://{event_path.resolve()}",
        "receipt_ref": f"file://{receipt_path.resolve()}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert FogStack validation records into platform evidence artifacts")
    parser.add_argument("--records-dir", type=Path, required=True, help="Directory containing *.validation.record.json files")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--service", default="fogstack-validation")
    args = parser.parse_args()

    layout = Layout(state_root=args.state_root, service=args.service)
    layout.ensure()

    emitted = []
    for path in sorted(args.records_dir.glob("*.validation.record.json")):
        emitted.append(emit_record(load_json(path), layout))

    print(json.dumps({"service": args.service, "count": len(emitted), "items": emitted}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
