# Channel-governed runtime gates v0.1

## Status

Contract-only runtime binding for Reciprocal Channel Governance.

This document consumes ProCybernetica doctrine, Ontogenesis `rcg:` vocabulary, Memory Mesh channel-provenance write gates, Regis epistemic edge records, and HolographMe projection-loss profiles. It does not implement production ingestion, memory writes, graph writes, publication, or external actions.

## Purpose

Prophet Platform is the runtime/API surface where channel-conditioned observations become requests, proposals, receipts, projections, memory candidates, graph candidates, and operational decisions. Without a runtime gate, downstream systems may accidentally treat transcripts, summaries, dashboards, graph slices, telemetry, or agent reports as facts.

The channel-governed runtime gate records the minimum evidence required before a platform operation may route a channel-conditioned percept to a consequential sink.

## Core rule

A platform operation must not route a channel-conditioned percept into durable memory, graph truth, claim promotion, policy binding, publication, export, or high-consequence execution unless the operation has:

1. source channel lineage;
2. percept and interpretant refs;
3. known confusability modes;
4. confidence type and level;
5. authority envelope;
6. requested sink;
7. sink authorization decision;
8. repair or revalidation posture;
9. evidence refs;
10. policy decision refs;
11. non-claims.

## Runtime gate classes

- `ingest_gate` — normalizes external or internal input into a channel observation.
- `collapse_gate` — records selection of one interpretant from candidates.
- `memory_sink_gate` — permits or blocks Memory Mesh candidate/confirmed write routing.
- `graph_sink_gate` — permits or blocks Regis edge candidate/confirmed routing.
- `projection_sink_gate` — permits or blocks projection/dashboard/summary routing.
- `action_sink_gate` — permits or blocks high-consequence runtime execution.

## Sink posture

`display`, `suggest`, and `candidate_memory` may be allowed for low/medium confidence channel percepts when source basis and non-claims are present.

`confirmed_memory`, `graph_edge`, `claim_promotion`, `policy_binding`, `publication`, `export`, and `high_consequence_execution` require stronger provenance, repair/revalidation, policy decision refs, and explicit approval posture.

## Runtime non-claim

This tranche is a platform contract fixture and validator. It does not create live enforcement middleware, message broker policy, database schema, or API endpoint behavior.
