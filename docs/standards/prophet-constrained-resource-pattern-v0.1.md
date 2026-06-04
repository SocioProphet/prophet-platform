# Prophet Constrained Resource Pattern v0.1

Status: planning contract / architecture standard

Scope: Prophet Platform, Sociosphere, AgentPlane, SourceOS, GAIA, Sherlock, Holmes, semantic-serdes, model governance, and constrained edge/fog runtimes.

Non-claim: this document does not implement CoAP, OSCORE, CoMI, SenML, LwM2M, or any IETF protocol. It defines a compatible architectural pattern and a future adapter profile for constrained-resource interoperability.

## 1. Purpose

The Prophet Constrained Resource Pattern defines a transport-neutral resource model for discovery, registration, compact schema identifiers, topic trees, asynchronous result handling, overload control, security-context separation, and interop validation.

The design is intentionally compatible with lessons from IETF CoRE patterns without making CoAP the mandatory runtime substrate. HTTP, gRPC, TriTRPC, local IPC, event streams, and future CoAP/CBOR bindings should all map to the same resource semantics.

## 2. Compatibility anchors

The pattern is informed by these external design anchors:

- Resource Directory: registration, lookup, replication, multiple resource directories, and eventual consistency.
- DNS-SD style discovery: discovery hooks should be extension points rather than hard-coded registry assumptions.
- CoMI/YANG-CBOR/SID: compact management identifiers and schema item IDs are useful for constrained environments and for large semantic estates.
- Pub/Sub and Dynlink: topic trees, dynamic links, and conditional notification are the correct shape for eventing and observation.
- Pending / Too Many Requests: asynchronous result availability and overload feedback must be explicit protocol states.
- CoCoA congestion lessons: blind retry loops and reset-to-initial-RTO behavior are unsafe under fan-out, bufferbloat, constrained links, and agent swarms.
- OSCORE group communication: separate common, sender, recipient, group-manager, epoch, and runtime-derived security context concepts.
- F-Interop: interoperability should be validated with coordinated sessions, traffic capture, message dissection, replay, and verdict generation.

## 3. Resource model

Every platform object that can be discovered, addressed, observed, managed, invoked, or audited SHOULD be modeled as a resource.

Canonical resource classes:

- agent
- tool
- model
- adapter
- dataset
- topic
- device
- node
- service
- observation
- evidence
- policy
- job
- workflow
- capability
- schema
- ontology-term
- trust-context
- runtime-context

Each resource SHOULD expose:

```json
{
  "resource_id": "prophet.resource.<stable-id>",
  "resource_type": "agent|tool|model|dataset|topic|device|node|service|observation|evidence|policy|job|workflow|capability|schema|ontology-term|trust-context|runtime-context",
  "href": "/registry/resources/<resource_id>",
  "links": [],
  "capabilities": [],
  "schemas": [],
  "topics": [],
  "owner": null,
  "tenant": null,
  "trust_level": "unknown|untrusted|attested|verified|privileged",
  "policy_tags": [],
  "evidence_refs": [],
  "created_at": null,
  "updated_at": null,
  "expires_at": null
}
```

## 4. Registry and discovery endpoints

Prophet services SHOULD expose a well-known metadata endpoint where practical:

```text
/.well-known/prophet
```

The minimum response SHOULD include registry, topic, policy, health, and evidence links:

```json
{
  "profile": "prophet-constrained-resource-pattern-v0.1",
  "resource_directory": "/registry/resources",
  "lookup": "/registry/lookup",
  "topics": "/registry/topics",
  "policy": "/policy",
  "evidence": "/evidence",
  "health": "/healthz",
  "schemas": "/schemas"
}
```

Core registry endpoints:

```text
POST /registry/resources
GET  /registry/resources/{resource_id}
GET  /registry/lookup?type=&capability=&topic=&tenant=&policy_tag=&trust_level=
POST /registry/replicate
GET  /registry/topics
GET  /registry/topics/{topic_path}
```

Registries MAY be replicated. Replication MUST be explicit about consistency class:

```json
{
  "consistency": "strong|bounded-stale|eventual",
  "source_registry": "prophet.registry.a",
  "target_registry": "prophet.registry.b",
  "watermark": "opaque-log-position",
  "evidence_ref": "prophet.evidence.<id>"
}
```

