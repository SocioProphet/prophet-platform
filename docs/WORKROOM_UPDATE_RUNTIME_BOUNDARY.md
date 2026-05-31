# Workroom Update Runtime Boundary

Status: draft boundary design  
Authority repo: `SocioProphet/prophet-platform`  
Claim level: runtime architecture / pre-implementation boundary  
Scope: requirements before a no-runtime workroom update contract may become an executable platform service

## Purpose

This document defines the runtime boundary for future Professional Workroom update behavior in Prophet Platform.

The current workroom update lane is contract-only:

- `contracts/workspace/workroom-update-request.example.json`
- `contracts/workspace/workroom-update-response.accepted.example.json`
- `tools/validate_workroom_update_contract.py`

Those fixtures prove only shape, reference discipline, and no-runtime mutation boundaries. They do not implement an endpoint, message handler, database write, policy gate, workroom mutation, AgentPlane handoff, or receipt emission service.

This document states what must be true before that contract can become runtime behavior.

## Authority split

| Surface | Authority |
| --- | --- |
| Workroom product semantics and UX contracts | `SocioProphet/prophet-workspace` |
| Runtime service composition and deployment | `SocioProphet/prophet-platform` |
| Workspace topology and cross-repo governance graph | `SocioProphet/sociosphere` |
| Estate state and adoption/drift ledger | `SocioProphet/workspace-inventory` |
| Privacy and memory semantics | `SocioProphet/ontogenesis` |
| Topic-pack membrane semantics | `SocioProphet/slash-topics` |
| Audio-first review semantics | `SocioProphet/speechlab` |
| Agent execution/evidence/replay | `SocioProphet/agentplane` |
| Agent identity and capability authority | `SocioProphet/agent-registry` |
| Policy and guardrail decisions | `policy-fabric` / `guardrail-fabric` |
| Model/memory/learning receipts | `SocioProphet/model-governance-ledger` |
| Institutional learning receipts | `SocioProphet/systems-learning-loops` |

Prophet Platform may host the service that applies a workroom update. It must not become the semantic owner of all referenced authorities.

## Runtime promotion rule

A workroom update may become runtime behavior only when the request can pass these gates:

1. **Contract shape gate** — request and response conform to platform-side workroom update contract expectations.
2. **Workspace product gate** — target workroom and fields remain compatible with `prophet-workspace` Professional Workroom schema.
3. **Identity gate** — actor or agent identity is registered and authorized.
4. **Policy gate** — policy and guardrail decisions admit the proposed operation.
5. **Privacy gate** — DoNotLearn / DoNotLink decisions admit any learning or linking effect.
6. **Topic membrane gate** — topic-pack refs, if present, admit the source/operator/display scope.
7. **Audio review gate** — audio/transcript refs, if present, preserve transcript provenance and correction state.
8. **Persistence gate** — target store and mutation semantics are explicit.
9. **Receipt gate** — successful, rejected, or no-op outcomes emit receipts.
10. **Replay gate** — update can be audited or replayed from request, decisions, and receipts.

Failure at any gate must produce a rejected or require-review response rather than partial mutation.

## Candidate endpoint / message family

No endpoint is defined yet.

A future implementation may choose one of these forms:

```text
POST /workrooms/{workroomId}/updates
```

or a typed message family:

```text
workspace.workroom.update.request
workspace.workroom.update.accepted
workspace.workroom.update.rejected
workspace.workroom.update.applied
workspace.workroom.update.noop
```

or a TriTRPC / control-plane envelope after the TriTRPC vNext control-plane substrate becomes normative enough for use.

Until a protocol choice is made, the JSON examples remain contract fixtures only.

## Request lifecycle

```text
Receive -> Parse -> Contract Validate -> Resolve Workroom -> Resolve Authority Refs -> Policy Check -> Privacy Check -> Plan Mutation -> Persist or Reject -> Emit Receipt -> Emit Adoption/Telemetry Event
```

### Receive

The platform receives a request through a future endpoint, message bus, or internal invocation path.

### Parse

The platform parses the request into a typed internal object.

### Contract Validate

The request must conform to the platform-side workroom update contract and reference a compatible Professional Workroom contract surface.

### Resolve Workroom

The platform resolves the target workroom id and current state.

### Resolve Authority Refs

The platform resolves or records refs for policy decisions, privacy decisions, topic packs, memory scopes, audio reviews, learning receipts, semantic receipts, evidence, and adoption events.

### Policy Check

