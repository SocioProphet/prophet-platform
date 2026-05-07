# Personal Intelligence Cell Social Environment and Reputation Lane

Status: post-MVP overtake lane
Related service: `apps/cell-service/`
Related issue: `#384`
Related SocioSphere standards: `SocioProphet/sociosphere/standards/personal-intelligence-cell/`

## Purpose

This lane completes the Aigents overtake path for social awareness and reputation. The goal is not merely to show a people graph. The goal is to produce governed, auditable social-environment snapshots and contextual reputation deltas that can be consumed by SocioSphere, Policy Fabric, Sherlock, New Hope, and downstream analytics.

## Runtime module

Implemented in:

```text
apps/cell-service/src/cell_service/social_environment.py
```

The module provides:

- `social_environment_snapshot(...)`
- `reputation_delta_event(...)`
- `anti_manipulation_assessment(...)`
- `coordinated_amplification_flags(...)`
- `relationship_hygiene_recommendations(...)`
- `social_snapshot_fact(...)`
- `reputation_delta_fact(...)`
- `source_quality_fact(...)`

## Social-environment snapshot

A snapshot summarizes the local social environment around a Personal Intelligence Cell:

```text
cell_id
snapshot_at
peer_count
stale_tie_count
emerging_community_count
attention_sink_count
coordinated_amplification_flags
stale_ties
emerging_communities
attention_sinks
relationship_hygiene
```

It is designed for SocioSphere governance and relationship/source hygiene, not for opaque ranking.

## Reputation delta

A reputation delta is contextual and evidence-backed. It applies to a bounded subject:

```text
human | agent | source | model | workflow | community | claim
```

A delta includes:

- evidence refs;
- delta score in `[-1, 1]`;
- decay policy;
- dispute state;
- policy effect;
- anti-manipulation assessment;
- confidence interval;
- separated trust / authority / popularity / expertise components.

This prevents collapsing popularity, expertise, authority, and trust into a single misleading score.

## Anti-manipulation controls

The first anti-manipulation assessment includes:

- repeated-actor/Sybil-style repetition score;
- repeated-claim/collusion score;
- provenance weight;
- anti-gaming weight;
- flags such as `possible_sybil_repetition`, `coordinated_claim_amplification`, and `weak_provenance`.

The policy effect becomes `review_required` when manipulation flags are present.

## ClickHouse alignment

This lane maps to the previously declared analytical tables:

```text
cell_source_quality_facts
cell_reputation_deltas
cell_social_environment_snapshots
```

The runtime module emits fact-shape helpers for these tables. Full live emission to ClickHouse can be wired in a later deployment pass after the first four fact tables are operational.

## SocioSphere standards

SocioSphere owns the governance-level standards:

```text
standards/personal-intelligence-cell/social-environment-snapshot.schema.json
standards/personal-intelligence-cell/social-environment-snapshot.example.json
standards/personal-intelligence-cell/reputation-delta.schema.json
standards/personal-intelligence-cell/reputation-delta.example.json
tools/validate_personal_intelligence_cell_social_environment.py
```

Validate in SocioSphere:

```bash
python3 tools/validate_personal_intelligence_cell_social_environment.py
```

## Platform validation

Platform validation lives at:

```text
tools/validate_cell_social_environment.py
apps/cell-service/tests/test_social_environment.py
```

`tools/validate_repo.py` runs the platform social-environment validator.

## What this overtakes from Aigents

Aigents had useful social-awareness and reputation concepts. This lane upgrades those into:

- explicit social-environment snapshots;
- relationship hygiene;
- source/attention hygiene;
- coordinated amplification detection;
- contextual reputation deltas;
- provenance-sensitive reputation;
- confidence intervals;
- anti-manipulation flags;
- separated trust, authority, popularity, and expertise signals;
- SocioSphere-governed standards rather than ad hoc social scoring.
