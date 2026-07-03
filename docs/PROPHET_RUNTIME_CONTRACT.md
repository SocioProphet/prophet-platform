# Prophet Runtime Contract v0

## Purpose

This contract makes Prophet the canonical SocioProphet agentic control plane at the runtime boundary. It is intentionally narrower than the whole platform thesis: it defines the request, response, decision trace, and audit-header envelope that downstream systems can validate before they rely on any Prophet decision.

## Canonical agent identity

The only live agent string is:

```text
Prophet
```

Legacy `EBA` tokens are allowed only in explicit deprecation or redirect fixtures. Runtime traces, responses, audit headers, and SourceOS run-capsule bindings must use `Prophet`.

## Namespaces

```text
prp=https://id.socioprophet.org/prophet#
sp=https://id.socioprophet.org/ns#
```

## Required runtime artifacts

- `schemas/prophet/prophet-run-request.schema.json`
- `schemas/prophet/prophet-run-response.schema.json`
- `schemas/prophet/prophet-decision-trace.schema.json`
- `schemas/prophet/prophet-audit-headers.schema.json`

## Required decision-trace fields

Every Prophet decision trace must include:

- `agent_id: "Prophet"`
- `agent_version`
- `agent_mc`
- `critic_features_hash`
- `dtr`
- `ho`
- `policies`
- `tokens`
- `workloads`
- `inputs_hash`
- `outputs_hash`
- `policy_decision_refs`
- `source_receipt_refs`

## HTTP surface

Authoritative routes:

```text
POST /prophet/run
GET  /prophet/explain
POST /prophet/critique
POST /prophet/simulate
POST /prophet/recommend
```

Compatibility routes:

```text
/eba/*
```

Compatibility routes must return HTTP `308 Permanent Redirect` to `/prophet/*` and include:

```text
X-API-Deprecated: EBA
```

## Audit headers

Every Prophet runtime response and artifact export should stamp:

```text
X-SocioProphet-Agent: Prophet
X-SocioProphet-Agent-Version: <semver+gitsha>
X-SocioProphet-Decision-Trace: dtr:sha256:<digest>
X-SocioProphet-Policy-Hash: pol:sha256:<digest>
X-SocioProphet-Namespaces: prp=https://id.socioprophet.org/prophet#, sp=https://id.socioprophet.org/ns#
```

## Cross-estate bindings

- Policy Fabric validates canonical agent identity, policy binding, and audit-header presence.
- AgentPlane maps Prophet run capsules to placement, execution, replay, and evidence artifacts.
- SourceOS records machine-level run receipts that refer back to Prophet decision traces.
- Prophet Workspace renders decision trace, policy state, provenance, and redacted artifact metadata.
- Delivery Excellence scores runtime contract adoption and drift.

## Non-goals for v0

- This contract does not implement model routing.
- This contract does not grant mutation authority.
- This contract does not replace Policy Fabric, AgentPlane, Prophet Understand, or SourceOS receipts.
- This contract does not allow inferred graph facts to become execution authority.
