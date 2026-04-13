# Fog Stack bundle release shapes (initial)

This document defines the next release-engineering step beyond release metadata stubs.

## Scope

These shapes apply to Fog Stack offerings already merged into `prophet-platform`:
- `fogstack.access`
- `fogstack.knowledge`
- `fogstack.evaluation`

## Release manifest purpose

A release manifest should give one stable, machine-readable object per bundle release that captures:
- bundle identity and version
- pointers to the in-repo bundle and rulepack
- integrity references for those artifacts
- channel and support-state at the moment of publication
- whether the manifest is signed

The initial manifests added in this phase are unsigned stubs with digest placeholders.

## Validation evidence purpose

A validation evidence record should capture the minimum proof that a release candidate was checked through the repo-native Fog Stack validation path.

The initial evidence records in this phase are local records for shape only. They are not yet CI-emitted truth artifacts.

## Future evolution

Still out of scope:
- detached signatures or Sigstore integration
- publication to a release registry
- machine-emitted CI evidence packages
- automatic support-state publication from release tooling