The platform asks policy/guardrail authorities whether the proposed update is admitted, denied, or requires review.

### Privacy Check

The platform evaluates whether the request has any learning or linking effect. If it does, DoNotLearn / DoNotLink decisions are required.

### Plan Mutation

The platform creates a mutation plan without applying it.

### Persist or Reject

Only after gates pass may the platform persist the update. Rejections must be explicit and receipted.

### Emit Receipt

The platform emits a runtime receipt for accepted, rejected, applied, no-op, or require-review outcomes.

### Emit Adoption / Telemetry Event

Where applicable, the platform emits adoption telemetry without implying human acceptance unless the human-review event exists.

## Required runtime objects

Before implementation, define these objects or equivalent contract surfaces:

### WorkroomUpdateRequest

Executable form of the current request fixture.

### WorkroomUpdatePlan

Non-mutating plan produced after contract, policy, privacy, and authority-ref resolution.

### WorkroomUpdateDecision

Policy/privacy/governance decision bundle for the proposed mutation.

### WorkroomUpdateReceipt

Receipt recording request, plan, decision, mutation/no-op/rejection, hashes, timestamps, actor, and evidence refs.

### WorkroomUpdateAuditRecord

Replayable audit record linking request, previous state selector, new state selector or no-op reason, and receipts.

## Persistence boundary

No persistence model is selected in this document.

A future implementation must specify:

- target store;
- state versioning model;
- optimistic concurrency or lock behavior;
- idempotency key;
- mutation atomicity;
- rollback or compensating event behavior;
- retention policy;
- audit-log sink;
- receipt storage and lookup semantics.

Absent those elements, the platform must not perform live workroom mutation.

## Policy and privacy requirements

A runtime update must not rely on refs existing in the request as proof of authorization.

The platform must verify or record:

- actor authorization;
- policy decision status;
- privacy decision status;
- whether the update has learning effect;
- whether the update has linking effect;
- whether topic-pack membrane constraints apply;
- whether audio/transcript refs include correction/provenance state;
- whether agent output requires review before adoption.

## Response classes

A future runtime service should distinguish:

- `accepted_for_review` — request shape accepted, no mutation yet;
- `rejected` — request cannot be admitted;
- `requires_policy_review` — blocked pending policy review;
- `requires_privacy_review` — blocked pending learning/linking decision;
- `planned` — mutation plan produced but not applied;
- `applied` — mutation committed and receipted;
- `noop` — no state change needed, receipt emitted;
- `failed` — internal failure before valid outcome.

Only `applied` may indicate runtime mutation.

## Receipt requirements

Every non-trivial runtime result must emit or reference a receipt.

Minimum receipt fields:

- receipt id;
- request id;
- workroom id;
- actor ref;
- operation;
- policy decision refs;
- privacy decision refs;
- prior state selector or hash;
- planned state selector or hash;
- applied state selector or hash, if any;
- status;
- timestamp;
- evidence refs;
- error or review reason where applicable.

## Failure modes to prevent

- Treating `accepted_for_review` as mutation.
- Mutating workroom state without policy decision refs.
- Mutating memory or linking refs without privacy decision refs.
- Using topic-pack refs as implicit memory permission.
- Using transcript/audio refs as durable memory permission.
- Writing agent output into accepted workroom state before human or policy review.
- Emitting adoption telemetry before an adoption event exists.
- Making Prophet Platform the semantic owner of product, policy, memory, topic, or audio authorities.

## Implementation readiness checklist

Do not implement a live service until all are true:

1. Request/response schemas exist, not only examples.
2. Validator covers positive and negative fixtures.
3. Policy decision verification path exists.
4. Privacy decision verification path exists.
5. Workroom state store is selected.
6. Idempotency and concurrency semantics are defined.
7. Receipt schema and sink are defined.
8. Rejection and require-review responses are modeled.
9. AgentPlane handoff is modeled if agents can request updates.
10. Prophet Workspace confirms product contract compatibility.
11. Sociosphere and workspace-inventory can record adoption/drift state.

## Non-goals

This document does not implement the workroom update service, define a production endpoint, choose storage, define a broker topic, add persistence, mutate workrooms, or grant agents authority to update workrooms.

It also does not make TriTRPC mandatory for this surface. TriTRPC remains a candidate future control-plane substrate until promoted by its own authority process.

## Claim boundary

This is a runtime-boundary design document. It upgrades the no-runtime contract lane with implementation prerequisites but does not claim runtime readiness.
