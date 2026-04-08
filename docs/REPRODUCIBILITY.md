# Reproducibility

## Rules

- platform runtime behavior should be driven by pinned upstream standards and explicit platform bindings
- local generated artifacts should be deterministic where practical
- smoke tests should prove the current bootstrap path end to end
- service imports should preserve provenance instead of silently forking upstream code

## Current reproducibility anchors

- `standards.lock.yaml`
- repo drift checks
- transport topology checks
- bootstrap smoke path for gateway -> api
- Lampstand local vertical slice artifacts under `SOCIOPROFIT_STATE_HOME`
