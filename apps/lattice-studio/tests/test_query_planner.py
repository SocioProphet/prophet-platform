import json

from lattice_studio.query_planner import (
    demo_query_routing_dry_run_plan,
    query_routing_evidence,
    query_routing_to_platform_record,
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


def test_query_routing_dry_run_preserves_no_execution_boundary() -> None:
    plan = demo_query_routing_dry_run_plan()
    boundary = set(plan.to_dict()["boundary"])

    assert "dry-run-only" in boundary
    assert "no-remote-query-execution" in boundary
    assert "no-local-index-read" in boundary
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
    assert "ontology-query-route" in evidence["evidenceReports"]
    assert "sherlock-route" in evidence["evidenceReports"]
    assert "slash-topics-route" in evidence["evidenceReports"]
    assert "new-hope-route" in evidence["evidenceReports"]
    assert "lampstand-route" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "query-routing-dry-run-plan"
    assert "federated-query" in record["compatibilitySurfaces"]


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
