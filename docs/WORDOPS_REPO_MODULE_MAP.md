# WordOps Repo / Module Map v0.1

## Primary upstream home

The primary upstream home for the WordOps reference architecture pack is `SocioProphet/prophet-platform`.

Reason:
- this repo is the runtime and deployment hub
- it already owns platform-level docs, contracts, infra, and deployment wiring
- the WordOps pack is implementation-oriented platform architecture, not merely abstract standards prose

## Cross-repository alignment

### `SocioProphet/socioprophet-standards-storage`
Use for normative standards that later graduate from platform guidance into canonical standards.

Examples:
- connector bundle standard
- capability lease standard
- moderation/publication normative profile
- approval-to-lease governance standard

### `SocioProphet/socioprophet-standards-knowledge`
Use for executable semantic and knowledge-context standards, not for the core WordOps platform architecture pack.

### `SocioProphet/socioprophet-docs`
Use as a public-facing documentation and exposition surface that points back to the platform repo as the engineering source of truth.

### `SocioProphet/agentplane`
Consumer of:
- agent lifecycle rules
- MCP and A2A posture
- public/extended card model
- lease and task-binding expectations

### `SocioProphet/policy-fabric`
Consumer of:
- approval-to-lease governance
- policy decision model
- risk classes and autonomy classes

### `SocioProphet/mcp-a2a-zero-trust`
Consumer of:
- agent interoperability rules
- lease model
- card exposure rules
- trust-boundary guidance

### `SocioProphet/TriTRPC`
Normative transport source of truth for wire and transport semantics.
WordOps references it, but does not replace it.

### `SocioProphet/sociosphere`
Consumer of:
- workspace/controller implications
- room factory / environment / orchestration patterns
- OIDC, policy, and platform operating posture

## Suggested module layout inside `prophet-platform`

```text
docs/
  WORDOPS_REFERENCE_ARCHITECTURE.md
  WORDOPS_UPSTREAM_PLACEMENT_EVALUATION.md
  WORDOPS_MODERATION_AND_PUBLICATION_PROFILE.md
  WORDOPS_APPROVAL_TO_LEASE_GOVERNANCE.md
  WORDOPS_CONNECTOR_BUNDLE_CONTRACT.md
  WORDOPS_REPO_MODULE_MAP.md
  WORDOPS_PHASE0_IMPLEMENTATION_CHECKLIST.md
  WORDOPS_ACCEPTANCE_CRITERIA.md

schemas/wordops/
  capability-lease.schema.json

policy/opa/wordops/
  lease_policy.rego
```

## Placement rule

Platform implementation guidance lives in `prophet-platform` first.
If a document matures into reusable normative canon, it should be mirrored or promoted into the appropriate standards repo and then referenced back here.
