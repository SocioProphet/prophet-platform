"""Dry-run query routing planner for the Lattice federated query plane.

The planner proves routing decisions without executing remote queries. It binds a
query language to the governed backend declared by FederatedQueryPlane and emits
route, policy, catalog, memory, lab, and safety evidence.

Architecture rule: Slash Topics and New Hope are not merely peer backends.
Every nontrivial query is routed through a governance envelope first:

1. Slash Topics provides the public query/governance surface, explicit topic scope,
   topic pack, public adapter, future runtime alias, and memory posture.
2. New Hope provides the internal membrane/runtime substrate and compatibility refs
   for carrier/receptor/protocol/membrane/replay/provenance/federation semantics.
3. Memory Mesh records scoped recall/writeback/evidence policy without storing raw
   sensitive payloads by default.
4. Lab profiles define model/customization inputs for embeddings, NLP, image,
   speech, and vision without executing lab runtimes during dry-run planning.
5. Physical routing selects Sherlock, Drill, SPARQL, Cypher, Atomese, Lampstand,
   or other backend lanes only after that envelope is present.
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
class QueryGovernanceEnvelope:
    envelope_id: str
    topic_scope_ref: str
    topic_pack_ref: str
    membrane_ref: str
    public_surface_ref: str
    runtime_substrate_ref: str
    runtime_alias_ref: str
    compatibility_ref: str
    memory_profile_ref: str
    memory_event_ref: str
    lab_profile_refs: list[str]
    required_sequence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelopeId": self.envelope_id,
            "topicScopeRef": self.topic_scope_ref,
            "topicPackRef": self.topic_pack_ref,
            "membraneRef": self.membrane_ref,
            "publicSurfaceRef": self.public_surface_ref,
            "runtimeSubstrateRef": self.runtime_substrate_ref,
            "runtimeAliasRef": self.runtime_alias_ref,
            "compatibilityRef": self.compatibility_ref,
            "memoryProfileRef": self.memory_profile_ref,
            "memoryEventRef": self.memory_event_ref,
            "labProfileRefs": self.lab_profile_refs,
            "requiredSequence": self.required_sequence,
        }


@dataclass(frozen=True)
class QueryRouteRequest:
    request_id: str
    language: QueryLanguage
    query: str
    catalog_scope: str
    actor_ref: str
    policy_ref: str
    governance: QueryGovernanceEnvelope

    def to_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "language": self.language,
            "query": self.query,
            "catalogScope": self.catalog_scope,
            "actorRef": self.actor_ref,
            "policyRef": self.policy_ref,
            "governanceEnvelope": self.governance.to_dict(),
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
    governance_envelope_ref: str
    governance_sequence: list[str]
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
            "governanceEnvelopeRef": self.governance_envelope_ref,
            "governanceSequence": self.governance_sequence,
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
                "slash-topic-scope-required",
                "slash-topics-public-surface-required",
                "newhope-membrane-required",
                "new-hope-runtime-substrate-required",
                "new-hope-compatibility-ref-preserved",
                "slash-topics-runtime-alias-preserved",
                "memory-mesh-context-bound",
                "lab-profile-bound",
                "no-remote-query-execution",
                "no-local-index-read",
                "no-memory-writeback",
                "no-embedding-job",
                "no-lab-runtime-call",
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


def demo_query_governance_envelope(topic: str = "/lattice/federated-query") -> QueryGovernanceEnvelope:
    payload = {"topic": topic, "membrane": "query-admission", "memory": "scoped-recall"}
    compatibility_ref = "newhope://membranes/query-admission@0.1.0"
    return QueryGovernanceEnvelope(
        envelope_id=_digest("query-governance", payload),
        topic_scope_ref=f"slash-topic://{topic.strip('/')}",
        topic_pack_ref="slash-topics://packs/lattice-federated-query@0.1.0",
        membrane_ref=compatibility_ref,
        public_surface_ref="slash-topics://surfaces/lattice-query-governance@0.1.0",
        runtime_substrate_ref="newhope://runtime/membrane-substrate@0.1.0",
        runtime_alias_ref="slash-topics://runtime/membranes/query-admission@0.1.0",
        compatibility_ref=compatibility_ref,
        memory_profile_ref="memory-mesh://profiles/slash-topic-scoped-recall@0.1.0",
        memory_event_ref="memory-mesh://events/query-route-dry-run",
        lab_profile_refs=[
            "lab://nlp-lab/default",
            "lab://embedding-lab/default",
            "lab://image-lab/default",
            "lab://speech-lab/default",
            "lab://vision-lab/default",
        ],
        required_sequence=[
            "slash-topic-scope",
            "newhope-membrane-admission",
            "memory-mesh-recall-policy",
            "lab-profile-selection",
            "physical-backend-route",
        ],
    )


def _blocked_decision(request: QueryRouteRequest, reason: str) -> QueryRouteDecision:
    payload = {"requestId": request.request_id, "language": request.language, "status": "blocked", "reason": reason}
    return QueryRouteDecision(
        decision_id=_digest("query-route", payload),
        request_id=request.request_id,
        status="blocked",
        backend_id=None,
        backend_kind=None,
        endpoint_ref=None,
        policy_ref=None,
        catalog_scope=[],
        governance_envelope_ref=request.governance.envelope_id,
        governance_sequence=request.governance.required_sequence,
        reason=reason,
    )


def route_query(request: QueryRouteRequest) -> QueryRouteDecision:
    if not request.governance.topic_scope_ref.startswith("slash-topic://"):
        return _blocked_decision(request, "Missing Slash Topic scope.")
    if not request.governance.topic_pack_ref.startswith("slash-topics://packs/"):
        return _blocked_decision(request, "Missing Slash Topics topic pack reference.")
    if not request.governance.public_surface_ref.startswith("slash-topics://surfaces/"):
        return _blocked_decision(request, "Missing Slash Topics public query/governance surface reference.")
    if not request.governance.membrane_ref.startswith("newhope://membranes/"):
        return _blocked_decision(request, "Missing New Hope membrane admission reference.")
    if not request.governance.runtime_substrate_ref.startswith("newhope://runtime/"):
        return _blocked_decision(request, "Missing New Hope runtime substrate reference.")
    if not request.governance.runtime_alias_ref.startswith("slash-topics://runtime/membranes/"):
        return _blocked_decision(request, "Missing future Slash Topics runtime alias reference.")
    if request.governance.compatibility_ref != request.governance.membrane_ref:
        return _blocked_decision(request, "New Hope compatibility reference must match membrane admission reference.")
    if not request.governance.memory_profile_ref.startswith("memory-mesh://profiles/"):
        return _blocked_decision(request, "Missing Memory Mesh scoped memory profile.")
    if not request.governance.lab_profile_refs:
        return _blocked_decision(request, "Missing lab profile references.")

    plane = demo_federated_query_plane()
    candidates = [backend for backend in plane.backends if backend.language == request.language]
    if not candidates:
        return _blocked_decision(request, f"No backend registered for language {request.language}.")
    backend = candidates[0]
    scope_allowed = request.catalog_scope in backend.catalog_scope or request.catalog_scope == "*"
    status: RouteDecisionStatus = "routable" if scope_allowed else "blocked"
    reason = "Catalog scope is allowed after Slash Topics public surface, New Hope runtime substrate, Memory Mesh, and lab-profile envelope checks." if scope_allowed else "Requested catalog scope is outside selected backend policy scope."
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
        governance_envelope_ref=request.governance.envelope_id,
        governance_sequence=request.governance.required_sequence,
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
    governance = demo_query_governance_envelope()
    for language, query, scope in raw:
        payload = {"language": language, "scope": scope, "query": query, "governance": governance.envelope_id}
        requests.append(
            QueryRouteRequest(
                request_id=_digest("query-request", payload),
                language=language,  # type: ignore[arg-type]
                query=query,
                catalog_scope=scope,
                actor_ref="actor://lattice-studio/demo",
                policy_ref="policy://query/federated",
                governance=governance,
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
            "slash-topic-scope-required",
            "slash-topics-public-surface",
            "newhope-membrane-required",
            "new-hope-runtime-substrate",
            "new-hope-compatibility-preserved",
            "slash-topics-runtime-alias",
            "memory-mesh-context-bound",
            "lab-profile-bound",
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
        "version": "0.3.0",
        "sourceApiVersion": "studio.socioprophet.dev/v1",
        "sourceKind": "QueryRoutingDryRunPlan",
        "producerRepo": "SocioProphet/prophet-platform",
        "policyRef": "policy://query/federated",
        "evidenceCorrelationId": plan.plan_id,
        "promotionChannel": "dry-run",
        "compatibilitySurfaces": [
            "lattice-studio",
            "federated-query",
            "query-routing-dry-run",
            "slash-topics-public-surface",
            "slash-topics",
            "slash-topics-runtime-alias",
            "new-hope-runtime-substrate",
            "new-hope-compatibility",
            "new-hope",
            "memory-mesh",
            "nlp-lab",
            "embedding-lab",
            "image-lab",
            "speech-lab",
            "vision-lab",
            "apache-drill",
            "document-store",
            "annotation-store",
            "sparql",
            "ontology-query",
            "cypher",
            "graphbrain",
            "atomese",
            "sherlock-search",
            "lampstand",
            "ontogenesis",
        ],
    }
