# FogStack State Coherence

Status: **bounded-local-demo-ready**
Posture: `compressed-estate-demo-coherence`
Production boundary: non-mutating local proof; live mutation, production signing, registry publication, and managed multi-tenant service operations remain post-MVP
Sociosphere record: `github://SocioProphet/sociosphere/registry/state-coherence/fogstack-local-demo-state-coherence-v0.1.json`

## Repo bindings

| ID | Repo | Demo binding | Role |
|---|---|---|---|
| `fogstack-runtime-spine` | `github://SocioProphet/prophet-platform` | `primary` | bounded local demo proof, release proof, deploy plan, GitOps, runtime dry-run, and parity readiness spine |
| `estate-control-plane` | `github://SocioProphet/sociosphere` | `control-plane` | estate intelligence, repository topology, control-plane status, and cross-repo coherence registry |
| `sourceos-state-integrity` | `github://SourceOS-Linux/sourceos-syncd` | `supporting-evidence` | local-first state integrity, event/report contracts, repair planning, and store-backed evidence surface |
| `agent-machine-substrate` | `github://SourceOS-Linux/agent-machine` | `substrate` | Agent Machine bootstrap, trust, activation, provenance, release evidence, and governed local execution surface |
| `sourceos-operator-surfaces` | `github://SourceOS-Linux/BearBrowser` | `operator-surface` | governed browser/operator surface, policy actions, provenance events, and local app status/open/reset controls |
| `guardrail-boundary` | `github://SocioProphet/guardrail-fabric` | `policy-boundary` | SourceOS guardrail decision ABI, hook adapter, policy simulation, deterministic baseline policies, and anti-tamper controls |
| `agentplane-governance-context` | `github://SocioProphet/agentplane` | `runtime-governance` | agent runtime governance context, protocol identity aliases, run/replay/session evidence propagation |
| `semantic-contract-plane` | `github://SocioProphet/ontogenesis` | `semantic-layer` | semantic enterprise ontology, ValueFlows/SHIR projection, sector scenarios, and OrgGov semantic alignment |

## Integration surfaces

- `release-proof-to-runtime-evidence`
- `gitops-readiness-to-local-demo-summary`
- `runtime-dry-run-to-agentplane-run-linkage`
- `runtime-dry-run-to-policyplane-decision-linkage`
- `agent-machine-node-profile-to-runtime-adapter`
- `immutable-update-readiness-to-demo-artifact-index`
- `sourceos-state-integrity-to-supporting-evidence-plane`
- `guardrail-decision-abi-to-policy-boundary`
- `operator-surfaces-to-sourceos-node-profile`
- `semantic-contracts-to-governed-evidence-plane`

## Required demo principles

- one operator command should produce one evidence directory
- every generated artifact should be digest-indexed or explicitly reported as a supporting external ref
- live cluster mutation must remain disabled by default
- policy and guardrail decisions must be explicit artifacts, not implicit runtime behavior
- SourceOS local-first state integrity must be treated as substrate evidence, not an optional sidecar
