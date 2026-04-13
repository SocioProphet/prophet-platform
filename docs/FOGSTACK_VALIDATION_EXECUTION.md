# Fog Stack validation execution criteria

This document defines what should count as **proof of execution** for Fog Stack validation in `prophet-platform`.

## Why this exists

The repository now has:
- `tools/fogstack_verify.py`
- `tools/validate_fogstack.py`
- bundle and rulepack files for the initial offerings

That means Fog Stack validation is present in the repo and wired into the validation chain. What is still needed is a clear standard for when validation evidence stops being a placeholder and becomes a trustworthy release artifact.

## Minimum proof of execution

A Fog Stack validation record should be treated as executed truth only when all of the following are true:
1. the bundle and rulepack referenced by the record exist on the validated ref
2. the record source is `ci`
3. the record includes the summary fields emitted by the verifier
4. the record is produced by the native validation path (`make validate` or equivalent CI entrypoint)
5. the exit code in the record matches the actual process result

## Shape-only records

A validation record with `source: local` and `status: shape-only` is useful for schema and release-surface development, but it should not be treated as release evidence.

## Future CI evidence path

The next release-engineering tranche should promote:
- local `shape-only` records -> CI-emitted `executed` records
- unsigned release manifests -> signed manifests
- repo-local release stubs -> published release metadata with stable references
