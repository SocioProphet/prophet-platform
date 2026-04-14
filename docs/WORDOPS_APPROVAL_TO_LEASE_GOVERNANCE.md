# WordOps Approval-to-Lease Governance v0.1

## Purpose

This document defines how actions move from request -> policy evaluation -> approval -> lease issuance.

Approval is not the same thing as capability.
Approval only authorizes the broker to mint a bounded lease for a specific action shape.
The lease remains short-lived, audience-bound, and scope-bound.

## Autonomy classes

### A0 — Observe only
Examples:
- read logs
- read metrics
- list rooms
- list tickets
Approval: none
Step-up: none
Lease TTL: short, read-only

### A1 — Draft only
Examples:
- draft message
- draft case update
- create proposed room plan
Approval: normally none
Step-up: none
Lease TTL: short, non-sending / non-mutating

### A2 — Low-risk execute
Examples:
- create low-risk ticket
- create incident scaffold
- create private room through factory
Approval: usually policy-only
Step-up: recommended
Lease TTL: very short

### A3 — High-risk execute with approval
Examples:
- production platform mutation
- privileged outbound communications
- privileged domain adapter mutation
Approval: explicit human approval required
Step-up: required
Lease TTL: extremely short and action-bound

### A4 — Emergency constrained action
Examples:
- emergency break-glass access
- urgent containment action
- emergency communications under incident policy
Approval: emergency policy path with heavy audit
Step-up: required where feasible, waived only under documented break-glass policy
Lease TTL: shortest possible

## Approval envelope

Each approval should bind:
- actor
- acting-on-behalf-of principal if any
- requested action
- target audience/system
- case id
- task id
- risk class
- environment
- allowed scope set
- approval id
- approval timestamp
- expiry window
- digest of the requested action payload

## Lease minting rules

1. No lease without policy evaluation.
2. No A3/A4 lease without explicit approval record.
3. Lease must be narrower than or equal to the approved scope.
4. Lease must be audience-bound.
5. Lease must be case/task-bound when the action is case-related.
6. Lease expiry must be short enough that replay has low value.
7. Long-running work requires renewal or explicit continuation policy.

## Audit requirements

Every approval and lease issuance must record:
- request digest
- policy decision id
- approver or emergency policy path
- lease id / jti
- case/task correlation ids
- target audience
- expiry
- outcome
