# DevSecOps Workroom Guardrail Action-Safety Scope v0.1

Status: Workstream 6 scope closure  
Plane: Prophet Platform Workroom consumption of Guardrail Fabric decisions  
Related: `docs/architecture/devsecops-intelligence-workroom-v0.1.md`

## Purpose

This note closes the v0.1 scope for Guardrail/action-safety integration in the DevSecOps Intelligence Workroom.

The v0.1 objective is to ensure that Workroom action grants and remediation candidates are checked against Guardrail Fabric posture before any action is treated as admissible.

## v0.1 included scope

The v0.1 integration covers:

- Guardrail Fabric adversarial AIOps fixture mirrors;
- poisoned evidence denial/escalation posture;
- unsafe mutation without ActionGrant denial posture;
- credential-sensitive action escalation posture;
- safe read-only probe allow posture;
- Workroom action-grant alignment checks;
- high-risk remediation candidate review posture;
- Guardrail decision-binding artifact for Workroom records.

Current Prophet artifacts:

```text
fixtures/external/guardrail-fabric/devsecops-workroom/*.json
tools/validate_workroom_guardrail_action_safety.py
contracts/workroom/devsecops-workroom-guardrail-decision-binding-v0.1.schema.json
tests/fixtures/workroom/devsecops-workroom.guardrail-decision-binding.valid.json
tools/validate_workroom_guardrail_decision_binding.py
```

## v0.1 excluded scope

The v0.1 integration does not cover:

- live Guardrail Fabric policy-engine invocation from Prophet Platform;
- live agent command interception;
- production credential access;
- production mutation;
- signed break-glass authority;
- autonomous remediation;
- runtime enforcement by AgentPlane.

These exclusions are intentional. Prophet Platform is the Workroom/product surface, not the execution authority or policy-enforcement runtime.

## Claim boundary

Allowed v0.1 claim:

```text
The Workroom validates action-grant and remediation posture against Guardrail Fabric fixture decisions.
```

Forbidden v0.1 claims:

```text
The Workroom executes Guardrail policy in production.
The Workroom authorizes remediation.
The Workroom grants credential access.
The Workroom executes mutation actions.
The Workroom replaces AgentPlane runtime enforcement.
The Workroom certifies Signadot-style feature parity.
```

## Required validation posture

A valid Workroom-to-Guardrail binding must preserve:

- read-only Workroom grants align with `safe_read_only_probe -> allow`;
- production-change grants remain `requires_human_approval`;
- high-risk remediation remains `candidate` and requires review;
- credential-sensitive actions must escalate rather than be allowed;
- poisoned evidence cannot become action authority;
- unsafe mutation without an ActionGrant is denied.

## Deferred tranche

A later tranche should bind Workroom reports to live or recorded Guardrail `PolicyDecision` artifacts emitted by Guardrail Fabric or AgentPlane.

That tranche must preserve execution authority outside Prophet Platform.

## Non-claims

This note does not execute infrastructure.

This note does not inspect production systems.

This note does not authorize remediation.

This note does not grant credential access.

This note does not certify Signadot feature parity.
