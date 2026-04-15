# Fog Stack release artifact linking

This document defines the first repo-native helper for **back-linking** release and trust artifacts.

## Goal

Move from separate machine-readable artifacts to artifacts that can point back to each other consistently for one bundle version.

The helper in this phase updates:
- the release manifest
- the validation record
- the signature verification record
- the signature trust record

so each can carry the relevant backlink refs.

## Minimal flow

1. emit or prepare the individual artifacts
2. emit the release evidence index
3. run `tools/link_fogstack_release_artifacts.py`
4. persist the updated artifacts back to their deterministic release paths

## Example

```bash
python3 tools/link_fogstack_release_artifacts.py \
  --manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --validation-record releases/evidence/fogstack.access-v0.1.validation.record.json \
  --signature-verification-record releases/evidence/fogstack.access-v0.1.signature-verification.record.json \
  --signature-trust-record releases/evidence/fogstack.access-v0.1.signature-trust.record.json \
  --evidence-index-ref releases/evidence/fogstack.access-v0.1.evidence.index.json
```

## Out of scope

This phase does not yet provide:
- automatic CI execution of the linker
- mutation of artifacts after publication
- cryptographic verification of linked refs
- registry publication of the linked artifact set
