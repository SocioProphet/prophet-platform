# WordOps Surface Adapter Model v0.3

## Decision

WordOps and AgentTerm are peer surface adapters over the same platform control fabric. Neither supersedes the other.

## Distinct design goals

### WordOps

WordOps is the Matrix-native, GUI/network-native, client-facing ChatOps self-service agent surface.

Its primary users are:
- clients
- customers
- support requesters
- community members
- non-operator internal users
- first-line triage participants

Its job is to provide the first line of defense for support, case intake, guided troubleshooting, scheduling, feedback capture, and controlled escalation.

WordOps should optimize for:
- Matrix rooms and spaces
- guided self-service flows
- support/case triage
- public-to-private case pivot
- calendar/office-hours flows
- survey/NPS feedback capture
- safe client-facing automation
- escalation into operator and case workflows

### AgentTerm

AgentTerm is the terminal-native operator console for users who want to coordinate agents from a terminal.

Its primary users are:
- operators
- engineers
- incident commanders
- platform maintainers
- power users
- agent wranglers

Its job is to provide a local/terminal-first ChatOps console over the same underlying agents, rooms, workrooms, search packets, policy decisions, and execution evidence.

AgentTerm should optimize for:
- terminal-native command flow
- local operator event log
- slash-command ergonomics
- process-backed participants
- engineering workflows
- evidence/event tailing
- workroom and agent coordination

## Shared substrate

Both surfaces consume the same substrate:
- Prophet Platform runtime and deployment topology
- Matrix as canonical network ChatOps substrate
- Agent Registry identity and session authority
- Policy Fabric decision and evidence authority
- AgentPlane execution, run, replay, and evidence authority
- Sherlock Search search-packet and retrieval evidence authority
- Sociosphere workspace materialization and topology authority
- MCP tool/resource contracts
- A2A agent discovery and task contracts
- capability leases
- canonical task/case/event correlation
- audit and provenance spine

## Authority split

| Concern | Authority |
| --- | --- |
| Client-facing self-service ChatOps | WordOps |
| Terminal-native operator console | AgentTerm |
| Search packets and retrieval evidence | Sherlock Search |
| Non-human identity, sessions, grants, revocation | Agent Registry |
| Policy decision and side-effect admission | Policy Fabric |
| Agent execution, placement, replay, evidence | AgentPlane |
| Workspace materialization and repo/workspace state | Sociosphere |
| Runtime/deployment hub and platform contracts | Prophet Platform |

## Matrix-native WordOps role

WordOps owns the Matrix-native client interaction model:
- public intake rooms
- support self-service rooms
- guided troubleshooting flows
- public-to-private escalation rooms
- case handoff surfaces
- client-facing agent replies
- scheduling and office-hours coordination
- feedback, poll, and survey handoff
- safe outbound communication requests

WordOps does not own durable case authority, non-human identity authority, or policy authority.

## Terminal-native AgentTerm role

AgentTerm owns the terminal operator interaction model:
- operator shell
- terminal command loop
- local event log
- operator-visible room/channel/thread view
- CLI-driven adapter dispatch
- terminal-first agent coordination

AgentTerm does not own client-facing self-service UX or the Matrix-native support triage surface.

## Design invariant

A capability that exists in WordOps must be representable as a governed connector/capability in the shared substrate.
A capability that exists in AgentTerm must be representable the same way.

Surface-specific UX is allowed. Surface-specific authority is not.
