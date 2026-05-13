# Semantic Projection Kernel v0.1

Status: working platform contract  
Owner: Prophet Platform  
Scope: user-relative knowledge projection over governed semantic hypergraph state

## Purpose

The Semantic Projection Kernel converts the Semantic Fibration thesis into an implementable platform contract.

The runtime contract is typed, auditable, policy-bound semantic projection:

```text
E   = governed semantic hypergraph
F_u = user/context/policy/provenance fiber
B_u = projected knowledge surface
p_u: E -> B_u
```

`E` is the total governed semantic state: entities, events, claims, relationships, source artifacts, policy records, model outputs, contradictions, temporal intervals, provenance, and action eligibility metadata.

`F_u` is the operational perspective bundle: identity, authorization, task, query intent, trust policy, redaction policy, memory scope, time horizon, contradiction policy, and action context.

`B_u` is the projected surface shown to a user or agent: visible claims, entities, relationships, evidence, contradictions, redactions, explanations, and permitted actions.

## Boundary of claims

The fibration language is an organizing analogy for the product narrative. The runtime contract is semantic projection.

Allowed implementation claims:

- user-relative projection from governed state;
- hypergraph-friendly claim and relation structure;
- provenance preservation;
- temporal coherence;
- contradiction retention;
- policy-bound visibility;
- action eligibility gates;
- replayable audit records.

Disallowed implementation claims:

- product narrative analogies as runtime dependencies;
- global organization knowledge without user-relative provenance;
- action from projected knowledge without explicit eligibility;
- silent contradiction removal.

## Contract artifacts

```text
contracts/semantic-projection/projection-request.v0.1.schema.json
contracts/semantic-projection/projection-result.v0.1.schema.json
contracts/semantic-projection/claim-record.v0.1.schema.json
contracts/semantic-projection/contradiction-record.v0.1.schema.json
contracts/semantic-projection/projection-audit-record.v0.1.schema.json
```

Valid examples live beside the schemas. Negative fixtures live under:

```text
contracts/semantic-projection/invalid/
```

Validate the lane with:

```bash
python3 tools/validate_semantic_projection.py
```

## Core invariants

### 1. No projection without policy

Projection requests and results must carry authorization, trust, and redaction policy references.

### 2. No promoted claim without provenance

A promoted claim must contain source artifact lineage and validator or review evidence.

### 3. Perspective non-collapse

The platform must not collapse all users into one universal knowledge surface. Groupoid views are aggregations of user-relative, provenance-bearing projections.

### 4. Time preservation

Projection must preserve `createdAt`, `observedAt`, `validFrom`, `validUntil`, and `asOf` boundaries when records are time-bound.

### 5. Contradiction retention

Known contradictions must be exposed, summarized, or policy-suppressed with disclosure. They must not disappear silently.

### 6. Action requires eligibility

Visible knowledge is not automatically actionable. Runtime action requires explicit action eligibility.

### 7. Replayability

Projection audit records must preserve policy bundle IDs, model versions, replay key, and input/output hashes.

## Product narrative mapping

| Narrative phrase | Runtime meaning |
| --- | --- |
| Semantic fibration | User-relative projection from governed semantic state |
| User fiber | Identity, context, policy, memory, provenance, and task bundle |
| Knowledge surface | Projected claims, relations, evidence, contradictions, and actions |
| Awareness with memory | Time-aware, provenance-preserving semantic state |
| Groupoid intelligence | Aggregation of user-relative projections under governance |
| Truth survives the loop | Claim promotion after source, contradiction, temporal, and policy gates |

## Architectural placement

`prophet-platform` owns this kernel as a runtime-facing contract. Upstream standards and governance remain in dedicated repositories, but this repo is where the contract becomes deployable platform discipline.

Expected downstream consumers:

- Prophet Platform services: query, reasoning, surface rendering, action gating;
- SocioSphere: groupoid-level aggregation and project-state presentation;
- AgentPlane: pre-action projection and post-action evidence binding;
- PolicyFabric: authorization, trust, redaction, and promotion policies;
- ProCybernetica: conformance and adversarial validation;
- Ontogenesis: vocabulary, ontology, and shape formalization.

## First implementation boundary

This tranche is contract-only. It adds schemas, fixtures, invalid fixtures, validator, Makefile hook, and CI. It does not add runtime service code.

The next tranche should bind the projection result to a minimal API or semantic-bridge surface and require action eligibility before any agent operation consumes projected knowledge.
