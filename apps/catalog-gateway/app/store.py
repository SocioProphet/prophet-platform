"""Catalog entry store — reads Crystal Atlas catalog entries from the shared
platform file-state layout (the same convention crystal-atlas-contract-intel and
evidence-receipts use).

Entries live at:
    $SOCIOPROFIT_STATE_HOME/prophet-platform/catalog/<kind>/<id>.json

The gateway is read-only over this layout for the first increment; registration
(the write path) lands later.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

SERVICE = "catalog-gateway"
KINDS = ("source", "asset", "model", "workflow")

# ids are opaque handles, but they index into the filesystem — so constrain them
# to a safe charset. This is the path-traversal gate: no "/", no "..", no NUL.
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")


def state_home() -> Path:
    if v := os.environ.get("SOCIOPROFIT_STATE_HOME"):
        return Path(v)
    return Path.home() / ".local" / "state"


def catalog_root() -> Path:
    return state_home() / "prophet-platform" / "catalog"


def is_valid_id(entry_id: str) -> bool:
    # charset gate + explicit ".." reject: "." is legal in ids (versions), so the
    # regex alone would admit ".." — the traversal token — which must be refused.
    return bool(_SAFE_ID.match(entry_id or "")) and ".." not in entry_id


def list_ids(kind: str) -> list[str]:
    """Return the ids of every catalog entry of `kind` (sorted, deterministic).
    Empty on an unknown kind or an absent catalog root — never raises. This is the
    denominator source for coverage KPIs (e.g. which cataloged sources are cold)."""
    if kind not in KINDS:
        return []
    d = catalog_root() / kind
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.json") if p.is_file())


def get_entry(kind: str, entry_id: str) -> dict[str, Any] | None:
    """Return the catalog entry, or None if the kind/id is invalid or absent.
    Fails closed on a bad id (path-traversal attempt) — returns None, never reads
    outside the catalog root."""
    if kind not in KINDS or not is_valid_id(entry_id):
        return None
    path = (catalog_root() / kind / f"{entry_id}.json").resolve()
    root = catalog_root().resolve()
    # defence in depth: the resolved path must stay under the catalog root.
    if root not in path.parents:
        return None
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
