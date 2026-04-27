"""Ontogenesis semantic-governance context for Lattice Studio.

Ontogenesis owns the RDF/OWL/JSON-LD/SHACL lifecycle for platform semantics.
This sidecar binds Lattice Studio artifacts to the ontology modules and gates
that must validate them before catalog/search/memory/governance promotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class OntogenesisContext:
    ontogenesis_context_id: str
    namespace_base: str
    module_refs: list[str]
    shape_refs: list[str]
    jsonld_context_refs: list[str]
    governed_record_kinds: list[str]
    promotion_gates: list[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "OntogenesisContext",
            "ontogenesisContextId": self.ontogenesis_context_id,
            "namespaceBase": self.namespace_base,
            "moduleRefs": self.module_refs,
            "shapeRefs": self.shape_refs,
            "jsonldContextRefs": self.jsonld_context_refs,
            "governedRecordKinds": self.governed_record_kinds,
            "promotionGates": self.promotion_gates,
            "createdAt": self.created_at,
            "sourceRepo": "SocioProphet/ontogenesis",
        }


def demo_ontogenesis_context() -> OntogenesisContext:
    seed = "ontogenesis:lattice-studio:datahub"
    return OntogenesisContext(
        ontogenesis_context_id="ontogenesis-context:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
        namespace_base="https://socioprophet.github.io/ontogenesis/",
        module_refs=[
            "Upper/upper-core.ttl",
            "Middle/system-architecture.ttl",
            "Lower/bindings-core.ttl",
            "Platform/SourceOS.ttl",
            "Platform/Mesh.ttl",
            "Domains/metadata.ttl",
            "Domains/product-service.ttl",
            "prophet/prophet_cli.ttl",
            "prophet/capd.ttl",
        ],
        shape_refs=[
            "shapes/core.shacl.ttl",
            "shapes/ontogenesis.shacl.ttl",
            "shapes/product-service.shacl.ttl",
        ],
        jsonld_context_refs=[
            "docs/specs/namespaces.md",
            "catalog/registry.ttl",
        ],
        governed_record_kinds=[
            "CatalogAsset",
            "CatalogAssetVersion",
            "NotebookSession",
            "PaaSDeploymentPlan",
            "AtlasContext",
            "LocalDevSession",
            "LampstandLocalSearchResult",
            "DataHubPromotionProposal",
            "MemoryEvent",
            "PlatformAssetRecord",
        ],
        promotion_gates=[
            "rdf-parse-validation",
            "shacl-validation",
            "jsonld-roundtrip",
            "ledger-build-verify",
            "spdx-sbom",
            "semantic-promotion-review",
        ],
    )


def ontogenesis_evidence(context: OntogenesisContext) -> dict[str, Any]:
    doc = context.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "OntogenesisContextEvidence",
        "ontogenesisContextId": context.ontogenesis_context_id,
        "contextDigest": f"sha256:{digest}",
        "evidenceReports": [
            "namespace-binding",
            "ontology-module-binding",
            "shacl-gate-binding",
            "jsonld-context-binding",
            "governed-record-kind-binding",
            "promotion-gate-binding",
        ],
    }


def ontogenesis_to_platform_record(context: OntogenesisContext) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": context.ontogenesis_context_id,
        "assetKind": "ontogenesis-context",
        "name": "lattice-studio-ontogenesis-context",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "OntogenesisContext",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "SocioProphet/ontogenesis:shapes/ontogenesis.shacl.ttl",
        "evidenceCorrelationId": context.ontogenesis_context_id,
        "promotionChannel": "semantic-governance-demo",
        "compatibilitySurfaces": [
            "lattice-studio",
            "datahub",
            "ontogenesis",
            "json-ld",
            "rdf",
            "shacl",
            "memory-mesh",
            "sherlock-search",
        ],
    }
