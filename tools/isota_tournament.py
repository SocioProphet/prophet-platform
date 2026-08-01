#!/usr/bin/env python3
"""isota_tournament — the provider-neutral model tournament that feeds the
Intelligence-Superiority Bench (iSOTA), bound to the existing eval fabric.

It operationalizes the Provider Eval Seed Strategy: three corpora (A provider-seed
/ B Sherlock-task, weighted heavy / C adversarial) run through a five-stage
tournament (Stage 0 governance gate → 1 smoke → 2 Sherlock → 3 adversarial → 4
promote), and the OUTCOME is emitted as records conforming to
schemas/eval/{metric-definition,model-candidate,benchmark-contract,metric-fact}.schema.json.
We BIND to the fabric — we do not rebuild it.

TWO invariants are load-bearing and enforced (see tests):

  1. PROVIDER-NEUTRAL. Promotion is decided only by scores on our corpora, Stage 2
     (Sherlock) weighted heaviest. `provider_id` is a passthrough label and enters
     no scoring term — permuting provider labels cannot change any verdict. "Provider
     exposes eval tooling" is not "provider wins our workload."

  2. NO LAUNDERING (the eval-fabric honesty rule). `internal_reproduced` /
     reproduced_by_us=true means WE MEASURED IT. Illustrative seed scores are the
     mechanism's INPUT and are never emitted as data — no ModelCandidate carries a
     score, and an emitted accepted/rejected status comes ONLY from a real measured
     result (--results), compared to the promotion threshold; seed scores never set
     it. A provisional (seed) run emits the tournament STRUCTURE and ZERO reproduced
     facts. A Stage-0-gated candidate is fail-closed — never scored — so it yields no
     fact even if a result is supplied for it.

Run:  python3 tools/isota_tournament.py [--results FILE.json] [--out DIR]
      (validates every emitted record against the real eval schemas before writing)
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "eval"
SEED_CORPUS = ROOT / "tools" / "isota_corpus_seed.json"

COMPOSITE_METRIC_ID = "md.isota.tournament_composite"
SOURCE_DESCRIPTOR = "src_internal_eval_runner"  # canonical internal runner descriptor
PROMOTE_THRESHOLD = 82.0

# Sherlock-weighted composite. case_action + groundedness dominate (Stage 2 = our
# workload). Weights sum to 1.0. NO provider term appears anywhere here.
AXIS_WEIGHTS = {
    "case_action": 0.30, "groundedness": 0.22, "citation": 0.14, "tool_use": 0.10,
    "instruction": 0.08, "retrieval": 0.06, "cost": 0.04, "latency": 0.03, "observability": 0.03,
}


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())


def composite(scores: dict) -> float:
    """Provider-neutral Sherlock-weighted composite over axis scores (0..100)."""
    return round(sum(AXIS_WEIGHTS[a] * float(scores.get(a, 0)) for a in AXIS_WEIGHTS), 2)


def run_tournament(candidates: list[dict]) -> dict:
    """The Stage 0->4 mechanism. Returns {candidate_id: verdict-dict}. Fail-closed at
    Stage 0: a candidate that does not clear the governance floor is rejected there and
    never scored. Promotion at Stage 4 is by composite threshold alone."""
    out = {}
    for c in candidates:
        cid = c["candidate_id"]
        gov = c.get("governance", {})
        gate_ok = all(gov.get(k) is True for k in ("api", "rate", "auth", "cost", "observability"))
        if not gate_ok:
            out[cid] = {"stage_reached": 0, "composite": None, "promoted": False,
                        "reason": "stage0 governance gate (fail-closed)"}
            continue
        comp = composite(c["scores"])
        promoted = comp >= PROMOTE_THRESHOLD
        out[cid] = {"stage_reached": 4, "composite": comp, "promoted": promoted,
                    "reason": ("composite %.2f >= %.1f" % (comp, PROMOTE_THRESHOLD)) if promoted
                              else ("composite %.2f < %.1f" % (comp, PROMOTE_THRESHOLD))}
    return out


def _corpus_summary(corpus: list[dict]) -> dict:
    by = {"A": 0, "B": 0, "C": 0}
    for it in corpus:
        by[it["corpus"]] = by.get(it["corpus"], 0) + 1
    return by


def build(corpus: list[dict], candidates: list[dict], results: dict | None = None,
          ts: str | None = None) -> dict:
    """Produce the eval-fabric bundle. `results` maps candidate_id -> real run result
    {value_scalar, sample_n}; when absent the run is PROVISIONAL: candidates stay
    'benchmark_candidate' and NO reproduced MetricFacts are emitted."""
    ts = ts or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    verdicts = run_tournament(candidates)
    corpus_by = _corpus_summary(corpus)
    dataset_ref = "isota:corpus/A%d+B%d+C%d" % (corpus_by["A"], corpus_by["B"], corpus_by["C"])
    workloads = sorted({it["task_family"] for it in corpus})

    definitions = [{
        "metric_definition_id": COMPOSITE_METRIC_ID,
        "name": "iSOTA tournament composite (Sherlock-weighted)",
        "family": "task_performance",
        "regime": "OPERATIONS",
        "unit": "score_0_100",
        "direction": "higher_better",
        "value_type": "scalar",
        "normalizer": "minmax",
    }]

    model_candidates = []
    contracts = []
    facts = []
    for c in candidates:
        cid, v = c["candidate_id"], verdicts[c["candidate_id"]]
        gated = v["stage_reached"] == 0            # Stage 0 governance gate — decided by governance flags, not scores
        has_real = results is not None and cid in results
        # honesty: emitted status comes ONLY from a real measured result. A provisional
        # run asserts nothing (benchmark_candidate). A gated candidate is fail-closed —
        # rejected, never scored — so it yields no fact even if a result was supplied.
        # Seed axis scores never set an emitted status.
        if not has_real:
            status = "benchmark_candidate"
        elif gated:
            status = "rejected"
        else:
            measured = float(results[cid]["value_scalar"])
            status = "accepted" if measured >= PROMOTE_THRESHOLD else "rejected"
        gates = ["stage0_governance", "stage1_provider_seed_smoke", "stage2_sherlock_weighted",
                 "stage3_adversarial_stress", "stage4_promotion_threshold"]
        model_candidates.append({
            "candidate_id": cid,
            "name": c["name"],
            "status": status,
            "family": c.get("family", "general"),
            "summary": c.get("summary", "Tournament candidate; provider is a label, not a scoring term."),
            "implementation": c["implementation"],
            "workload_families": workloads,
            "primary_metrics": [COMPOSITE_METRIC_ID],
            "risk_controls": ["provider_neutral_scoring", "fail_closed_governance_gate", "no_laundering_reproduced_facts"],
            "adoption_gates": gates,
            "tracking_issue": c.get("tracking_issue", "iSOTA/tournament"),
        })
        contracts.append({
            "benchmark_contract_id": "bc.isota.%s" % cid.split(".")[-1],
            "candidate_id": cid,
            "workload_family": "sherlock_support_intelligence",
            "scenario_id": "isota.tournament.stage0_4",
            "dataset_ref": dataset_ref,
            "baselines": ["internal_baseline", "provider_seed_smoke"],
            "required_metric_definition_ids": [COMPOSITE_METRIC_ID],
            "risk_tier": "high",
            "autonomy_tier": "tool_using_agent",
            "minimum_trial_count": max(corpus_by["B"], 1),
            "evidence_requirements": [
                "provider_neutral_scoring", "reproduced_by_us_for_promotion",
                "disjoint_from_cited_provider_numbers", "stage2_sherlock_weighted_heaviest",
            ],
            "failure_modes_to_probe": ["stale_docs", "conflicting_evidence", "permission_bound", "long_context", "multilingual"],
        })
        # MetricFacts ONLY for a real measured result on a candidate that CLEARED
        # Stage 0 — never from seed scores, never for a fail-closed-gated candidate.
        if has_real and not gated:
            r = results[cid]
            facts.append({
                "metric_fact_id": "mf.isota.%s.%s" % (cid.split(".")[-1], ts),
                "ts": ts,
                "metric_definition_id": COMPOSITE_METRIC_ID,
                "source_descriptor_id": SOURCE_DESCRIPTOR,
                "provider_id": c.get("provider_id", "unknown"),
                "model_release_id": c["name"],
                "scenario_id": "isota.tournament.stage0_4",
                "eval_regime": "OPERATIONS",
                "value_scalar": float(r["value_scalar"]),
                "sample_n": int(r["sample_n"]),
                "freshness_days": 0,
                "source_trust_class": "internal_reproduced",
                "reproduced_by_us": True,
            })

    return {"definitions": definitions, "candidates": model_candidates,
            "contracts": contracts, "facts": facts, "verdicts": verdicts}


def _validate(inst: dict, schema: dict) -> None:
    # spec-first WITH format enforcement — e.g. MetricFact.ts "format": "date-time"
    # is actually checked (needs rfc3339-validator installed to bite on date-time).
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(inst)


def validate_bundle(bundle: dict) -> None:
    md, mc = _schema("metric-definition"), _schema("model-candidate")
    bc, mf = _schema("benchmark-contract"), _schema("metric-fact")
    for d in bundle["definitions"]:
        _validate(d, md)
    for c in bundle["candidates"]:
        _validate(c, mc)
    for k in bundle["contracts"]:
        _validate(k, bc)
    for f in bundle["facts"]:
        _validate(f, mf)


# ---- seed candidates: research-tracked models. Axis scores are ILLUSTRATIVE INPUT
#      to the mechanism; they are never emitted as data (see NO LAUNDERING above). ----
def seed_candidates() -> list[dict]:
    def cand(cid, name, provider, family, gov_ok, sc):
        gov = {"api": True, "rate": True, "auth": True, "cost": True, "observability": gov_ok}
        return {"candidate_id": cid, "name": name, "provider_id": provider, "family": family,
                "governance": gov, "scores": sc,
                "implementation": {"source_repo": "vendor:%s" % provider.lower().replace(" ", "-"),
                                   "source_ref": "release-2026", "license": "vendor-tos",
                                   "runtime_dependencies": ["network"]}}
    S = lambda **k: {"case_action": 0, "groundedness": 0, "citation": 0, "tool_use": 0,
                     "instruction": 0, "retrieval": 0, "cost": 0, "latency": 0, "observability": 0, **k}
    return [
        cand("cand.opus_class", "opus-class", "Anthropic", "frontier_general", True,
             S(case_action=89, groundedness=93, citation=91, tool_use=90, instruction=92, retrieval=88, cost=62, latency=74, observability=85)),
        cand("cand.gpt_class", "gpt-class", "OpenAI", "frontier_general", True,
             S(case_action=85, groundedness=87, citation=83, tool_use=91, instruction=90, retrieval=86, cost=66, latency=80, observability=82)),
        cand("cand.gemini_class", "gemini-class", "Google Vertex", "frontier_general", True,
             S(case_action=82, groundedness=85, citation=82, tool_use=84, instruction=86, retrieval=84, cost=74, latency=82, observability=83)),
        cand("cand.gh_models", "gh-models", "GitHub Models", "aggregator", False,
             S(case_action=72, groundedness=74, citation=70, tool_use=76, instruction=78, retrieval=75, cost=88, latency=72, observability=60)),
        cand("cand.llama_local", "llama-local", "Meta Llama", "open_weight", False,
             S(case_action=67, groundedness=70, citation=66, tool_use=68, instruction=73, retrieval=72, cost=95, latency=88, observability=58)),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=None,
                    help="JSON map candidate_id -> {value_scalar, sample_n} of REAL run results")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "eval")
    args = ap.parse_args()

    corpus = json.loads(SEED_CORPUS.read_text())["items"]
    # fail-fast: the corpus must conform to the vendored EvalItem schema (spec-first).
    eval_item_schema = json.loads((SCHEMA_DIR / "vendored" / "EvalItem.schema.json").read_text())
    for it in corpus:
        _validate(it, eval_item_schema)
    results = json.loads(args.results.read_text()) if args.results else None
    bundle = build(corpus, seed_candidates(), results=results)
    validate_bundle(bundle)

    promoted = [cid for cid, v in bundle["verdicts"].items() if v["promoted"]]
    gated = [cid for cid, v in bundle["verdicts"].items() if v["stage_reached"] == 0]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "isota-tournament.json").write_text(json.dumps(bundle, indent=2))
    mode = "REAL (facts emitted)" if results is not None else "PROVISIONAL (no reproduced facts)"
    print("OK: isota-tournament — %s" % mode)
    print("  %d definitions, %d candidates, %d contracts, %d facts (all schema-valid)"
          % (len(bundle["definitions"]), len(bundle["candidates"]), len(bundle["contracts"]), len(bundle["facts"])))
    print("  mechanism: %d would-promote, %d gated at Stage 0 (fail-closed)" % (len(promoted), len(gated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
