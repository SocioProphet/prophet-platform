# Slash topics integration (platform note)

`slash-topics` is the governed context and scoping plane that revives the blekko-era "explicit scope" mechanic as modern, signed, replayable artifacts.

This platform repo is where those standards become running services, receipts, and deployable app surfaces.

## What the platform must support

1) **Mountable topic packs**
- topic packs are versioned, content-addressed artifacts
- they are loaded as context inputs under policy
- their identity must be visible in receipts

2) **Executable capsules**
- capsules are the executable form of slash topics: signed pipelines that transform queries/carriers into artifacts
- capsule runs must emit receipts with:
  - capsule ref
  - scope ref
  - topic pack refs
  - operator chain digest
  - policy snapshot refs

3) **Contract spine**

The platform materializes a small, repo-local contract family under `contracts/` so runtime services can validate payloads without reaching into multiple upstream repos.

This PR introduces:
- `TopicPackRef` (topic pack identity for receipts)
- `CapsuleRef` (capsule identity)
- `CapsuleOutput` (capsule output artifact index)
- `QueryRequest` and `SearchResultSet` (typed query + candidate set stubs)

## Pinning and provenance

Operationally, the platform should treat `slash-topics` as a pinned upstream input (similar to other items in `standards.lock.yaml`).

Until it is added to the lock file, this repo carries an explicit integration note and contracts so services can proceed without ambiguity.

## Runtime placement

- the authoritative spec source remains `SocioProphet/slash-topics`
- this repo holds:
  - platform-facing contracts
  - service skeletons
  - deployment wiring
  - end-to-end smoke tests
