# Ops Fabric and Sherlock Search Alignment

Prophet Real-Time Ops Fabric must integrate with Sherlock Search as the discovery and chat-ops retrieval plane.

Ops Fabric produces operational events, evidence references, intelligence references, action proposals, and handoff candidates.

Sherlock Search provides the federated discovery layer that lets operators and agents retrieve those artifacts across Lampstand local search, platform workspace indexes, memory-mesh recall, and ontogenesis-backed semantic alignment.

## Required v0.1 seams

- Ops Fabric artifacts must be searchable as platform result records.
- Action proposals must preserve titles, summaries, target IDs, evidence references, policy status, and intelligence references for retrieval.
- Sherlock chat-ops flows must be able to ask: what changed, what is risky, what evidence supports this recommendation, what policy blocked it, and what handoff candidate exists.
- Search results must preserve permission boundaries and source metadata.
- Sherlock remains the discovery and chat-ops surface; Ops Fabric remains the operational control-plane producer.

## Runtime binding

The first binding is through the existing platform search runtime lane and the future `services/search-orchestrator/` provider seam.

Ops Fabric should emit searchable records with source `OPS_FABRIC`, entity types such as `TELEMETRY_EVENT`, `ACTION_PROPOSAL`, `HANDOFF_CANDIDATE`, and `OPS_EVIDENCE`, and stable IDs that Sherlock can rank and fuse with local, memory, and semantic sources.

This makes Sherlock Search the Watson Discovery plus chat-ops analogue for the open SocioProphet stack.
