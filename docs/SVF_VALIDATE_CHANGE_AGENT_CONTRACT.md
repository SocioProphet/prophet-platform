# SVF `validate_change` Agent Contract

Status: platform contract declaration  
Plane: Prophet Platform / agent invocation  
Upstream authority: ProCybernetica SVF policy primitive  
Workspace registry/state: Sociosphere SVF workspace state readout

## Purpose

This document defines the Prophet Platform contract for an agent-facing `validate_change` capability.

The capability lets a coding agent ask the workspace fabric which Sovereign Validation Fabric (SVF) Plans apply to a repository change, receive selected Plans and required validation commands, and later attach receipt references to PR readiness summaries.

This contract does not execute Actions. It does not bypass policy. It does not certify a change. It is the agent-plane invocation contract over Sociosphere workspace state and ProCybernetica authority.

## Plane boundaries

ProCybernetica owns SVF authority vocabulary, claim scopes, side-effect classes, CapabilityPolicy, and Receipt semantics.

Sociosphere owns workspace registry, repo-to-plan mapping, changed-path selection, read-only runner behavior, and workspace validation-state readout.

Prophet Platform owns the agent-facing API contract, PR-readiness summary shape, and product surface.

Model router may consume Sociosphere validation state for autonomy and verifier-depth decisions, but it does not define validity.

Superconscious/Subconscious may consume Sociosphere validation-history summaries, failure patterns, and plan usefulness signals. It does not authorize execution, mutate policy, or certify receipts.

## Sociosphere workspace-state dependency

The first `validate_change` implementation must consume or mirror Sociosphere workspace state, not raw GitHub CI status.

For an applicable profile, Sociosphere may report:

```text
selected_missing_observation
```

with warning:

```text
validation_observation_missing
```

Prophet Platform must preserve that state in its response and PR-readiness summary. It may recommend the repo-local validation command, but it must not convert selection into validation success.

Raw CI checks may later become an observation provider, but they are not the semantic source of workspace validation state. Sociosphere is the workspace-state source. ProCybernetica remains the authority source.

## Contract posture

The first `validate_change` contract is read-only and advisory. It may:

1. accept repo, ref, changed paths, diff digest, actor, and requested validation depth;
2. call or mirror Sociosphere plan selection and workspace-state semantics;
3. return selected Plan ids, mode, repo profile, validation command, workspace validation status, and missing-observation warnings;
4. produce a PR-readiness summary object that says whether blocking/advisory validation evidence is present.

It may not:

1. execute SVF Actions;
2. create or sign ValidationReceipts;
3. promote advisory results to blocking status;
4. mutate Sociosphere registry or ProCybernetica policy;
5. bypass failed or missing blocking receipts;
6. claim live or production readiness from advisory contract validation;
7. treat raw CI status as a substitute for Sociosphere workspace state.

## Validation evidence states

`validate_change` and DevSecOps Workroom records must keep validation evidence state separate from broad runtime parity labels.

Allowed evidence states are:

- `not_configured`
- `selected_only`
- `missing_evidence`
- `synthetic_observed`
- `runtime_observed`
- `verified_receipt`
- `failed_receipt`
- `stale_receipt`

`runtime_observed` is not a claim that may be inferred from plan selection, command recommendation, or raw CI status. In v0.1 fixture semantics, `runtime_observed` requires `validation_evidence_state: verified_receipt` plus a `source_refs.validation_receipt_ref` whose value is represented by a `runtime_receipt` evidence packet provenance reference.

`synthetic_observed` may be used for synthetic fixture evidence, but it must not be escalated to `runtime_observed` without verified receipt evidence.

Receipt references are pointers to upstream evidence. Prophet Platform consumes them for agent-facing readiness summaries; it does not issue, sign, or certify SVF receipts.

## Initial request shape

```json
{
  "schema_version": "1.0",
  "request_id": "svf:validate-change-request:example",
  "repo": "SocioProphet/SCOPE-D",
  "ref": "feature/example",
  "changed_paths": ["svf/scope-d-defensive-assurance-basic.json"],
  "diff_digest": {"algorithm": "sha256", "digest": "example"},
  "actor": {"actor_class": "coding_agent", "actor_id": "agent://example"},
  "validation_depth": "advisory"
}
```

## Initial response shape

```json
{
  "schema_version": "1.0",
  "request_id": "svf:validate-change-request:example",
  "status": "selected",
  "repo": "SocioProphet/SCOPE-D",
  "workspace_validation_status": "selected_missing_observation",
  "selected_plans": [
    {
      "plan_id": "svf:plan:scope-d.defensive-assurance-basic",
      "profile_id": "svf:profile:scope-d.defensive-assurance",
      "mode": "advisory",
      "validation_command": "npm run validate:svf",
      "selected_by": "changed_path_selector"
    }
  ],
  "required_observations": ["npm run validate:svf"],
  "warnings": ["validation_observation_missing"],
  "non_claims": ["Selection does not execute validation actions."]
}
```

## PR readiness summary

A PR readiness summary may state that Plans were selected, commands were recommended, or receipts are missing. It may not say that a change is validated unless matching receipts or observed validation evidence are attached through Sociosphere workspace state.

For the first tranche, missing observed validation must be surfaced as `validation_observation_missing`, not silently converted into success.

A readiness summary may report `runtime_observed` only when the Workroom or validate_change response carries a verified receipt reference and a matching runtime-receipt evidence packet. It must report `selected_only`, `missing_evidence`, `failed_receipt`, or `stale_receipt` when receipt evidence is absent, failed, or stale.

## Initial implementation order

1. Add this contract document.
2. Add JSON fixture examples under `contracts/svf/`.
3. Add a validator under `tools/` for request/response/readiness fixture shape.
4. Wire a Makefile lane.
5. Later, implement product/API behavior that consumes Sociosphere workspace state output.

## Non-claims

This document does not implement an API route.

This document does not execute validation commands.

This document does not create receipts.

This document does not grant agent autonomy beyond selection and reporting.
