# Ops Fabric and Global DevSecOps Intelligence Alignment

Prophet Real-Time Ops Fabric must integrate with `SocioProphet/global-devsecops-intelligence` as the upstream operations-domain intelligence plane.

`prophet-platform` owns runtime APIs, event and evidence contracts, deployment wiring, and the operational proposal surface.

`global-devsecops-intelligence` owns the DevSecOps, AIOps, and AI4IT domain specialization: operations taxonomy, topic ladder, entity extraction schemas, mapping DSL, story grouping, explainability, feedback loops, measurement profile, IBM ITOPS seed alignment, and operational graph projections.

Ops Fabric must consume this intelligence rather than recreate it locally.

## Required v0.1 seams

- `ActionProposal` should support `intelligence_refs` for DevSecOps and AI4IT evidence.
- `TelemetryEvent` should support an operations profile reference when events are classified by the AI4IT profile.
- Security and operational-exhaust signals from `global-devsecops-intelligence` should influence proposal scoring before any execution lease is emitted.
- Future `ops-fabric-api` routes should preserve intelligence references in proposal, policy-check, and lease-candidate responses.

## Dependency direction

`platform standards -> knowledge / ontology standards -> global-devsecops-intelligence -> prophet-platform runtime implementations`

This keeps `prophet-platform` as the runtime implementation layer and keeps domain intelligence in the repository that already owns AI4IT and ITOPS semantics.
