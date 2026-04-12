# Fog Stack Knowledge (initial upstream slice)

This document records the minimal initial landing for **Fog Stack Knowledge** inside `prophet-platform`.

## Runtime anchors

Fog Stack Knowledge is grounded in existing platform runtime surfaces:
- `apps/knowledge-reason` — governed claim-evaluation ingress scaffold
- `apps/lampstand` — local-daemon integration target for local indexing and receipt/catalog emission

This means the offering spans two existing runtime classes already recognised by the substrate:
- `cluster-service`
- `local-daemon`

## Upstream artifacts in this slice

- `bundles/fogstack.knowledge-v0.1.yaml`
- `conformance/rulepacks/fogstack.knowledge-v0.1.yaml`

## Why this is a separate follow-on slice

The initial Access slice establishes the verifier path and bundle/rulepack layout.
Knowledge should follow only after that first path exists, because it is the first offering that explicitly combines two runtime classes in one bundle.

## What remains sandbox-only for now

The following remain in sandbox incubation until this second slice is accepted:
- operator pack
- compatibility matrix and machine-readable compatibility policy object
- pass/fail bundle examples and generated result JSON
- broader catalog/lifecycle promotion

## Intended next step

After this slice is accepted, the next offering should be **Fog Stack Evaluation**, grounded in the platform evaluation fabric lane.
