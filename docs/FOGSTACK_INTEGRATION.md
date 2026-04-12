# Fog Stack integration (initial upstream slice)

This document explains the **minimal initial Fog Stack landing** inside `prophet-platform`.

## Why this repo gets the first slice

`prophet-platform` is already the runtime and deployment home for platform services, with explicit runtime classes (`edge-service`, `cluster-service`, `local-daemon`) and an existing validation/reproducibility posture. Fog Stack should therefore land here as a **productization and conformance layer for deployable runtime bundles**, not as a second substrate.

## What is upstream in this initial slice

This branch adds:
- `tools/fogstack_verify.py` — prototype verifier for Fog Stack bundles
- `tools/validate_fogstack.py` — helper that runs the verifier over the initial Access bundle
- `bundles/fogstack.access-v0.1.yaml` — first in-repo bundle definition
- `conformance/rulepacks/fogstack.access-v0.1.yaml` — first in-repo offering rulepack

## What remains sandbox-only for now

The following stay in sandbox incubation until the first substrate hook is reviewed:
- Knowledge and Evaluation bundles/rulepacks
- machine-readable lifecycle catalog
- broader offering catalog docs
- operator packs and example pass/fail outputs
- release-discipline artifacts for signed bundle publication

## Integration principle

Fog Stack should mature here incrementally:
1. land one bundle + one rulepack + one verifier helper
2. wire validation into the repo validation chain
3. add a second and third offering only after the first path is accepted
4. keep standards/policies that should outlive the runtime in `prophet-platform-standards`

## Manual follow-up still required

This initial slice does **not** yet edit the root `Makefile`.

The next repo-native step is to add:

```make
.PHONY: validate-fogstack

validate: validate-repo drift-check standards-check topology-check test-go validate-phase4 test-python-apps validate-fogstack

validate-fogstack:
	python3 tools/validate_fogstack.py
```

That delta is intentionally kept separate so the first branch remains small and reviewable.
