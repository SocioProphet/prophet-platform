# Contract migration note: LensOutput -> CapsuleOutput

This platform repo currently contains `contracts/LensOutput.v0.1.json` as an early artifact-index contract.

However, current naming direction is:
- **Capsule** = executable slash-topic pipeline
- **CapsuleOutput** = capsule output artifact index + receipt binding

## Posture

- `LensOutput.v0.1` remains present for backward compatibility.
- New work SHOULD emit `CapsuleOutput.v0.1`.
- When upstream callers have migrated, `LensOutput.v0.1` can be deprecated and eventually removed in a controlled change.

## Minimal mapping

- `lens_ref` -> `capsule_ref`
- Everything else carries forward with the same receipt and artifact index intent.

## Follow-on

A follow-on PR should:
1) update `contracts/README.md` to list `CapsuleOutput` explicitly and mark `LensOutput` as legacy
2) update any emitting code paths to emit `CapsuleOutput`
