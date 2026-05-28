# PROMETHEUS AgentPlane Schema Pin

Status: v0.1 local schema snapshot.

This tranche pins Prophet Platform PROMETHEUS run-artifact validation to the AgentPlane symbolic-regression schema contract without requiring live cross-repo fetches during CI.

## Source

The pinned schema source is `SocioProphet/agentplane` at commit `fd99c38c52bb01ef8b0a401aeb5bca5e79970b20`.

Pinned local snapshots:

- `schemas/agentplane/symbolic-regression/sr-run-artifact.schema.json`
- `schemas/agentplane/symbolic-regression/sr-candidate-ref.schema.json`

## Purpose

Prophet Platform emits PROMETHEUS candidate and SRRunArtifact outputs. AgentPlane owns the evidence schema. This pin makes the platform output checkable against the AgentPlane contract while avoiding a live dependency on AgentPlane during platform CI.

## Validation

`tools/validate_prometheus_agentplane_schema_pin.py` checks:

- local pinned schema snapshot hashes;
- generated local-demo run artifacts contain AgentPlane-required fields;
- method families remain within the AgentPlane enum;
- SINDy `controlAuthority` remains false;
- candidate references preserve required fields;
- inconsistent units cannot be proposed or admitted.

## Boundary

The pinned copy is a platform validation snapshot, not a new authority source. AgentPlane remains the owner of the SRRunArtifact and SRCandidateRef schema contract. Updates to the AgentPlane schema require an explicit platform pin update.
