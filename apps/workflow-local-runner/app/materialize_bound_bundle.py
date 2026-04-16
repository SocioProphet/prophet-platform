from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bound_bundle import build_bound_bundle


def materialize_bound_bundle(
    *,
    service: str,
    correlation_id: str,
    workflow_run: dict[str, Any],
    execution_envelope: dict[str, Any],
    event_doc: dict[str, Any],
    receipt_doc: dict[str, Any],
    payload_doc: dict[str, Any],
    catalog_entry: dict[str, Any],
    platform_root: Path,
) -> Path:
    """Write the richer bound-bundle projection to disk as a first-class artifact.

    This does not alter receipt canon. It materializes a derived artifact that downstream
    tooling can inspect, sign, or publish.
    """

    bundle = build_bound_bundle(
        workflow_run=workflow_run,
        execution_envelope=execution_envelope,
        event_doc=event_doc,
        receipt_doc=receipt_doc,
        payload_doc=payload_doc,
        catalog_entry=catalog_entry,
    )

    bundle_dir = platform_root / "bundles" / service
    bundle_dir.mkdir(parents=True, exist_ok=True)
    out_path = bundle_dir / f"{correlation_id}.bound_bundle.json"
    out_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
