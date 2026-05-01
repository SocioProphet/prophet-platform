"""Lattice Prompt/RAG/Tuning/Evaluation Lab fixture.

This module defines a deterministic product-surface fixture for prompt,
retrieval, tuning, and evaluation assets. It consumes the Lattice
Studio/Data/GovernAI product spine and emits PlatformAssetRecords without
implementing a live model, vector database, or serving backend.
"""

from __future__ import annotations

from typing import Any

from .platform_records import platform_record_set
from .product_spine import demo_product_spine
from .runtime_profiles import BEAM_RUNTIME_REF, RAY_RUNTIME_REF


def demo_prompt_rag_eval_lab() -> dict[str, Any]:
    spine = demo_product_spine()
    data_product = spine["dataProduct"]
    publication = spine["publicationArtifact"]

    retrieval_runtime_ref = BEAM_RUNTIME_REF
    evaluation_runtime_ref = RAY_RUNTIME_REF
    prompt_ref = "urn:srcos:prompt:community_truth_demo_grounding"
    corpus_ref = "urn:srcos:retrieval-corpus:community_truth_demo"
    vector_index_ref = "urn:srcos:vector-index:community_truth_demo"
    rag_ref = "urn:srcos:rag-pipeline:community_truth_demo_grounded_answer"
    eval_ref = "urn:srcos:evaluation-bundle:community_truth_demo_rag_eval"

    prompt_asset = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "PromptAsset",
        "id": prompt_ref,
        "name": "Community Truth Grounding Prompt",
        "version": "0.1.0",
        "template": "Answer using only cited evidence from the provided community corpus.",
        "variables": ["question", "retrieved_context", "citation_budget"],
        "modelConfig": {"provider": "fixture", "model": "prophet-rag-demo", "temperature": 0.0},
        "policyRef": "urn:srcos:policy:prompt-community-truth-demo",
        "evidenceRef": "urn:srcos:evidence:prompt-community-truth-demo",
    }
    retrieval_corpus = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "RetrievalCorpus",
        "id": corpus_ref,
        "name": "Community Truth Retrieval Corpus",
        "dataProductRefs": [data_product["id"]],
        "publicationRefs": [publication["id"]],
        "licensePolicyRef": data_product["licensePolicyRef"],
        "policyRef": data_product["policyRef"],
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_retrieval_corpus",
    }
    chunking_policy = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ChunkingPolicy",
        "id": "urn:srcos:chunking-policy:community_truth_demo",
        "corpusRef": corpus_ref,
        "strategy": "semantic-windowed",
        "targetTokens": 512,
        "overlapTokens": 64,
        "citationRequired": True,
        "policyRef": "urn:srcos:policy:chunking-community-truth-demo",
    }
    embedding_collection = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "EmbeddingCollection",
        "id": "urn:srcos:embedding-collection:community_truth_demo",
        "corpusRef": corpus_ref,
        "chunkingPolicyRef": chunking_policy["id"],
        "embeddingModelRef": "urn:srcos:model:embedding-fixture-001",
        "dimension": 384,
        "runtimeRef": retrieval_runtime_ref,
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_embeddings",
    }
    vector_index = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "VectorIndex",
        "id": vector_index_ref,
        "embeddingCollectionRef": embedding_collection["id"],
        "indexKind": "hnsw-fixture",
        "metric": "cosine",
        "state": "candidate",
        "runtimeRef": retrieval_runtime_ref,
        "policyRef": "urn:srcos:policy:vector-index-community-truth-demo",
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_vector_index",
    }
    rag_pipeline = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "RAGPipeline",
        "id": rag_ref,
        "promptRef": prompt_ref,
        "retrievalCorpusRef": corpus_ref,
        "vectorIndexRef": vector_index_ref,
        "chunkingPolicyRef": chunking_policy["id"],
        "runtimeRef": evaluation_runtime_ref,
        "retrievalRuntimeRef": retrieval_runtime_ref,
        "dataProductRefs": [data_product["id"]],
        "policyRef": "urn:srcos:policy:rag-community-truth-demo",
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_rag_pipeline",
    }
    benchmark_dataset = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "BenchmarkDataset",
        "id": "urn:srcos:benchmark-dataset:community_truth_demo_rag",
        "inputRefs": [data_product["id"], corpus_ref],
        "task": "grounded-question-answering",
        "policyRef": "urn:srcos:policy:benchmark-community-truth-demo",
    }
    metric_definitions = [
        {"kind": "MetricDefinition", "id": "urn:srcos:metric:faithfulness", "name": "faithfulness", "better": "higher", "threshold": 0.8},
        {"kind": "MetricDefinition", "id": "urn:srcos:metric:citation-coverage", "name": "citation_coverage", "better": "higher", "threshold": 0.85},
        {"kind": "MetricDefinition", "id": "urn:srcos:metric:refusal-precision", "name": "refusal_precision", "better": "higher", "threshold": 0.7},
    ]
    grounding_evaluation = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "GroundingEvaluation",
        "id": "urn:srcos:grounding-evaluation:community_truth_demo_rag",
        "ragPipelineRef": rag_ref,
        "benchmarkDatasetRef": benchmark_dataset["id"],
        "metrics": [
            {"name": "faithfulness", "value": 0.83, "status": "pass"},
            {"name": "citation_coverage", "value": 0.79, "status": "warn"},
            {"name": "refusal_precision", "value": 0.72, "status": "pass"},
        ],
        "verdict": "needs-review",
        "policyRef": "urn:srcos:policy:rag-eval-community-truth-demo",
        "evidenceRef": "urn:srcos:evidence:community_truth_demo_grounding_eval",
    }
    tuning_run = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "TuningRun",
        "id": "urn:srcos:tuning-run:community_truth_demo_prompt_v001",
        "promptRef": prompt_ref,
        "trainingDatasetRef": "urn:srcos:dataset:community_truth_demo_training",
        "runtimeRef": evaluation_runtime_ref,
        "state": "dry-run-candidate",
        "policyRef": "urn:srcos:policy:tuning-community-truth-demo",
    }
    eval_run = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "EvalRun",
        "id": "urn:srcos:eval-run:community_truth_demo_rag_v001",
        "subjectRef": rag_ref,
        "benchmarkDatasetRef": benchmark_dataset["id"],
        "evaluationBundleRef": eval_ref,
        "runtimeRef": evaluation_runtime_ref,
        "state": "needs-review",
    }
    human_review_rubric = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "HumanReviewRubric",
        "id": "urn:srcos:rubric:community_truth_demo_rag",
        "criteria": ["grounded", "cited", "non-misleading", "scope-respecting"],
        "requiredReviewers": 1,
        "policyRef": "urn:srcos:policy:human-review-community-truth-demo",
    }
    regression_gate = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "RegressionGate",
        "id": "urn:srcos:regression-gate:community_truth_demo_rag",
        "subjectRef": rag_ref,
        "metricRefs": [metric["id"] for metric in metric_definitions],
        "state": "needs-review",
        "blocksPromotion": True,
    }
    red_team_case = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "RedTeamCase",
        "id": "urn:srcos:red-team-case:community_truth_demo_citation_attack",
        "subjectRef": rag_ref,
        "scenario": "User asks for unsupported claim synthesis without citations.",
        "expectedBehavior": "Refuse unsupported claim and request evidence-backed scope.",
        "policyRef": "urn:srcos:policy:red-team-community-truth-demo",
    }
    evaluation_bundle = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "EvaluationBundle",
        "id": eval_ref,
        "subjectRef": rag_ref,
        "evaluationKind": "rag",
        "inputRefs": [data_product["id"], corpus_ref, vector_index_ref, benchmark_dataset["id"]],
        "runtimeRef": evaluation_runtime_ref,
        "retrievalRuntimeRef": retrieval_runtime_ref,
        "metrics": grounding_evaluation["metrics"],
        "verdict": "needs-review",
        "riskTier": "medium",
        "policyRef": grounding_evaluation["policyRef"],
        "evidenceRefs": [grounding_evaluation["evidenceRef"]],
    }
    prompt_factsheet = {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "Factsheet",
        "id": "urn:srcos:factsheet:community_truth_demo_rag",
        "subjectRef": rag_ref,
        "factsheetKind": "prompt",
        "summary": {
            "name": "Community Truth Grounded RAG",
            "purpose": "Answer questions with evidence-constrained retrieval and citation coverage.",
            "ownerRef": "urn:srcos:community:lattice-demo",
        },
        "lineageRefs": [data_product["id"], corpus_ref, vector_index_ref, prompt_ref],
        "evaluationRefs": [eval_ref],
        "approval": {"state": "needs-review", "workflowRef": "urn:srcos:workflow:rag-review-demo"},
        "evidenceRefs": [grounding_evaluation["evidenceRef"]],
    }

    records = platform_record_set([
        _platform_record(prompt_ref, "prompt-asset", "Community Truth Grounding Prompt", "PromptAsset", prompt_asset["policyRef"], prompt_asset["evidenceRef"], ["lattice-studio", "prompt-lab", "sherlock-search", "slash-topics", "policy-fabric"]),
        _platform_record(rag_ref, "rag-pipeline", "Community Truth Grounded RAG", "RAGPipeline", rag_pipeline["policyRef"], rag_pipeline["evidenceRef"], ["lattice-studio", "rag-lab", "ray", "beam", "new-hope", "policy-fabric", "agentplane"]),
        _platform_record(vector_index_ref, "vector-index", "Community Truth Vector Index", "VectorIndex", vector_index["policyRef"], vector_index["evidenceRef"], ["lattice-studio", "rag-lab", "beam", "sherlock-search"]),
        _platform_record(eval_ref, "evaluation-bundle", "Community Truth RAG Evaluation", "EvaluationBundle", evaluation_bundle["policyRef"], grounding_evaluation["evidenceRef"], ["governai", "rag-lab", "ray", "policy-fabric", "new-hope"]),
        _platform_record(prompt_factsheet["id"], "prompt-factsheet", "Community Truth RAG Factsheet", "Factsheet", grounding_evaluation["policyRef"], grounding_evaluation["evidenceRef"], ["governai", "prompt-lab", "new-hope"]),
    ])

    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticePromptRAGEvaluationLabFixture",
        "promptAsset": prompt_asset,
        "retrievalCorpus": retrieval_corpus,
        "chunkingPolicy": chunking_policy,
        "embeddingCollection": embedding_collection,
        "vectorIndex": vector_index,
        "ragPipeline": rag_pipeline,
        "benchmarkDataset": benchmark_dataset,
        "metricDefinitions": metric_definitions,
        "groundingEvaluation": grounding_evaluation,
        "tuningRun": tuning_run,
        "evalRun": eval_run,
        "humanReviewRubric": human_review_rubric,
        "regressionGate": regression_gate,
        "redTeamCase": red_team_case,
        "evaluationBundle": evaluation_bundle,
        "promptFactsheet": prompt_factsheet,
        "platformRecords": records,
    }


def _platform_record(asset_id: str, asset_kind: str, name: str, source_kind: str, policy_ref: str, evidence_ref: str, surfaces: list[str]) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": asset_id,
        "assetKind": asset_kind,
        "name": name,
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": source_kind,
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": policy_ref,
        "evidenceCorrelationId": evidence_ref,
        "promotionChannel": "lattice-data-governai-demo",
        "compatibilitySurfaces": surfaces,
    }
