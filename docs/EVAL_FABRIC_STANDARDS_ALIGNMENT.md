# Eval Fabric Standards Alignment

The platform evaluation, observability, and competition-intelligence lane in `prophet-platform` should treat the repository below as the **normative upstream profile anchor**:

- `SocioProphet/socioprophet-agent-standards`

That repository is the intended home for agent-plane standards, conformance, evidence, and compatibility semantics. `prophet-platform` should consume and operationalize those standards rather than inventing a parallel vocabulary.

## Practical implication for this repo

The eval-fabric lane here should align its runtime and control-plane objects to the upstream standards profile where applicable, especially for:
- conformance objects
- evidence and provenance semantics
- compatibility and profile metadata
- contract naming discipline

## Current gap

The current platform bootstrap carries useful platform-local objects for replay, attribution, methodology snapshots, and crosswalks, but these should be reviewed against the upstream standards repo and normalized further over time.

## Immediate next step

When wiring these objects into runtime API responses and the score pipeline, prefer upstream-compatible naming and semantics where possible.
