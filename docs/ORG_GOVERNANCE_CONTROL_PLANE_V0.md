# Organization Governance Control Plane v0

## Purpose

Organization Governance Control Plane v0 is the SocioProphet product tranche for governed human-agent institutional work.

The core competitive lesson is product compression: enterprises do not buy a pile of agents. They buy a control plane that can show what work exists, who or what is allowed to act, what happened, what evidence exists, what changed, what remains risky, and what improves next.

## Positioning

Wand manages agentic labor.

SocioProphet proves, governs, audits, composes, and improves cybernetic institutions.

## Canonical loop

```text
Objective → Workroom → Actor → Role → Policy → Asset → Action → Evidence → Review → Outcome → Score → Learning
```

This loop is the product body. Subsystems should attach to the loop rather than inventing separate local metaphors.

## Estate mapping

| Loop object | Canonical owner | Notes |
|---|---|---|
| Objective | `prophet-platform`, `delivery-excellence` | Platform contract plus KPI/OKR semantics. |
| Workroom | `prophet-workspace` | Buyer-visible control room and workspace context. |
| Actor | `agent-registry` | Humans, agents, services, sessions, grants, revocation. |
| Role | `agent-registry`, `ontogenesis` | Role vocabulary and workroom-bound authority. |
| Policy | `policy-fabric` | Role/action/asset decisions, replay, constraints, escalation. |
| Asset | `ontogenesis`, `prophet-platform`, `sourceos-syncd` | Repo, document, dataset, service, state, or external reference. |
| Action | `agentplane`, `prophet-platform` | Work-order execution envelope. |
| Evidence | `agentplane`, `model-governance-ledger`, `sourceos-syncd` | Receipts, replay, model/tool/data/state evidence. |
| Review | `prophet-workspace`, `delivery-excellence` | Human or policy review over evidence. |
| Outcome | `delivery-excellence`, `prophet-platform` | Accepted, rejected, blocked, superseded, remediated. |
| Score | `delivery-excellence` | Completeness, quality, policy coverage, cycle time, value. |
| Learning | `alexandrian-academy`, `model-governance-ledger`, `policy-fabric` | Policy, playbook, model, ontology, or agent improvement. |

## v0 executable slice

The first dogfood slice is:

```text
GitHub issue → work order → actor/role binding → policy gate → contract/action artifact → evidence reference → review → outcome → score
```

The initial fixture lives in:

```text
contracts/orggov/orggov-control-plane.v0.1.example.json
```

Validate it with:

```bash
python3 tools/validate_orggov_contracts.py
```

## Non-goals

- Do not clone closed agent-labor product language.
- Do not build a generic task manager.
- Do not make chat the product.
- Do not bypass policy or evidence for demo speed.
- Do not store secrets, credentials, or raw private prompts in evidence fixtures.

## Acceptance criteria for tranche closure

- Platform contract and fixture validate.
- Ontogenesis adds canonical terms and SHACL gates.
- Prophet Workspace renders the loop as a Professional Workroom control room.
- Agent Registry binds human and agent actors to roles, authority, grants, and revocation.
- Policy Fabric produces role/action/asset decisions and replay packs.
- AgentPlane carries work-order and policy references into run/replay evidence.
- Model Governance Ledger links model/tool/data/eval receipts to work outcomes.
- Sociosphere registers topology, ownership, and propagation rules.
- Delivery Excellence computes useful scorecards.
- Sherlock indexes evidence and supports control-graph search.
- SourceOS syncd links local-first state integrity events to governed work evidence.
