"""Conformance tests for the intelligence-superiority datastore seed generator.

Guards that the persisted seed stays faithful to the canonical metric bundle:
  1. the committed seed files are IN SYNC with the bundle (drift guard — re-emitting
     metrics without regenerating the seed must fail here, not silently ship stale rows);
  2. every ClickHouse metric_facts row has exactly the 27 columns the real table declares;
  3. the honesty split survives into the seed (our facts reproduced_by_us=1/internal_reproduced,
     cited facts =0/official_provider), same invariant the producer test enforces upstream.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The bundle artifact is gitignored, so in CI the generator falls back to the producer, whose ts is
# stamped at build() time. Normalize the ts literal before the drift compare so the guard checks the
# facts (ids/values/columns) — the thing that must not silently drift — not the emission timestamp.
_TS_LITERAL = re.compile(r"'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d'")


def _norm_ts(sql: str) -> str:
    return _TS_LITERAL.sub("'<TS>'", sql)


def _gen():
    path = ROOT / "tools" / "gen_intelligence_superiority_seed.py"
    spec = importlib.util.spec_from_file_location("gen_superiority_seed", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _fact_rows(sql: str) -> list[str]:
    return [ln.strip().rstrip(",").rstrip(";") for ln in sql.splitlines() if ln.startswith("  (")]


def test_committed_seeds_are_in_sync_with_the_bundle():
    # Drift guard: what the generator produces from the current bundle must equal what is committed.
    gen = _gen()
    bundle = gen.load_bundle()
    assert gen.render_pg(bundle) == gen.PG_SEED.read_text(encoding="utf-8"), (
        "postgres seed is stale — run `python3 tools/gen_intelligence_superiority_seed.py`"
    )
    assert _norm_ts(gen.render_ch(bundle)) == _norm_ts(gen.CH_SEED.read_text(encoding="utf-8")), (
        "clickhouse seed is stale — run `python3 tools/gen_intelligence_superiority_seed.py`"
    )


def test_seed_row_counts_match_the_bundle():
    gen = _gen()
    bundle = gen.load_bundle()
    def_rows = [ln for ln in gen.PG_SEED.read_text().splitlines() if ln.startswith("  (")]
    fact_rows = _fact_rows(gen.CH_SEED.read_text())
    assert len(def_rows) == len(bundle["definitions"]) == 6
    assert len(fact_rows) == len(bundle["facts"]) == 9


def test_every_clickhouse_row_has_all_27_columns():
    gen = _gen()
    assert len(gen._CH_FACT_COLUMNS) == 27
    for row in _fact_rows(gen.CH_SEED.read_text()):
        # inner "( ... )" — value_json is the only field with braces, no embedded commas, so a plain
        # top-level split is exact here.
        inner = row[row.index("(") + 1 : row.rindex(")")]
        assert len(inner.split(", ")) == 27, f"row is not 27-wide: {row[:60]}..."


def test_honesty_split_survives_into_the_seed():
    gen = _gen()
    ch = gen.CH_SEED.read_text()
    for row in _fact_rows(ch):
        if "'socioprophet'" in row:
            assert row.rstrip(")").endswith("1, 'internal_reproduced'"), "our facts must be reproduced/internal"
        else:
            assert row.rstrip(")").endswith("0, 'official_provider'"), "cited facts must be not-reproduced/official"


def test_seed_files_are_auto_discovered_numbered_migrations():
    # eval_fabric_migrate picks up files whose first 3 chars are digits; keep that contract.
    gen = _gen()
    assert gen.PG_SEED.name[:3].isdigit()
    assert gen.CH_SEED.name[:3].isdigit()
