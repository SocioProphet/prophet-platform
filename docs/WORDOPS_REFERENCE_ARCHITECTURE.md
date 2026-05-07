# WordOps Reference Architecture v0.3

## Purpose

WordOps is the Matrix-native, client-facing ChatOps self-service agent for SocioProphet support, case intake, and first-line defense.

It is designed for people who enter through chat, public rooms, support rooms, office-hours flows, booking links, guided troubleshooting, and escalation paths. It is not the same surface as AgentTerm, which is the terminal-native operator console for engineers and platform operators.

## Architecture principle

WordOps is a surface over the shared platform control fabric. It must not become the durable case authority, the policy authority, or the agent identity authority.

The shared fabric remains:
- Prophet Platform runtime/deployment topology
- Matrix as canonical network ChatOps substrate
- Agent Registry for non-human identity, sessions, grants, and revocation
- Policy Fabric for side-effect admission and policy evidence
- AgentPlane for execution, placement, replay, and evidence
- Sherlock Search for search packets and retrieval evidence
- Sociosphere for workspace materialization and topology
- MCP for tool/resource access
- A2A for agent collaboration and tasking

## Planes

WordOps keeps these planes separate:
- collaboration plane
- capability plane
- workflow/case plane
- policy/trust plane
- systems-of-record plane
- analytics/search plane

Chat is not the database. Matrix room power is not authorization. MCP session state is not authority. Agent presence is not permission.

## Primary users

WordOps serves:
- clients
- customers
- support requesters
- non-operator internal users
- community members
- first-line triage participants

AgentTerm serves:
- operators
- engineers
- incident commanders
- platform maintainers
- agent wranglers

## Matrix estates

### Public Matrix edge
The public estate handles:
- public support intake
- community rooms
- public help flows
- low-sensitivity self-service
- public-facing agent rendezvous only when intentionally exposed

Public rooms must never hold regulated case authority or sensitive case content.

### Private Matrix core
The private estate handles:
- private support escalation rooms
- per-case rooms
- incident rooms
- internal ops rooms
- regulated collaboration rooms
- agent workspaces tied to real tasks and leases

Sensitive work pivots from the public edge to the private core.

## WordOps first-line defense flow

1. User enters through Matrix, web, email, voice, or another supported ingress.
2. WordOps performs guided intake and self-service triage.
3. Low-risk issues may be resolved by self-service guidance.
4. If the issue needs human or regulated handling, WordOps creates or updates a case/task and pivots into a private room.
5. Policy Fabric decides which side effects are allowed.
6. Agent Registry, AgentPlane, Sherlock Search, and Sociosphere provide governed capabilities through leases.
7. Outcomes are recorded into the appropriate system of record and evidence spine.

## Ephemeral capabilities

No agent, bot, or adapter receives standing meaningful authority. Capabilities are:
- task-bound
- case-bound where relevant
- audience-bound
- time-bound
- policy-approved

The broker issues short-lived capability leases after policy evaluation and, when required, human approval.

## Canonical Task model

WordOps actions must correlate to a shared Task abstraction that can map to:
- A2A Task
- Flowable task/job
- FHIR Task where applicable
- OpenProject work item
- support/case task record

Core fields:
- task id
- case id
- intent
- status
- risk class
- requester
- owner
- correlation ids
- related artifacts
- provenance

## Search and evidence

Sherlock Search owns search-packet and retrieval evidence behavior. WordOps consumes Sherlock packets for guided support, client-facing search assistance, case context hydration, and escalation evidence.

WordOps should not invent a parallel search-packet format.

## Analytics and investigation

WordOps may request analytics and charting over logs/metrics, but sensitive access must use capability leases. Python/notebook/job runners do not get standing access merely because they are internal.

## Surface adapter invariant

WordOps and AgentTerm may offer different UX and command ergonomics. They must converge on the same underlying contracts for identity, policy, leases, tasks, search packets, events, and evidence.
