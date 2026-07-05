#!/usr/bin/env python3
"""Generate datastore seed SQL for the intelligence-superiority metric bundle.

Single source of truth is the schema-validated producer
(``emit_intelligence_superiority_metrics.build``); this tool maps that canonical
bundle onto the real eval-fabric table schemas so the facts get *persisted*
rather than only served in-process by dashboard-bff.

Emits two numbered seed files picked up automatically by ``eval_fabric_migrate``:
  * Postgres   ``infra/datastores/postgres/006_intelligence_superiority_seed.sql``
      -> ``metric_definitions`` (6 rows)
  * ClickHouse ``infra/datastores/clickhouse/003_intelligence_superiority_seed.sql``
      -> ``metric_facts``       (9 rows)

Deferred on purpose: ``source_descriptors`` rows and the ``metric_crosswalks``
row. Those live in Postgres and reference descriptor ids whose FK ordering is
not yet verified here; seeding them belongs in a follow-up that confirms the
source_descriptors seed covers src_socioprophet / src_anthropic / src_openai /
noetica_operator_board.

Run ``python3 tools/gen_intelligence_superiority_seed.py`` to (re)generate, or
``--check`` to print the row counts without writing (used by the test).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ARTIFACT = ROOT / "build" / "eval" / "intelligence-superiority-metrics.json"
PG_SEED = ROOT / "infra" / "datastores" / "postgres" / "006_intelligence_superiority_seed.sql"
CH_SEED = ROOT / "infra" / "datastores" / "clickhouse" / "003_intelligence_superiority_seed.sql"

# Full ClickHouse metric_facts column order (infra/datastores/clickhouse/001_eval_fabric.sql).
# Columns absent from a metric-fact record are filled with schema-honest defaults
# ('' for unset String dimensions, '{}' for value_json, 0 for uncollected numerics).
_CH_FACT_COLUMNS = [
    "ts", "metric_fact_id", "metric_definition_id", "source_descriptor_id",
    "provider_id", "model_release_id", "benchmark_suite_id", "scenario_id",
    "case_id", "run_id", "trial_id", "context_slice_id", "risk_tier",
    "autonomy_tier", "eval_regime", "value_scalar", "value_json",
    "sample_n", "trial_count", "cost_usd", "latency_ms_p50", "latency_ms_p95",
    "latency_ms_p99", "freshness_days", "contamination_risk",
    "reproduced_by_us", "source_trust_class",
]
_PG_DEF_COLUMNS = [
    "metric_definition_id", "name", "family", "regime", "unit",
    "direction", "value_type", "normalizer",
]


def load_bundle() -> dict:
    """Read the canonical emitted artifact (stable, reviewed snapshot; deterministic ts).

    Falls back to the in-process producer only if the artifact is absent, so a
    fresh checkout can still generate. Preferring the artifact keeps regenerated
    seeds byte-stable instead of churning ``ts`` on every run (build() stamps now()).
    """
    if BUNDLE_ARTIFACT.exists():
        return json.loads(BUNDLE_ARTIFACT.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "tools"))
    import emit_intelligence_superiority_metrics as producer  # type: ignore

    return producer.build()


def _sql_str(value: object) -> str:
    """Render a value as a single-quoted SQL string literal, escaping quotes."""
    return "'" + str(value).replace("'", "''") + "'"


def _ch_datetime(iso_ts: str) -> str:
    """ISO-8601 (with tz/microseconds) -> ClickHouse ``DateTime`` 'YYYY-MM-DD HH:MM:SS' in UTC."""
    dt = datetime.fromisoformat(iso_ts)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _fact_row(fact: dict) -> str:
    values = {
        "ts": _sql_str(_ch_datetime(fact["ts"])),
        "metric_fact_id": _sql_str(fact["metric_fact_id"]),
        "metric_definition_id": _sql_str(fact["metric_definition_id"]),
        "source_descriptor_id": _sql_str(fact["source_descriptor_id"]),
        "provider_id": _sql_str(fact["provider_id"]),
        "model_release_id": _sql_str(fact["model_release_id"]),
        "benchmark_suite_id": _sql_str(fact["benchmark_suite_id"]),
        # sample_n and scenario_id are absent on cited frontier facts (no disclosed
        # sample/scenario); default to unknown rather than fabricate a value.
        "scenario_id": _sql_str(fact.get("scenario_id", "")),
        "case_id": "''",
        "run_id": "''",
        "trial_id": "''",
        "context_slice_id": "''",
        "risk_tier": "''",
        "autonomy_tier": "''",
        "eval_regime": _sql_str(fact["eval_regime"]),
        "value_scalar": repr(float(fact["value_scalar"])),
        "value_json": "'{}'",
        "sample_n": str(int(fact.get("sample_n", 0))),
        "trial_count": "0",
        "cost_usd": "0",
        "latency_ms_p50": "0",
        "latency_ms_p95": "0",
        "latency_ms_p99": "0",
        "freshness_days": str(int(fact["freshness_days"])),
        "contamination_risk": "''",
        "reproduced_by_us": "1" if fact["reproduced_by_us"] else "0",
        "source_trust_class": _sql_str(fact["source_trust_class"]),
    }
    return "  (" + ", ".join(values[c] for c in _CH_FACT_COLUMNS) + ")"


def _def_row(defn: dict) -> str:
    return "  (" + ", ".join(_sql_str(defn[c]) for c in _PG_DEF_COLUMNS) + ")"


def render_pg(bundle: dict) -> str:
    rows = ",\n".join(_def_row(d) for d in bundle["definitions"])
    return (
        "-- GENERATED by tools/gen_intelligence_superiority_seed.py -- do not edit by hand.\n"
        "-- Persists the intelligence-superiority metric DEFINITIONS (Postgres).\n"
        f"insert into metric_definitions (\n  {', '.join(_PG_DEF_COLUMNS)}\n) values\n"
        f"{rows};\n"
    )


def render_ch(bundle: dict) -> str:
    rows = ",\n".join(_fact_row(f) for f in bundle["facts"])
    return (
        "-- GENERATED by tools/gen_intelligence_superiority_seed.py -- do not edit by hand.\n"
        "-- Persists the intelligence-superiority metric FACTS (ClickHouse).\n"
        f"insert into metric_facts (\n  {', '.join(_CH_FACT_COLUMNS)}\n) values\n"
        f"{rows};\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="print row counts, do not write")
    args = parser.parse_args()

    bundle = load_bundle()
    n_defs, n_facts = len(bundle["definitions"]), len(bundle["facts"])

    if args.check:
        print(json.dumps({"definitions": n_defs, "facts": n_facts}))
        return 0

    PG_SEED.write_text(render_pg(bundle), encoding="utf-8")
    CH_SEED.write_text(render_ch(bundle), encoding="utf-8")
    print(f"wrote {PG_SEED.relative_to(ROOT)} ({n_defs} definitions)")
    print(f"wrote {CH_SEED.relative_to(ROOT)} ({n_facts} facts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
