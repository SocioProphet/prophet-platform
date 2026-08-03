# Agentic shell — sovereign Gitea backend (gap #6)

The agentic supervisory shell reads repo signals and stages actions over a source
backend. Today that is GitHub; the sovereign target is **Gitea + Zot**. This makes
the switch a **config change, not a rewrite**.

## The move: backend-abstract by contract
`contracts/ShellBackendAdapter.v0.1.json` is the capability surface the shell talks
to. Both backends declare a manifest (`contracts/adapters/{github,gitea}.adapter.json`)
mapping each shell op to a backend endpoint. The shell never calls GitHub or Gitea
directly — it calls the adapter — so pointing it at Gitea is selecting a manifest.
`tools/validate_shell_backend_adapter.py` enforces **op-set parity**: Gitea must
implement every op GitHub does, or the shell is not portable.

## Why this is currently a HOLD, not a bug
`gitea-sovereign` is an **L0 scaffold by design** — its README puts runtime token
issuance, live mutation, and cross-node federation **out of scope**. So the Gitea
manifest is the *wiring spec*, ready; the live backend is the deliberate next step.

## What unblocks it (needs Michael's go + infra)
1. **CI-minted token** — a Gitea App/OAuth token minted in CI (WIF), written to
   `secret://ci/GITEA_OPS_TOKEN`, never a laptop PAT (per the secrets-in-CI rule).
   Scopes: `read:repository`, `write:issue`, `write:pull_request`.
2. **Live Gitea endpoint** — promote `gitea-sovereign` from scaffold to a running
   instance at `gitea.sourceos.dev/api/v1` (the board-parity Gitea plane, currently
   BLOCKED on exactly this token).
3. **Adapter client** — a thin `ShellBackend` client that reads a manifest + the
   minted token and implements the 8 ops (GitHub client already exists as
   `build_health_matrix.collect_signals_gh`).
4. **Consent + Governor** — every mutating op (`create_issue_draft`, `create_mr_draft`,
   `apply_labels`) already declares a consent purpose (ship/administer) in the
   manifest, so it flows through the consent-plane gate + guardrail-fabric Governor
   the shell already uses. No new enforcement.

## Cutover
Runs on the existing GitHub⇄Gitea board-parity rail: the shell keeps working on
GitHub while the Gitea manifest is validated for parity; flip the active manifest
when the minted token + live endpoint land. Zot backs release/artifact reads the
same way (a future `zot.adapter.json`).
