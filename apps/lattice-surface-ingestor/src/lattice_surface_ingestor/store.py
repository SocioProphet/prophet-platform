"""Deterministic local record store for Lattice platform asset records.

This module is deliberately file-based and side-effect-scoped. It writes only to
a caller-provided directory so the first catalog/evidence persistence path can be
validated without introducing a database dependency or long-running service.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ASSET_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def sanitize_asset_id(asset_id: str) -> str:
    sanitized = ASSET_ID_SAFE_RE.sub("_", asset_id).strip("_")
    if not sanitized:
        raise ValueError("assetId produced an empty filename")
    return sanitized


def write_record_set(record_set: dict[str, Any], output_dir: Path) -> list[Path]:
    """Write a PlatformAssetRecordSet into deterministic per-record JSON files."""

    if record_set.get("kind") != "PlatformAssetRecordSet":
        raise ValueError("record_set.kind must be PlatformAssetRecordSet")
    records = record_set.get("records")
    if not isinstance(records, list):
        raise ValueError("record_set.records must be a list")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each record must be an object")
        asset_id = record.get("assetId")
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("each record must include a non-empty assetId")
        path = output_dir / f"{sanitize_asset_id(asset_id)}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)

    manifest = {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordStoreManifest",
        "recordCount": len(written),
        "records": [path.name for path in written],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.append(manifest_path)
    return written
