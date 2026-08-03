"""Catalog operational plane — SLO gate (the verdict).

WO-1 (readout.py) turns the captured event stream into KPIs. This turns the KPIs
into a JUDGEMENT: the Assay verdict (ok / sad / bad) a gate can act on, not just a
number a human squints at.

Each objective grades one KPI against two thresholds (ok / sad; below sad = bad).
The overall verdict is the WORST applicable objective — MEET / min semantics, the
same fail-closed rule the estate uses for Truth = Law × Evidence: a single bad
objective makes the whole readout bad, no averaging a failure away.

Small-sample honesty: an objective with fewer than `min_n` observations returns
`insufficient_data` rather than a confident grade, and does NOT drag the overall
verdict — you cannot fail an SLO you have no evidence for, nor pass it. When every
objective is insufficient/na the overall verdict is `insufficient_data` too.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from . import ops, readout

SCHEMA_VERSION = "crystal-atlas.catalog.ops.slo.v0"

# rank for MEET(min): a higher number is worse, so overall = max(rank) → worst verdict.
_GRADED = {"ok": 0, "sad": 1, "bad": 2}
_MIN_N_DEFAULT = 30  # estate rule: a grade needs n>=30 observations or it is not evidence

# Default SLO objectives. Each: (kind, ok_threshold, sad_threshold, direction).
# direction "high" = higher is better (value>=ok → ok); "low" = lower is better.
DEFAULT_SLO: dict[str, dict[str, Any]] = {
    "resolve_hit_rate": {"ok": 0.90, "sad": 0.70, "direction": "high"},
    "dcat_coverage":    {"ok": 0.80, "sad": 0.50, "direction": "high"},
    "cold_source_ratio":{"ok": 0.20, "sad": 0.50, "direction": "low"},
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _grade(value: float | None, ok: float, sad: float, direction: str, n: int,
           min_n: int) -> tuple[str, str]:
    """Return (verdict, note). insufficient_data when value is unknown or n<min_n."""
    if value is None:
        return "insufficient_data", "no observations"
    if n < min_n:
        return "insufficient_data", f"n={n} < min_n={min_n}"
    if direction == "high":
        if value >= ok:
            return "ok", ""
        return ("sad", "") if value >= sad else ("bad", "")
    # direction == "low": lower is better
    if value <= ok:
        return "ok", ""
    return ("sad", "") if value <= sad else ("bad", "")


def evaluate(ro: dict[str, Any] | None = None, *, slo: dict[str, dict[str, Any]] | None = None,
             min_n: int = _MIN_N_DEFAULT) -> dict[str, Any]:
    """Grade a readout against the SLO. Computes a fresh readout if none is passed."""
    ro = ro if ro is not None else readout.compute_readout()
    slo = slo or DEFAULT_SLO

    resolve_total = ro["resolve"]["total"]
    cataloged_sources = ro["sources"]["cataloged"]
    cold = len(ro["sources"]["cold"])

    # objective input values + their sample sizes
    cold_ratio = round(cold / cataloged_sources, 4) if cataloged_sources else None
    inputs = {
        "resolve_hit_rate": (ro["resolve"]["hit_rate"], resolve_total),
        "dcat_coverage": (ro["dcat"]["coverage_of_resolved_assets"], ro["dcat"]["distinct_assets"]),
        "cold_source_ratio": (cold_ratio, cataloged_sources),
    }

    objectives: list[dict[str, Any]] = []
    for name in sorted(slo):
        cfg = slo[name]
        value, n = inputs.get(name, (None, 0))
        verdict, note = _grade(value, cfg["ok"], cfg["sad"], cfg["direction"], n, min_n)
        objectives.append({
            "name": name, "verdict": verdict, "value": value, "n": n,
            "thresholds": {"ok": cfg["ok"], "sad": cfg["sad"], "direction": cfg["direction"]},
            "note": note,
        })

    graded = [o["verdict"] for o in objectives if o["verdict"] in _GRADED]
    overall = max(graded, key=lambda v: _GRADED[v]) if graded else "insufficient_data"

    return {
        "schema_version": SCHEMA_VERSION,
        "slo_id": "slo_" + uuid.uuid4().hex[:16],
        "generated_at": _now(),
        "producer": ops.PRODUCER,
        "readout_ref": ro.get("readout_id"),
        "verdict": overall,
        "objectives": objectives,
        "window": dict(ro["window"]),
    }


def emit_slo(*, slo: dict[str, dict[str, Any]] | None = None,
             min_n: int = _MIN_N_DEFAULT) -> tuple[dict[str, Any], str | None]:
    """Evaluate AND crystallize the verdict as a catalog.ops.slo.v0 event."""
    doc = evaluate(slo=slo, min_n=min_n)
    event_id = ops.emit(SCHEMA_VERSION, dict(doc))
    return doc, event_id
