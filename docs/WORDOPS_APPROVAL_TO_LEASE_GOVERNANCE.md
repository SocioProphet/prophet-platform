# Approval-to-Lease Governance v0.1

## Purpose

This document defines how high-risk actions move from request -> approval -> lease issuance.

## Core rule

Approval is not the same thing as capability.
Approval authorizes the broker to mint a bounded lease for one action shape.
The lease is still short-lived, audience-bound, and scope-bound.

## Autonomy classes

### A0 Observe only
Examples:
- logs query
- metrics query
- list rooms
- list tickets
Approval: none
Step-up: none

### A1 Draft only
Examples:
- create room
- draft case
- define case templates
- define issue templates
Approval: only for specific cases
Step-up: none

### A2 Low-risk execute
Examples:
- create incident
- invoke basic MCP APIs
Approval: non-specific
Step-up: required

### A3 High-risk execute with approval
Examples:
- issue privileged tools
- modify platform-wide controls
Approval: only for specific cases
Step-up: required

### A4 Emergency constrained action
Examples:
- case de-escalation
- power on critical service
Approval: emergency
Step-up: none