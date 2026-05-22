# Workspace Context Runtime Binding

Status: v0.1 platform binding note
Runtime claim: none

## Purpose

This document records how Prophet Platform should consume the Workspace Context Fabric contracts introduced in `SocioProphet/prophet-workspace`.

The workspace repository owns product and domain semantics. Prophet Platform owns runtime services, platform contracts, storage, transport, evidence, and deployment.

## Platform binding rule

Every material workspace-context action should map to existing platform evidence primitives:

| Workspace action | Platform primitive |
| --- | --- |
| Context graph recorded | `EventEnvelope` plus `EvidenceReceipt` |
| Provider capture recorded | `CarrierIngested` plus `EvidenceReceipt` |
| Provider projection evaluated | `MembraneDecision` |
| Provider projection allowed | `ExportApproved` plus `EvidenceReceipt` |
| Provider projection denied | `ExportDenied` plus `EvidenceReceipt` |
| Share grant created | `EventEnvelope` plus `EvidenceReceipt` |
| Share grant revoked | `EventEnvelope` plus `EvidenceReceipt` |
| Recall candidate created | `EventEnvelope` plus `EvidenceReceipt` |
| External continuation recorded | `EventEnvelope` plus `EvidenceReceipt` |

## Boundary posture

Prophet Platform must not redefine workspace-domain objects. Platform contracts should reference the workspace objects by stable refs and preserve the existing platform evidence family.

## First implementation target

The first platform implementation should be contract-only:

- add small event contracts under `contracts/workspace-context/`;
- add a synthetic example fixture;
- add validation that checks schema/example parseability and required refs;
- avoid runtime service claims until the contract surface is merged and reviewed.

## Follow-up service targets

Later service work can add:

- a workspace-context API surface;
- a projection compiler service;
- a policy/membrane evaluation route;
- event and receipt emission into the platform evidence store;
- local and cluster deployment wiring.