## 5. Compact identifiers

A Prophet compact identifier system SHOULD be introduced for high-volume resources, constrained edge runtimes, and semantic interoperability.

Identifier namespaces:

```text
prophet.sid.<integer-or-token>          schema item or ontology term
prophet.resource.<id>                  resource
prophet.topic.<path-id>                topic tree node
prophet.capability.<id>                agent/tool/model capability
prophet.device.<id>                    device identity
prophet.node.<id>                      SourceOS or runtime node
prophet.evidence.<content-address>     evidence artifact
prophet.policy.<id>                    policy rule or bundle
prophet.job.<id>                       async operation
```

Compact IDs MUST be resolvable to canonical schema metadata. They MUST NOT be treated as opaque authority without provenance.

Resolution endpoint:

```text
GET /registry/ids/{compact_id}
```

Response shape:

```json
{
  "compact_id": "prophet.sid.70001",
  "canonical_uri": "prophet://schema/comi-interop/interface",
  "schema_ref": "prophet.schema.interface.v1",
  "version": "1.0.0",
  "status": "experimental|reserved|active|deprecated|retired",
  "owner": "SocioProphet",
  "evidence_ref": "prophet.evidence.<id>"
}
```

## 6. Topic trees and conditional notification

Topic paths SHOULD be hierarchical and discoverable:

```text
/prophet/platform/events
/prophet/agentplane/agents/{agent_id}/events
/prophet/gaia/observations/{domain}/{region}
/prophet/sourceos/nodes/{node_id}/sync
/prophet/sherlock/evidence/{case_id}
/prophet/models/{model_id}/evals
```

Subscribers MAY attach conditional notification parameters.

Base parameters:

```json
{
  "pmin": "minimum notification interval",
  "pmax": "maximum notification interval",
  "lt": "less-than threshold",
  "gt": "greater-than threshold",
  "st": "step threshold",
  "band": "band-pass filter mode"
}
```

Prophet extensions:

```json
{
  "confidence_gte": 0.8,
  "policy_tags_any": ["regulated", "evidence"],
  "jurisdiction": "US|EU|global|local",
  "sensitivity_lte": "internal",
  "trust_level_gte": "attested",
  "evidence_class": "audit|forensic|operational|simulation",
  "tenant": "tenant-id",
  "schema": "prophet.schema.observation.v1"
}
```

## 7. Async pending/result monitor pattern

Long-running operations MUST return an explicit async status rather than hiding state in polling loops.

Creation response:

```http
202 Accepted
Location: /jobs/prophet.job.123
Retry-After: 30
```

Job monitor response:

```json
{
  "job_id": "prophet.job.123",
  "state": "accepted|pending|running|blocked|deferred|complete|failed|cancelled",
  "submitted_at": null,
  "updated_at": null,
  "not_before": null,
  "retry_after_seconds": 30,
  "result_location": null,
  "policy_verdict": "allow|deny|defer|manual_review|required_evidence_missing",
  "evidence_refs": [],
  "diagnostics": [],
  "non_claims": []
}
```

Use cases:

- agent task execution
- model evaluation
- GAIA data ingestion and fusion
- SourceOS node enrollment
- Sherlock evidence processing
- Holmes language jobs
- policy simulation
- registry replication
- forensic chain-of-custody packaging

## 8. Overload, backoff, and congestion discipline

All agent, sync, ingestion, model-routing, and observation loops MUST implement explicit retry discipline.

Required behavior:

- Retain backed-off retry state across related exchanges.
- Do not reset to an aggressive initial retry interval after a failed exchange.
- Restore normal cadence only after clean success without retransmission or overload response.
- Apply jitter to fan-out retries.
- Bound concurrency per actor, tenant, topic, and resource class.
- Emit observable overload events.

Canonical overload verdicts:

```json
{
  "verdict": "rate_limit|defer|shed|queue|brownout|circuit_open|manual_review",
  "retry_after_seconds": 60,
  "scope": "actor|tenant|topic|resource|service|node|global",
  "reason": "congestion|quota|policy|dependency|maintenance|safety",
  "evidence_ref": "prophet.evidence.<id>"
}
```

Implementation targets:

