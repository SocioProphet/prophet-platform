#!/usr/bin/env python3
"""Rail orchestrator (Workspace Control Plane, Phase 4 / D4).

Routes each root through its declared rail and aggregates governed output:

* **mirror** — connector produces indexed assets + events; the root's
  `delta_cursor` is advanced (incremental).
* **live**   — events only, no cached assets; cursor advances.
* **action** — no ingestion here (side effects run through `workflow-run`).

The orchestrator does not fetch anything itself — it drives the Phase-3
connectors, so the mirror/live/action split is enforced structurally rather than
mixed into one uncontrolled access path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from connector_roots import RootConnector


@dataclass
class RailResult:
    """Per-root outcome of an orchestration pass."""

    root_id: str
    rail: str
    assets: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    new_cursor: Any = None
    deferred_to_workflow: bool = False


VALID_RAILS = ("mirror", "live", "action")


def orchestrate(
    roots: list[dict[str, Any]],
    connectors: dict[str, RootConnector],
) -> list[RailResult]:
    """Run one orchestration pass across roots, honoring each root's rail.

    `connectors` maps `root_id -> RootConnector`. Returns a `RailResult` per root
    with its (possibly advanced) delta cursor; the caller persists cursors back
    onto the roots.
    """
    results: list[RailResult] = []
    for root in roots:
        root_id = root["root_id"]
        rail = root.get("sync_mode", "mirror")
        if rail not in VALID_RAILS:
            # Keep the mirror/live/action split structural: reject unknown rails.
            raise ValueError(f"unknown sync_mode {rail!r} for root {root_id!r}; expected one of {VALID_RAILS}")
        conn = connectors.get(root_id)
        if conn is None:
            raise KeyError(f"no connector registered for root {root_id!r}")

        if rail == "action":
            # The action rail performs side effects via workflow-run, not ingestion.
            results.append(RailResult(root_id=root_id, rail=rail, new_cursor=root.get("delta_cursor"),
                                      deferred_to_workflow=True))
            continue

        assets, events, cursor = conn.sync(root, root.get("delta_cursor"))
        results.append(RailResult(root_id=root_id, rail=rail, assets=assets, events=events, new_cursor=cursor))
    return results


def apply_cursors(roots: list[dict[str, Any]], results: list[RailResult]) -> None:
    """Persist advanced delta cursors back onto the root records (in place)."""
    by_id = {r["root_id"]: r for r in roots}
    for res in results:
        if res.root_id in by_id:
            by_id[res.root_id]["delta_cursor"] = res.new_cursor
