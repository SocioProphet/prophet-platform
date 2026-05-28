# PROMETHEUS SR Run Artifact Emission

Status: v0.1 platform evidence handoff.

This tranche connects Prophet Platform candidate emission to the AgentPlane evidence spine by emitting an AgentPlane-compatible `SRRunArtifact` from a platform `EquationCandidate`.

## Boundary

This is evidence plumbing only.

The emitted run artifact is not an ontology mutation, SRAssertionProposal, policy admission, controller signal, or deployment authorization. It records how the candidate was produced so AgentPlane and CHRONOS can evaluate replay and governance state.

## Flow

1. `tools/prometheus_pysr_mvp.py` emits `EquationCandidate`.
2. `tools/prometheus_emit_sr_run_artifact.py` wraps the candidate into `SRRunArtifact`.
3. `tools/validate_prometheus_sr_run_artifact.py` verifies required fields and recomputes `replayHash`.

## Replay hash

The replay hash uses the same canonical field order established in AgentPlane:

- datasetRef.uri
- datasetRef.contentHash
- methodFamily
- operatorLibrary.binaryOperators sorted ascending
- operatorLibrary.unaryOperators sorted ascending
- operatorLibrary.customOperators sorted ascending
- randomSeed
- runtimeEnvironment.packages sorted by name, then version
- candidateRefs[*].equationLatex sorted ascending

Canonical serialization is UTF-8 JSON with lexicographically sorted keys and no insignificant whitespace.

## Non-authority

`controlAuthority` is always false. The platform may emit evidence, but does not turn symbolic-regression output into runtime authority.
