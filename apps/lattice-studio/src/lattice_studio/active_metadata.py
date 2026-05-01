"""Lattice active metadata ingestion fixture.

Active metadata is emitted by product/execution events, not only hand-authored
catalog records. This fixture normalizes records from the current Lattice
Studio/Data/GovernAI product surfaces into ingestion events and derived
PlatformAssetRecord enrichment sidecars.
"""

from __future__ import annotations

from typing import Any

from .annotation_training import demo_annotation_training_loop
from .model_zoo import demo_model_zoo_entry
from .platform_records import platform_record_set
from .product_spine import demo_product_spine
from .prompt_rag_eval import demo_prompt_rag_eval_lab
from .publication_review import demo_publication_review_package


def demo_active_metadata_spine() -> dict[str, Any]:
    product_spine = demo_product_spine()
    annotation_training = demo_annotation_training_loop()
    model_zoo = demo_model_zoo_entry()
    prompt_rag = demo_prompt_rag_eval_lab()
    publication_review = demo_publication_review_package()

    source_sets = [
        ("product-spine", product_spine["platformRecords"]["records"]),
        ("annotation-training", annotation_training["platformRecords"]["records"]),
        ("model-zoo", model_zoo["platformRecords"]["records"]),
        ("prompt-rag-eval", prompt_rag["platformRecords"]["records"]),
        ("publication-review", publication_review["platformRecords"]["records"]),
    ]
    events: list[dict[str, Any]] = []
    enrichments: list[dict[str, Any]] = []
    for source_surface, records in source_sets:
        for record in records:
            event = _event_from_record(source_surface, record)
            events.append(event)
            enrichments.append(_enrichment_from_event(event))

    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "LatticeActiveMetadataFixture",
        "sourceSurfaces": [name for name, _ in source_sets],
        "events": events,
        "enrichmentRecords": platform_record_set(enrichments),
        "routing": {
            "searchConsumer": "SocioProphet/sherlock-search#30",
            "topicConsumer": "SocioProphet/slash-topics#23",
            "semanticMembraneConsumer": "SocioProphet/new-hope#7",
            "policyConsumer": "SocioProphet/policy-fabric#39",
            "topologyConsumer": "SocioProphet/sociosphere#238",
        },
        "safety": {"fixtureOnly": True, "network": "none", "secrets": "none", "hostMutation": False},
    }


def _event_from_record(source_surface: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "ActiveMetadataEvent",
        "eventId": f"active-metadata:{source_surface}:{record['assetKind']}:{_safe(record['assetId'])}",
        "sourceSurface": source_surface,
        "sourceRepo": record["producerRepo"],
        "assetId": record["assetId"],
        "assetKind": record["assetKind"],
        "sourceKind": record["sourceKind"],
        "policyRef": record.get("policyRef"),
        "evidenceCorrelationId": record.get("evidenceCorrelationId"),
        "promotionChannel": record.get("promotionChannel"),
        "compatibilitySurfaces": list(record.get("compatibilitySurfaces", [])),
        "emittedBy": "lattice-studio-active-metadata-fixture",
        "emittedAt": "2026-05-01T21:30:00Z",
    }


def _enrichment_from_event(event: dict[str, Any]) -> dict[str, Any]:
    surfaces = set(event["compatibilitySurfaces"])
    surfaces.update({"active-metadata", "sherlock-search", "slash-topics", "policy-fabric"})
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": event["assetId"],
        "assetKind": f"active-metadata-{event['assetKind']}",
        "name": f"Active metadata for {event['assetKind']}",
        "version": "0.1.0",
        "sourceApiVersion": event["apiVersion"],
        "sourceKind": "ActiveMetadataEvent",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": event["policyRef"],
        "evidenceCorrelationId": event["evidenceCorrelationId"],
        "promotionChannel": event["promotionChannel"],
        "compatibilitySurfaces": sorted(surfaces),
    }


def _safe(value: str) -> str:
    return value.replace(":", "-").replace("/", "-")
