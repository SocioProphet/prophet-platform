# ProCybernetica Cybernetic Governance Evidence Adapter

Status: v0.1 platform adapter specification  
Upstream issue: `SocioProphet/ProCybernetica#28`  
Platform issue: `SocioProphet/prophet-platform#473`  
Runtime claim: none

## Purpose

This document defines how Prophet Platform should consume ProCybernetica cybernetic-governance objects as runtime/eval-fabric evidence references without forking their constitutional semantics.

ProCybernetica owns the public constitutional schema and validator surface. Prophet Platform owns runtime/eval-fabric services, deployment records, readiness records, and platform evidence production.

## Upstream ProCybernetica anchors

- `SocioProphet/ProCybernetica#26` — Tier 1 `schemas/cybernetic-governance/*` schema bundle.
- `SocioProphet/ProCybernetica#27` — defensive fixtures, validator, tests, and Makefile lane.
- `SocioProphet/ProCybernetica#28` — integration-boundary record.

## Adapter rule

Platform records may reference ProCybernetica objects by schema ID, object ID, content digest, validation receipt, or public-safe fixture reference. Platform records must not silently redefine these objects.

Allowed:

- platform-side adapter metadata;
- links to ProCybernetica schema IDs;
- links to platform runtime/eval records;
- public-safe synthetic fixtures;
- bridge fields that preserve source schema names.

Disallowed:

- changing ProCybernetica object semantics in platform contracts;
- treating ProCybernetica schemas as platform runtime ownership;
- publishing private telemetry as public ProCybernetica evidence;
- collapsing safety-case records into production-readiness claims.

## Object mapping

| ProCybernetica object | Platform consumption |
| --- | --- |
| `evidence_receipt.v1.json` | Runtime/eval evidence reference or exported evidence receipt link. |
| `monitor_alert.v1.json` | Platform monitor event reference. |
| `meta_monitor_report.v1.json` | Monitor health, calibration, or drift reference. |
| `release_delta_report.v1.json` | Release/readiness delta evidence. |
| `cybernetic_safety_case.v1.json` | Platform readiness or assurance evidence package reference. |
| `authority_chain.v1.json` | Governed runtime action authority reference. |
| `tool_permission_scope.v1.json` | Runtime tool/capability permission boundary reference. |
| `agent_action_trace.v1.json` | Agentic action trace evidence reference. |
| `privacy_evidence_classification.v1.json` | Public/private evidence disclosure posture. |
| `incident_record.v1.json` | Platform incident/control-failure bridge reference. |

## Public-synthetic fixture

The initial fixture is:

```text
contracts/procybernetica/cybernetic-governance-evidence-adapter.synthetic.json
```

It demonstrates a platform readiness record that references ProCybernetica evidence receipt, monitor alert, release delta, safety case, authority chain, and tool permission objects without importing private telemetry or claiming production readiness.

## Validation boundary

The upstream validation lane remains in ProCybernetica:

```bash
make cybernetic-governance-fixtures
make cybernetic-governance-ci
```

Prophet Platform should later add platform-side adapter validation that checks:

- every referenced ProCybernetica object has a schema ID;
- every bridge field preserves source object type;
- runtime/eval records keep platform-specific fields outside ProCybernetica object bodies;
- public examples contain no secrets, private telemetry, or customer data.

## Non-claims

This document does not implement runtime evidence emission, deployment gating, production telemetry, safety-case adjudication, or policy enforcement. It defines the platform adapter boundary and the first public-synthetic fixture surface.
