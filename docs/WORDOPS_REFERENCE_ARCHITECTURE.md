# WordOps Reference Architecture v0.2

## Purpose

WordOps is a sovereign operations and case-control fabric with chat as one control surface, not the durable authority, not the policy engine, and not the regulated system of record.

The architecture is designed to support:
- public/community Matrix ingress
- private operator and case collaboration
- agentic execution with ephemeral capabilities
- support and scheduling flows
- DevOps and platform control
- analytics and Python-based investigation
- regulated case orchestration via domain packs

## Core principle

We keep five planes separate:
- collaboration plane
- capability plane
- workflow plane
- policy/trust plane
- systems-of-record plane

That separation prevents chat history, bot state, or ad hoc tool sessions from becoming shadow authorities.

## Topology

```text
Public Matrix Edge
  -> public/community intake only
  -> no regulated authority

Private Matrix Core
  -> operator rooms
  -> incident rooms
  -> case rooms
  -> regulated collaboration

Capability Broker
  -> Keycloak token exchange
  -> OPA policy decisions
  -> SPIFFE/SPIRE workload identity
  -> short-lived capability leases

Agent Plane
  -> MCP servers
  -> A2A agents
  -> public cards
  -> authenticated extended cards

Workflow / Case Plane
  -> canonical Task service
  -> Flowable CMMN/BPMN/DMN orchestration
  -> durable case and process state

Systems of Record
  -> OpenProject / Zammad / domain adapters / analytics stores
```

## Matrix split

### Public Matrix edge
Use the public estate for:
- community rooms
- intake rooms
- public support entry
- low-sensitivity rendezvous only

Never use it as the regulated case record.

### Private Matrix core
Use the private estate for:
- case rooms
- support escalation rooms
- incident rooms
- internal ops rooms
- agent workspaces tied to real tasks and leases

Defaults:
- private visibility
- room version 12
- room creation through a dedicated service account
- federation disabled for sensitive rooms unless explicitly justified

## Agentic alignment

### MCP role
MCP is the agent-to-tool and agent-to-resource interface.
We use it for:
- tools
- prompts
- resources
- session-scoped access
- host compatibility such as ChatGPT apps

MCP is not the durable workflow ledger.

### A2A role
A2A is the agent-to-agent collaboration layer.
We use it for:
- agent discovery
- public Agent Cards
- authenticated extended cards
- delegated work
- long-running tasks
- async completion and push

A2A is not the systems-of-record layer.

## Ephemeral capability model

No principal gets standing meaningful privilege merely because it exists.
Every meaningful capability must be:
- task-bound
- case-bound where relevant
- audience-bound
- time-bound
- policy-approved

Lease flow:
1. requester initiates action
2. policy evaluates identity, task, case, risk, and requested scope
3. broker issues a short-lived lease
4. MCP server or A2A agent accepts only that lease
5. session ends or token expires
6. privilege disappears

## Canonical lease fields

Minimum lease fields:
- sub
- act
- aud
- scope
- case_id
- task_id
- risk
- approval_id
- iat / nbf / exp
- jti
- sender-constraining material where supported

## Canonical Task abstraction

We unify work across protocols with one internal Task model that maps to:
- A2A Task
- FHIR Task
- Flowable task/job
- OpenProject work item
- support/ops task records

Canonical fields:
- task id
- case id
- kind
- intent
- owner
- requester
- status
- priority
- risk class
- due window
- related artifacts
- approval state
- originating protocol
- correlation ids
- provenance

## Workflow and case kernel

Durable orchestration lives outside chat and outside MCP.

Use:
- CMMN for evolving case work
- BPMN for repeatable subprocesses
- DMN for transparent routing and decision logic

The current practical target is Flowable.

## Systems of record

Authoritative systems remain authoritative:
- commercial support -> Zammad
- internal ops/project work -> OpenProject
- healthcare -> FHIR-facing domain adapter / clinical system
- justice/public safety -> authoritative domain adapter
- analytics -> observability + notebooks + BI

The kernel orchestrates around them. It does not flatten them into one giant table.

## Connector bundle rule

Every connector should implement the same bundle shape:
- service face
- event face
- MCP face
- optional A2A face
- governance face

That is how we normalize the connector estate across bots, agents, BlueEdge, host apps, and runtime services.

## Identity and trust

### Human identity
- OIDC subject
- SCIM-managed lifecycle
- step-up auth for high-risk actions

### Workload identity
- SPIFFE/SPIRE
- short-lived workload credentials

### Agent identity
- registered principal
- public card
- authenticated extended card
- delegated lease for action

### Policy enforcement
OPA decides:
- whether a lease may be issued
- what scopes are allowed
- whether approval is required
- what environments are reachable
- whether the action is dry-run only

## Room taxonomy

- public intake room
- community room
- support escalation room
- case room
- incident room
- agent workspace room
- ops room
- moderation room

## Public-to-private case pivot

1. intake arrives through Matrix, web, email, voice, or another ingress
2. intake is classified
3. low-risk generic conversation may remain on the public edge briefly
4. sensitive or regulated work creates a private case room and private case record
5. public thread keeps only sanitized status, if any
6. real work proceeds only in the private estate and case kernel

## Analytics and scripting plane

Python analytics, charting, and investigation are first-class, but analytics jobs must also use bounded leases when they touch sensitive data.
No notebook runner receives standing unrestricted access merely because it is internal.

## Communication plane

Email, SMS, phone, and other outbound communications are transport-neutral tasks.
Channels are adapters.
Policy and approval decide what may be sent and by whom.
Outcomes write back into the case/task timeline.

## Survey and poll plane

Separate:
- lightweight in-room polls
- structured surveys and quality metrics

Structured feedback belongs in analytical and quality layers, not just chat history.

## Domain packs

Initial packs:
- commercial support
- platform ops / DevOps
- healthcare triage
- justice / public safety
- human-services referral
- marketing / campaign automation

Each pack declares:
- canonical entities
- authoritative records
- exchange standards
- confidentiality class
- audit requirements
- retention rules
- approval gates
- allowed autonomy class

## Autonomy classes

- A0 Observe only
- A1 Draft only
- A2 Low-risk execute
- A3 High-risk execute with approval
- A4 Emergency constrained action

Every connector and capability should be tagged accordingly.

## Implementation slices

### Slice 1
Private support and scheduling

### Slice 2
Ops / incident control

### Slice 3
Agent lease path

### Slice 4
Regulated case pilot

## Placement

Primary upstream home: `SocioProphet/prophet-platform`
Cross-reference consumers: standards repos, agentplane, policy-fabric, mcp-a2a-zero-trust, TriTRPC, sociosphere

## Decision

WordOps is now defined as:
- Matrix as collaboration/control surface
- ephemeral lease-based capability fabric
- MCP for tool/resource access
- A2A for agent collaboration
- Flowable-backed workflow/case kernel
- policy/trust plane separate from chat and separate from tools
