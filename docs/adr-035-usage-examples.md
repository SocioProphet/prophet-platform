# ADR-035 — Usage Examples and Validation Guide

Status: operator reference.

ADR-035 defines transparent fault attribution and embedded engine policy contracts for prophet-platform. This document explains each contract and provides worked examples for common integration scenarios.

## Contracts

| Contract | File | Purpose |
|---|---|---|
| `FaultEnvelope` | `contracts/FaultEnvelope.v0.1.json` | Typed crash/fault report with process chain, engine, privacy, and policy context |
| `EngineManifest` | `contracts/EngineManifest.v0.1.json` | Policy declaration for an embedded engine (network, file, credential, diagnostic) |
| `BoundaryTransition` | `contracts/BoundaryTransition.v0.1.json` | Audit record for a cross-boundary event (engine init, network open, AI invocation, …) |
| `RolloutReceipt` | `contracts/RolloutReceipt.v0.1.json` | Provenance record for a feature flag or policy activation |
| `DiagnosticRedactionPolicy` | `contracts/DiagnosticRedactionPolicy.v0.1.json` | Tier-based redaction rules for diagnostic exports |

All contracts use `"schemaVersion": "v0.1"` and pass JSON Schema draft/2020-12 validation. See `make validate-adr-035-contracts` for CI gate.

## Relation to ADR-033

ADR-033 defines `EventEnvelope` and `EvidenceReceipt` — the generic wrappers. ADR-035 contracts **specialize** those types for fault, engine, and boundary attribution:

- A `FaultEnvelope` _is_ an `EventEnvelope` with `eventType` constrained to a typed fault taxonomy.
- A `BoundaryTransition` _is_ an `EvidenceReceipt` for a specific boundary crossing.
- `EngineManifest` and `DiagnosticRedactionPolicy` are _policy declarations_, not event records — they appear as refs (`engineManifestRef`, `redactionPolicyRef`) inside `FaultEnvelope`.

## Worked Examples

### 1. Browser renderer crash (FaultEnvelope)

Scenario: BearBrowser's renderer process crashes due to a guard fault in the embedded WebKit renderer.

```json
{
  "schemaVersion": "v0.1",
  "kind": "FaultEnvelope",
  "eventId": "bearbrowser-renderer-guard-fault-001",
  "timestamp": "2026-06-11T10:15:00Z",
  "eventType": "renderer_crash",
  "severity": "process_terminated",
  "process": {
    "pid": 7892,
    "name": "BearBrowser Renderer",
    "binary": "/Applications/BearBrowser.app/Contents/Frameworks/BearRenderer",
    "parent": "BearBrowser",
    "codeIdentity": "ai.socioprophet.bearbrowser.renderer"
  },
  "componentChain": ["browser_shell", "tab_controller", "renderer_process"],
  "fault": {
    "namespace": "WEBKIT",
    "subtype": "GUARD_TYPE_USER",
    "signalOrException": "EXC_GUARD",
    "intentional": true,
    "simulated": false,
    "policyRelated": "sandboxDenial"
  },
  "engine": {
    "engineManifestRef": "EngineManifest.v0.1.json",
    "engineType": "web_renderer",
    "engineName": "WebKitLegacy",
    "networkAllowed": false,
    "fileAccessAllowed": false
  },
  "privacy": {
    "redactionPolicyRef": "DiagnosticRedactionPolicy.v0.1.json",
    "tier": "shareableDefault",
    "userIdRedacted": true,
    "pathsRedacted": true
  }
}
```

### 2. Hidden embedded engine initialization (BoundaryTransition)

Scenario: A document renderer silently initializes a network-capable engine without user gesture. ADR-035 requires this be recorded as a `BoundaryTransition` with `boundaryType: embedded_engine_initialization`.

```json
{
  "schemaVersion": "v0.1",
  "kind": "BoundaryTransition",
  "transitionId": "bt-engine-init-bearbrowser-001",
  "timestamp": "2026-06-11T10:14:58Z",
  "sourceComponent": "document_renderer",
  "targetComponent": "embedded_web_view",
  "boundaryType": "embedded_engine_initialization",
  "initiator": "automatic",
  "userVisible": false,
  "policyOutcome": "logged",
  "engineManifestRef": "EngineManifest.v0.1.json"
}
```

