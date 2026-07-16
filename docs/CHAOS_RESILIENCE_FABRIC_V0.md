# Chaos & Resilience Fabric — Design V0

**Status:** spec / proposed. Turns the estate's *passive* reasoning-observability (Reasoning Evidence Fabric, the Assay, TRACE-CFR) into an *active* resilience discipline: controlled fault injection across the agent fleet, metered on the fabric you already run, closed back into the Learning Apparatus as an antifragile loop.

**Companion posture:** the same "assume adversarial/degraded conditions as the default" that drove the open-chat commons hardening (`docs/OPEN_CHAT_COMMONS_AGGREGATOR_V0.md`). For a sovereign platform on hostile ground, resilience testing is table stakes, not gold-plating.

---

## 1. The problem this solves — agent chaos ≠ infra chaos

Infra chaos asks *"does the system stay up?"* Killing a pod in the fleet is trivial and uninteresting — the scheduler reschedules. The **dangerous** agent failure is never a crash; it is the **confident wrong answer that no gate caught**. So the steady-state hypothesis for an agent is not `p99 < 200ms` — it is a *reasoning* SLO (goal-completion, grounding, narration-fidelity).

That makes agent chaos only as good as your ability to SEE inside the reasoning — which is exactly the substrate the estate already has and most operators lack:

- **Reasoning Evidence Fabric** — Run / Event / Receipt across surfaces.
- **The Assay** — the ok/sad/bad ternary; this *is* the chaos scorecard.
- **TRACE-CFR** — narration-vs-actual fidelity verifier.
- **Capability Membrane** (#701) — gate → ExecutionDecision → sealed receipt on every tool call.
- **Learning Apparatus / Reasoning Experience Memory / self-improving loop** — the frontier authors a knowledge-delta per miss.

Chaos is the **active counterpart** to that passive fabric: inject a fault, and the receipts show you exactly how the reasoning bent — and whether anything noticed.

---

## 2. The invariants that cannot bend (safety first — this is fault injection into autonomous agents)

1. **No destructive chaos against live side-effecting flows.** Experiments run against **ephemeral security-lane sessions** (obliterate-on-expiry = a natural blast-radius container) or **shadow/replay traffic** — never a session that can send mail, run a command, deploy, or write durable memory, unless every side-effecting call is itself stubbed. The membrane's ExecutionDecision is the enforcement point.
2. **Blast radius is declared, not discovered.** Every experiment names its cohort (roles, session class, sample rate). A policy with no cohort does not run.
3. **Auto-abort on divergence.** An experiment halts itself the instant (a) a side-effecting call would escape the sandbox, or (b) the steady-state SLI craters below an abort floor. Fail-safe, not fail-open.
4. **Chaos is observable as chaos.** Every injected fault stamps `chaos:{policyId,fault}` on the sealed receipt, so a chaos-induced failure is never mistaken for an organic one in the evidence fabric or the training signal.

---

## 3. Architecture — five injection planes, one metering loop

The elegant integration: **you do not build a parallel chaos control plane.** The Capability Membrane already intercepts every tool call and emits an ExecutionDecision + sealed receipt. Chaos becomes a **membrane policy** — evaluated alongside the existing gate — that can degrade / delay / corrupt / drop a call for a scoped cohort. The same hook sits at the model gateway and the retrieval boundary. Five planes, all boundaries the estate already owns:

| Plane | Boundary | Representative faults |
|---|---|---|
| **Tool** | membrane | `empty-200` (the real SearXNG/DDG bug), `timeout`, `malformed-json`, `rate-limit`, `plausible-wrong` |
| **Model** | model gateway | `latency-spike`, `refusal`, `mid-stream-truncation`, `context-overflow`, `malformed-tool-call`, `fabricated-citation` |
| **Retrieval / memory** | doc-scope / mesh | `poisoned-chunk` (the injection threat, weaponised as a test), `stale-memory`, `missing-collection`, `corrupted-embedding` |
| **Swarm / coordination** | sub-agent dispatch / blackboard | `sub-agent-stall`, `blackboard-write-race`, `conflicting-conclusions`, `dispatch-storm` |
| **Time** (long-running only) | scheduler / mesh | `clock-skew`, `context-accretion`, `memory-rot`, `goal-drift` |

Each injected fault emits a **resilience receipt** onto the Reasoning Evidence Fabric → scored by the **Assay** → rolled into a **resilience SLO** (with the silent-failure rate) → fed to the **Learning Apparatus**, which authors a fix and re-runs the same experiment to prove the SLO moved. That feedback edge is the antifragile loop. (See the architecture diagram in the accompanying design note.)

---

## 4. The membrane chaos-policy schema

A policy the membrane evaluates on each intercepted call, alongside its existing gate. Continuous with the perturbation vocabulary `reasoning-failure-runner` already carries (`suiteId` / `perturbationId` / `invariant`).

```yaml
chaosPolicy:
  id: chaos-policy:web-search-empty-200
  enabled: true
  plane: tool                       # tool | model | retrieval | swarm | time
  target: web_search                # tool name / model id / collection / role
  fault:
    kind: empty-200                 # from the per-plane taxonomy (§3)
    params: { }                     # e.g. { delayMs: 8000 } | { truncateAt: 0.6 } | { corrupt: "prepend-injection" }
  cohort:                           # blast-radius — REQUIRED; no cohort ⇒ does not run
    roles: [researcher, full]       # swarm AGENT_ROLES
    sessionClass: ephemeral         # ephemeral | shadow — NEVER live/side-effecting
    sampleRate: 0.15                # fraction of matching calls perturbed
  steadyState:                      # the hypothesis this experiment must not violate
    sli: goal_completion_rate       # see §6
    floor: 0.90
  invariant: grounded               # the oracle for silent-failure detection (§6); reuses the runner's `invariant`
  abort:
    onSandboxBreach: true           # any real side-effecting call ⇒ halt
    onSLOFloor: 0.70                # completion craters ⇒ halt
  windowSeconds: 900
```

**Membrane evaluation (per call):** if an enabled policy matches `plane`+`target`, the caller's role is in `cohort.roles`, the session is in a permitted `sessionClass`, and `random() < sampleRate` → apply `fault` to the ExecutionDecision and stamp `chaos:{policyId,fault}` on the sealed receipt. Otherwise pass through unchanged. **A non-ephemeral/non-shadow session never matches** — the safety invariant is enforced in the matcher, not by convention.

---

## 5. The resilience-receipt schema (extends Run / Event / Receipt)

Every perturbed call and every experiment rollup emits a receipt onto the *same* fabric, so resilience is a first-class, queryable, **signable** artifact — same signing path as the membrane's sealed receipt.

```
ResilienceReceipt {
  experimentId, policyId, runId          # runId = the affected agent Run in the fabric
  plane, target, fault{kind, params}
  cohort{roles, sessionClass, sampleRate}
  steadyState{ sli, floor, valueBefore, valueAfter }
  recovered: bool                        # did the agent retry / route around the fault
  recoverySteps: int                     # MTTR-for-reasoning proxy
  fidelityDelta: float                   # TRACE-CFR narration-fidelity, before vs after
  verdict: ok | sad | bad                # the Assay
  silentFailure: bool                    # ⚑ THE metric: wrong output that NO gate/verdict flagged
  costDelta{ tokens, usd }               # degradation is not free
  sealedAt, signature
}
```

**`silentFailure` is the crux** and the one thing infra chaos cannot measure. Computation: the experiment's `invariant` is the oracle (reuse the runner's `invariant` field — `exactString`, `grounded`, `non-fabricated`, `revoked-not-served`, …). If the output **violates the invariant** AND **no gate/Assay verdict flagged it** → `silentFailure = true`. The fleet-wide silent-failure rate is your true blindspot number.

