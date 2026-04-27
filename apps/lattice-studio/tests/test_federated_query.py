import json

from lattice_studio.federated_query import (
    demo_federated_query_plane,
    federated_query_evidence,
    federated_query_to_platform_record,
)
from lattice_studio.federated_query_cli import main


def test_federated_query_plane_covers_required_languages_and_backends() -> None:
    plane = demo_federated_query_plane()
    doc = plane.to_dict()

    assert doc["kind"] == "FederatedQueryPlane"
    languages = {backend["language"] for backend in doc["backends"]}
    assert languages == {
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
    backend_kinds = {backend["kind"] for backend in doc["backends"]}
    assert "drill-sql" in backend_kinds
    assert "ontology-reasoner" in backend_kinds
    assert "sherlock-index" in backend_kinds
    assert "slash-topic-pack" in backend_kinds
    assert "newhope-runtime" in backend_kinds
    assert "lampstand-local-index" in backend_kinds


def test_federated_query_plane_declares_required_repo_integrations() -> None:
    plane = demo_federated_query_plane()
    integrations = {integration["repoRef"]: integration for integration in plane.to_dict()["integrations"]}

    assert set(integrations) == {
        "SocioProphet/sherlock-search",
        "SocioProphet/slash-topics",
        "SocioProphet/new-hope",
        "SocioProphet/lampstand",
    }
    assert "query-replay-receipts" in integrations["SocioProphet/sherlock-search"]["evidenceOutputs"]
    assert "policy-membrane" in integrations["SocioProphet/slash-topics"]["evidenceOutputs"]
    assert "membrane-decision" in integrations["SocioProphet/new-hope"]["evidenceOutputs"]
    assert "local-index-health" in integrations["SocioProphet/lampstand"]["evidenceOutputs"]


def test_federated_query_evidence_and_platform_record() -> None:
    plane = demo_federated_query_plane()
    evidence = federated_query_evidence(plane)
    record = federated_query_to_platform_record(plane)

    assert evidence["kind"] == "FederatedQueryEvidence"
    assert evidence["backendCount"] == 12
    assert evidence["integrationCount"] == 4
    assert "ontology-query" in evidence["evidenceReports"]
    assert "sherlock-query" in evidence["evidenceReports"]
    assert "slash-topic-query" in evidence["evidenceReports"]
    assert "newhope-membrane-query" in evidence["evidenceReports"]
    assert "lampstand-local-query" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "federated-query-plane"
    assert "slash-topics" in record["compatibilitySurfaces"]
    assert "new-hope" in record["compatibilitySurfaces"]
    assert "lampstand" in record["compatibilitySurfaces"]


def test_federated_query_cli_emits_demo_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "federated-query"
    rc = main(["emit-demo", "--output-dir", str(output_dir)])
    assert rc == 0

    plane = json.loads((output_dir / "federated-query-plane.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "federated-query-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "federated-query-platform-record.json").read_text(encoding="utf-8"))

    assert plane["kind"] == "FederatedQueryPlane"
    assert evidence["kind"] == "FederatedQueryEvidence"
    assert record["kind"] == "PlatformAssetRecord"