- AgentPlane dispatch loops
- Sociosphere topic fan-out
- sourceos-syncd repair/sync loops
- GAIA ingestion and tile generation
- Sherlock evidence indexing
- model-router fallback storms
- policy-fabric simulation queues
- MCP/A2A gateway retry logic

## 9. Security-context separation

Security context MUST be modeled independently from transport address.

Required concepts:

```json
{
  "group_id": "prophet.security_group.<id>",
  "epoch": "opaque-key-epoch",
  "common_context": {},
  "sender_context": {},
  "recipient_contexts": [],
  "group_manager": "prophet.resource.<id>",
  "capability_grants": [],
  "revocation_refs": [],
  "evidence_refs": []
}
```

Design rule: never conflate network group, application group, and security group.

Security groups SHOULD support:

- DID-bound membership
- scoped capabilities
- epoch rotation
- revocation
- recipient context derivation
- evidence signing
- policy-governed admission
- group manager audit trails

## 10. Interop and conformance harness

Every compatible protocol surface SHOULD ship an interop fixture and validator before production runtime expansion.

Harness capabilities:

- session orchestration
- fixture-driven clients and servers
- traffic capture where appropriate
- structured message traces
- schema validation
- policy validation
- replay
- verdict generation: PASS / FAIL / INCONCLUSIVE
- evidence receipts
- non-claim output

Minimum artifact bundle:

```text
interop/<surface>/fixtures/*.json
interop/<surface>/schemas/*.schema.json
interop/<surface>/traces/*.jsonl
interop/<surface>/evidence/*.json
tools/validate_<surface>_interop.py
```

Verdict shape:

```json
{
  "surface": "prophet-constrained-resource-pattern",
  "fixture": "interop/example.json",
  "passed": true,
  "verdict": "PASS|FAIL|INCONCLUSIVE",
  "problems": [],
  "evidence_refs": [],
  "non_claims": [
    "Validator checks fixtures only.",
    "Validator does not certify production interoperability.",
    "Validator does not execute external network workloads."
  ]
}
```

## 11. CoAP/CBOR compatibility profile

Future constrained-resource adapters MAY expose CoAP/CBOR bindings.

Adapter profile:

- CoAP methods map to resource operations.
- CBOR maps to canonical JSON schema shapes.
- compact IDs map through the Prophet identifier registry.
- OSCORE-style security maps to Prophet security contexts.
- CoRE Pub/Sub topic trees map to Sociosphere topics.
- CoMI/YANG-CBOR maps to device/node/resource management schemas.

Non-goal for v0.1: implementing CoAP transport directly in core Prophet Platform.

## 12. Repository placement

Initial landing repo:

- `SocioProphet/prophet-platform`: canonical architecture spec and validation fixture.

Follow-on implementation targets:

- `SocioProphet/agent-registry`: resource/capability registry fixture.
- `SocioProphet/agentplane`: async job, overload, retry, interop harness.
- `SocioProphet/sociosphere`: topic tree and conditional notification semantics.
- `SourceOS-Linux/sourceos-syncd`: constrained sync/repair resource profile.
- `SocioProphet/gaia-world-model`: observation topic tree and evidence-backed resource discovery.
- `SocioProphet/sherlock-search`: evidence resource and interop verdict profile.
- `SocioProphet/semantic-serdes`: compact identifier serialization profile.
- `SocioProphet/mcp-a2a-zero-trust`: security-context and A2A group profile.

## 13. Acceptance criteria for v0.2

- Add JSON schema for resource records.
- Add JSON schema for compact identifier records.
- Add JSON schema for async job monitor records.
- Add JSON schema for overload verdicts.
- Add fixture examples for registry, topic, job, overload, and security context.
- Add one validator that emits PASS / FAIL / INCONCLUSIVE.
- Add non-claim language to every validator.
- Add repo crosswalk issue list for downstream implementation.

## 14. Non-claims

- This pattern does not certify IETF compliance.
- This pattern does not replace CoAP, OSCORE, SenML, CoMI, LwM2M, DNS-SD, or YANG.
- This pattern does not assert that all Prophet surfaces are constrained-device safe.
- This pattern does not implement cryptographic transport security by itself.
- This pattern does not guarantee eventual consistency without an implementation and validator.
- This pattern is a planning contract until schemas, fixtures, validators, and runtime surfaces land.
