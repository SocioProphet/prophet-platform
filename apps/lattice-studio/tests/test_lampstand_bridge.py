import json

from lattice_studio.cli import main
from lattice_studio.lampstand import (
    context_pack_for_results,
    demo_local_search_results,
    local_search_result_to_platform_record,
    promotion_proposals_for_results,
)


def test_demo_lampstand_results_cover_catalog_asset_classes() -> None:
    results = demo_local_search_results()
    by_type = {result.detected_asset_type: result for result in results}

    assert {"data", "ml-model", "application", "service"} == set(by_type)
    assert by_type["data"].candidate_catalog_asset_id == "catalog://datasets/demo-csv"
    assert by_type["ml-model"].candidate_catalog_asset_id == "catalog://models/demo-classifier"
    assert by_type["application"].candidate_catalog_asset_id == "catalog://applications/demo-notebook-app"
    assert by_type["service"].candidate_catalog_asset_id == "catalog://services/demo-inference-service"
    assert "attach-coding-agent" in by_type["service"].suggested_actions


def test_context_pack_and_promotion_proposals_are_deterministic() -> None:
    results = demo_local_search_results()
    context = context_pack_for_results(results, workspace_ref="workspace://demo")
    proposals = promotion_proposals_for_results(results)

    assert context.workspace_ref == "workspace://demo"
    assert "create-catalog-asset" in context.recommended_actions
    assert len(proposals) == 4
    assert {proposal.proposed_asset_type for proposal in proposals} == {"data", "ml-model", "application", "service"}
    assert all(proposal.required_policy_review for proposal in proposals)
    assert all("/datahub" in proposal.suggested_topics for proposal in proposals)


def test_lampstand_results_convert_to_platform_records() -> None:
    records = [local_search_result_to_platform_record(result) for result in demo_local_search_results()]
    kinds = {record["assetKind"] for record in records}

    assert "lampstand-local-data" in kinds
    assert "lampstand-local-ml-model" in kinds
    assert "lampstand-local-application" in kinds
    assert "lampstand-local-service" in kinds
    assert all("lampstand-local-search" in record["compatibilitySurfaces"] for record in records)


def test_cli_emits_lampstand_local_search_and_promotion_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "lampstand"
    rc = main(["emit-lampstand-demo", "--workspace-ref", "workspace://demo", "--output-dir", str(output_dir)])
    assert rc == 0

    results = json.loads((output_dir / "lampstand-local-search-results.json").read_text(encoding="utf-8"))
    context = json.loads((output_dir / "lampstand-context-pack.json").read_text(encoding="utf-8"))
    proposals = json.loads((output_dir / "datahub-promotion-proposals.json").read_text(encoding="utf-8"))
    records = json.loads((output_dir / "lampstand-platform-records.json").read_text(encoding="utf-8"))

    assert results["kind"] == "LampstandLocalSearchResultSet"
    assert context["kind"] == "LampstandContextPack"
    assert proposals["kind"] == "DataHubPromotionProposalSet"
    assert records["kind"] == "PlatformAssetRecordSet"
    assert len(results["results"]) == 4
    assert len(proposals["proposals"]) == 4
    assert len(records["records"]) == 4
