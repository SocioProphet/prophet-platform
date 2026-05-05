from __future__ import annotations

import json
from pathlib import Path

from cell_service import CellService
from cell_service.feed import private_feed_document, rss_feed_document
from cell_service.publication import cell_publication_bundle, new_hope_membrane_event, sherlock_search_packet, slash_topic_surface

ROOT = Path(__file__).resolve().parents[3]
LOOP_CONTRACT = ROOT / "contracts/cell/personal-intelligence-cell.loop.v1.example.json"


def load_loop() -> dict:
    return json.loads(LOOP_CONTRACT.read_text(encoding="utf-8"))


def test_private_feed_document_and_rss() -> None:
    loop = load_loop()
    cell = loop["cell"]
    feed_item = loop["feed_item"]
    signal = loop["signal"]
    private = private_feed_document(cell, [feed_item], {signal["id"]: signal})

    assert private["feed_kind"] == "private"
    assert private["cell_id"] == cell["id"]
    assert private["item_count"] == 1
    assert private["items"][0]["signal"]["extractions"]["repo"] == "SocioProphet/prophet-platform"

    rss = rss_feed_document(cell=cell, feed_items=[feed_item], signals={signal["id"]: signal})
    assert "<rss version=\"2.0\"" in rss
    assert "Runtime design changed in prophet-platform" in rss
    assert signal["id"] in rss


def test_publication_bridge_shapes() -> None:
    loop = load_loop()
    slash = slash_topic_surface(cell=loop["cell"], watch=loop["watch"], signal=loop["signal"], feed_item=loop["feed_item"])
    membrane = new_hope_membrane_event(cell=loop["cell"], signal=loop["signal"], feed_item=loop["feed_item"])
    packet = sherlock_search_packet(cell=loop["cell"], watch=loop["watch"], signal=loop["signal"], feed_item=loop["feed_item"])

    assert slash["surfaceKind"] == "slash-topic-cell-signal"
    assert slash["topicRef"].startswith("/cell/")
    assert slash["evidenceRefs"] == loop["signal"]["evidence_refs"]

    assert membrane["schemaVersion"] == "new-hope-cell-membrane.v0.1"
    assert membrane["membraneOutcome"] == "admit"
    assert membrane["lineage"]["signalRef"] == loop["signal"]["id"]

    assert packet["schemaVersion"] == "v0.1"
    assert packet["results"][0]["resultId"] == loop["signal"]["id"]
    assert packet["evidenceRefs"] == loop["signal"]["evidence_refs"]
    assert packet["scope"]["policyDecisionRefs"]


def test_cell_service_exports_feed_and_publication_bundle() -> None:
    service = CellService()
    loop = load_loop()
    result = service.run_loop_contract(loop)

    private = result["private_feed"]
    rss = result["rss_feed"]
    bundle = result["publication_bundle"]

    assert private["item_count"] == 1
    assert "<rss version=\"2.0\"" in rss
    assert bundle["slashTopicSurface"]["signalRef"] == result["signal"]["id"]
    assert bundle["newHopeMembraneEvent"]["membraneOutcome"] == "admit"
    assert bundle["sherlockSearchPacket"]["results"][0]["confidence"] == result["signal"]["confidence_score"]


def test_cell_publication_bundle_contains_all_required_surfaces() -> None:
    loop = load_loop()
    bundle = cell_publication_bundle(cell=loop["cell"], watch=loop["watch"], signal=loop["signal"], feed_item=loop["feed_item"])

    assert set(bundle) == {"slashTopicSurface", "newHopeMembraneEvent", "sherlockSearchPacket"}
