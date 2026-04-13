# cloudshell-fog Kyverno Policy Bundle

This directory vendors the current `cloudshell-fog` Kyverno baseline into `prophet-platform` so that policy can be reconciled as a first-class platform deployment lane.

## Why vendored here?

The upstream product/spec repo (`SocioProphet/cloudshell-fog`) remains the normative source for policy intent.

This platform repo vendors the current baseline so that:

- Argo CD can reconcile policy independently of the runtime app
- deployment state stays self-contained inside the platform repo
- drift can be validated by platform tooling

## Current bundle

- `require-image-digest.yaml`
- `verify-signed-images.yaml`
- `runtime-baseline.yaml`
- `kustomization.yaml`

## Follow-on work

- add provenance/SBOM admission controls once the cluster-side mechanism is selected
- decide whether to keep vendoring or move to a pinned remote Kustomize reference later
