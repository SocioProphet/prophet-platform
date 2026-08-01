#!/usr/bin/env python3
"""Emit a governed Web Intelligence scorecard from component metric events.

Synthesizes `webintel.scorecard.generated.v0` from upstream metric events. The
scorecard's `overall_epistemic_level` is the **meet** (lowest) of its components'
levels — one weak input caps the whole, per the governance thesis — and it
carries a value-driver breakdown so intel arrives with equity-weighted impact.

Actionable: with `--emit` it writes an event/receipt/payload bundle to the
platform state spine, the same layout `apps/web-intel-metrics` reads.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Epistemic lattice, lowest to highest. meet = the lower of two.
_LEVELS = ["rejected", "speculative", "synthetic", "empirical", "bounded", "proved"]

SERVICE = "web-intel-metrics"


def meet_all(levels: list[str]) -> str:
    """The meet (lowest) of a set of epistemic levels; empty -> 'speculative'."""
    ranks = [_LEVELS.index(x) for x in levels if x in _LEVELS]
    if not ranks:
        return "speculative"
    return _LEVELS[min(ranks)]


def _headline(components: list[dict[str, Any]]) -> dict[str, float]:
    head: dict[str, float] = {}
    for c in components:
        if "site_health_score" in c:
            head["site_health_score"] = float(c["site_health_score"])
        if "authority_score" in c:
            head["authority_score"] = float(c["authority_score"])
        if "visibility_score" in c:
            head["ai_visibility_score"] = float(c["visibility_score"])
        if "share_of_voice_pct" in c:
            head["share_of_voice_pct"] = float(c["share_of_voice_pct"])
    return head


def _value_drivers(head: dict[str, float]) -> list[dict[str, Any]]:
    spec = [
        ("Discoverability", "site_health_score", 0.30),
        ("Authority", "authority_score", 0.25),
        ("AI-Search Presence", "ai_visibility_score", 0.25),
        ("Demand Capture", "share_of_voice_pct", 0.20),
    ]
    drivers = []
    for driver, kpi, weight in spec:
        if kpi in head:
            drivers.append({"driver": driver, "kpi": kpi, "score": head[kpi], "equity_weight": weight})
    return drivers


def compute_scorecard(
    components: list[dict[str, Any]],
    *,
    subject: str,
    relation: str,
    tenant_id: str = "socioprophet",
    producer: str = SERVICE,
) -> dict[str, Any]:
    """Build a scorecard payload from component metric events (pure function)."""
    head = _headline(components)
    return {
        "event_id": f"wi-sc-{uuid.uuid4().hex[:12]}",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "producer": producer,
        "subject": subject,
        "relation": relation,
        "overall_epistemic_level": meet_all([c.get("epistemic_level", "speculative") for c in components]),
        "component_event_ids": [c["event_id"] for c in components if "event_id" in c],
        "headline": head,
        "value_drivers": _value_drivers(head),
    }


def _state_root() -> Path:
    home = os.environ.get("SOCIOPROFIT_STATE_HOME")
    base = Path(home) if home else Path.home() / ".local" / "state"
    return base / "prophet-platform"


def emit(scorecard: dict[str, Any]) -> str:
    """Write event/receipt/payload bundle to the state spine. Returns correlation id."""
    corr = scorecard["event_id"]
    root = _state_root()
    for kind, payload in (
        ("payloads", scorecard),
        ("events", {"event_type": "webintel.scorecard.generated.v0", "created_at": scorecard["emitted_at"], "subject_ref": scorecard["subject"]}),
        ("receipts", {"status": "succeeded", "action": "GenerateWebIntelScorecard", "subject_ref": scorecard["subject"], "created_at": scorecard["emitted_at"]}),
    ):
        d = root / kind / SERVICE
        d.mkdir(parents=True, exist_ok=True)
        suffix = {"payloads": "payload", "events": "event", "receipts": "receipt"}[kind]
        (d / f"{corr}.{suffix}.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return corr


def _load_components(in_dir: Path) -> list[dict[str, Any]]:
    comps = []
    for p in sorted(in_dir.glob("*.json")):
        if p.name.startswith("scorecard"):
            continue
        comps.append(json.loads(p.read_text(encoding="utf-8")))
    return comps


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit a governed Web Intelligence scorecard.")
    ap.add_argument("--in", dest="in_dir", required=True, help="Directory of component metric event JSON files.")
    ap.add_argument("--subject", required=True, help="Subject domain.")
    ap.add_argument("--relation", default="self", choices=["self", "competitor", "prospect", "partner"])
    ap.add_argument("--emit", action="store_true", help="Write the bundle to the state spine.")
    args = ap.parse_args()

    components = _load_components(Path(args.in_dir))
    scorecard = compute_scorecard(components, subject=args.subject, relation=args.relation)
    print(json.dumps(scorecard, indent=2, sort_keys=True))
    if args.emit:
        corr = emit(scorecard)
        print(f"emitted: {corr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
