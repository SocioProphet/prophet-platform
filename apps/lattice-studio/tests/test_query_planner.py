import json

from lattice_studio.query_planner import (
    QueryRouteRequest,
    demo_query_governance_envelope,
    demo_query_routing_dry_run_plan,
    query_routing_evidence,
    query_routing_to_platform_record,
    route_query,
)
from lattice_studio.query_planner_cli import main


REQUIRED_LANGUAGES = {
    "sql",
    "document-query",
    "annotation-query",
    "sparql",
    "ontology-query",
    "cypher",
    "graphbrain-hypergraph",
    "atomese",
    "sherlock-query",
    "slash-topic-query",
    "newhope-membrane-query",
    "lampstand-local-query",
}


def test_query_routing_dry_run_routes_every_required_language() -> None:
    plan = demo_query_routing_dry_run_plan()
    doc = plan.to_dict()

    assert doc["kind"] == "QueryRoutingDryRunPlan"
    assert {request["language"] for request in doc["requests"]} == REQUIRED_LANGUAGES
    assert len(doc["decisions"]) == len(REQUIRED_LANGUAGES)
    assert {decision["status"] for decision in doc["decisions"]} == {"routable"}
    backend_kinds = {decision["backendKind"] for decision in doc["decisions"]}
    assert "drill-sql" in backend_kinds
    assert "ontology-reasoner" in backend_kinds
    assert "sherlock-index" in backend_kinds
    assert "slash-topic-pack" in backend_kinds
    assert "newhope-runtime" in backend_kinds
    assert "lampstand-local-index" in backend_kinds


def test_query_routing_requires_governance_envelope_before_backend_selection() -> None:
    plan = demo_query_routing_dry_run_plan()
    doc = plan.to_dict()

    for request in doc["requests"]:
        envelope = request["governanceEnvelope"]
        assert envelope["topicScopeRef"].startswith("slash-topic://")
        assert envelope["topicPackRef"].startswith("slash-topics://packs/")
        assert envelope["publicSurfaceRef"].startswith("slash-topics://surfaces/")
        assert envelope["membraneRef"].startswith("newhope://membranes/")
        assert envelope["runtimeSubstrateRef"].startswith("newhope://runtime/")
        assert envelope["runtimeAliasRef"].startswith("slash-topics://runtime/membranes/")
        assert envelope["compatibilityRef"] == envelope["membraneRef"]
        assert envelope["memoryProfileRef"].startswith("memory-mesh://profiles/")
        assert envelope["memoryEventRef"] == "memory-mesh://events/query-route-dry-run"
        assert "lab://nlp-lab/default" in envelope["labProfileRefs"]
        assert "lab://embedding-lab/default" in envelope["labProfileRefs"]
        assert "lab://image-lab/default" in envelope["labProfileRefs"]
        assert "lab://speech-lab/default" in envelope["labProfileRefs"]
        assert "lab://vision-lab/default" in envelope["labProfileRefs"]
        assert envelope["requiredSequence"] == [
            "slash-topic-scope",
            "newhope-membrane-admission",
            "memory-mesh-recall-policy",
            "lab-profile-selection",
            "physical-backend-route",
        ]

    for decision in doc["decisions"]:
        assert decision["governanceEnvelopeRef"]
        assert decision["governanceSequence"][0] == "slash-topic-scope"
        assert decision["governanceSequence"][1] == "newhope-membrane-admission"
        assert decision["governanceSequence"][2] == "memory-mesh-recall-policy"
        assert decision["governanceSequence"][3] == "lab-profile-selection"
        assert decision["governanceSequence"][4] == "physical-backend-route"


def test_query_routing_blocks_when_governance_envelope_is_missing_runtime_substrate() -> None:
    envelope = demo_query_governance_envelope()
    broken = type(envelope)(
        envelope_id=envelope.envelope_id,
        topic_scope_ref=envelope.topic_scope_ref,
        topic_pack_ref=envelope.topic_pack_ref,
        membrane_ref=envelope.membrane_ref,
        public_surface_ref=envelope.public_surface_ref,
        runtime_substrate_ref="",
        runtime_alias_ref=envelope.runtime_alias_ref,
        compatibility_ref=envelope.compatibility_ref,
        memory_profile_ref=envelope.memory_profile_ref,
        memory_event_ref=envelope.memory_event_ref,
        lab_profile_refs=envelope.lab_profile_refs,
        required_sequence=envelope.required_sequence,
    )
    request = QueryRouteRequest(
        request_id="query-request:missing-runtime-substrate",
        language="sql",
        query="SELECT 1",
        catalog_scope="catalog://datasets",
        actor_ref="actor://lattice-studio/demo",
        policy_ref="policy://query/federated",
        governance=broken,
    )

    decision = route_query(request)
    assert decision.status == "blocked"
    assert decision.backend_id is None
    assert "runtime substrate" in decision.reason