### 3. Terminal automation bridge use (BoundaryTransition)

Scenario: TurtleTerm's automation bridge is invoked for a shell execution. User gesture was required and confirmed.

```json
{
  "schemaVersion": "v0.1",
  "kind": "BoundaryTransition",
  "transitionId": "bt-automation-turtleterm-001",
  "timestamp": "2026-06-11T10:20:00Z",
  "sourceComponent": "turtleterm_shell",
  "targetComponent": "automation_bridge",
  "boundaryType": "automation_bridge_use",
  "initiator": "user_gesture",
  "userVisible": true,
  "policyOutcome": "allowed",
  "engineManifestRef": "EngineManifest.v0.1.json"
}
```

### 4. Diagnostic export redaction (DiagnosticRedactionPolicy)

Scenario: A diagnostic export is requested for a public issue report. ADR-035 requires the `publicIssue` tier: device IDs omitted, paths redacted, instruction bytes omitted.

```json
{
  "schemaVersion": "v0.1",
  "kind": "DiagnosticRedactionPolicy",
  "tiers": {
    "localPrivate": {
      "stableDeviceIds": "preserve",
      "bootSessionIds": "preserve",
      "instructionBytes": "preserve",
      "fullPaths": "preserve",
      "tokensOrSecrets": "redact"
    },
    "shareableDefault": {
      "stableDeviceIds": "hash_with_local_salt",
      "bootSessionIds": "hash_with_local_salt",
      "instructionBytes": "omit",
      "fullPaths": "redact",
      "tokensOrSecrets": "redact"
    },
    "publicIssue": {
      "stableDeviceIds": "omit",
      "bootSessionIds": "omit",
      "instructionBytes": "omit",
      "fullPaths": "redact",
      "tokensOrSecrets": "redact"
    }
  }
}
```

### 5. Rollout receipt resolution (RolloutReceipt)

Scenario: A new embedded AI worker policy is activated for a subset of users. The rollout receipt provides provenance for policy fabric gates to verify which policy class is active.

```json
{
  "schemaVersion": "v0.1",
  "kind": "RolloutReceipt",
  "rolloutId": "rollout-ai-worker-policy-v1-001",
  "featureName": "ai_worker_sandboxed_v1",
  "featureVersion": "1.0.0",
  "owner": "platform-security",
  "activationReason": "Security hardening: AI worker now runs in dedicated sandbox with deny-all network default.",
  "activationRule": "percent_rollout:10",
  "policyClass": "ai_worker_sandbox_v1",
  "privacyClass": "internal",
  "affectedBoundaries": ["ai_invocation", "worker_spawn"],
  "buildProvenance": {
    "repo": "SocioProphet/prophet-platform",
    "commit": "sha256:abcdef1234567890abcdef1234567890abcdef12",
    "ciReceipt": "ci-receipt-20260611-001"
  }
}
```

## Validation

To validate the existing synthetic Script Editor guard-fault fixture against `FaultEnvelope.v0.1.json`:

```
make validate-adr-035-contracts
```

This target runs `tools/validate_adr_035_contracts.py`, which validates:
- `tests/fixtures/fault-envelope-script-editor-synthetic.json` against `contracts/FaultEnvelope.v0.1.json`
- `contracts/examples/adr-035-*.json` worked examples against their respective contracts

## Cross-repo implementation matrix

| Repo | Follow-up | Status |
|---|---|---|
| SocioProphet/prophet-platform | This issue (#465) | In progress |
| BearBrowser | BearBrowser#26 — BearBrowser renderer crash events | Pending |
| TurtleTerm | TurtleTerm#11 — TurtleTerm automation bridge events | Pending |
| SourceOS Shell | sourceos-shell — helper causal receipt mapping | Pending |
| Ontogenesis | Ontogenesis — fault attribution surface | Pending |
| Sociosphere | Sociosphere — boundary atlas consumption | Pending |

## Non-goals

ADR-035 defines canonical contracts and examples. Product-specific component inspectors, transcripts, and surface implementations belong in the product repos.
