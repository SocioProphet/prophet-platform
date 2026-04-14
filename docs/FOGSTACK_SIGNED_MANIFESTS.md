# Fog Stack signed manifests

This document defines the first repo-native meaning of a **signed Fog Stack bundle manifest**.

## Goal

Move from unsigned manifest stubs to manifests that explicitly carry signature metadata in a way that matches the existing `FogStackBundleManifest` schema.

## Minimal signed-manifest flow

1. prepare an unsigned bundle manifest under `releases/manifests/`
2. produce or obtain a signature artifact reference (for example a future Sigstore or Cosign output)
3. run `python3 tools/attach_fogstack_manifest_signature.py` to attach the signature metadata to the manifest
4. publish the updated manifest as the release manifest for that bundle version

## Example

```bash
python3 tools/attach_fogstack_manifest_signature.py \
  --manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --signature-type cosign \
  --signature-ref artifact://release/fogstack.access-v0.1.sig \
  --output /tmp/fogstack.access-v0.1.signed.manifest.json
```

## What this phase does and does not mean

This phase means:
- the manifest shape can now carry signature metadata explicitly
- release tooling has a minimal helper for attaching that metadata

This phase does **not** yet mean:
- signatures are verified automatically in CI
- signatures are published to a registry
- signature refs are globally resolvable
- release publication is fully automated

## Next step

The next release-engineering step after this helper is to define how CI should verify the signature reference and emit a corresponding executed validation/evidence artifact.