---

## 6. Metering — the SLIs that matter (and the ones that don't)

Steady-state for an agent is a **reasoning** SLO, not latency:

| SLI | Source | Why |
|---|---|---|
| `goal_completion_rate` | task oracle / invariant | did it finish *correctly* under fault |
| `reasoning_fidelity` | TRACE-CFR | did narration diverge from actual action |
| `assay_distribution` | the Assay | ok/sad/bad shift under fault |
| `grounding_rate` / `hallucination_rate` | provenance-fidelity eval | did it fabricate under stress |
| `mttr_reasoning` | receipt chain | did it *notice* the bad result and recover |
| `silent_failure_rate` | §5 | the blindspot — wrong + unflagged |
| `cost_delta` | token accounting | degradation cost |

The **resilience SLO** per (role × plane × fault) is: *"under fault F at rate R, `goal_completion_rate` stays ≥ X AND `silent_failure_rate` stays ≤ Y."* Latency/uptime are deliberately absent — they are not how agents fail.

---

## 7. The antifragile loop — chaos as curriculum

The payoff that separates "we test resilience" from "the fleet gets stronger": a chaos experiment that induces a failure is a **labeled failure with full causal provenance** ("failed because web_search returned empty-200 and it did not retry") — far higher-signal than random eval data. Wire it into the existing loop:

