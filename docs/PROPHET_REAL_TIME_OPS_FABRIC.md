# Prophet Real-Time Ops Fabric v0.1

Prophet Real-Time Ops Fabric is the agent-native operations lane for Prophet Platform.

It aligns the useful parts of enterprise streaming, observability, AIOps, AI4IT, and resource optimization while avoiding closed-suite architecture. The fabric lets governed agents observe runtime state, reason over typed evidence, propose operational changes, pass policy gates, and hand approved work to execution surfaces with replayable receipts.

v0.1 is report-only. Autonomous mutation is out of scope.

## Capability lanes

1. Event spine: normalized operational facts from telemetry, CI/CD, runtime, cost, energy, policy, and security sources.
2. Observability graph: typed relationships among services, workloads, nodes, deployments, traces, metrics, costs, incidents, and security signals.
3. Resource governor: deterministic `ActionProposal` generation for right-sizing, autoscaling policy, SLO risk, cost risk, and security risk.
4. Policy gate: policy-fabric evaluation before any recommendation can become executable.
5. Agentplane bridge: approved proposals become action-lease candidates with evidence, rollback, and replay references.
6. Evidence memory: memory-mesh persistence for operational recommendations and incident/action history.
7. Search surface: lampstand indexing over services, incidents, proposals, receipts, and operational evidence.
8. DevSecOps intelligence: `global-devsecops-intelligence` supplies the AI4IT and ITOPS domain profile, taxonomy, mapping semantics, and operational graph projections.

## Repository ownership

`prophet-platform` owns runtime APIs, contracts, local and cluster services, deployment wiring, and product surface.

`global-devsecops-intelligence` owns the operations-domain intelligence plane: DevSecOps, AIOps, AI4IT taxonomy, IBM ITOPS seed mapping, entity extraction, story grouping, explainability, feedback loops, and operational graph projections.

`ontogenesis` owns broader canonical ontology and promotion gates.

`policy-fabric` owns action legality, blast-radius controls, autonomy tiers, and approval thresholds.

`agentplane` owns governed execution, leases, run artifacts, replay artifacts, receipts, and placement decisions.

`memory-mesh` owns evidence memory and recommendation history.

`lampstand` owns local and platform search/index surfaces.

## v0.1 contracts

Tranche 1 introduces:

- `EvidenceRef`
- `TelemetryEvent`
- `ActionProposal`
- `ActionLease`

These contracts are intentionally small. They establish evidence references, source classification, proposal scoring inputs, policy status, and the lease handoff seam.

## Agent-native flow

1. A collector receives or synthesizes operational facts.
2. Facts become typed platform events.
3. Events attach stable evidence references.
4. The observability graph links services, workloads, metrics, costs, security signals, and topology.
5. The resource governor emits an `ActionProposal`.
6. The proposal is policy checked.
7. Allowed proposals may become `ActionLease` candidates.
8. Evidence is written to memory surfaces.
9. Search/index surfaces expose the proposal, evidence, and receipt chain.
10. Execution remains manual or supervised in v0.1.

## Initial proposal types

- `RIGHTSIZE_WORKLOAD`
- `ADJUST_REPLICA_POLICY`
- `ADJUST_AUTOSCALER_TARGET`
- `ADD_BUDGET_GUARDRAIL`
- `FLAG_SLO_RISK`
- `FLAG_SECURITY_RISK`

## Policy status values

- `NOT_EVALUATED`
- `ALLOWED_REPORT_ONLY`
- `ALLOWED_WITH_APPROVAL`
- `DENIED`

## Acceptance criteria

- JSON schemas exist for core event, evidence, proposal, and lease contracts.
- Example payloads exist for the first right-sizing scenario.
- No autonomous mutation is introduced.
- Every proposal includes evidence references, impact estimates, blast radius, reversibility, autonomy tier, and policy status.
- The contracts are ready for the next read-only service slice: `services/ops-fabric-api/`.