def test_query_routing_blocks_when_governance_envelope_is_missing_memory_profile() -> None:
    envelope = demo_query_governance_envelope()
    broken = type(envelope)(
        envelope_id=envelope.envelope_id,
        topic_scope_ref=envelope.topic_scope_ref,
        topic_pack_ref=envelope.topic_pack_ref,
        membrane_ref=envelope.membrane_ref,
        public_surface_ref=envelope.public_surface_ref,
        runtime_substrate_ref=envelope.runtime_substrate_ref,
        runtime_alias_ref=envelope.runtime_alias_ref,
        compatibility_ref=envelope.compatibility_ref,
        memory_profile_ref="",
        memory_event_ref=envelope.memory_event_ref,
        lab_profile_refs=envelope.lab_profile_refs,
        required_sequence=envelope.required_sequence,
    )
    request = QueryRouteRequest(
        request_id="query-request:missing-memory",
        language="sql",
        query="SELECT 1",
        catalog_scope="catalog://datasets",
        actor_ref="actor://lattice-studio/demo",
        policy_ref="policy://query/federated",
        governance=broken,
    )

    decision = route_query(request)
    assert decision.status == "blocked"
    assert decision.backend_id is None
    assert "Memory Mesh" in decision.reason


def test_query_routing_dry_run_preserves_no_execution_boundary() -> None:
    plan = demo_query_routing_dry_run_plan()
    boundary = set(plan.to_dict()["boundary"])

    assert "dry-run-only" in boundary
    assert "slash-topic-scope-required" in boundary
    assert "slash-topics-public-surface-required" in boundary
    assert "newhope-membrane-required" in boundary
    assert "new-hope-runtime-substrate-required" in boundary
    assert "new-hope-compatibility-ref-preserved" in boundary
    assert "slash-topics-runtime-alias-preserved" in boundary
    assert "memory-mesh-context-bound" in boundary
    assert "lab-profile-bound" in boundary
    assert "no-remote-query-execution" in boundary
    assert "no-local-index-read" in boundary
    assert "no-memory-writeback" in boundary
    assert "no-embedding-job" in boundary
    assert "no-lab-runtime-call" in boundary
    assert "no-sql-submission" in boundary
    assert "no-sherlock-query-submission" in boundary
    assert "no-topic-pack-read" in boundary
    assert "no-newhope-runtime-call" in boundary
    assert "no-lampstand-rpc-call" in boundary


def test_query_routing_evidence_and_platform_record() -> None:
    plan = demo_query_routing_dry_run_plan()
    evidence = query_routing_evidence(plan)
    record = query_routing_to_platform_record(plan)

    assert evidence["kind"] == "QueryRoutingEvidence"
    assert evidence["requestCount"] == 12
    assert evidence["decisionCount"] == 12
    assert evidence["routableCount"] == 12
    assert "dry-run-only" in evidence["evidenceReports"]
    assert "slash-topic-scope-required" in evidence["evidenceReports"]
    assert "slash-topics-public-surface" in evidence["evidenceReports"]
    assert "newhope-membrane-required" in evidence["evidenceReports"]
    assert "new-hope-runtime-substrate" in evidence["evidenceReports"]
    assert "new-hope-compatibility-preserved" in evidence["evidenceReports"]
    assert "slash-topics-runtime-alias" in evidence["evidenceReports"]
    assert "memory-mesh-context-bound" in evidence["evidenceReports"]
    assert "lab-profile-bound" in evidence["evidenceReports"]
    assert "ontology-query-route" in evidence["evidenceReports"]
    assert "sherlock-route" in evidence["evidenceReports"]
    assert "slash-topics-route" in evidence["evidenceReports"]
    assert "new-hope-route" in evidence["evidenceReports"]
    assert "lampstand-route" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "query-routing-dry-run-plan"
    assert record["version"] == "0.3.0"
    assert "federated-query" in record["compatibilitySurfaces"]
    assert "slash-topics-public-surface" in record["compatibilitySurfaces"]
    assert "slash-topics-runtime-alias" in record["compatibilitySurfaces"]
    assert "new-hope-runtime-substrate" in record["compatibilitySurfaces"]
    assert "new-hope-compatibility" in record["compatibilitySurfaces"]
    assert "memory-mesh" in record["compatibilitySurfaces"]
    assert "embedding-lab" in record["compatibilitySurfaces"]


def test_query_planner_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "query-routing"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    plan = json.loads((output_dir / "query-routing-dry-run-plan.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "query-routing-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "query-routing-platform-record.json").read_text(encoding="utf-8"))

    assert plan["kind"] == "QueryRoutingDryRunPlan"
    assert evidence["kind"] == "QueryRoutingEvidence"
    assert record["kind"] == "PlatformAssetRecord"