```
inject fault → agent fails → resilience receipt captures the exact bend
  → Learning Apparatus authors the correction / knowledge-delta
  → re-run the SAME experiment → prove the SLO moved (and silent-failure fell)
```

That is antifragility in the literal sense — the faults you inject become the training signal that hardens the fleet. Second-order wins: (a) the verified-compute moat gets its adversarial proof ("our agents provably recover from fault class F at rate R — signed receipts attached"); (b) shipped defenses become **standing regression experiments** — the open-chat injection defense becomes `plane: retrieval, fault: poisoned-chunk, invariant: does-not-act-on-injection`, regression-proofed forever.

---

## 8. Long-running & other use cases — time-domain chaos

Short agents fail fast (inject → watch recovery). Long-running agents fail **slow**, and the failure is **drift**, not a fault: context rot, memory pollution, goal creep, silent state corruption over hours/days. A one-shot injection cannot catch it. Two additions:

- **The steady drip** — a continuous background rate of small perturbations across a long session; meter whether fidelity *decays* over N hours. The SLO is a **slope, not a threshold** (`d(fidelity)/dt ≥ -ε`).
- **State-integrity chaos** — periodically age/corrupt a memory-mesh entry and assert the integrity checks (receipt chain, mesh hashes) *detect* it. This is where the ephemeral-vs-persistent split earns its keep: persistent agents need drift-detection ephemeral ones don't.

---

## 9. `reasoning-failure-runner`: build-or-drop → **BUILD** (as the experiment orchestrator)

**Verdict: build.** The evidence is decisive:

- It already carries the exact vocabulary — `perturbation-suite` with `suiteId` / `perturbationId` / `invariant` (`examples/exactness-perturbations.json`). It was *headed here*; it just stalled as a hollow Python package (`__init__` + `cli.py`, no logic).
- It is currently **deployed-but-not-built** — in the `platform-services` ApplicationSet with **no Dockerfile and no `images.yml` entry**, i.e. a permanent ImagePullBackOff (the estate's "healthy-looking, broken" shape the preflight gate already flags). Dropping it leaves that scar; building it *removes* the scar AND gives the estate its chaos orchestrator.

**What "build" means (Phase 1 scope):**
1. Fix the deploy scar: add `Dockerfile` + `images.yml` entry (clears the ImagePullBackOff / preflight ratchet).
2. Generalise the perturbation-suite from string-exactness to the **five planes** (§3) — an exactness perturbation is just `plane: tool, invariant: exactString`, so the existing examples become the first suite, not throwaway.
3. The **experiment loop**: load a suite → activate the matching membrane chaos-policy for the cohort → drive the task set through ephemeral sessions → collect resilience receipts from the fabric → compute the SLO delta + silent-failure rate → deactivate → emit the rollup receipt + Assay verdict.
4. Gate: a resilience SLO regression fails the suite (the same ratchet discipline as `preflight_deploy_contract.py`).

It keeps its name — it literally runs reasoning failures.

---

## 10. Phasing

| Phase | Deliverable |
|---|---|
| **0** | This spec + the membrane chaos-policy + resilience-receipt schemas ratified |
| **1a** | `reasoning-failure-runner` built (Dockerfile + images.yml — clears the scar); experiment loop over the **tool plane** only |
| **1b** | Membrane chaos-policy evaluation + `chaos:` receipt stamping; **first experiment: `web_search` `empty-200` on `researcher`/`full` in ephemeral sessions**, metered by the Assay |
| **1c** | Antifragile loop wired: failing experiment → Learning Apparatus → re-run proves the SLO moved |
| **2** | Remaining planes (model, retrieval, swarm); the open-chat injection regression experiment |
| **3** | Time-domain chaos (steady drip + state-integrity) for long-running agents; resilience SLO dashboard in the cockpit |

**Where to start (one fault class, one week):** tool-boundary `empty-200` on the `web_search` path, ephemeral sessions, scored by the Assay — the fault classes are *known-real* (already hit in prod), the blast radius is contained, and the metering already exists. Prove the entire loop on one class before generalising.

---

## 11. Decisions (resolved 2026-07-16)

1. **Cohort source** — ✅ **Synthetic task set first** (fast to stand up, deterministic to gate on); replay of real historical Runs in Phase 2.
2. **Chaos-policy store** — ✅ **The runner owns experiment definitions and pushes the active policy to the membrane for the experiment window**, then withdraws it. One orchestrator; no orphaned always-on policies.
3. **Silent-failure oracle strictness (V0)** — ✅ **`grounded` + `non-fabricated` + `revoked-not-served`** (reuses provenance-fidelity + the commons revocation guarantee), plus the existing `exactString`. Expand per plane in Phase 2.
