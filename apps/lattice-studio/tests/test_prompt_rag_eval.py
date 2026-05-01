from lattice_studio.prompt_rag_eval import demo_prompt_rag_eval_lab
from lattice_studio.runtime_profiles import BEAM_RUNTIME_REF, RAY_RUNTIME_REF


def test_prompt_rag_eval_lab_emits_required_objects() -> None:
    fixture = demo_prompt_rag_eval_lab()

    assert fixture["kind"] == "LatticePromptRAGEvaluationLabFixture"
    assert fixture["promptAsset"]["kind"] == "PromptAsset"
    assert fixture["retrievalCorpus"]["kind"] == "RetrievalCorpus"
    assert fixture["chunkingPolicy"]["kind"] == "ChunkingPolicy"
    assert fixture["embeddingCollection"]["kind"] == "EmbeddingCollection"
    assert fixture["vectorIndex"]["kind"] == "VectorIndex"
    assert fixture["ragPipeline"]["kind"] == "RAGPipeline"
    assert fixture["benchmarkDataset"]["kind"] == "BenchmarkDataset"
    assert fixture["groundingEvaluation"]["kind"] == "GroundingEvaluation"
    assert fixture["tuningRun"]["kind"] == "TuningRun"
    assert fixture["evalRun"]["kind"] == "EvalRun"
    assert fixture["humanReviewRubric"]["kind"] == "HumanReviewRubric"
    assert fixture["regressionGate"]["kind"] == "RegressionGate"
    assert fixture["redTeamCase"]["kind"] == "RedTeamCase"
    assert fixture["evaluationBundle"]["kind"] == "EvaluationBundle"
    assert fixture["promptFactsheet"]["kind"] == "Factsheet"


def test_prompt_rag_eval_lab_preserves_data_runtime_and_retrieval_lineage() -> None:
    fixture = demo_prompt_rag_eval_lab()

    data_product_ref = "urn:srcos:data-product:community_truth_demo"
    prompt_ref = fixture["promptAsset"]["id"]
    corpus_ref = fixture["retrievalCorpus"]["id"]
    vector_ref = fixture["vectorIndex"]["id"]
    rag_ref = fixture["ragPipeline"]["id"]
    eval_ref = fixture["evaluationBundle"]["id"]

    assert fixture["retrievalCorpus"]["dataProductRefs"] == [data_product_ref]
    assert fixture["embeddingCollection"]["corpusRef"] == corpus_ref
    assert fixture["embeddingCollection"]["runtimeRef"] == BEAM_RUNTIME_REF
    assert fixture["vectorIndex"]["embeddingCollectionRef"] == fixture["embeddingCollection"]["id"]
    assert fixture["vectorIndex"]["runtimeRef"] == BEAM_RUNTIME_REF
    assert fixture["ragPipeline"]["promptRef"] == prompt_ref
    assert fixture["ragPipeline"]["retrievalCorpusRef"] == corpus_ref
    assert fixture["ragPipeline"]["vectorIndexRef"] == vector_ref
    assert fixture["ragPipeline"]["runtimeRef"] == RAY_RUNTIME_REF
    assert fixture["ragPipeline"]["retrievalRuntimeRef"] == BEAM_RUNTIME_REF
    assert fixture["ragPipeline"]["dataProductRefs"] == [data_product_ref]
    assert fixture["tuningRun"]["runtimeRef"] == RAY_RUNTIME_REF
    assert fixture["evalRun"]["runtimeRef"] == RAY_RUNTIME_REF
    assert fixture["evaluationBundle"]["runtimeRef"] == RAY_RUNTIME_REF
    assert fixture["evaluationBundle"]["retrievalRuntimeRef"] == BEAM_RUNTIME_REF
    assert fixture["evalRun"]["subjectRef"] == rag_ref
    assert fixture["evalRun"]["evaluationBundleRef"] == eval_ref
    assert fixture["promptFactsheet"]["subjectRef"] == rag_ref
    assert fixture["promptFactsheet"]["evaluationRefs"] == [eval_ref]
    assert data_product_ref in fixture["promptFactsheet"]["lineageRefs"]


def test_prompt_rag_eval_lab_has_governance_gates_and_review_posture() -> None:
    fixture = demo_prompt_rag_eval_lab()

    grounding = fixture["groundingEvaluation"]
    regression = fixture["regressionGate"]
    red_team = fixture["RedTeamCase"] if "RedTeamCase" in fixture else fixture["redTeamCase"]
    bundle = fixture["evaluationBundle"]
    factsheet = fixture["promptFactsheet"]

    metric_statuses = {metric["name"]: metric["status"] for metric in grounding["metrics"]}
    assert metric_statuses["faithfulness"] == "pass"
    assert metric_statuses["citation_coverage"] == "warn"
    assert grounding["verdict"] == "needs-review"
    assert bundle["verdict"] == "needs-review"
    assert bundle["riskTier"] == "medium"
    assert factsheet["approval"]["state"] == "needs-review"
    assert regression["blocksPromotion"] is True
    assert regression["state"] == "needs-review"
    assert red_team["expectedBehavior"].startswith("Refuse unsupported claim")


def test_prompt_rag_eval_lab_emits_platform_records_for_search_policy_and_membrane() -> None:
    records = demo_prompt_rag_eval_lab()["platformRecords"]

    assert records["kind"] == "PlatformAssetRecordSet"
    kinds = {record["assetKind"] for record in records["records"]}
    assert kinds == {
        "prompt-asset",
        "rag-pipeline",
        "vector-index",
        "evaluation-bundle",
        "prompt-factsheet",
    }
    rag_record = next(record for record in records["records"] if record["assetKind"] == "rag-pipeline")
    assert "new-hope" in rag_record["compatibilitySurfaces"]
    assert "policy-fabric" in rag_record["compatibilitySurfaces"]
    assert "ray" in rag_record["compatibilitySurfaces"]
    assert "beam" in rag_record["compatibilitySurfaces"]
    vector_record = next(record for record in records["records"] if record["assetKind"] == "vector-index")
    assert "beam" in vector_record["compatibilitySurfaces"]
    prompt_record = next(record for record in records["records"] if record["assetKind"] == "prompt-asset")
    assert "sherlock-search" in prompt_record["compatibilitySurfaces"]
    assert "slash-topics" in prompt_record["compatibilitySurfaces"]
