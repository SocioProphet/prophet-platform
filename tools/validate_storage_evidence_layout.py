#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORAGE_RECEIPTS = ROOT / "apps" / "storage-promotion" / "receipts.py"
EVIDENCE_APP = ROOT / "apps" / "evidence-receipts"


def fail(msg: str) -> int:
    print(f"ERR: {msg}", file=sys.stderr)
    return 2


def load_storage_receipts():
    spec = importlib.util.spec_from_file_location("storage_receipts", STORAGE_RECEIPTS)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load storage receipt helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    sys.path.insert(0, str(EVIDENCE_APP))
    from app.store import get_bundle, list_services

    storage_receipts = load_storage_receipts()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(Path(tmp) / "state")
        payload = {"kind": "storage-layout-smoke", "ok": True}
        payload_path, payload_ref = storage_receipts.write_payload(payload, stem="storage-layout-smoke")
        bundle = storage_receipts.make_bundle(
            event_type="storage.layout.smoke",
            action="StorageLayoutSmoke",
            status="succeeded",
            subject_ref="storage://layout-smoke",
            payload_ref=payload_ref,
            correlation_id="storage-layout-smoke",
            classifiers=["slice:storage-promotion", "layout:type-first"],
        )
        event_path, receipt_path = storage_receipts.write_bundle(bundle, stem="storage-layout-smoke")

        if not payload_path.exists() or not event_path.exists() or not receipt_path.exists():
            return fail("storage receipt artifacts were not written")
        services = list_services()
        if "storage-promotion" not in services:
            return fail(f"storage-promotion missing from services: {services}")
        readback = get_bundle(service="storage-promotion", correlation_id="storage-layout-smoke")
        if readback is None:
            return fail("evidence-receipts could not read storage bundle")
        if readback.get("payload") != payload:
            return fail("readback payload mismatch")
        if readback.get("event", {}).get("event_type") != "storage.layout.smoke":
            return fail("readback event mismatch")
        if readback.get("receipt", {}).get("service_ref") != "apps/storage-promotion":
            return fail("readback receipt service mismatch")

    print("OK: storage evidence layout aligns with evidence-receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
