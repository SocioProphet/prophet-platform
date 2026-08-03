#!/usr/bin/env python3
"""emit_intelligence_superiority_board — build the canonical Intelligence-Superiority feature-board
dataset (schemas/eval/examples/intelligence-superiority-board.json) that the cockpit boards render.

"We can't beat what we haven't benchmarked." This is the competitive-intelligence contract: for every
capability category it declares the top competitors, the litmus features that decide the category, and
a scored estate-vs-each verdict (BEAT|MEET|PARTIAL|GAP) with evidence, maturity (live|spec) and
assessment_basis. The dataset is emitted from a compact table (per-feature default verdict + explicit
per-competitor overrides) so a lead is stated ONCE and only the cells that differ are broken out.

Honesty discipline baked into emission:
  * assessment_basis is self_assessed for every cell — none of these are externally certified, and the
    schema/validator would REJECT an externally_certified cell without a cert_ref.
  * a BEAT/MEET cell that is thin — maturity=='spec' OR fewer than 2 evidence pointers — is emitted with
    provisional=true (the validator REJECTS a thin lead that forgets the flag). This is what keeps
    "capable, not yet released (a deliberate choice)" honestly distinct from "battle-tested and live".
  * evidence_ref points at real estate artifacts (repo / path / PR / memory node). PARTIAL/GAP cells
    need no evidence — you don't have to prove you are behind.

Every emitted board is run through validate_intelligence_superiority_board.validate_board BEFORE it is
written; emission fails loudly if the board would not pass the gate.

Run:  python3 tools/emit_intelligence_superiority_board.py [--out PATH] [--check]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "schemas" / "eval" / "examples" / "intelligence-superiority-board.json"
# Deterministic stamp — a re-emit must be byte-identical so the drift guard has meaning.
GENERATED_TS = "2026-08-03T00:00:00Z"
SPEC_VERSION = "1.0.0"
MIN_EVIDENCE_REFS = 2


def _load_validator():
    path = ROOT / "tools" / "validate_intelligence_superiority_board.py"
    spec = importlib.util.spec_from_file_location("is_board_validator", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # dataclasses on 3.12 resolve cls.__module__ via sys.modules; the module must be
    # registered before exec_module or that lookup returns None.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The compact scoring table. Each feature carries a `default` cell applied to every competitor,
# plus `overrides` for the competitors whose cell differs. Evidence lives on the estate claim (the
# default) and is inherited unless an override supplies its own.
# ─────────────────────────────────────────────────────────────────────────────────────────────
def _c(verdict, maturity, evidence=None, rationale=None):
    cell: dict[str, Any] = {"verdict": verdict, "maturity": maturity}
    if evidence:
        cell["evidence_ref"] = evidence
    if rationale:
        cell["rationale"] = rationale
    return cell


CATEGORIES: list[dict[str, Any]] = [
    # ── 1. RAG ─────────────────────────────────────────────────────────────────────────────────
    {
        "category_id": "rag",
        "name": "Retrieval-Augmented Generation",
        "description": "Noetica RAG (advanced-RAG family, receipt-gated inference, GraphRAG grounded answers, "
                       "embedding-space governance, temporal retrieval) vs the productized RAG field.",
        "competitors": ["Glean", "Perplexity", "Cohere", "Vectara", "Watson Discovery"],
        "features": [
            {"feature_id": "advanced_rag_breadth", "name": "Advanced-RAG pattern breadth",
             "definition": "Number and composition of retrieval patterns fused in one governed harness.",
             "criteria": "BEAT = >=8 fused patterns (HippoRAG/RAPTOR/HyDE/CRAG-gate/temporal) in a single live library.",
             "default": _c("BEAT", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/retrieval.ts",
                             "note": "817 LOC, 11 fused patterns incl. HippoRAG/RAPTOR/HyDE + CRAG gate + temporal"},
                            {"memory": "competitive_intel_localrag", "note": "field CI: harness > model"}])},
            {"feature_id": "inference_receipts", "name": "Replayable inference receipts",
             "definition": "Per-turn, hash-chained, replayable evidence for every retrieved-and-generated answer.",
             "criteria": "BEAT = open, SHA-256 hash-chained, replay-classed receipts on every turn.",
             "default": _c("BEAT", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/reasoning-evidence.ts",
                             "note": "SHA-256 hash-chain, replayClass, safe-trace"},
                            {"repo": "Noetica", "path": "agent-machine/lib/connector-receipt.ts"},
                            {"repo": "Noetica", "path": "agent-machine/server.ts", "note": "wiring @ ~4256"}],
                           rationale="No competitor ships open replayable per-turn inference receipts.")},
            {"feature_id": "embedding_governance", "name": "Embedding-space governance",
             "definition": "Enforced embedding-dimension/space contract preventing silent index/query mismatch.",
             "criteria": "BEAT = fail-closed EmbeddingSpaceMismatchError + dim pin + source-scan CI guard.",
             "default": _c("BEAT", "live",
                           [{"pr": "82", "note": "embedding-space pin"}, {"pr": "602"}, {"pr": "605",
                             "note": "EmbeddingSpaceMismatchError, CORPUS_EMBED_DIM pin, embed-space-contract.test.ts, reindexIfDimMismatch"}])},
            {"feature_id": "graph_rag_grounding", "name": "GraphRAG grounded answers",
             "definition": "Graph-structured retrieval with per-claim grounding to a resolvable source reference.",
             "criteria": "BEAT = MS-GraphRAG + per-claim grounding + fail-closed page-reference CI contract.",
             "default": _c("BEAT", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/graph-rag.ts",
                             "note": "MS GraphRAG + per-claim grounding + trust + DRIFT"},
                            {"repo": "prophet-workspace", "pr": "103",
                             "note": "grounded-answer-with-page-reference; graphrag-grounding.yml 32 checks; proof-artifact-spine sealed"}],
                           rationale="Module + CI contract are live; live PageIndex->HellGraph binding is SPEC (fixtures).")},
            {"feature_id": "hybrid_fusion", "name": "Hybrid dense/lexical/graph fusion",
             "definition": "Reciprocal-rank fusion across dense, lexical (BM25) and graph retrieval.",
             "criteria": "MEET = shipping BM25 + dense RRF; BEAT requires a decisive quality edge.",
             "default": _c("MEET", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/hybrid-retrieve.ts", "note": "BM25 + dense RRF"},
                            {"memory": "competitive_intel_localrag"}],
                           rationale="Glean/Cohere/Vectara match on hybrid fusion.")},
            {"feature_id": "verified_grounded_citations", "name": "Verified, resolvable citations",
             "definition": "Citations that are verified against source (grounding score) and resolve to an exact locus.",
             "criteria": "BEAT = verified + receipted + page-resolvable citation; MEET = strong UX parity.",
             "default": _c("BEAT", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/research-verify.ts",
                             "note": "verifyGrounding pass@0.7 + per-chunk file#idx"},
                            {"repo": "prophet-workspace", "pr": "103", "note": "resolvable page_ref"}]),
             "overrides": {"Perplexity": _c("MEET", "live",
                           rationale="Perplexity leads on citation UX/scale; estate leads on verified+receipted+page-resolvable.")}},
            {"feature_id": "reranking", "name": "Reranking quality",
             "definition": "Precision of the reranker over the fused candidate set.",
             "criteria": "BEAT = trained cross-encoder parity or better; PARTIAL = unsupervised RRF/MMR only.",
             "default": _c("MEET", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/rerank-rrf.ts"},
                            {"repo": "Noetica", "path": "agent-machine/lib/rag-rerank.ts", "note": "RRF + MMR, unsupervised"}]),
             "overrides": {"Cohere": _c("PARTIAL", "live",
                           rationale="Cohere Rerank (trained cross-encoder) LEADS on pure relevance; estate rerank is unsupervised.")}},
            {"feature_id": "hallucination_control", "name": "Hallucination control",
             "definition": "Defenses that suppress unsupported generations (poisoned-RAG, self-consistency, grounding checks).",
             "criteria": "BEAT = layered deterministic defense breadth; PARTIAL where a trained detector leads one axis.",
             "default": _c("BEAT", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/rag-trust.ts", "note": "PoisonedRAG defense"},
                            {"repo": "Noetica", "path": "agent-machine/lib/research-verify.ts", "note": "verifyGrounding + crag-gate self-consistency"}]),
             "overrides": {"Vectara": _c("PARTIAL", "live",
                           rationale="Vectara HHEM (trained hallucination model) LEADS on that single axis; estate leads on breadth.")}},
            {"feature_id": "contextual_retrieval_fusion", "name": "Contextual retrieval + RAG-Fusion",
             "definition": "Contextual-chunk retrieval and query-variant RAG-Fusion.",
             "criteria": "BEAT = merged, tested contextual retrieval + RAG-Fusion; live requires ingest/query wiring.",
             "default": _c("BEAT", "spec",
                           [{"pr": "607", "note": "contextual-retrieval: merged + tested, NOT wired into live ingest/query"},
                            {"pr": "604", "note": "query-variant RAG-Fusion: merged + tested, not live-wired"}],
                           rationale="Built and tested; not yet wired into the live ingest/query path.")},
            {"feature_id": "temporal_retrieval", "name": "Temporal retrieval correctness",
             "definition": "Retrieval filtered/validated by temporal validity of facts.",
             "criteria": "BEAT = general temporal-KG validity model; PARTIAL = scoped recency filter only.",
             "default": _c("PARTIAL", "live",
                           rationale="Live 7-day SPARQL FILTER (recent-messages scoped) only, not a general temporal-KG validity model.")},
            {"feature_id": "retrieval_scale", "name": "Retrieval quality at scale",
             "definition": "Retrieval quality sustained at billion-document corpora.",
             "criteria": "BEAT = proven billion-doc scale; PARTIAL/GAP = workspace-scale in-memory scans.",
             "default": _c("PARTIAL", "live",
                           rationale="In-memory g.allNodes() scans = workspace-scale."),
             "overrides": {"Glean": _c("GAP", "live", rationale="Glean proven at enterprise/billion-doc scale."),
                           "Vectara": _c("GAP", "live"), "Watson Discovery": _c("GAP", "live")}},
            {"feature_id": "connector_breadth", "name": "Connector breadth + permission sync",
             "definition": "Breadth of source connectors with document-level permission synchronization.",
             "criteria": "BEAT = 100+ connectors with permission-sync; PARTIAL = open audited connectors, fewer.",
             "default": _c("PARTIAL", "live",
                           rationale="connector-receipt.ts gives open audited connectors; Glean leads on 100+ connectors with permission-sync.")},
        ],
    },
    # ── 2. Agent framework ──────────────────────────────────────────────────────────────────────
    {
        "category_id": "agent_framework",
        "name": "Agent framework",
        "description": "prophet-mesh / superconscious / AgentPassport + agent ontology + zero-trust A2A, "
                       "ControlNode/ControlLoop, Crown, agentplane governed runner, memory-mesh vs the agent-framework field.",
        "competitors": ["LangGraph", "CrewAI", "AutoGen", "MS Agent Framework", "Devin", "Dust"],
        "features": [
            {"feature_id": "governance_policy_gating", "name": "Governance / policy gating",
             "definition": "Constitutional gates that can refuse an agent action (separation-of-powers invariants).",
             "criteria": "BEAT = merged constitution + judge/objective gates that fail closed on unconstitutional acts.",
             "default": _c("BEAT", "live",
                           [{"repo": "hellgraph", "pr": "52", "note": "Crown constitution ADR-0004, MERGED to main"},
                            {"repo": "ProCybernetica", "pr": "124",
                             "note": "ControlNode + ADR-0003; 7 teeth incl. NO_VALUE_JUDGMENT_GATE / JUDGE_DENIED_BUT_FIRED / UNCONSTITUTIONAL_OBJECTIVE_CROWN_K1"},
                            {"repo": "ProCybernetica", "pr": "126", "note": "agentic-execution class"}],
                           rationale="Crown + ControlNode merged (live); the ControlLoop remediation itself is measurement/design only (SPEC).")},
            {"feature_id": "agent_identity_passport", "name": "Agent identity / passport",
             "definition": "OS-process-level agent classification and fail-closed authorization.",
             "criteria": "BEAT = OS-process->authority binding with live fail-closed authorize gate.",
             "default": _c("BEAT", "live",
                           [{"repo": "sourceos-spec", "path": "AgentPassport.json", "note": "5-class, T0-1, OS-process level"},
                            {"repo": "mcp-a2a-zero-trust", "pr": "18", "note": "trust-tiers"},
                            {"repo": "agent-registry", "pr": "50", "note": "live fail-closed authorize.py"}],
                           rationale="Unique: OS-process-level agent classification.")},
            {"feature_id": "receipts_auditability", "name": "Receipts / auditability",
             "definition": "Hash-chained, deterministically-replayable proof artifacts for agent runs.",
             "criteria": "BEAT = SHA-256 proof-artifact spine + deterministic replay + sealed hygiene passports.",
             "default": _c("BEAT", "live",
                           [{"repo": "agentplane", "pr": "327", "note": "proof-artifact-spine SHA-256 hash-chained + deterministic replay (327 commits)"},
                            {"note": "epigov hygiene runtime: sealed CountertestRun/Bias/Calibration passports", "path": "commit 559d19a"}],
                           rationale="Strongest lead in the category.")},
            {"feature_id": "standards_conformance", "name": "Standards conformance",
             "definition": "Coverage of open agent-interop standards under a zero-trust profile.",
             "criteria": "BEAT = HUA/AG-UI/A2A/MCP/ANP zero-trust stack + published agent-standard profiles.",
             "default": _c("BEAT", "live",
                           [{"repo": "ProCybernetica", "pr": "126", "note": "agentic-execution-class"},
                            {"repo": "socioprophet-agent-standards", "note": "HUA/AG-UI/A2A/MCP/ANP zero-trust profiles"}])},
            {"feature_id": "os_workspace_native", "name": "OS / workspace-native",
             "definition": "Agents bound to OS-process authority within a sovereign workspace/OS layer.",
             "criteria": "BEAT = SourceOS + AgentPassport OS-process->authority binding.",
             "default": _c("BEAT", "live",
                           [{"repo": "SourceOS", "note": "OS layer"},
                            {"repo": "sourceos-spec", "path": "AgentPassport.json", "note": "OS-process->authority binding"}],
                           rationale="agentic-os-api is a read-only seed (PARTIAL-live).")},
            {"feature_id": "self_maintenance_contract", "name": "Self-maintenance contract",
             "definition": "A closed sense->model->judge->act->receipt control loop for self-maintenance.",
             "criteria": "BEAT = specified closed-loop contract; live requires shipping runtime remediation.",
             "default": _c("BEAT", "spec",
                           [{"repo": "ProCybernetica", "pr": "124", "note": "ControlLoop ADR-0003: sense->model->judge->act->receipt"}],
                           rationale="No runtime remediation ships yet (SPEC).")},
            {"feature_id": "multi_agent_orchestration", "name": "Multi-agent orchestration",
             "definition": "Coordinating multiple role-specialized agents toward a shared objective.",
             "criteria": "MEET = conductor + role choir + A2A coordination; BEAT requires a live edge.",
             "default": _c("MEET", "spec",
                           [{"repo": "prophet-mesh", "note": "conductor + 10-role choir"},
                            {"repo": "ProCybernetica", "note": "A2A inter-agent-coordination exec class; dry-run/validators = SPEC"}],
                           rationale="Estate coordination is dry-run/validator level."),
             "overrides": {"CrewAI": _c("PARTIAL", "spec", rationale="CrewAI leads on live multi-agent loops."),
                           "AutoGen": _c("PARTIAL", "spec", rationale="AutoGen leads on live multi-agent loops.")}},
            {"feature_id": "memory_governed", "name": "Governed agent memory",
             "definition": "Multi-type agent memory with regime characterization and governed writeback.",
             "criteria": "BEAT = FSMS multi-type memory + regime characterizer + governed writeback; MEET = raw recall parity.",
             "default": _c("MEET", "live",
                           [{"repo": "memory-mesh", "note": "FSMS 6-type + regime characterizer + governed writeback (memoryd)"},
                            {"repo": "memory-mesh", "pr": "47"}, {"repo": "memory-mesh", "pr": "50"}],
                           rationale="Estate leads on GOVERNED writeback/regime; at parity on raw recall.")},
            {"feature_id": "orchestration_runtime", "name": "Live orchestration runtime",
             "definition": "A production graph/runtime that actually executes multi-step agent flows.",
             "criteria": "BEAT = live executing graph; PARTIAL = deterministic dry-run router only.",
             "default": _c("PARTIAL", "spec",
                           rationale="prophet-mesh router is deterministic dry-run only; LangGraph/AutoGen/CrewAI ship live graphs.")},
            {"feature_id": "autonomous_execution", "name": "Autonomous execution",
             "definition": "End-to-end autonomous task execution (e.g. autonomous coding).",
             "criteria": "BEAT = executes autonomous runs; GAP = contract carrier that does not execute.",
             "default": _c("GAP", "spec",
                           rationale="GovernedRunContract does not execute a run (v0 carrier + fixtures)."),
             "overrides": {"Devin": _c("GAP", "spec", rationale="Devin executes autonomous coding; estate does not execute runs yet.")}},
        ],
    },
    # ── 3. Model lab + eval ─────────────────────────────────────────────────────────────────────
    {
        "category_id": "model_lab_eval",
        "name": "Model lab + evaluation",
        "description": "tritfabric, lattice-forge/studio, model-plane T7, receipt-gateway/InferenceReceipts, "
                       "reproduce-bench/RecipeProof vs the ML experiment/eval field.",
        "competitors": ["Weights & Biases", "MLflow", "Hugging Face", "Galileo", "Patronus", "Arize"],
        "features": [
            {"feature_id": "experiment_tracking", "name": "Experiment tracking",
             "definition": "Tracking runs, params, artifacts and comparisons across model experiments.",
             "criteria": "BEAT = mature tracking UX + governance; PARTIAL = emerging tracking surface.",
             "default": _c("PARTIAL", "live",
                           rationale="W&B/MLflow lead on mature tracking UX; lattice-studio leaderboard is the emerging estate surface.")},
            {"feature_id": "receipted_eval", "name": "Receipt-gated evaluation",
             "definition": "Every eval/inference result carries a sealed, hash-chained receipt.",
             "criteria": "BEAT = per-call SHA-256 hash-chained InferenceReceipts + trust-class provenance.",
             "default": _c("BEAT", "live",
                           [{"repo": "prophet-platform", "path": "apps/receipt-gateway", "note": "hash-chained InferenceReceipts per call, SEAM-011"},
                            {"repo": "prophet-platform", "path": "schemas/eval/metric-fact.schema.json",
                             "note": "source_trust_class + reproduced_by_us provenance on every fact"}],
                           rationale="Competitors do not seal per-call inference receipts.")},
            {"feature_id": "reproducibility_recipeproof", "name": "RecipeProof reproducibility",
             "definition": "Deterministic, environment-pinned replay of an eval run from a recipe.",
             "criteria": "BEAT = recipe + repro-ledger + reproduce-run-record enabling deterministic replay.",
             "default": _c("BEAT", "live",
                           [{"repo": "prophet-platform", "path": "schemas/eval/repro-ledger-entry.schema.json"},
                            {"repo": "prophet-platform", "path": "schemas/eval/reproduce-run-record.schema.json"}])},
            {"feature_id": "honesty_no_laundering", "name": "Anti-laundering honesty gate",
             "definition": "Structural prevention of citing a number as if it were reproduced by us.",
             "criteria": "BEAT = disjoint reproduced-vs-cited facts + a no_laundering submission gate.",
             "default": _c("BEAT", "live",
                           [{"repo": "prophet-platform", "path": "tools/validate_submission.py", "note": "no_laundering gate"},
                            {"repo": "prophet-platform", "path": "schemas/eval/division-rules.json"}],
                           rationale="Structural anti-laundering has no vendor equivalent.")},
            {"feature_id": "llm_eval_guardrails", "name": "LLM eval + guardrails",
             "definition": "Productized LLM output evaluation and guardrailing (safety/quality scorers).",
             "criteria": "BEAT = broad governed scorers; PARTIAL where a vendor leads productization.",
             "default": _c("MEET", "spec",
                           [{"repo": "guardrail-fabric", "note": "runtime guardrails"},
                            {"memory": "counter_test_gate", "note": "counter-test gate"}]),
             "overrides": {"Galileo": _c("PARTIAL", "spec", rationale="Galileo leads on productized LLM eval."),
                           "Patronus": _c("PARTIAL", "spec", rationale="Patronus leads on productized LLM eval.")}},
            {"feature_id": "model_registry_governance", "name": "Governed model registry",
             "definition": "Model registry with governance ledger over promotions/lineage.",
             "criteria": "BEAT = registry + governance ledger; MEET = registry parity.",
             "default": _c("MEET", "spec",
                           [{"repo": "model-governance-ledger"}, {"repo": "tritfabric"}],
                           rationale="MLflow leads on mature registry; estate leads on governance ledger.")},
            {"feature_id": "production_observability", "name": "Production ML observability",
             "definition": "Live monitoring of model quality/drift in production.",
             "criteria": "BEAT = mature drift/quality monitoring; PARTIAL = telemetry capture only.",
             "default": _c("PARTIAL", "spec",
                           rationale="Arize leads on production ML observability; estate has telemetry capture."),
             "overrides": {"Arize": _c("GAP", "spec", rationale="Arize is purpose-built for production ML observability at scale.")}},
        ],
    },
    # ── 4. AI governance / trust / epistemics ───────────────────────────────────────────────────
    {
        "category_id": "ai_governance",
        "name": "AI governance / trust / epistemics",
        "description": "Crown Truth-Engine, SILENT firewall, counter-test-gate, hygiene runtime "
                       "(bias-passport/CTEST), truth=law x evidence, receipts-everywhere vs the AI-trust field.",
        "competitors": ["Credo AI", "Robust Intelligence", "Fiddler", "Arize", "Patronus"],
        "features": [
            {"feature_id": "truth_engine", "name": "Truth engine (law x evidence)",
             "definition": "A truth model where a verdict = law applied to evidence, not model preference.",
             "criteria": "BEAT = an explicit law x evidence truth contract driving verdicts.",
             "default": _c("BEAT", "spec",
                           [{"repo": "prophet-truth"}, {"memory": "truth_law_evidence_contract"}],
                           rationale="No vendor ships a law x evidence truth engine.")},
            {"feature_id": "silent_firewall", "name": "SILENT runtime firewall",
             "definition": "A fail-closed runtime firewall that blocks silent-wrong / unsafe actions.",
             "criteria": "BEAT = live fail-closed preflight firewall with degraded->warn handling.",
             "default": _c("BEAT", "live",
                           [{"repo": "guardrail-fabric", "path": "tools/validate_preflight_handoff.py"},
                            {"repo": "guardrail-fabric", "path": "docs/trustops-preflight-handoff.md"}])},
            {"feature_id": "counter_test_gate", "name": "Counter-test gate",
             "definition": "A gate that requires a passing counter-test (attempt to disprove) before a claim ships.",
             "criteria": "BEAT = sealed CountertestRun required to promote a claim.",
             "default": _c("BEAT", "spec",
                           [{"memory": "counter_test_gate"},
                            {"note": "epigov CountertestRun passport", "path": "commit 559d19a"}])},
            {"feature_id": "bias_calibration_passports", "name": "Bias / calibration passports",
             "definition": "Sealed bias and calibration passports emitted by a runtime hygiene layer.",
             "criteria": "BEAT = sealed bias/calibration passports produced at runtime.",
             "default": _c("BEAT", "live",
                           [{"note": "epigov hygiene runtime bias-passport/CTEST, sealed passports", "path": "commit 559d19a"},
                            {"repo": "guardrail-fabric"}])},
            {"feature_id": "receipts_everywhere", "name": "Receipts everywhere",
             "definition": "Every consequential action across the estate emits a hash-chained receipt.",
             "criteria": "BEAT = SHA-256 proof-artifact receipts spanning agent/eval/graph/governance.",
             "default": _c("BEAT", "live",
                           [{"repo": "agentplane", "pr": "327", "note": "proof-artifact-spine"},
                            {"repo": "prophet-platform", "path": "schemas/eval/oais-deposition.schema.json", "note": "SHA-256 fixity"}])},
            {"feature_id": "external_certification", "name": "External / third-party certification",
             "definition": "Independent, third-party certification of governance controls.",
             "criteria": "BEAT = externally certified controls; GAP = self-assessed only.",
             "default": _c("PARTIAL", "spec",
                           rationale="All estate controls are self_assessed; Credo AI / Robust Intelligence lead on external audit/certification."),
             "overrides": {"Credo AI": _c("GAP", "spec", rationale="Credo AI is purpose-built for third-party governance certification.")}},
        ],
    },
    # ── 5. Knowledge graph ──────────────────────────────────────────────────────────────────────
    {
        "category_id": "knowledge_graph",
        "name": "Knowledge graph",
        "description": "HellGraph (governed, receipted, federated graph substrate) vs mature graph databases.",
        "competitors": ["Neo4j", "TigerGraph"],
        "features": [
            {"feature_id": "graph_engine_maturity", "name": "Graph engine maturity / scale",
             "definition": "Distributed, production-hardened graph storage and query at scale.",
             "criteria": "BEAT = billion-edge distributed engine; PARTIAL = emerging engine.",
             "default": _c("PARTIAL", "spec",
                           rationale="Neo4j/TigerGraph lead on mature distributed graph-DB engines.")},
            {"feature_id": "governed_graph_receipts", "name": "Governed, receipted graph ops",
             "definition": "Graph mutations/queries that emit governance receipts and honor a contract.",
             "criteria": "BEAT = receipted, contract-bound graph operations.",
             "default": _c("BEAT", "spec",
                           [{"repo": "hellgraph"}, {"repo": "graphbrain-contract"}],
                           rationale="Governed/receipted graph ops have no graph-DB-vendor equivalent.")},
            {"feature_id": "federated_graph", "name": "Federated graph",
             "definition": "Federation of graphs across repos/domains under one query plane.",
             "criteria": "BEAT = live federated query plane; MEET = federation contract.",
             "default": _c("MEET", "spec",
                           [{"repo": "hellgraph", "memory": "hellgraph_federated"},
                            {"repo": "prophet-sheaf-hellgraph"}])},
            {"feature_id": "graphrag_native", "name": "Native GraphRAG",
             "definition": "First-class GraphRAG retrieval over the graph substrate.",
             "criteria": "BEAT = grounded GraphRAG bound to the graph engine.",
             "default": _c("MEET", "live",
                           [{"repo": "Noetica", "path": "agent-machine/lib/graph-rag.ts"},
                            {"repo": "hellgraph"}],
                           rationale="Estate leads on grounded GraphRAG; graph-DB vendors leave RAG to the app layer.")},
        ],
    },
    # ── 6. Ecosystem / marketplace ──────────────────────────────────────────────────────────────
    {
        "category_id": "ecosystem_marketplace",
        "name": "Ecosystem / marketplace",
        "description": "prophet-mesh + outcome-pricing (governed agent marketplace) vs the ecosystem field.",
        "competitors": ["LangChain / LangSmith", "Hugging Face Hub", "OpenAI GPT Store", "AWS Bedrock Marketplace"],
        "features": [
            {"feature_id": "outcome_pricing", "name": "Outcome-based pricing",
             "definition": "Pricing bound to delivered, receipted outcomes rather than tokens/seats.",
             "criteria": "BEAT = an outcome-priced, receipt-verified transaction model.",
             "default": _c("BEAT", "spec",
                           [{"repo": "prophet-mesh"}, {"memory": "portfolio_agent_choice", "note": "outcome-pricing thesis"}],
                           rationale="Outcome pricing tied to receipts has no marketplace equivalent (frontier, not shipped).")},
            {"feature_id": "governed_agent_marketplace", "name": "Governed agent marketplace",
             "definition": "A marketplace where listings are gated by passport/governance, not just uploaded.",
             "criteria": "BEAT = passport-gated marketplace; MEET/PARTIAL = curation without governance gates.",
             "default": _c("PARTIAL", "spec",
                           [{"repo": "prophet-mesh"}, {"repo": "agent-registry"}],
                           rationale="Estate has governance primitives; HF Hub / GPT Store lead on live marketplace scale.")},
            {"feature_id": "ecosystem_scale", "name": "Ecosystem scale / network effects",
             "definition": "Breadth of third-party contributors, integrations and downloads.",
             "criteria": "BEAT = large live ecosystem; GAP = pre-network-effect.",
             "default": _c("GAP", "spec",
                           rationale="HF Hub / OpenAI / AWS have massive live ecosystems; estate is pre-network-effect.")},
        ],
    },
    # ── 7. Reproducibility ──────────────────────────────────────────────────────────────────────
    {
        "category_id": "reproducibility",
        "name": "Reproducibility",
        "description": "RecipeProof / repro-ledger / OAIS deposition + benchmark-contract vs reproducibility bodies.",
        "competitors": ["MLCommons", "Collective Knowledge (CK)", "Zenodo"],
        "features": [
            {"feature_id": "reproducible_run_contract", "name": "Reproducible run contract",
             "definition": "Environment/seed/methodology pinned so a run can be replayed deterministically.",
             "criteria": "BEAT = recipe + repro-ledger + run-record enabling deterministic replay.",
             "default": _c("BEAT", "live",
                           [{"repo": "prophet-platform", "path": "schemas/eval/recipe-proof.schema.json"},
                            {"repo": "prophet-platform", "path": "schemas/eval/repro-ledger-entry.schema.json"}])},
            {"feature_id": "preservation_deposition", "name": "Preservation / deposition",
             "definition": "Citable, fixity-checked archival deposition of artifacts.",
             "criteria": "BEAT = OAIS AIP with SHA-256 fixity + OAI-PMH; PARTIAL vs a DOI-minting archive.",
             "default": _c("MEET", "live",
                           [{"repo": "prophet-platform", "path": "schemas/eval/oais-deposition.schema.json"},
                            {"repo": "prophet-platform", "path": "tools/oais_deposition.py", "note": "SHA-256 fixity + OAI-PMH"}]),
             "overrides": {"Zenodo": _c("PARTIAL", "live", rationale="Zenodo is a mature DOI-minting archive with global recognition.")}},
            {"feature_id": "benchmark_governance", "name": "Benchmark submission governance",
             "definition": "A validated submission contract governing what counts as a benchmark result.",
             "criteria": "BEAT = submission validity gate + receipts; MEET vs an established standards body.",
             "default": _c("MEET", "live",
                           [{"repo": "prophet-platform", "path": "tools/validate_submission.py"},
                            {"repo": "prophet-platform", "path": "schemas/eval/benchmark-contract.schema.json"}],
                           rationale="MLCommons is the recognized standard; estate adds receipts + anti-laundering.")},
            {"feature_id": "external_recognition", "name": "External recognition",
             "definition": "Industry/community recognition of the reproducibility artifacts.",
             "criteria": "BEAT = widely recognized; GAP = internal only.",
             "default": _c("GAP", "live",
                           rationale="MLCommons/Zenodo are industry-recognized; estate artifacts are internal/self_assessed.")},
        ],
    },
    # ── 8. World-model / twin ───────────────────────────────────────────────────────────────────
    {
        "category_id": "world_model_twin",
        "name": "World-model / twin",
        "description": "gaia value-flow world-model + Self<->Body<->Universe twin hierarchy (largely unique) "
                       "vs the nearest digital-twin/ontology platforms.",
        "competitors": ["NVIDIA Omniverse", "Palantir Foundry", "Generic simulation vendors"],
        "features": [
            {"feature_id": "value_flow_world_model", "name": "Value-flow world model",
             "definition": "A world model that propagates value over value x time, not just physical state.",
             "criteria": "BEAT = an explicit value-flow world-model substrate.",
             "default": _c("BEAT", "spec",
                           [{"repo": "gaia-world-model"}, {"memory": "galactic_twin_dashboard", "note": "gaia value-flow"}],
                           rationale="No competitor ships a value-flow world model (frontier, deliberate).")},
            {"feature_id": "twin_hierarchy", "name": "Self<->Body<->Universe twin hierarchy",
             "definition": "A nested twin hierarchy spanning self, body and universe scales.",
             "criteria": "BEAT = a live nested twin hierarchy; spec where surfaces are still fixtures.",
             "default": _c("BEAT", "spec",
                           [{"repo": "human-digital-twin"},
                            {"memory": "galactic_twin_dashboard", "note": "Self<->Body<->Universe 5D cube"}])},
            {"feature_id": "ontogenesis_binding", "name": "Ontogenesis concept binding",
             "definition": "New capabilities routed through ontogenesis and bound upward to the world-model/twin.",
             "criteria": "BEAT = capabilities declare world-model/twin binding via ontogenesis.",
             "default": _c("BEAT", "spec",
                           [{"memory": "bind_upward_worldmodel_ontogenesis"},
                            {"memory": "ontogenesis_gi_unshaped_classes"}],
                           rationale="Concept-governance binding upward is unique to the estate.")},
        ],
    },
    # ── 9. Risk / value ─────────────────────────────────────────────────────────────────────────
    {
        "category_id": "risk_value",
        "name": "Risk / value",
        "description": "omnirisk / Economic-Prophet financial spine (regime-aware calculus over value x time) "
                       "vs quant/risk vendors.",
        "competitors": ["MSCI / Barra", "Bloomberg (PORT/BQuant)", "RiskMetrics", "Palantir"],
        "features": [
            {"feature_id": "regime_aware_calculus", "name": "Regime-aware risk calculus",
             "definition": "Risk calculus that is explicitly regime-aware (EP kernel + FTP + vol-surface + microstructure).",
             "criteria": "BEAT = a regime-aware calculus over value x time.",
             "default": _c("BEAT", "spec",
                           [{"repo": "economic-prophet"}, {"memory": "omnirisk_ep_financial_spine"}],
                           rationale="Regime-aware value x time calculus is a frontier design (SPEC).")},
            {"feature_id": "value_time_conservation", "name": "Value x time / welfare conservation",
             "definition": "A value-energy conservation model annealing toward global quality-of-life.",
             "criteria": "BEAT = an explicit value-conservation / welfare-annealing model.",
             "default": _c("BEAT", "spec",
                           [{"memory": "welfare_annealing_framework"}, {"repo": "economic-prophet"}])},
            {"feature_id": "receipted_risk", "name": "Receipted risk outputs",
             "definition": "Risk outputs carrying governance receipts / provenance.",
             "criteria": "BEAT = receipted risk outputs; MEET = provenance parity.",
             "default": _c("MEET", "spec",
                           [{"repo": "economic-prophet"}, {"repo": "agentplane", "pr": "327", "note": "proof-artifact-spine reusable"}])},
            {"feature_id": "market_data_scale", "name": "Market-data breadth + regulatory acceptance",
             "definition": "Breadth of market data and regulatory/industry acceptance of the risk models.",
             "criteria": "BEAT = broad data + regulatory acceptance; GAP = no such footprint.",
             "default": _c("GAP", "spec",
                           rationale="Bloomberg/MSCI have vast data and regulatory acceptance; estate has neither yet.")},
        ],
    },
]


def _expand_score(feature: dict, competitor: str) -> dict:
    """Merge the feature default with any per-competitor override into one score row."""
    default = feature["default"]
    ov = (feature.get("overrides") or {}).get(competitor, {})
    verdict = ov.get("verdict", default["verdict"])
    maturity = ov.get("maturity", default["maturity"])
    evidence = ov.get("evidence_ref", default.get("evidence_ref"))
    rationale = ov.get("rationale", default.get("rationale"))

    score: dict[str, Any] = {
        "feature_id": feature["feature_id"],
        "competitor": competitor,
        "verdict": verdict,
        "maturity": maturity,
        "assessment_basis": "self_assessed",
    }
    if verdict in ("BEAT", "MEET") and evidence:
        score["evidence_ref"] = [dict(e) for e in evidence]
    if rationale:
        score["rationale"] = rationale
    # Honesty flag: a thin lead (spec, or fewer than MIN_EVIDENCE_REFS pointers) is provisional.
    if verdict in ("BEAT", "MEET"):
        n_ev = len(score.get("evidence_ref") or [])
        if maturity == "spec" or n_ev < MIN_EVIDENCE_REFS:
            score["provisional"] = True
    return score


def build_board() -> dict:
    categories = []
    for cat in CATEGORIES:
        features = cat["features"]
        litmus = [{"feature_id": f["feature_id"], "name": f["name"],
                   "definition": f["definition"], "criteria": f["criteria"]} for f in features]
        scores = []
        for f in features:
            for comp in cat["competitors"]:
                scores.append(_expand_score(f, comp))
        categories.append({
            "category_id": cat["category_id"],
            "name": cat["name"],
            "description": cat["description"],
            "competitors": list(cat["competitors"]),
            "litmus_features": litmus,
            "scores": scores,
        })
    return {
        "board_id": "intelligence-superiority-board",
        "title": "Intelligence-Superiority Feature-Board",
        "generated_ts": GENERATED_TS,
        "spec_version": SPEC_VERSION,
        "notes": "We can't beat what we haven't benchmarked. Governed competitive-intelligence contract; "
                 "every BEAT/MEET carries evidence, thin/spec leads are provisional, all cells self_assessed. "
                 "Sealed by tools/validate_intelligence_superiority_board.py.",
        "categories": categories,
    }


def render(board: dict) -> str:
    return json.dumps(board, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Emit the canonical Intelligence-Superiority feature-board.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true", help="verify committed dataset matches emission (no write)")
    args = ap.parse_args(argv)

    board = build_board()

    # Gate emission on the validator — never write a board that would be REJECTED.
    validator = _load_validator()
    verdict = validator.validate_board(board)
    if not verdict.valid:
        print("EMISSION REJECTED by validator:", *(f"\n  - {r}" for r in verdict.rejections))
        return 1

    text = render(board)
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(f"DRIFT: {args.out} is out of sync with emit_intelligence_superiority_board.py")
            return 1
        print(f"OK: {args.out} in sync ({verdict.tally['scores']} scores across {verdict.tally['categories']} categories)")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    t = verdict.tally
    vc = t["verdicts"]
    print(f"WROTE {args.out}: {t['categories']} categories, {t['scores']} scores "
          f"(BEAT={vc['BEAT']} MEET={vc['MEET']} PARTIAL={vc['PARTIAL']} GAP={vc['GAP']}, {t['provisional']} provisional)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
