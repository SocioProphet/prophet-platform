# SVF `validate_change` Agent Contract

Status: platform contract declaration  
Plane: Prophet Platform / agent invocation  
Upstream authority: ProCybernetica SVF policy primitive  
Workspace registry: Sociosphere SVF workspace registry

## Purpose

This document defines the Prophet Platform contract for an agent-facing `validate_change` capability.

The capability lets a coding agent ask the workspace fabric which Sovereign Validation Fabric (SVF) Plans apply to a repository change, receive selected Plans and required validation commands, and later attach receipt references to PR readiness summaries.

This contract does not execute Actions. It does not bypass policy. It does not certify a change. It is the agent-plane invocation contract over Sociosphere discovery and ProCybernetica authority.

## Plane boundaries

ProCybernetica owns SVF authority vocabulary, claim scopes, side-effect classes, CapabilityPolicy, and Receipt semantics.

Sociosphere owns workspace registry, repo-to-plan mapping, changed-path selection, and read-only runner behavior.

Prophet Platform owns the agent-facing API contract, PR-readiness summary shape, and product surface.

Model router may consume validation state for autonomy and verifier-depth decisions, but it does not define validity.

Superconscious/Subconscious may consume validation-history summaries, failure patterns, and plan usefulness signals. It does not authorize execution, mutate policy, or certify receipts.

## Contract posture

The first `validate_change` contract is read-only and advisory. It may:

1. accept repo, ref, changed paths, diff digest, actor, and requested validation depth;
2. call or mirror Sociosphere plan selection semantics;
3. return selected Plan ids, mode, repo profile, validation command, and missing-observation warnings;
4. produce a PR-readiness summary object that says whether blocking/advisory validation evidence is present.

It may not:

1. execute SVF Actions;
2. create or sign ValidationReceipts;
3. promote advisory results to blocking status;
4. mutate Sociosphere registry or ProCybernetica policy;
5. bypass failed or missing blocking receipts;
6. claim live or production readiness from advisory contract validation.

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
  "non_claims": ["Selection does not execute validation actions."]
}
```

## PR readiness summary

A PR readiness summary may state that Plans were selected, commands were recommended, or receipts are missing. It may not say that a change is validated unless matching receipts or observed validation evidence are attached.

For the first tranche, missing observed validation must be surfaced as `validation_observation_missing`, not silently converted into success.

## Initial implementation order

1. Add this contract document.
2. Add JSON fixture examples under `contracts/svf/`.
3. Add a validator under `tools/` for request/response/readiness fixture shape.
4. Wire a Makefile lane.
5. Later, implement product/API behavior that consumes Sociosphere registry output.

## Non-claims

This document does not implement an API route.

This document does not execute validation commands.

This document does not create receipts.

This document does not grant agent autonomy beyond selection and reporting.
