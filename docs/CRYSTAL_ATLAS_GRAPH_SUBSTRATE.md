# Crystal Atlas graph substrate

## Core posture

Crystal Atlas stores:
- canonical identities
- typed edges
- claims
- evidence
- materialized views

It does **not** silently collapse all evidence into single-source truth rows.

## Graph layers

### Identity layer
Canonical nodes such as organization, person, product, contract, clause, obligation, entitlement, event, document, provider, channel, agent, workflow run.

### Relationship layer
Typed edges such as:
- organization_offers_product
- contract_has_clause
- clause_imposes_obligation
- account_entitled_to_product
- event_mentions_entity

### Claim layer
Typed assertions with confidence and evidence refs.

### Evidence layer
Source refs, anchors, timestamps, extractor/provider refs, receipts, and distribution class.

## Materialized views
The graph can materialize:
- public company profiles
- competitor landscapes
- entitlement adjacency maps
- diligence packs
- trigger/news timelines
- workflow/session summaries

## Graph API shape
Minimum platform-facing operations:
- upsert nodes/edges/claims/evidence
- read node by id
- read neighbors
- read claims/evidence for a subject
- materialize profile view
