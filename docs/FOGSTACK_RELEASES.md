# Fog Stack release discipline (initial upstream slice)

This document defines the smallest release-discipline surface for Fog Stack artifacts that live inside `prophet-platform`.

## Scope of this phase

This phase currently covers the upstream Access and Knowledge slices:
- `bundles/fogstack.access-v0.1.yaml`
- `conformance/rulepacks/fogstack.access-v0.1.yaml`
- `bundles/fogstack.knowledge-v0.1.yaml`
- `conformance/rulepacks/fogstack.knowledge-v0.1.yaml`
- `tools/fogstack_verify.py`
- `tools/validate_fogstack.py`

It does **not** yet define the full release process for the broader Fog Stack catalog.

## Release channels

Fog Stack artifacts inherit the same broad release posture as the platform, but with offering-specific states:

- `preview` — reviewed but still evolving; shape may change
- `candidate` — ready for broader validation and operator trial
- `stable` — accepted shape with an established validation path
- `deprecated` — superseded; removal announced in advance

The initial Access and Knowledge slices are `preview`.

## Minimum release conditions for a bundle

A bundle should not be treated as released in this repo unless:
1. the bundle file exists under `bundles/`
2. the rulepack exists under `conformance/rulepacks/`
3. `tools/validate_fogstack.py` passes on the branch
4. the offering has a current status document under `docs/`

## Promotion path

Preview -> Candidate -> Stable should be driven by:
- successful validation on the active branch
- no critical verifier failures
- reviewed runtime anchors in existing substrate services
- acceptance of the offering shape in draft PR review

## Future additions

The following remain for later phases:
- signed bundle manifests
- publication metadata
- machine-readable support-state emission
- evidence packaging for bundle releases
- compatibility snapshots for each promoted offering
