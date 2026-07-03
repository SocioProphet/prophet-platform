"""Conformance + honesty tests for the intelligence-superiority metric producer.

Guards two things the schema enforces and we must never regress:
  1. every emitted record validates against the real eval schemas (spec-first);
  2. the HONESTY invariants — our numbers are internal_reproduced/reproduced_by_us=true, cited numbers
     are official_provider/false, and no cross-benchmark "superiority" is asserted (our MMLU number and a
     frontier GPQA/FrontierMath number live on DIFFERENT metric_definition_ids).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "eval"


def _producer():
    path = ROOT / "tools" / "emit_intelligence_superiority_metrics.py"
    spec = importlib.util.spec_from_file_location("emit_metrics", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"metric-{name}.schema.json").read_text())


def test_every_record_validates_against_the_real_schema():
    mod = _producer()
    bundle = mod.build()
    for d in bundle["definitions"]:
        jsonschema.validate(d, _schema("definition"))
    for f in bundle["facts"]:
        jsonschema.validate(f, _schema("fact"))
    for x in bundle["crosswalks"]:
        jsonschema.validate(x, _schema("crosswalk"))


def test_our_facts_are_reproduced_cited_facts_are_not():
    bundle = _producer().build()
    for f in bundle["facts"]:
        if f["provider_id"] == "socioprophet":
            assert f["reproduced_by_us"] is True
            assert f["source_trust_class"] == "internal_reproduced"
        else:
            assert f["reproduced_by_us"] is False
            assert f["source_trust_class"] == "official_provider"


def test_no_cross_benchmark_superiority_pairing_is_possible():
    # the ONLY metric where we and a frontier provider both have facts must be NONE — our numbers sit on
    # metrics we reproduced (mmlu_stem, kg_triple), theirs on metrics we did not (gpqa, swebench, ...).
    bundle = _producer().build()
    ours = {f["metric_definition_id"] for f in bundle["facts"] if f["reproduced_by_us"]}
    cited = {f["metric_definition_id"] for f in bundle["facts"] if not f["reproduced_by_us"]}
    assert ours.isdisjoint(cited), (
        "a metric has both reproduced and cited facts — that would let the dashboard render a direct "
        "cross-provider comparison the honesty discipline forbids without an independent-harness reproduction"
    )


def test_the_valid_superiority_claim_is_present_and_significant():
    # within our OWN reproduced facts on mmlu_stem_accuracy, verified-compute must beat the baseline.
    bundle = _producer().build()
    mmlu = [f for f in bundle["facts"] if f["metric_definition_id"] == "mmlu_stem_accuracy" and f["reproduced_by_us"]]
    baseline = next(f for f in mmlu if f["model_release_id"] == "noetica-7b-baseline")
    compute = [f for f in mmlu if f["model_release_id"] == "noetica-7b-verified-compute"]
    assert all(c["value_scalar"] > baseline["value_scalar"] for c in compute), "verified-compute must lead baseline"
    assert baseline["sample_n"] >= 30, "the min-N discipline: no accuracy claim below n=30"
