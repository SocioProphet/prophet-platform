"""Dry-run query routing planner for the Lattice federated query plane.

The planner proves routing decisions without executing remote queries. It binds a
query language to the governed backend declared by FederatedQueryPlane and emits
route, policy, catalog, and safety evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .federated_query import QueryLanguage, demo_federated_query_plane

RouteDecisionStatus = Literal["routable", "blocked"]


@dataclass(frozen=True)
class QueryRouteRequest:
    request_id: str
    language: QueryLanguage
    query: str
    catalog_scope: str
    actor_ref: str
    policy_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "language": self.language,
            "query": self.query,
            "catalogScope": self.catalog_scope,
            "actorRef": self.actor_ref,
            "policyRef": self.policy_ref,
        }


@dataclass(frozen=True)
class QueryRouteDecision:
    decision_id: str
    request_id: str
    status: RouteDecisionStatus
    backend_id: str | None
    backend_kind: str | None
    endpoint_ref: str | None
    policy_ref: str | None
    catalog_scope: list[str]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisionId": self.decision_id,
            "requestId": self.request_id,
            "status": self.status,
            "backendId": self.backend_id,
            "backendKind": self.backend_kind,
            "endpointRef": self.endpoint_ref,
            "policyRef": self.policy_ref,
            "catalogScope": self.catalog_scope,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class QueryRoutingDryRunPlan:
    plan_id: str
    query_plane_ref: str
    requests: list[QueryRouteRequest]
    decisions: list[QueryRouteDecision]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": "studio.socioprophet.dev/v1",
            "kind": "QueryRoutingDryRunPlan",
            "planId": self.plan_id,
            "queryPlaneRef": self.query_plane_ref,
            "requests": [request.to_dict() for request in self.requests],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "createdAt": self.created_at,
            "boundary": [
                "dry-run-only",
                "no-remote-query-execution",
                "no-local-index-read",
                "no-sql-submission",
                "no-sparql-submission",
                "no-cypher-submission",
                "no-atomese-submission",
                "no-sherlock-query-submission",
                "no-topic-pack-read",
                "no-newhope-runtime-call",
                "no-lampstand-rpc-call",
            ],
        }


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    seed = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def route_query(request: QueryRouteRequest) -> QueryRouteDecision:
    plane = demo_federated_query_plane()
    candidates = [backend for backend in plane.backends if backend.language == request.language]
    if not candidates:
        payload = {"requestId": request.request_id, "language": request.language, "status": "blocked"}
        return QueryRouteDecision(
            decision_id=_digest("query-route", payload),
            request_id=request.request_id,
            status="blocked",
            backend_id=None,
            backend_kind=None,
            endpoint_ref=None,
            policy_ref=None,
            catalog_scope=[],
            reason=f"No backend registered for language {request.language}.",
        )
    backend = candidates[0]
    scope_allowed = request.catalog_scope in backend.catalog_scope or request.catalog_scope == "*"
    status: RouteDecisionStatus = "routable" if scope_allowed else "blocked"
    reason = "Catalog scope is allowed for selected backend." if scope_allowed else "Requested catalog scope is outside selected backend policy scope."
    payload = {"requestId": request.request_id, "backendId": backend.backend_id, "status": status}
    return QueryRouteDecision(
        decision_id=_digest("query-route", payload),
        request_id=request.request_id,
        status=status,
        backend_id=backend.backend_id,
        backend_kind=backend.kind,
        endpoint_ref=backend.endpoint_ref,
        policy_ref=backend.policy_ref,
        catalog_scope=backend.catalog_scope,
        reason=reason,
    )


def demo_query_route_requests() -> list[QueryRouteRequest]:
    raw = [
        ("sql", "SELECT * FROM dfs.`catalog/datasets/demo.parquet` LIMIT 10", "catalog://datasets"),
        ("document-query", "FIND documents WHERE tags CONTAINS 'lattice' LIMIT 10", "catalog://documents"),
        ("annotation-query", "FIND annotations WHERE label='claim'", "catalog://annotations"),
        ("sparql", "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10", "catalog://knowledge-graphs"),
        ("ontology-query", "FIND classes WHERE subclassOf='socioprophet:PlatformAsset'", "catalog://ontologies"),
        ("cypher", "MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 10", "catalog://graphs"),
        ("graphbrain-hypergraph", "MATCH hyperedge WHERE lemma='prove' LIMIT 10", "catalog://semantic-hypergraphs"),
        ("atomese", "(Get (VariableList (Variable \"$x\")) (ConceptNode \"Lattice\"))", "catalog://atomspace"),
        ("sherlock-query", "SEARCH lattice FACET assetKind", "catalog://platform-records"),
        ("slash-topic-query", "/lattice/federated-query SELECT topicPack", "catalog://topic-packs"),
        ("newhope-membrane-query", "FIND claims WHERE membrane.decision='allow'", "catalog://claims"),
        ("lampstand-local-query", "LOCAL SEARCH 'notebook promotion' LIMIT 20", "catalog://local-files"),
    ]
    requests: list[QueryRouteRequest] = []
    for language, query, scope in raw:
        payload = {"language": language, "scope": scope, "query": query}
        requests.append(
            QueryRouteRequest(
                request_id=_digest("query-request", payload),
                language=language,  # type: ignore[arg-type]
                query=query,
                catalog_scope=scope,
                actor_ref="actor://lattice-studio/demo",
                policy_ref="policy://query/federated",
            )
        )
    return requests


def demo_query_routing_dry_run_plan() -> QueryRoutingDryRunPlan:
    plane = demo_federated_query_plane()
    requests = demo_query_route_requests()
    decisions = [route_query(request) for request in requests]
    payload = {"planeId": plane.plane_id, "requests": len(requests), "decisions": len(decisions)}
    return QueryRoutingDryRunPlan(
        plan_id=_digest("query-routing-dry-run", payload),
        query_plane_ref=plane.plane_id,
        requests=requests,
        decisions=decisions,
    )


def query_routing_evidence(plan: QueryRoutingDryRunPlan) -> dict[str, Any]:
    doc = plan.to_dict()
    digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "apiVersion": "studio.socioprophet.dev/v1",
        "kind": "QueryRoutingEvidence",
        "planId": plan.plan_id,
        "planDigest": f"sha256:{digest}",
        "requestCount": len(plan.requests),
        "decisionCount": len(plan.decisions),
        "routableCount": sum(1 for decision in plan.decisions if decision.status == "routable"),
        "evidenceReports": [
            "dry-run-only",
            "no-remote-query-execution",
            "query-language-routing",
            "catalog-scope-policy-check",
            "backend-policy-binding",
            "drill-sql-route",
            "document-query-route",
            "annotation-query-route",
            "sparql-route",
            "ontology-query-route",
            "cypher-route",
            "graphbrain-route",
            "atomese-route",
            "sherlock-route",
            "slash-topics-route",
            "new-hope-route",
            "lampstand-route",
        ],
    }


def query_routing_to_platform_record(plan: QueryRoutingDryRunPlan) -> dict[str, Any]:
    return {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecord",
        "assetId": plan.plan_id,
        "assetKind": "query-routing-dry-run-plan",
        "name": "lattice-studio-query-routing-dry-run-plan",
        "version": "0.1.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "QueryRoutingDryRunPlan",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://query/federated",
        "evidenceCorrelationId": plan.plan_id,
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "lattice-studio",
            "federated-query",
            "apache-drill",
            "document-store",
            "annotation-store",
            "sparql",
            "ontology-query",
            "cypher",
            "graphbrain",
            "atomese",
            "sherlock-search",
            "slash-topics",
            "new-hope",
            "lampstand",
            "ontogenesis",
        ],
    }
