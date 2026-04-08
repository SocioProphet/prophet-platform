from __future__ import annotations

import hashlib
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from .catalog import append_entry, make_entry
from .paths import ensure_service_dirs, payloads_root
from .receipts import make_bundle, write_bundle, utc_now


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _payload_path(stem: str, *, service: str = "lampstand") -> Path:
    ensure_service_dirs(service)
    return payloads_root(service) / f"{stem}.CarrierIngested.json"


def build_carrier_ingested(
    *,
    path: Path,
    scope_ref: str,
    service_ref: str = "apps/lampstand",
) -> dict[str, Any]:
    content_sha256 = _sha256_file(path)
    event_id = str(uuid.uuid4())
    mime, _ = mimetypes.guess_type(str(path))
    payload = {
        "version": "0.1",
        "event_id": event_id,
        "created_at": utc_now(),
        "service_ref": service_ref,
        "carrier_ref": f"carrier://sha256/{content_sha256}",
        "source_path": str(path.resolve()),
        "content_sha256": content_sha256,
        "size_bytes": path.stat().st_size,
        "scope_ref": scope_ref,
        "receipt": {
            "hash": "",
            "algo": "sha256"
        }
    }
    if mime:
        payload["mime_type"] = mime
    return payload


def ingest_path(
    *,
    file_path: str,
    scope_ref: str = "scope://local/default",
    service_ref: str = "apps/lampstand",
    classifiers: list[str] | None = None,
) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)

    payload = build_carrier_ingested(path=path, scope_ref=scope_ref, service_ref=service_ref)
    payload_path = _payload_path(payload["event_id"])
    payload_ref = f"file://{payload_path}"

    inferred_classifiers = list(classifiers or [])
    suffix = path.suffix.lower().lstrip(".")
    if suffix:
        inferred_classifiers.append(f"suffix:{suffix}")
    inferred_classifiers.append("event:carrier.ingested")
    inferred_classifiers.append("service:lampstand")

    bundle = make_bundle(
        event_type="carrier.ingested",
        action="CarrierIngest",
        status="succeeded",
        subject_ref=payload["carrier_ref"],
        payload_ref=payload_ref,
        service_ref=service_ref,
        scope_ref=scope_ref,
        correlation_id=payload["event_id"],
        classifiers=sorted(set(inferred_classifiers)),
        metrics={
            "size_bytes": payload["size_bytes"],
            "source_path": payload["source_path"],
            "content_sha256": payload["content_sha256"],
        },
        output_refs=[payload_ref],
    )

    event_path, receipt_path = write_bundle(bundle, stem=payload["event_id"])

    payload["receipt"] = {
        "hash": bundle.receipt["hash"],
        "algo": bundle.receipt["hash_algo"],
    }
    payload["evidence_receipt_ref"] = f"file://{receipt_path.resolve()}"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    entry = make_entry(
        service_ref=service_ref,
        event_type=bundle.envelope["event_type"],
        status=bundle.receipt["status"],
        subject_ref=bundle.envelope["subject_ref"],
        scope_ref=scope_ref,
        envelope_ref=f"file://{event_path.resolve()}",
        receipt_ref=f"file://{receipt_path.resolve()}",
        payload_ref=f"file://{payload_path.resolve()}",
        correlation_id=bundle.envelope["correlation_id"],
        classifiers=bundle.envelope.get("classifiers", []),
    )
    catalog_path = append_entry(entry)

    return {
        "ok": True,
        "carrier_ref": payload["carrier_ref"],
        "payload_path": str(payload_path),
        "event_path": str(event_path),
        "receipt_path": str(receipt_path),
        "catalog_path": str(catalog_path),
        "entry": entry,
    }
