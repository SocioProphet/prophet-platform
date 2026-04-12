# WordOps Reference Architecture v0.2

## Purpose

WordOps is a sovereign operations and case-control fabric with chat as one control surface, not the durable authority, not the policy engine, and not the regulated system of record.

The architecture is designed to support:
- public and community Matrix ingress
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
- policy and trust plane
- systems-of-record plane

That separation prevents chat history, bot state, or ad hoc tool sessions from becoming shadow authorities.

## Matrix estates

### Public Matrix edge
Use the public estate for:
- community rooms
- intake rooms
- public support entry
- low-sensitivity office-hours or booking coordination
- public-facing bot entry points

Never use it as the regulated case record.

### Private Matrix core
Use the private estate for:
- private ops rooms
- incident rooms
- case rooms
- agent workspaces tied to real tasks
- regulated collaboration

Defaults:
- room version 12
- private visibility
- per-case or per-incident room factory
- no third-party identity server by default
- encrypted where appropriate
- non-federated where required by policy
- created by long-lived service account, not ad hoc by operators

## Agentic interoperability

### MCP
MCP is the agent-to-tool and agent-to-resource surface.
We use it for tools, prompts, resources, session-scoped access, and host wrappers such as ChatGPT apps.
MCP is not the durable workflow ledger.

### A2A
A2A is the agent-to-agent collaboration layer.
We use it for agent discovery, public Agent Cards, authenticated extended cards, delegated work, async tasking, and push notifications.
A2A is not the domain system of record.

## Ephemeral capability model

No principal gets standing meaningful privilege merely because it exists.
Every meaningful capability is:
- task-bound
- case-bound where relevant
- audience-bound
- time-bound
- policy-approved

Lease flow:
1. requester initiates action
2. policy evaluates actor, case/task context, environment, risk, and requested scope
3. broker mints a short-lived downscoped lease
4. target MCP server or A2A agent accepts only that lease
5. lease expires or is revoked
6. session is explicitly torn down where possible

## Canonical Task abstraction

A single internal Task model is required to map:
- workflow engine tasks/jobs
- A2A Tasks
- FHIR Tasks
- ops/support work items

Core fields:
- `task_id`
- `case_id`
- `intent`
- `status`
- `risk_class`
- `owner`
- `requester`
- `due_at`
- `approvals`
- `correlation_ids`
- `artifacts`
- `provenance`

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
- analytics -> observability plus notebooks and BI

The kernel orchestrates around them. It does not flatten them into one giant table.

## Non-negotiable rules

1. Public rooms are not regulated case records.
2. Sensitive work pivots into private rooms and private workflow state immediately.
3. Matrix membership and room power are not treated as authorization to mutate external systems.
4. MCP sessions are not authentication and do not replace leases.
5. A2A public Agent Cards expose discovery only; extended cards expose privileged capabilities only in authenticated sessions.
6. Durable workflow state stays outside Matrix and outside MCP.
