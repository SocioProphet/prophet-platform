# ADR-035: Transparent fault attribution and embedded engine policy

## Status
Proposed

## Context
ADR-033 introduced canonical receipts and event envelopes so platform events can be replayed,
audited, correlated, and indexed consistently. The next failure class is narrower and more
operator-facing: first-party applications can cross hidden runtime boundaries during ordinary UI
or document loading. A non-browser utility may instantiate an embedded browser engine, terminal
bridge, automation bridge, AI worker, media decoder, network service, or diagnostic reporter
without making that boundary visible to the human operator.

The motivating case is a first-party Script Editor diagnostic report where the process terminates
through a simulated guard fault in the WebKit namespace while loading AppKit/UIFoundation window
state. That artifact is not evidence of external tampering by itself; it is evidence that dense
machine diagnostics can still fail to explain causal continuity to the operator.

## Decision
Extend the ADR-033 event/evidence model with five transparent fault-attribution contracts:

- `contracts/FaultEnvelope.v0.1.json`
- `contracts/EngineManifest.v0.1.json`
- `contracts/BoundaryTransition.v0.1.json`
- `contracts/RolloutReceipt.v0.1.json`
- `contracts/DiagnosticRedactionPolicy.v0.1.json`

Rules:

1. Every crash, guard fault, sandbox denial, policy abort, renderer failure, worker failure,
   plugin failure, watchdog termination, and memory-pressure kill MUST produce a `FaultEnvelope`
   or be represented as a domain event referenced by one.
2. Every browser renderer, document renderer, terminal/PTTY bridge, automation bridge, AI worker,
   media decoder, credential bridge, file picker bridge, diagnostic reporter, or network profiler
   MUST have an `EngineManifest`.
3. Every material transition across those boundaries MUST emit a `BoundaryTransition` linked to
   a user action, system trigger, policy decision, or agent intent receipt.
4. Every feature rollout or staged behavior that can affect diagnostics, engines, privacy,
   policy, network behavior, credential access, or fault handling MUST resolve through a
   human-readable `RolloutReceipt`.
5. Diagnostic export MUST be tiered by `DiagnosticRedactionPolicy`, separating local-private
   forensic bundles from default shareable reports and public issue artifacts.

## Non-goals
This ADR does not implement the BearBrowser component inspector, TurtleTerm system-action
transcript, SourceOS Shell degraded-mode UI, or Sociosphere cross-repo rollup. It defines the
portable contracts those product surfaces will consume.

## Consequences
- The platform can distinguish an actual compromise signal from a first-party opaque subsystem
  fault.
- Operator reports can answer “why is this engine running?” instead of only showing stack traces.
- Built-in components receive at least the same transparency requirements as extensions.
- Rollout state becomes locally resolvable rather than a mystery identifier.
- Shareable diagnostics stop leaking stable identifiers by default.
- Product repos can implement UI/UX incrementally while sharing one evidence vocabulary.

## Follow-up implementation homes
- BearBrowser: component inspector and embedded renderer manifests.
- TurtleTerm: terminal/system-action transcript and PTY/automation boundary transitions.
- SourceOS Shell: document/PDF/browser/terminal surface degraded mode and diagnostic UX.
- Sociosphere: schema registration, repo-governance linkage, and cross-repo placement checks.
- Ontogenesis: ontology terms and SHACL shapes for fault, engine, boundary, rollout, and redaction
  classes.
