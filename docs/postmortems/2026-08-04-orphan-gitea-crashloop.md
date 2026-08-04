# Postmortem — the orphan `gitea` that crashlooped in prod for 26h

**Date:** 2026-08-04 · **Severity:** medium (no data loss; a stranded broken workload + a lying deploy control) · **Status:** remediated

## Summary
A `gitea` Deployment in `socioprophet` (prod) was `CrashLoopBackOff` for ~26h (310+ restarts), unnoticed. Root cause is a bug in a *declared* manifest, hidden by a deploy workflow that **reports green while the workload it created is broken** — the exact `declared ≠ enforced` defect this estate's whole program exists to abolish, living in our own tooling.

## Timeline
- **2026-08-03T05:24:19Z** — a single out-of-band `kubectl apply` (the `deploy-gitea-authority.yml` CI workflow) created BOTH `gitea-authority` and a second `gitea` Deployment. `gitea` crashed at first write and never started.
- **05:24 → +26h** — `gitea` crashlooped 310+ times. **Nothing detected it.** ArgoCD didn't (out-of-band, unmanaged). The deploy workflow reported success. No admission gate existed. No runtime watcher existed.
- **2026-08-04 (this session)** — the newly-scheduled deploy-health alerter surfaced it. Diagnosed + remediated.

## Root cause (the failure chain — five layers, each of which should have stopped it)
1. **Manifest defect.** `deploy/gitea-authority/k8s/gitea-sovereign.yaml` declares the sovereign source-control PAIR: `gitea-authority` (the token-signing authority, port 8081) **and** `gitea` (the actual Gitea git server, port 3000, exposed at gitea.sourceos.dev). Both are intended. The `gitea` server has **no `securityContext` at all** — its `gitea:*-rootless` image runs non-root and cannot write the mounted PVC (`gitea-data`): `mkdir: can't create directory '/var/lib/gitea/git': Permission denied` → `exit 1`, forever. Fix = add `securityContext.fsGroup`, NOT delete (an early misread called it a duplicate; reading the manifest header — "the authority + a Gitea instance" — corrected it. The "look before you delete" discipline caught it).
2. **The deploy control LIED (the core defect).** `.github/workflows/deploy-gitea-authority.yml` applies both deployments, but only `kubectl rollout status deploy/gitea-authority`; for the other it runs `get deploy/gitea ... || true` — **swallowing the crashloop and exiting 0.** A control that verifies one of the two things it created and ignores the other's failure is a paper control.
3. **Out-of-band deploy.** The workflow does imperative `kubectl apply`, not ArgoCD. So there is no continuous reconciliation, no drift/prune, and the workload is invisible to GitOps.
4. **No admission gate.** Kyverno (the policy engine) was not running, so nothing rejected a PVC-writer pod with no `fsGroup` — or a workload with no provenance.
5. **No runtime detection.** Until the deploy-health alerter shipped this session, nothing watched live pod state; a crashloop could run indefinitely.

## Why self-healing failed
| Mechanism | Why it missed this |
|---|---|
| **ArgoCD (GitOps)** | Only reconciles what it *manages*. An out-of-band `kubectl apply` of a workload it doesn't know is **invisible** — no drift, no prune, no alert. GitOps heals declared→live; it is blind to live-but-undeclared. |
| **The deploy workflow** | It was the *liar*: `|| true` + verifying only one of two deployments → green while broken. |
| **Admission (Kyverno)** | Absent (Missing) until this session. |
| **Runtime detection** | Absent until the deploy-health alerter (this session). |
| **Self-heal daemon** | Keys on declared failure classes; an orphan crashloop wasn't in its vocabulary. |

## The policy-level failure (owning it)
The estate permits critical services to reach prod via imperative `kubectl apply` workflows that (a) are not ArgoCD-reconciled, (b) do not verify what they deploy, and (c) face no admission gate. That is a **policy hole**, not a one-off bug: any workflow can apply a broken workload to prod and report success, and it will rot undetected. The class is *"enforced ≠ declared"* — the inverse of the usual defect: a thing running in prod that no continuously-reconciled declaration owns. Census at time of writing: **2 of 61 prod deployments are out-of-band** (both gitea).

## Remediation — two automated-healing layers + the instance
**Instance:** add `securityContext.fsGroup: 1000` to the `gitea` server in `gitea-sovereign.yaml` (source fix); it redeploys correctly via the (now-honest) workflow. The live pod is scaled to 0 (crashloop stopped) until that redeploy.

**Layer 1 — ADMISSION (prevent).** Kyverno `require-fsgroup-for-pvc-writers` (Audit→Enforce): a pod mounting a writable PVC must declare `securityContext.fsGroup` — rejects the exact bug at creation. (Runs on the kyverno installed this session.)

**Layer 2 — DETECT what admission misses (two parts).**
- **Honest deploy control:** fix `deploy-gitea-authority.yml` to `rollout status` **every** deployment it applies and drop `|| true` — it can no longer report green while a workload it created is broken. Generalize with a workflow-lint gate that rejects `kubectl apply … || true` + unverified applies.
- **Orphan detector:** a scheduled check (`verify_no_orphan_workloads.py`, and the deploy-health alerter) that lists prod workloads and flags any not owned by an ArgoCD Application — surfacing the out-of-band class (the 2 gitea today), which GitOps is structurally blind to. Shrink-only allowlist for the sanctioned few.

Together: Layer 1 stops the *bug* at admission; Layer 2 stops the *class* (out-of-band + lying-workflow) by making both the undeclared workload and the dishonest control observable and gated.

## Addendum (same day, later session): the detector's own blind spot — a THIRD out-of-band gitea

The "2 of 61 … both gitea" census above was itself incomplete. `verify_no_orphan_workloads.py` defaults to `--namespace socioprophet`, so it never looked anywhere else — and there was a second, entirely separate Gitea running in namespace `scm` (Deployment `gitea`, Service, GCE Ingress at `code.socioprophet.ai`, PVC `gitea-data`) that this postmortem and its follow-ups (#1426/#1431/#1434) never knew existed. It predates this incident: applied out-of-band on 2026-07-15 (originally captured only in stash `capture/stash-4-e9a17e7`, never committed to a tracked branch), part of a deliberate ST018 migration to move the estate's ~122 repos off GitHub — **it is the real, live, data-holding sovereign SCM** (125 repos verified live), not a duplicate or a relic of the `socioprophet`-namespace instance this postmortem is about. That `socioprophet/gitea` instance, by contrast, has an empty PVC (no `repositories/` directory at all) and its `gitea.sourceos.dev` DNS was never pointed at it — it is a migration target that was never populated, not "the sovereign SCM" the earlier text above assumed.

Fixed by bringing `scm/gitea` under ArgoCD (`deploy/argocd/gitea-scm-sovereign.yaml`, `deploy/scm/gitea-sovereign.yaml`) with the same `fsGroupChangePolicy: OnRootMismatch` + digest-pin hardening #1431 gave the other instance, and by making the detector itself namespace-aware: `SANCTIONED_OUT_OF_BAND` entries are now `"<namespace>/<name>"`-qualified (a bare `"gitea"` string would have silently conflated the two separate Deployments), and the default scan now covers `DEFAULT_NAMESPACES = ("socioprophet", "scm")` instead of one hardcoded namespace. The lesson generalizes: *a detector for "workloads no declaration owns" is itself a declaration with a scope, and an unscanned namespace is exactly as invisible to it as an unmanaged workload is to ArgoCD.*
