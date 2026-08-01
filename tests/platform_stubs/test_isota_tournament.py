"""Conformance + invariant tests for the iSOTA provider-neutral tournament harness.

Guards, with teeth proven BOTH ways:
  1. every emitted record validates against the real eval schemas (spec-first);
  2. PROVIDER-NEUTRAL — permuting provider labels changes no verdict, but changing a
     score does (the control is not vacuous);
  3. FAIL-CLOSED Stage 0 — a governance-failing candidate is gated regardless of score,
     and the same candidate with governance restored is scored/promoted;
  4. NO LAUNDERING — a provisional (seed) run emits ZERO reproduced MetricFacts and no
     accepted/rejected status; only a real-results run emits internal_reproduced facts.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "eval"


def _mod():
    path = ROOT / "tools" / "isota_tournament.py"
    spec = importlib.util.spec_from_file_location("isota_tournament", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _corpus():
    return json.loads((ROOT / "tools" / "isota_corpus_seed.json").read_text())["items"]


def test_seed_corpus_items_validate_against_vendored_evalitem_schema():
    schema = json.loads((SCHEMA_DIR / "vendored" / "EvalItem.schema.json").read_text())
    items = _corpus()
    assert items, "seed corpus is empty"
    for it in items:
        jsonschema.validate(it, schema)
    assert {i["corpus"] for i in items} == {"A", "B", "C"}, "all three corpora must be represented"


def test_every_emitted_record_validates_spec_first():
    mod = _mod()
    bundle = mod.build(_corpus(), mod.seed_candidates(), results=None)
    md = json.loads((SCHEMA_DIR / "metric-definition.schema.json").read_text())
    mc = json.loads((SCHEMA_DIR / "model-candidate.schema.json").read_text())
    bc = json.loads((SCHEMA_DIR / "benchmark-contract.schema.json").read_text())
    for d in bundle["definitions"]:
        jsonschema.validate(d, md)
    for c in bundle["candidates"]:
        jsonschema.validate(c, mc)
    for k in bundle["contracts"]:
        jsonschema.validate(k, bc)


def test_provisional_run_emits_zero_reproduced_facts_no_laundering():
    mod = _mod()
    bundle = mod.build(_corpus(), mod.seed_candidates(), results=None)
    assert bundle["facts"] == [], "seed/illustrative run must emit NO reproduced facts"
    assert all(c["status"] == "benchmark_candidate" for c in bundle["candidates"]), \
        "without real results no candidate may be marked accepted/rejected"


def test_real_results_emit_internal_reproduced_facts():
    mod = _mod()
    cands = mod.seed_candidates()
    # a real (measured) result for the two frontier candidates only
    results = {"cand.opus_class": {"value_scalar": 88.4, "sample_n": 610},
               "cand.gpt_class": {"value_scalar": 84.9, "sample_n": 610}}
    bundle = mod.build(_corpus(), cands, results=results)
    mf = json.loads((SCHEMA_DIR / "metric-fact.schema.json").read_text())
    assert len(bundle["facts"]) == 2
    for f in bundle["facts"]:
        jsonschema.validate(f, mf)
        assert f["source_trust_class"] == "internal_reproduced"
        assert f["reproduced_by_us"] is True
        assert f["metric_definition_id"] == mod.COMPOSITE_METRIC_ID
    # with real results, verdicts drive status
    statuses = {c["candidate_id"]: c["status"] for c in bundle["candidates"]}
    assert statuses["cand.opus_class"] in ("accepted", "rejected")


def test_stage0_gated_candidate_in_results_emits_no_fact_and_is_rejected():
    # the exact laundering/fail-closed hole: a governance-gated candidate present in
    # results must NOT yield a reproduced fact, and its status is rejected (fail-closed).
    mod = _mod()
    cands = mod.seed_candidates()
    gated_id = next(c["candidate_id"] for c in cands
                    if mod.run_tournament([c])[c["candidate_id"]]["stage_reached"] == 0)
    results = {gated_id: {"value_scalar": 99.0, "sample_n": 100}}  # even a top score
    bundle = mod.build(_corpus(), cands, results=results)
    assert bundle["facts"] == [], "a Stage-0-gated candidate must not yield a reproduced fact"
    status = {c["candidate_id"]: c["status"] for c in bundle["candidates"]}
    assert status[gated_id] == "rejected"


def test_emitted_status_tracks_measured_value_not_seed_scores():
    # a non-gated candidate whose MEASURED result is below threshold is rejected even
    # if its seed composite would promote — emitted status follows measurement, not seed.
    mod = _mod()
    cands = mod.seed_candidates()
    strong = next(c["candidate_id"] for c in cands
                  if mod.run_tournament([c])[c["candidate_id"]]["promoted"])
    low = {strong: {"value_scalar": 10.0, "sample_n": 50}}
    bundle = mod.build(_corpus(), cands, results=low)
    status = {c["candidate_id"]: c["status"] for c in bundle["candidates"]}
    assert status[strong] == "rejected", "measured value below threshold must reject, ignoring seed score"


def test_provider_neutral_permuting_labels_changes_no_verdict():
    mod = _mod()
    base = mod.seed_candidates()
    base_verdicts = mod.run_tournament(base)
    # permute provider_id labels across candidates; keep scores tied to identity
    permuted = copy.deepcopy(base)
    labels = [c["provider_id"] for c in permuted]
    rotated = labels[1:] + labels[:1]
    for c, lab in zip(permuted, rotated):
        c["provider_id"] = lab
    perm_verdicts = mod.run_tournament(permuted)
    assert perm_verdicts == base_verdicts, "provider label must not affect any verdict"


def test_neutrality_control_is_not_vacuous_score_flips_verdict():
    mod = _mod()
    cands = mod.seed_candidates()
    # a below-threshold candidate lifted above threshold on the heaviest axes must flip
    loser = next(c for c in cands if not mod.run_tournament([c])[c["candidate_id"]]["promoted"])
    before = mod.run_tournament([loser])[loser["candidate_id"]]["promoted"]
    lifted = copy.deepcopy(loser)
    lifted["governance"]["observability"] = True
    for a in ("case_action", "groundedness", "citation", "tool_use", "instruction", "retrieval"):
        lifted["scores"][a] = 95
    after = mod.run_tournament([lifted])[lifted["candidate_id"]]["promoted"]
    assert before is False and after is True, "score changes must be able to change verdicts"


def test_stage0_governance_gate_is_fail_closed_both_ways():
    mod = _mod()
    # a candidate with a governance floor failure is gated at Stage 0 even with top scores
    top = {a: 99 for a in mod.AXIS_WEIGHTS}
    gated = {"candidate_id": "cand.x", "name": "x", "provider_id": "P", "family": "f",
             "governance": {"api": True, "rate": True, "auth": True, "cost": True, "observability": False},
             "scores": top,
             "implementation": {"source_repo": "vendor:x", "source_ref": "r", "license": "l", "runtime_dependencies": []}}
    v = mod.run_tournament([gated])["cand.x"]
    assert v["stage_reached"] == 0 and v["promoted"] is False
    ok = copy.deepcopy(gated)
    ok["governance"]["observability"] = True
    v2 = mod.run_tournament([ok])["cand.x"]
    assert v2["stage_reached"] == 4 and v2["promoted"] is True
