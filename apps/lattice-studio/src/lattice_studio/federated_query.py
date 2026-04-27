"""Federated query plane contracts for Lattice Studio.

Lattice needs one governed query surface over many backends: Drill-compatible SQL,
document stores, annotation stores, RDF/SPARQL, property graphs/Cypher,
GraphBrain-style hypergraphs, and OpenCog AtomSpace/Atomese.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

QueryLanguage = Literal[
    "sql",
    "document-query",
    "annotation-query",
    "sparql",
    "cypher",
    "graphbrain-hypergraph",
    "atomese",
]
BackendKind = Literal[
    "drill-sql",
    "object-lake",
    "document-store",
    "annotation-store",
    "rdf-store",
    "property-graph",
    "hypergraph-store",
    "atomspace",
]


@dataclass(frozen=True)
class FederatedQueryBackend:
    backend_id: str
    kind: BackendKind
    language: QueryLanguage
    endpoint_ref: str
    catalog_scope: list[str]
    policy_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "backendId": self.backend_id,
            "kind": self.kind,
            "language": self.language,
            "endpointRef": self.endpoint_ref,
            "catalogScope": self.catalog_scope,
            "policyRef": self.policy_ref,
        }


@dataclass(frozen=True)
class FederatedQueryExample:
    example_id: str
    language: QueryLanguage
    backend_id: str
    query: str
    expected_result_shape: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "exampleId": self.example_id,
            "language": self.language,
            "backendId": self.backend_id,
            "query": self.query,
            "expectedResultShape": self.expected_result_shape,
        }


@dataclass(frozen=True)
class FederatedQueryPlane:
    plane_id: str
    backends: list[FederatedQueryBackend]
    examples: list[FederatedQueryExample]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "FederatedQueryPlane",
            "planeId": self.plane_id,
            "backends": [backend.to_dict() for backend in self.backends],
            "examples": [example.to_dict() for example in self.examples],
            "createdAt": self.created_at,
            "designRule": "Expose SQL-compatible, document, annotation, SPARQL, Cypher, hypergraph, and Atomese query surfaces through governed catalog and policy bindings.",
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def demo_federated_query_plane() -> FederatedQueryPlane:
    backends = [
        FederatedQueryBackend(
            backend_id="query-backend:drill-lakehouse",
            kind="drill-sql",
            language="sql",
            endpoint_ref="drill://lattice/drillbits/default",
            catalog_scope=["catalog://datasets", "catalog://tables", "catalog://objects"],
            policy_ref="policy://query/sql-federated",
        ),
        FederatedQueryBackend(
            backend_id="query-backend:document-store",
            kind="document-store",
            language="document-query",
            endpoint_ref="docstore://lattice/documents",
            catalog_scope=["catalog://documents", "catalog://reports"],
            policy_ref="policy://query/documents",
        ),
        FederatedQueryBackend(
            backend_id="query-backend:annotation-store",
            kind="annotation-store",
            language="annotation-query",
            endpoint_ref="annotations://lattice/annotations",
            catalog_scope=["catalog://annotations", "catalog://claims", "catalog://labels"],
            policy_ref="policy://query/annotations",
        ),
        FederatedQueryBackend(
            backend_id="query-backend:rdf-store",
            kind="rdf-store",
            language="sparql",
            endpoint_ref="sparql://ontogenesis/query",
            catalog_scope=["catalog://knowledge-graphs", "catalog://ontologies"],
            policy_ref="policy://query/sparql",
        ),
        FederatedQueryBackend(
            backend_id="query-backend:property-graph",
            kind="property-graph",
            language="cypher",
            endpoint_ref="cypher://graph/neo4j-compatible",
            catalog_scope=["catalog://graphs", "catalog://entity-graphs"],
            policy_ref="policy://query/cypher",
        ),
        FederatedQueryBackend(
            backend_id="query-backend:graphbrain",
            kind="hypergraph-store",
            language="graphbrain-hypergraph",
            endpoint_ref="graphbrain://contract/query",
            catalog_scope=["catalog://semantic-hypergraphs", "catalog://claims"],
            policy_ref="policy://query/graphbrain",
        ),
        FederatedQueryBackend(
            backend_id="query-backend:opencog-atomspace",
            kind="atomspace",
            language="atomese",
            endpoint_ref="atomspace://opencog/query",
            catalog_scope=["catalog://atomspace", "catalog://cognitive-graphs"],
            policy_ref="policy://query/atomese",
        ),
    ]
    examples = [
        FederatedQueryExample("query-example:sql-drill", "sql", "query-backend:drill-lakehouse", "SELECT * FROM dfs.`catalog/datasets/demo.parquet` LIMIT 10", "table"),
        FederatedQueryExample("query-example:document", "document-query", "query-backend:document-store", "FIND documents WHERE tags CONTAINS 'lattice' LIMIT 10", "document-list"),
        FederatedQueryExample("query-example:annotation", "annotation-query", "query-backend:annotation-store", "FIND annotations WHERE target='catalog://documents/demo' AND label='claim'", "annotation-list"),
        FederatedQueryExample("query-example:sparql", "sparql", "query-backend:rdf-store", "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10", "triple-table"),
        FederatedQueryExample("query-example:cypher", "cypher", "query-backend:property-graph", "MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 10", "graph-paths"),
        FederatedQueryExample("query-example:graphbrain", "graphbrain-hypergraph", "query-backend:graphbrain", "MATCH hyperedge WHERE lemma='prove' LIMIT 10", "hyperedge-list"),
        FederatedQueryExample("query-example:atomese", "atomese", "query-backend:opencog-atomspace", "(Get (VariableList (Variable \"$x\")) (ConceptNode \"Lattice\"))", "atom-list"),
    ]
    payload = {"backendCount": len(backends), "languages": sorted({backend.language for backend in backends})}
    return FederatedQueryPlane(
        plane_id=_digest("federated-query-plane", payload),
        backends=backends,
        examples=examples,
    )


def federated_query_evidence(plane: FederatedQueryPlane) -> dict[str, Any]:
    doc = plane.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    languages = sorted({backend.language for backend in plane.backends})
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "FederatedQueryEvidence",
        "planeId": plane.plane_id,
        "planeDigest": f"sha256:{digest}",
        "backendCount": len(plane.backends),
        "languages": languages,
        "evidenceReports": [
            "drill-compatible-sql",
            "document-query",
            "annotation-query",
            "sparql-query",
            "cypher-query",
            "graphbrain-hypergraph-query",
            "atomese-query",
            "policy-bound-query-backends",
        ],
    }


def federated_query_to_platform_record(plane: FederatedQueryPlane) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plane.plane_id,
        "assetKind": "federated-query-plane",
        "name": "lattice-studio-federated-query-plane",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "FederatedQueryPlane",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://query/federated",
        "evidenceCorrelationId": plane.plane_id,
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "lattice-studio",
            "apache-drill",
            "sql",
            "document-store",
            "annotation-store",
            "sparql",
            "cypher",
            "graphbrain",
            "opencog",
            "atomese",
            "sherlock-search",
            "ontogenesis",
        ],
    }
